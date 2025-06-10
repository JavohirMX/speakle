from django.contrib import admin
from .models import PotentialMatch, Match, MatchRequest

@admin.register(PotentialMatch)
class PotentialMatchAdmin(admin.ModelAdmin):
    list_display = ['user', 'potential_partner', 'user_teaches', 'user_learns', 'compatibility_score', 'created_at']
    list_filter = ['user_teaches', 'user_learns', 'created_at']
    search_fields = ['user__username', 'potential_partner__username']
    ordering = ['-compatibility_score', '-created_at']

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['user1', 'user2', 'user1_teaches', 'user1_learns', 'status', 'created_at']
    list_filter = ['status', 'user1_teaches', 'user1_learns', 'created_at']
    search_fields = ['user1__username', 'user2__username']
    ordering = ['-created_at']

@admin.register(MatchRequest)
class MatchRequestAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'sender_teaches', 'sender_learns', 'status', 'created_at']
    list_filter = ['status', 'sender_teaches', 'sender_learns', 'created_at']
    search_fields = ['sender__username', 'receiver__username']
    ordering = ['-created_at']
