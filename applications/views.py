from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ChatForm, GenerateForm, ProfileForm, SignUpForm, VacancyForm
from .models import Profile, Vacancy, VacancyChatMessage
from .services import chat_with_pi, generate_for_vacancy


def home(request):
    profile = None
    vacancies_count = 0
    latest_vacancies = []
    if request.user.is_authenticated:
        profile = Profile.get_for_user(request.user)
        vacancies = Vacancy.objects.filter(owner=request.user)
        vacancies_count = vacancies.count()
        latest_vacancies = vacancies[:5]
    return render(request, 'applications/home.html', {
        'profile': profile,
        'vacancies_count': vacancies_count,
        'latest_vacancies': latest_vacancies,
    })


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            login(request, user)
            messages.success(request, 'Регистрация завершена. Вы вошли в аккаунт.')
            return redirect('profile')
    else:
        form = SignUpForm()
    return render(request, 'applications/signup.html', {'form': form})


@login_required
def profile_edit(request):
    profile = Profile.get_for_user(request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            saved_profile = form.save(commit=False)
            saved_profile.user = request.user
            saved_profile.save()
            messages.success(request, 'Профиль сохранён.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'applications/profile_form.html', {'form': form, 'profile': profile})


@login_required
def vacancy_list(request):
    vacancies = Vacancy.objects.filter(owner=request.user)
    q = request.GET.get('q', '').strip()
    if q:
        vacancies = vacancies.filter(title__icontains=q)
    return render(request, 'applications/vacancy_list.html', {'vacancies': vacancies, 'q': q})


@login_required
def vacancy_create(request):
    if request.method == 'POST':
        form = VacancyForm(request.POST)
        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.owner = request.user
            vacancy.save()
            messages.success(request, 'Вакансия создана.')
            return redirect(vacancy)
    else:
        form = VacancyForm()
    return render(request, 'applications/vacancy_form.html', {'form': form, 'title': 'Новая вакансия'})


@login_required
def vacancy_edit(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = VacancyForm(request.POST, instance=vacancy)
        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.owner = request.user
            vacancy.save()
            messages.success(request, 'Вакансия сохранена.')
            return redirect(vacancy)
    else:
        form = VacancyForm(instance=vacancy)
    return render(request, 'applications/vacancy_form.html', {'form': form, 'vacancy': vacancy, 'title': 'Редактировать вакансию'})


@login_required
def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, owner=request.user)
    return render(request, 'applications/vacancy_detail.html', {
        'vacancy': vacancy,
        'generate_form': GenerateForm(),
        'chat_form': ChatForm(),
        'chat_messages': vacancy.chat_messages.all(),
    })


@require_POST
@login_required
def vacancy_delete(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, owner=request.user)
    vacancy.delete()
    messages.success(request, 'Вакансия удалена.')
    return redirect('vacancy_list')


@require_POST
@login_required
def vacancy_generate(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, owner=request.user)
    form = GenerateForm(request.POST)
    if form.is_valid():
        messages.info(request, 'Запущена генерация через pi. Страница обновится после завершения запроса.')
        generate_for_vacancy(Profile.get_for_user(request.user), vacancy, form.cleaned_data['extra_instructions'])
        messages.success(request, 'Материалы сгенерированы.')
    else:
        messages.error(request, 'Проверьте форму генерации.')
    return redirect(vacancy)


@require_POST
@login_required
def vacancy_chat(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk, owner=request.user)
    form = ChatForm(request.POST)
    if form.is_valid():
        user_message = form.cleaned_data['message']
        VacancyChatMessage.objects.create(vacancy=vacancy, role='user', message=user_message)
        answer, log = chat_with_pi(Profile.get_for_user(request.user), vacancy, user_message)
        if log:
            answer = f'{answer}\n\n---\nЛог: {log}'
        VacancyChatMessage.objects.create(vacancy=vacancy, role='assistant', message=answer)
        messages.success(request, 'Ответ pi добавлен в чат.')
    else:
        messages.error(request, 'Введите сообщение для pi.')
    return HttpResponseRedirect(reverse('vacancy_detail', args=[vacancy.pk]) + '#chat')
