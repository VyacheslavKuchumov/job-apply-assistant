import json
import os
import re
import shutil
import subprocess
import textwrap
import threading
import traceback
from html import escape
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import close_old_connections
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


JSON_KEYS = [
    'fit_assessment',
    'resume',
    'resume_latex',
    'cover_letter',
    'interview_tips',
]


def profile_to_prompt(profile):
    return f"""
ФИО: {profile.full_name}
Контакты: {profile.contacts}
Желаемая должность: {profile.desired_position}
Навыки и технологии: {profile.skills}
Опыт работы: {profile.experience}
Проекты и реальные кейсы: {profile.projects}
Образование: {profile.education}
Достижения: {profile.achievements}
Сильные стороны: {profile.strengths}
Дополнительные инструкции пользователя: {profile.ai_instructions}
""".strip()


def vacancy_to_prompt(vacancy):
    return f"""
Название вакансии: {vacancy.title}
Сайт компании: {vacancy.company_url}
Ссылка на вакансию: {vacancy.vacancy_url}
Описание вакансии:
{vacancy.description}
Заметки пользователя:
{vacancy.notes}
""".strip()


def build_generation_prompt(profile, vacancy, extra_instructions=''):
    return f"""
Ты помогаешь кандидату подготовить отклик на вакансию. Отвечай на русском языке.

ВАЖНЫЕ ПРАВИЛА:
- Опирайся прежде всего на реальные данные кандидата.
- Можно аккуратно переформулировать опыт и подчеркнуть релевантные стороны.
- Не выдумывай конкретные места работы, дипломы, сертификаты, цифры и факты, которых нет.
- Если вакансия слабо подходит, честно напиши это в оценке соответствия и дай план, как закрыть разрыв.
- Если используешь предположение, формулируй его как проверяемую гипотезу, а не как факт.
- Сделай материалы пригодными для hh.ru/ATS и для отправки HR.

ДАННЫЕ КАНДИДАТА:
{profile_to_prompt(profile)}

ВАКАНСИЯ:
{vacancy_to_prompt(vacancy)}

ДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ К ЭТОЙ ГЕНЕРАЦИИ:
{extra_instructions or 'нет'}

Верни СТРОГО JSON без markdown-обертки с ключами:
- fit_assessment: оценка соответствия и риски;
- resume: адаптированное текстовое резюме;
- resume_latex: полный LaTeX-документ резюме, предпочтительно XeLaTeX, аккуратный минималистичный шаблон;
- cover_letter: сопроводительное письмо;
- interview_tips: советы для собеседования: суть вакансии, вероятные задачи, вопросы, кейсы кандидата, что говорить, что подготовить.
Все значения JSON должны быть строками, не вложенными объектами и не массивами.
""".strip()


def build_chat_prompt(profile, vacancy, user_message):
    return f"""
Ты дорабатываешь материалы отклика на вакансию. Отвечай по-русски, конкретно и практически.

КАНДИДАТ:
{profile_to_prompt(profile)}

ВАКАНСИЯ:
{vacancy_to_prompt(vacancy)}

ТЕКУЩАЯ ОЦЕНКА:
{vacancy.fit_assessment}

ТЕКУЩЕЕ РЕЗЮМЕ:
{vacancy.generated_resume}

ТЕКУЩЕЕ ПИСЬМО:
{vacancy.generated_cover_letter}

ТЕКУЩИЕ СОВЕТЫ:
{vacancy.generated_interview_tips}

ЗАПРОС ПОЛЬЗОВАТЕЛЯ:
{user_message}

Дай готовую доработку. Если нужно заменить конкретный блок, явно напиши новый текст блока.
""".strip()


