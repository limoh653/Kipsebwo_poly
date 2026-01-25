from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'is_approved']
    list_filter = ['department', 'is_approved']
    actions = ['approve_users']

    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)