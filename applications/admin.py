from django.contrib import admin
from .models import Profile, Vacancy, VacancyChatMessage


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'desired_position', 'updated_at']
    search_fields = ['user__username', 'full_name', 'desired_position']


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'vacancy_url', 'generated_at', 'updated_at']
    list_filter = ['owner']
    search_fields = ['title', 'description', 'notes', 'owner__username']


@admin.register(VacancyChatMessage)
class VacancyChatMessageAdmin(admin.ModelAdmin):
    list_display = ['vacancy', 'role', 'created_at']
    search_fields = ['message']