def run_pi(prompt, timeout=240):
    pi_path = shutil.which('pi')
    if not pi_path:
        return '', 'Команда pi не найдена в PATH. Использован локальный fallback.'
    try:
        completed = subprocess.run(
            [pi_path, '-p', '--no-session', '--no-tools', prompt],
            cwd=settings.BASE_DIR,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return '', f'pi не ответил за {timeout} секунд. Использован локальный fallback.'
    except Exception as exc:
        return '', f'Ошибка запуска pi: {exc}. Использован локальный fallback.'

    log = ''
    if completed.stderr:
        log += completed.stderr.strip()
    if completed.returncode != 0:
        log += f'\npi завершился с кодом {completed.returncode}.'
    return completed.stdout.strip(), log.strip()


def parse_pi_json(raw):
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


KEY_LABELS = {
    'summary': 'Кратко',
    'match_level': 'Уровень соответствия',
    'main_risks': 'Главные риски',
    'how_to_position': 'Как позиционироваться',
    'gap_closing_plan': 'План закрытия пробелов',
    'likely_tasks': 'Вероятные задачи',
    'questions': 'Возможные вопросы',
    'focus_cases': 'Кейсы для акцента',
    'what_to_say': 'Что говорить',
    'prepare_topics': 'Что подготовить',
}


def humanize_key(key):
    return KEY_LABELS.get(str(key), str(key).replace('_', ' ').capitalize())


def render_structured(value, level=0):
    """Convert nested JSON fragments from pi to readable text instead of Python dict repr."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        lines = []
        for item in value:
            rendered = render_structured(item, level + 1).strip()
            if not rendered:
                continue
            if '\n' in rendered:
                lines.append(f'- {rendered.replace(chr(10), chr(10) + "  ")}')
            else:
                lines.append(f'- {rendered}')
        return '\n'.join(lines)
    if isinstance(value, dict):
        sections = []
        for key, item in value.items():
            rendered = render_structured(item, level + 1).strip()
            if not rendered:
                continue
            label = humanize_key(key)
            if isinstance(item, (list, dict)):
                sections.append(f'{label}:\n{rendered}')
            else:
                sections.append(f'{label}: {rendered}')
        return '\n\n'.join(sections)
    return str(value).strip()


def fallback_generation(profile, vacancy, raw_response='', log=''):
    skills = profile.skills or 'Укажите навыки в профиле, чтобы резюме стало точнее.'
    experience = profile.experience or 'Опыт пока не заполнен.'
    projects = profile.projects or 'Проекты пока не заполнены.'
    position = profile.desired_position or vacancy.title
    name = profile.full_name or 'Кандидат'

    fit = textwrap.dedent(f"""
    Локальная оценка без ответа pi: проверьте совпадение ключевых требований вакансии с навыками профиля.
    Целевая позиция кандидата: {position}.
    Если описание вакансии требует опыт, которого нет в анкете, лучше честно подготовить план закрытия пробелов.
    {log}
    """).strip()

    resume = textwrap.dedent(f"""
    {name}
    Целевая роль: {vacancy.title}

    Контакты:
    {profile.contacts or 'Заполните контакты в профиле.'}

    Ключевые навыки:
    {skills}

    Релевантный опыт:
    {experience}

    Проекты и кейсы:
    {projects}

    Образование:
    {profile.education or 'Не указано'}

    Достижения и сильные стороны:
    {profile.achievements or ''}
    {profile.strengths or ''}
    """).strip()

    cover = textwrap.dedent(f"""
    Здравствуйте!

    Меня заинтересовала вакансия «{vacancy.title}». По описанию вижу, что для роли важны задачи и технологии, которые пересекаются с моим опытом: {skills}.

    Буду рад обсудить, как мой опыт и проекты могут быть полезны вашей команде. Готов подробнее рассказать о релевантных кейсах и быстро уточнить недостающие детали по вакансии.

    С уважением,
    {name}
    """).strip()

    tips = textwrap.dedent(f"""
    1. Перед интервью выпишите 3–5 требований из вакансии и под каждое подготовьте реальный пример из опыта.
    2. Подготовьте краткий рассказ: задача → действия → результат → чему научился.
    3. Если есть пробелы, говорите честно: что уже знаете, что изучаете, как быстро сможете закрыть.
    4. Уточните у работодателя стек, формат работы, ожидания на испытательный срок и критерии успеха.

    Сырой ответ pi, если он был:
    {raw_response[:4000]}
    """).strip()

    return {
        'fit_assessment': fit,
        'resume': resume,
        'resume_latex': make_latex(profile, vacancy, resume),
        'cover_letter': cover,
        'interview_tips': tips,
    }


def latex_escape(value):
    replacements = {
        '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    return ''.join(replacements.get(ch, ch) for ch in value)


def make_latex(profile, vacancy, resume_text):
    safe_title = latex_escape(vacancy.title)
    safe_name = latex_escape(profile.full_name or 'Кандидат')
    body = '\n\n'.join(
        '\\par ' + latex_escape(block.strip()).replace('\n', '\\\\n')
        for block in resume_text.split('\n\n') if block.strip()
    )
    return rf"""\documentclass[11pt,a4paper]{{article}}
\usepackage{{fontspec}}
\usepackage[russian]{{babel}}
\usepackage[margin=1.6cm]{{geometry}}
\usepackage{{enumitem}}
\setmainfont{{DejaVu Sans}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.55em}}
\begin{{document}}
{{\LARGE \textbf{{{safe_name}}}}}\\
{{\large Резюме под вакансию: {safe_title}}}

