from django.db import models
from django.contrib.auth.models import AbstractUser

class Language(models.Model):
    """Model representing a language."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # ISO language code like 'en', 'es', 'fr'
    flag_emoji = models.CharField(max_length=10, blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class UserLanguage(models.Model):
    """Intermediate model for User-Language relationship with proficiency."""
    PROFICIENCY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('native', 'Native'),
    ]
    
    LANGUAGE_TYPE_CHOICES = [
        ('native', 'Native Language'),
        ('learning', 'Learning'),
        ('fluent', 'Fluent'),
    ]
    
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    proficiency = models.CharField(max_length=20, choices=PROFICIENCY_CHOICES)
    language_type = models.CharField(max_length=20, choices=LANGUAGE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'language']
        ordering = ['language__name']
    
    def __str__(self):
        return f"{self.user.username} - {self.language.name} ({self.get_proficiency_display()})"

class User(AbstractUser):
    """
    Custom user model that extends the AbstractUser model.
    """
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    interests = models.TextField(blank=True)
    languages = models.ManyToManyField(Language, through=UserLanguage, blank=True)
    
    # Keep legacy fields for backward compatibility (can be removed later)
    native_language = models.CharField(max_length=100, blank=True)
    target_language = models.CharField(max_length=100, blank=True)
    proficiency = models.CharField(max_length=50, blank=True)
    
    def get_native_languages(self):
        """Get user's native languages."""
        return self.userlanguage_set.filter(language_type='native')
    
    def get_learning_languages(self):
        """Get languages user is learning."""
        return self.userlanguage_set.filter(language_type='learning')
    
    def get_fluent_languages(self):
        """Get languages user is fluent in."""
        return self.userlanguage_set.filter(language_type='fluent')
    
    def can_teach(self):
        """Get languages user can teach (native + fluent)."""
        return self.userlanguage_set.filter(language_type__in=['native', 'fluent'])
    
    def __str__(self):
        return self.username