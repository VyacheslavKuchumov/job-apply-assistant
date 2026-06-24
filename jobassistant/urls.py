from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from applications import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('profile/', views.profile_edit, name='profile'),
    path('vacancies/', views.vacancy_list, name='vacancy_list'),
    path('vacancies/new/', views.vacancy_create, name='vacancy_create'),
    path('vacancies/<int:pk>/', views.vacancy_detail, name='vacancy_detail'),
    path('vacancies/<int:pk>/edit/', views.vacancy_edit, name='vacancy_edit'),
    path('vacancies/<int:pk>/delete/', views.vacancy_delete, name='vacancy_delete'),
    path('vacancies/<int:pk>/generate/', views.vacancy_generate, name='vacancy_generate'),
    path('vacancies/<int:pk>/chat/', views.vacancy_chat, name='vacancy_chat'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
