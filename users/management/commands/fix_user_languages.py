from django.core.management.base import BaseCommand
from users.models import User, Language, UserLanguage

class Command(BaseCommand):
    help = 'Fix and validate user language data, ensuring consistency between old and new systems'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force fix all users, even those with existing UserLanguage entries',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🔧 USER LANGUAGE DATA FIXER\n')
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        fixed_count = 0
        error_count = 0
        
        # Get all users
        all_users = User.objects.all()
        
        for user in all_users:
            try:
                user_has_languages = user.userlanguage_set.exists()
                has_legacy_data = bool(user.native_language or user.target_language)
                
                # Skip users who already have UserLanguage entries unless forced
                if user_has_languages and not force:
                    continue
                
                changes_made = False
                
                # Check native language
                if user.native_language:
                    try:
                        native_lang = Language.objects.get(name__iexact=user.native_language)
                        native_ul, created = UserLanguage.objects.get_or_create(
                            user=user,
                            language=native_lang,
                            language_type='native',
                            defaults={'proficiency': 'native'}
                        )
                        
                        if created and not dry_run:
                            changes_made = True
                            self.stdout.write(f'  ✅ Added native language {native_lang.name} for {user.username}')
                        elif created and dry_run:
                            self.stdout.write(f'  [DRY] Would add native language {native_lang.name} for {user.username}')
                        
                    except Language.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Native language "{user.native_language}" not found for {user.username}')
                        )
                        error_count += 1
                
                # Check target language
                if user.target_language:
                    try:
                        target_lang = Language.objects.get(name__iexact=user.target_language)
                        proficiency = user.proficiency if user.proficiency else 'beginner'
                        
                        target_ul, created = UserLanguage.objects.get_or_create(
                            user=user,
                            language=target_lang,
                            language_type='learning',
                            defaults={'proficiency': proficiency}
                        )
                        
                        if created and not dry_run:
                            changes_made = True
                            self.stdout.write(f'  ✅ Added target language {target_lang.name} ({proficiency}) for {user.username}')
                        elif created and dry_run:
                            self.stdout.write(f'  [DRY] Would add target language {target_lang.name} ({proficiency}) for {user.username}')
                        
                    except Language.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(f'  ❌ Target language "{user.target_language}" not found for {user.username}')
                        )
                        error_count += 1
                
                # Check for inconsistencies
                if user_has_languages:
                    # Validate that UserLanguage entries match legacy fields
                    native_uls = user.userlanguage_set.filter(language_type='native')
                    learning_uls = user.userlanguage_set.filter(language_type='learning')
                    
                    if user.native_language and not native_uls.filter(language__name__iexact=user.native_language).exists():
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  {user.username}: Legacy native language "{user.native_language}" doesn\'t match UserLanguage entries')
                        )
                    
                    if user.target_language and not learning_uls.filter(language__name__iexact=user.target_language).exists():
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  {user.username}: Legacy target language "{user.target_language}" doesn\'t match UserLanguage entries')
                        )
                
                if changes_made:
                    fixed_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  💥 Error processing user {user.username}: {str(e)}')
                )
                error_count += 1
        
        # Summary
        self.stdout.write(f'\n📊 SUMMARY:')
        if dry_run:
            self.stdout.write(f'Users that would be fixed: {fixed_count}')
        else:
            self.stdout.write(f'Users successfully fixed: {fixed_count}')
        self.stdout.write(f'Errors encountered: {error_count}')
        
        # Additional checks
        self.stdout.write(f'\n🔍 ADDITIONAL CHECKS:')
        
        # Users with no languages at all
        users_no_languages = User.objects.filter(
            userlanguage__isnull=True,
            native_language='',
            target_language=''
        ).count()
        
        if users_no_languages > 0:
            self.stdout.write(f'Users with no language data: {users_no_languages}')
        
        # Users with legacy data but no UserLanguage entries
        users_legacy_only = User.objects.filter(
            userlanguage__isnull=True
        ).exclude(
            native_language='',
            target_language=''
        ).count()
        
        if users_legacy_only > 0:
            self.stdout.write(f'Users with only legacy language data: {users_legacy_only}')
        
        # Users with UserLanguage but no legacy data
        users_new_only = User.objects.filter(
            userlanguage__isnull=False,
            native_language='',
            target_language=''
        ).count()
        
        if users_new_only > 0:
            self.stdout.write(f'Users with only new language data: {users_new_only}')
        
        # Orphaned UserLanguage entries
        orphaned_entries = UserLanguage.objects.filter(user__isnull=True).count()
        if orphaned_entries > 0:
            self.stdout.write(self.style.ERROR(f'Orphaned UserLanguage entries: {orphaned_entries}'))
        
        # Duplicate UserLanguage entries
        duplicates = UserLanguage.objects.values('user', 'language').annotate(
            count=models.Count('id')
        ).filter(count__gt=1).count()
        
        if duplicates > 0:
            self.stdout.write(self.style.WARNING(f'Users with duplicate language entries: {duplicates}'))
        
        if not dry_run and (fixed_count > 0 or error_count > 0):
            self.stdout.write(f'\n💡 TIP: Run with --dry-run to preview changes before applying them')

# Import models at the end to avoid circular imports
from django.db import models 