{body}
\end{{document}}
"""


def save_material_files(vacancy):
    base_dir = Path(settings.MEDIA_ROOT) / 'resumes'
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = f'vacancy_{vacancy.pk}_resume'

    latex_text = vacancy.generated_resume_latex or make_latex(ProfileFallback(), vacancy, vacancy.generated_resume)
    tex_path = base_dir / f'{stem}.tex'
    tex_path.write_text(latex_text, encoding='utf-8')
    with tex_path.open('rb') as fh:
        vacancy.resume_tex.save(f'{stem}.tex', File(fh), save=False)

    pdf_path = base_dir / f'{stem}.pdf'
    create_pdf(pdf_path, vacancy.title, vacancy.generated_resume or '')
    with pdf_path.open('rb') as fh:
        vacancy.resume_pdf.save(f'{stem}.pdf', File(fh), save=False)


class ProfileFallback:
    full_name = 'Кандидат'


def register_font():
    font_candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            if 'AppFont' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('AppFont', font_path))
            return 'AppFont'
    return 'Helvetica'


def create_pdf(path, title, text):
    font_name = register_font()
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleRu', parent=styles['Title'], fontName=font_name, fontSize=16, leading=20, spaceAfter=12
    )
    body_style = ParagraphStyle(
        'BodyRu', parent=styles['BodyText'], fontName=font_name, fontSize=10.5, leading=14, spaceAfter=8
    )
    story = [Paragraph(escape(title), title_style)]
    for block in (text or 'Резюме пока пустое.').split('\n\n'):
        cleaned = '<br/>'.join(escape(line) for line in block.strip().splitlines())
        if cleaned:
            story.append(Paragraph(cleaned, body_style))
            story.append(Spacer(1, 0.15 * cm))
    doc.build(story)


def generate_for_vacancy(profile, vacancy, extra_instructions=''):
    prompt = build_generation_prompt(profile, vacancy, extra_instructions)
    raw, log = run_pi(prompt)
    data = parse_pi_json(raw)
    had_error = False
    error_message = ''
    if not data:
        had_error = True
        error_message = log or 'pi не вернул корректный JSON, сохранён fallback.'
        data = fallback_generation(profile, vacancy, raw_response=raw, log=log)
    else:
        for key in JSON_KEYS:
            data.setdefault(key, '')
        if not data.get('resume_latex'):
            data['resume_latex'] = make_latex(profile, vacancy, render_structured(data.get('resume', '')))

    vacancy.fit_assessment = render_structured(data.get('fit_assessment', '')).strip()
    vacancy.generated_resume = render_structured(data.get('resume', '')).strip()
    vacancy.generated_resume_latex = render_structured(data.get('resume_latex', '')).strip() or make_latex(profile, vacancy, vacancy.generated_resume)
    vacancy.generated_cover_letter = render_structured(data.get('cover_letter', '')).strip()
    vacancy.generated_interview_tips = render_structured(data.get('interview_tips', '')).strip()
    vacancy.generated_at = timezone.now()
    vacancy.generation_status = vacancy.STATUS_ERROR if had_error else vacancy.STATUS_SUCCESS
    vacancy.generation_error = error_message
    vacancy.generation_log = log or 'pi ответил успешно'
    save_material_files(vacancy)
    vacancy.save()
    return vacancy


def enqueue_generation(vacancy_id, user_id, extra_instructions=''):
    """Run generation in a daemon thread so the web request returns immediately."""
    def worker():
        close_old_connections()
        try:
            from .models import Profile, Vacancy

            vacancy = Vacancy.objects.get(pk=vacancy_id, owner_id=user_id)
            profile = Profile.get_for_user(vacancy.owner)
            generate_for_vacancy(profile, vacancy, extra_instructions)
        except Exception as exc:
            error = f'{exc}\n\n{traceback.format_exc()}'
            try:
                from .models import Vacancy

                Vacancy.objects.filter(pk=vacancy_id, owner_id=user_id).update(
                    generation_status=Vacancy.STATUS_ERROR,
                    generation_error=error[:5000],
                    generation_log=error[:5000],
                    generated_at=timezone.now(),
                )
            except Exception:
                pass
        finally:
            close_old_connections()

    thread = threading.Thread(target=worker, name=f'vacancy-generation-{vacancy_id}', daemon=True)
    thread.start()
    return thread


def chat_with_pi(profile, vacancy, message):
    prompt = build_chat_prompt(profile, vacancy, message)
    raw, log = run_pi(prompt, timeout=180)
    if raw:
        return raw, log
    return (
        'pi сейчас не ответил. Сформулируйте правку вручную или попробуйте позже. '
        'Подсказка: попросите конкретно заменить блок резюме, письма или советов.',
        log,
    )
