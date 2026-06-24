from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        null=True,
        blank=True,
        verbose_name='Пользователь',
    )
    full_name = models.CharField('ФИО', max_length=255, blank=True)
    contacts = models.TextField('Контакты', blank=True)
    desired_position = models.CharField('Желаемая должность', max_length=255, blank=True)
    skills = models.TextField('Навыки и технологии', blank=True)
    experience = models.TextField('Опыт работы', blank=True)
    projects = models.TextField('Проекты и реальные кейсы', blank=True)
    education = models.TextField('Образование', blank=True)
    achievements = models.TextField('Достижения', blank=True)
    strengths = models.TextField('Сильные стороны', blank=True)
    ai_instructions = models.TextField('Дополнительные инструкции для нейронки', blank=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профиль'

    def __str__(self):
        return self.full_name or self.user_username or 'Профиль кандидата'

    @property
    def user_username(self):
        return self.user.get_username() if self.user_id else ''

    @classmethod
    def get_for_user(cls, user):
        profile, _ = cls.objects.get_or_create(user=user)
        return profile

    @classmethod
    def get_solo(cls):
        profile, _ = cls.objects.get_or_create(pk=1)
        return profile


class Vacancy(models.Model):
    STATUS_IDLE = 'idle'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    GENERATION_STATUS_CHOICES = [
        (STATUS_IDLE, 'Нужно сгенерировать'),
        (STATUS_RUNNING, 'Идёт генерация'),
        (STATUS_SUCCESS, 'Успешно'),
        (STATUS_ERROR, 'Ошибка'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vacancies',
        null=True,
        blank=True,
        verbose_name='Пользователь',
    )
    title = models.CharField('Название вакансии', max_length=255)
    company_url = models.URLField('Ссылка на сайт компании', blank=True)
    vacancy_url = models.URLField('Ссылка на вакансию', blank=True)
    description = models.TextField('Описание вакансии с hh.ru')
    notes = models.TextField('Заметки пользователя', blank=True)

    generated_resume = models.TextField('Сгенерированное резюме', blank=True)
    generated_resume_latex = models.TextField('LaTeX резюме', blank=True)
    generated_cover_letter = models.TextField('Сопроводительное письмо', blank=True)
    generated_interview_tips = models.TextField('Советы для собеседования', blank=True)
    fit_assessment = models.TextField('Оценка соответствия', blank=True)
    resume_pdf = models.FileField('PDF резюме', upload_to='resumes/', blank=True)
    resume_tex = models.FileField('LaTeX файл', upload_to='resumes/', blank=True)
    generated_at = models.DateTimeField('Сгенерировано', null=True, blank=True)
    generation_status = models.CharField(
        'Статус генерации',
        max_length=16,
        choices=GENERATION_STATUS_CHOICES,
        default=STATUS_IDLE,
    )
    generation_error = models.TextField('Ошибка генерации', blank=True)
    generation_log = models.TextField('Лог генерации', blank=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('vacancy_detail', args=[self.pk])

    @property
    def has_generation(self):
        return any([
            self.generated_resume,
            self.generated_cover_letter,
            self.generated_interview_tips,
        ])

    @property
    def generation_status_label(self):
        if self.generation_status == self.STATUS_RUNNING:
            return 'Идёт генерация'
        if self.generation_status == self.STATUS_ERROR:
            return 'Ошибка генерации'
        if self.generation_status == self.STATUS_SUCCESS or self.has_generation:
            return 'Успешно'
        return 'Нужно сгенерировать'

    @property
    def generation_status_class(self):
        if self.generation_status == self.STATUS_RUNNING:
            return 'running'
        if self.generation_status == self.STATUS_ERROR:
            return 'error'
        if self.generation_status == self.STATUS_SUCCESS or self.has_generation:
            return 'success'
        return 'idle'


class VacancyChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'Пользователь'),
        ('assistant', 'Pi агент'),
    ]
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='chat_messages')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Сообщение чата'
        verbose_name_plural = 'Сообщения чата'

    def __str__(self):
        return f'{self.get_role_display()}: {self.message[:50]}'
