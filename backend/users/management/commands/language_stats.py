from django.core.management.base import BaseCommand
from users.models import Language, UserLanguage, User
from collections import defaultdict

class Command(BaseCommand):
    help = 'Display statistics about languages in the system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed statistics including user counts per language',
        )

    def handle(self, *args, **options):
        detailed = options.get('detailed', False)
        
        # Basic statistics
        total_languages = Language.objects.count()
        total_users = User.objects.count()
        total_user_languages = UserLanguage.objects.count()
        
        self.stdout.write(
            self.style.SUCCESS(f'\n📊 SPEAKLE LANGUAGE STATISTICS\n')
        )
        
        self.stdout.write(f'Total Languages Available: {total_languages}')
        self.stdout.write(f'Total Users: {total_users}')
        self.stdout.write(f'Total User-Language Relationships: {total_user_languages}')
        
        if total_users > 0:
            avg_languages_per_user = total_user_languages / total_users
            self.stdout.write(f'Average Languages per User: {avg_languages_per_user:.1f}')
        
        # Language categories
        self.stdout.write(f'\n🌍 LANGUAGES BY REGION:')
        
        regions = {
            'European': ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'nl', 'sv', 'no', 'da', 'fi', 'pl', 'cs', 'hu', 'el', 'ro', 'bg', 'hr', 'sr', 'uk', 'sk', 'sl', 'et', 'lv', 'lt', 'ga', 'cy', 'is', 'eu', 'ca', 'gl', 'mt', 'lb', 'sq', 'mk', 'bs', 'cnr'],
            'Asian': ['zh', 'ja', 'ko', 'hi', 'th', 'vi', 'id', 'ms', 'fil', 'bn', 'ur', 'pa', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'si', 'my', 'km', 'lo', 'mn', 'ne'],
            'Middle Eastern': ['ar', 'he', 'fa', 'tr', 'ku', 'hy', 'ka', 'az'],
            'African': ['sw', 'am', 'yo', 'ig', 'ha', 'zu', 'xh', 'af', 'so'],
            'Americas': ['pt-br', 'qu', 'gn', 'nah', 'fr-ca'],
            'Pacific': ['mi', 'haw', 'sm', 'to', 'fj'],
            'Central Asian': ['kk', 'uz', 'ky', 'tg', 'tk'],
            'Sign/Constructed': ['asl', 'bsl', 'eo', 'la']
        }
        
        for region, codes in regions.items():
            count = Language.objects.filter(code__in=codes).count()
            self.stdout.write(f'  {region}: {count} languages')
        
        # Most popular languages
        if total_user_languages > 0:
            self.stdout.write(f'\n🔥 MOST POPULAR LANGUAGES:')
            
            popular_languages = Language.objects.filter(
                userlanguage__isnull=False
            ).distinct().annotate(
                user_count=models.Count('userlanguage')
            ).order_by('-user_count')[:10]
            
            for i, lang in enumerate(popular_languages, 1):
                self.stdout.write(f'  {i}. {lang.flag_emoji} {lang.name} - {lang.user_count} users')
            
            # Language types distribution
            self.stdout.write(f'\n📚 LANGUAGE LEARNING TYPES:')
            
            type_stats = defaultdict(int)
            for ul in UserLanguage.objects.all():
                type_stats[ul.language_type] += 1
            
            for lang_type, count in type_stats.items():
                percentage = (count / total_user_languages) * 100
                self.stdout.write(f'  {lang_type.title()}: {count} ({percentage:.1f}%)')
            
            # Proficiency distribution
            self.stdout.write(f'\n🎯 PROFICIENCY LEVELS:')
            
            proficiency_stats = defaultdict(int)
            for ul in UserLanguage.objects.all():
                proficiency_stats[ul.proficiency] += 1
            
            for proficiency, count in proficiency_stats.items():
                percentage = (count / total_user_languages) * 100
                self.stdout.write(f'  {proficiency.title()}: {count} ({percentage:.1f}%)')
        
        if detailed and total_user_languages > 0:
            self.stdout.write(f'\n📋 DETAILED LANGUAGE BREAKDOWN:')
            
            all_languages = Language.objects.all().order_by('name')
            for lang in all_languages:
                user_count = lang.userlanguage_set.count()
                native_count = lang.userlanguage_set.filter(language_type='native').count()
                learning_count = lang.userlanguage_set.filter(language_type='learning').count()
                fluent_count = lang.userlanguage_set.filter(language_type='fluent').count()
                
                if user_count > 0:
                    self.stdout.write(
                        f'  {lang.flag_emoji} {lang.name}: {user_count} users '
                        f'(Native: {native_count}, Learning: {learning_count}, Fluent: {fluent_count})'
                    )
        
        # Languages with no users
        unused_languages = Language.objects.filter(userlanguage__isnull=True).count()
        if unused_languages > 0:
            self.stdout.write(f'\n💤 Unused Languages: {unused_languages}')
            
            if detailed:
                self.stdout.write('  Languages not yet used by any user:')
                for lang in Language.objects.filter(userlanguage__isnull=True).order_by('name'):
                    self.stdout.write(f'    {lang.flag_emoji} {lang.name}')
        
        self.stdout.write(f'\n✨ Use --detailed flag for more comprehensive statistics')

# Import models at the end to avoid circular imports
from django.db import models 