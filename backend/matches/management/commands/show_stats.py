from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import Language, UserLanguage
from matches.models import PotentialMatch, Match, MatchRequest

User = get_user_model()

class Command(BaseCommand):
    help = 'Show statistics about users and matches in the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('📊 Speakle Platform Statistics'))
        self.stdout.write('=' * 50)
        
        # User statistics
        total_users = User.objects.count()
        regular_users = User.objects.filter(is_superuser=False, is_staff=False).count()
        admin_users = User.objects.filter(is_superuser=True).count()
        
        self.stdout.write(self.style.SUCCESS(f'👥 Users: {total_users} total ({regular_users} regular, {admin_users} admin)'))
        
        # Language statistics
        total_languages = Language.objects.count()
        self.stdout.write(self.style.SUCCESS(f'🌍 Languages: {total_languages} available'))
        
        # User language statistics
        user_languages = UserLanguage.objects.count()
        native_speakers = UserLanguage.objects.filter(language_type='native').count()
        fluent_speakers = UserLanguage.objects.filter(language_type='fluent').count()
        learners = UserLanguage.objects.filter(language_type='learning').count()
        
        self.stdout.write(self.style.SUCCESS(f'🗣️  User Languages: {user_languages} total'))
        self.stdout.write(f'   • Native speakers: {native_speakers}')
        self.stdout.write(f'   • Fluent speakers: {fluent_speakers}')
        self.stdout.write(f'   • Language learners: {learners}')
        
        # Match statistics
        potential_matches = PotentialMatch.objects.count()
        confirmed_matches = Match.objects.filter(status='active').count()
        total_requests = MatchRequest.objects.count()
        pending_requests = MatchRequest.objects.filter(status='pending').count()
        accepted_requests = MatchRequest.objects.filter(status='accepted').count()
        declined_requests = MatchRequest.objects.filter(status='declined').count()
        
        self.stdout.write(self.style.SUCCESS(f'🤝 Matches:'))
        self.stdout.write(f'   • Potential matches: {potential_matches}')
        self.stdout.write(f'   • Confirmed matches: {confirmed_matches}')
        self.stdout.write(f'   • Total requests: {total_requests}')
        self.stdout.write(f'   • Pending requests: {pending_requests}')
        self.stdout.write(f'   • Accepted requests: {accepted_requests}')
        self.stdout.write(f'   • Declined requests: {declined_requests}')
        
        # Top languages
        self.stdout.write(self.style.HTTP_INFO('\n🔥 Most Popular Languages:'))
        popular_native = UserLanguage.objects.filter(language_type__in=['native', 'fluent']).values('language__name').distinct()
        popular_learning = UserLanguage.objects.filter(language_type='learning').values('language__name').distinct()
        
        self.stdout.write(f'   • Teaching: {len(popular_native)} different languages')
        self.stdout.write(f'   • Learning: {len(popular_learning)} different languages')
        
        # Sample users
        self.stdout.write(self.style.HTTP_INFO('\n👤 Sample Users:'))
        sample_users = User.objects.filter(is_superuser=False)[:5]
        for user in sample_users:
            user_langs = user.userlanguage_set.all()
            teaches = [ul.language.name for ul in user_langs if ul.language_type in ['native', 'fluent']]
            learns = [ul.language.name for ul in user_langs if ul.language_type == 'learning']
            self.stdout.write(f'   • {user.username} - Teaches: {", ".join(teaches)} | Learns: {", ".join(learns)}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Statistics complete!')) 