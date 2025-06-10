from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Language, UserLanguage

class UserLanguageInline(admin.TabularInline):
    model = UserLanguage
    extra = 1

class UserAdmin(BaseUserAdmin):
    inlines = (UserLanguageInline,)
    
    # Add the custom fields to the user admin
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile Information', {
            'fields': ('bio', 'profile_picture', 'interests')
        }),
        ('Legacy Language Fields', {
            'fields': ('native_language', 'target_language', 'proficiency'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'flag_emoji')
    list_filter = ('code',)
    search_fields = ('name', 'code')
    ordering = ('name',)

@admin.register(UserLanguage)
class UserLanguageAdmin(admin.ModelAdmin):
    list_display = ('user', 'language', 'proficiency', 'language_type', 'created_at')
    list_filter = ('proficiency', 'language_type', 'language__name')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'language__name')
    ordering = ('user__username', 'language__name')

# Unregister the default User admin and register our custom one
# admin.site.unregister(User)
admin.site.register(User, UserAdmin)