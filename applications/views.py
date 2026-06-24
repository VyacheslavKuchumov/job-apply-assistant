from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ChatForm, GenerateForm, ProfileForm, VacancyForm
from .models import Profile, Vacancy, VacancyChatMessage
from .services import chat_with_pi, generate_for_vacancy


def home(request):
    profile = Profile.get_solo()
    vacancies_count = Vacancy.objects.count()
    latest_vacancies = Vacancy.objects.all()[:5]
    return render(request, 'applications/home.html', {
        'profile': profile,
        'vacancies_count': vacancies_count,
        'latest_vacancies': latest_vacancies,
    })


def profile_edit(request):
    profile = Profile.get_solo()
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль сохранён.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'applications/profile_form.html', {'form': form, 'profile': profile})


def vacancy_list(request):
    vacancies = Vacancy.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        vacancies = vacancies.filter(title__icontains=q)
    return render(request, 'applications/vacancy_list.html', {'vacancies': vacancies, 'q': q})


def vacancy_create(request):
    if request.method == 'POST':
        form = VacancyForm(request.POST)
        if form.is_valid():
            vacancy = form.save()
            messages.success(request, 'Вакансия создана.')
            return redirect(vacancy)
    else:
        form = VacancyForm()
    return render(request, 'applications/vacancy_form.html', {'form': form, 'title': 'Новая вакансия'})


def vacancy_edit(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    if request.method == 'POST':
        form = VacancyForm(request.POST, instance=vacancy)
        if form.is_valid():
            vacancy = form.save()
            messages.success(request, 'Вакансия сохранена.')
            return redirect(vacancy)
    else:
        form = VacancyForm(instance=vacancy)
    return render(request, 'applications/vacancy_form.html', {'form': form, 'vacancy': vacancy, 'title': 'Редактировать вакансию'})


def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    return render(request, 'applications/vacancy_detail.html', {
        'vacancy': vacancy,
        'generate_form': GenerateForm(),
        'chat_form': ChatForm(),
        'chat_messages': vacancy.chat_messages.all(),
    })


@require_POST
def vacancy_delete(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    vacancy.delete()
    messages.success(request, 'Вакансия удалена.')
    return redirect('vacancy_list')


@require_POST
def vacancy_generate(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    form = GenerateForm(request.POST)
    if form.is_valid():
        messages.info(request, 'Запущена генерация через pi. Страница обновится после завершения запроса.')
        generate_for_vacancy(Profile.get_solo(), vacancy, form.cleaned_data['extra_instructions'])
        messages.success(request, 'Материалы сгенерированы.')
    else:
        messages.error(request, 'Проверьте форму генерации.')
    return redirect(vacancy)


@require_POST
def vacancy_chat(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)
    form = ChatForm(request.POST)
    if form.is_valid():
        user_message = form.cleaned_data['message']
        VacancyChatMessage.objects.create(vacancy=vacancy, role='user', message=user_message)
        answer, log = chat_with_pi(Profile.get_solo(), vacancy, user_message)
        if log:
            answer = f'{answer}\n\n---\nЛог: {log}'
        VacancyChatMessage.objects.create(vacancy=vacancy, role='assistant', message=answer)
        messages.success(request, 'Ответ pi добавлен в чат.')
    else:
        messages.error(request, 'Введите сообщение для pi.')
    return HttpResponseRedirect(reverse('vacancy_detail', args=[vacancy.pk]) + '#chat')
