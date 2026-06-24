from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, Vacancy
from .services import render_structured


class AuthFlowTests(TestCase):
    def test_unauthenticated_home_redirects_to_login(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_protected_pages_redirect_to_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_signup_logs_user_in_and_creates_profile(self):
        response = self.client.post(reverse('signup'), {
            'username': 'candidate',
            'email': 'candidate@example.com',
            'password1': 'StrongPass12345',
            'password2': 'StrongPass12345',
        })
        self.assertRedirects(response, reverse('profile'))
        user = User.objects.get(username='candidate')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_vacancies_are_scoped_to_logged_in_user(self):
        owner = User.objects.create_user(username='owner', password='StrongPass12345')
        other = User.objects.create_user(username='other', password='StrongPass12345')
        Vacancy.objects.create(owner=owner, title='Owner vacancy', description='Django')
        Vacancy.objects.create(owner=other, title='Other vacancy', description='Python')

        self.client.login(username='owner', password='StrongPass12345')
        response = self.client.get(reverse('vacancy_list'))
        self.assertContains(response, 'Owner vacancy')
        self.assertNotContains(response, 'Other vacancy')

    def test_structured_json_is_rendered_as_readable_text(self):
        rendered = render_structured({
            'summary': 'Подходит частично',
            'main_risks': ['Мало опыта', 'Не указан Akka'],
        })
        self.assertIn('Кратко: Подходит частично', rendered)
        self.assertIn('Главные риски:', rendered)
        self.assertIn('- Мало опыта', rendered)
        self.assertNotIn("{'summary'", rendered)
