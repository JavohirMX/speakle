from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    """
    Custom user model that extends the AbstractUser model.
    """

    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    native_language = models.CharField(max_length=100, blank=True)
    target_language = models.CharField(max_length=100, blank=True)
    proficiency = models.CharField(max_length=50, blank=True)
    interests = models.TextField(blank=True)
    
    
    def __str__(self):
        return self.username