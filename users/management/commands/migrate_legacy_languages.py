from django.core.management.base import BaseCommand
from users.models import User, Language, UserLanguage

class Command(BaseCommand):
    help = 'Migrate legacy language text fields to new Language model system'

    def handle(self, *args, **options):
        migrated_count = 0
        
        # Get users with legacy language data who don't have UserLanguage entries
        users_to_migrate = User.objects.exclude(
            native_language='',
            target_language=''
        ).filter(
            userlanguage__isnull=True
        ).distinct()
        
        for user in users_to_migrate:
            try:
                # Try to find native language
                if user.native_language:
                    try:
                        native_lang = Language.objects.get(name__iexact=user.native_language)
                        UserLanguage.objects.get_or_create(
                            user=user,
                            language=native_lang,
                            defaults={
                                'proficiency': 'native',
                                'language_type': 'native'
                            }
                        )
                        self.stdout.write(f'Added native language {native_lang.name} for {user.username}')
                    except Language.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'Language "{user.native_language}" not found for user {user.username}')
                        )
                
                # Try to find target language
                if user.target_language:
                    try:
                        target_lang = Language.objects.get(name__iexact=user.target_language)
                        proficiency = user.proficiency if user.proficiency else 'beginner'
                        UserLanguage.objects.get_or_create(
                            user=user,
                            language=target_lang,
                            defaults={
                                'proficiency': proficiency,
                                'language_type': 'learning'
                            }
                        )
                        self.stdout.write(f'Added target language {target_lang.name} for {user.username}')
                    except Language.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'Language "{user.target_language}" not found for user {user.username}')
                        )
                
                migrated_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error migrating user {user.username}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully migrated {migrated_count} users')
        ) 