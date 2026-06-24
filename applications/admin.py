from django.contrib import admin
from .models import Profile, Vacancy, VacancyChatMessage


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'desired_position', 'updated_at']


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['title', 'vacancy_url', 'generated_at', 'updated_at']
    search_fields = ['title', 'description', 'notes']


@admin.register(VacancyChatMessage)
class VacancyChatMessageAdmin(admin.ModelAdmin):
    list_display = ['vacancy', 'role', 'created_at']
    search_fields = ['message']
