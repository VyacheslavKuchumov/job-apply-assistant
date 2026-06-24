from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile, Vacancy


TEXTAREA = {'class': 'textarea', 'rows': 5}
INPUT = {'class': 'input'}


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs=INPUT),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        labels = {
            'username': 'Логин',
            'password1': 'Пароль',
            'password2': 'Повтор пароля',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'input')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'full_name', 'contacts', 'desired_position', 'skills', 'experience',
            'projects', 'education', 'achievements', 'strengths', 'ai_instructions'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs=INPUT),
            'contacts': forms.Textarea(attrs={**TEXTAREA, 'rows': 3}),
            'desired_position': forms.TextInput(attrs=INPUT),
            'skills': forms.Textarea(attrs=TEXTAREA),
            'experience': forms.Textarea(attrs={**TEXTAREA, 'rows': 7}),
            'projects': forms.Textarea(attrs={**TEXTAREA, 'rows': 7}),
            'education': forms.Textarea(attrs=TEXTAREA),
            'achievements': forms.Textarea(attrs=TEXTAREA),
            'strengths': forms.Textarea(attrs=TEXTAREA),
            'ai_instructions': forms.Textarea(attrs={**TEXTAREA, 'rows': 6}),
        }


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = ['title', 'company_url', 'vacancy_url', 'description', 'notes']
        widgets = {
            'title': forms.TextInput(attrs=INPUT),
            'company_url': forms.URLInput(attrs=INPUT),
            'vacancy_url': forms.URLInput(attrs=INPUT),
            'description': forms.Textarea(attrs={**TEXTAREA, 'rows': 10}),
            'notes': forms.Textarea(attrs={**TEXTAREA, 'rows': 5}),
        }


class GenerateForm(forms.Form):
    extra_instructions = forms.CharField(
        label='Дополнительные инструкции к этой генерации',
        required=False,
        widget=forms.Textarea(attrs={**TEXTAREA, 'rows': 4, 'placeholder': 'Например: сделать письмо короче, акцент на Python/Django, не упоминать X'})
    )


class ChatForm(forms.Form):
    message = forms.CharField(
        label='Сообщение pi агенту',
        widget=forms.Textarea(attrs={**TEXTAREA, 'rows': 3, 'placeholder': 'Например: перепиши сопроводительное письмо дружелюбнее или усили блок про Django'})
    )
