from django.core.management.base import BaseCommand
from users.models import Language

class Command(BaseCommand):
    help = 'Populate the database with common languages'

    def handle(self, *args, **options):
        languages_data = [
            # Major European Languages
            {'name': 'English', 'code': 'en', 'flag_emoji': '🇺🇸'},
            {'name': 'Spanish', 'code': 'es', 'flag_emoji': '🇪🇸'},
            {'name': 'French', 'code': 'fr', 'flag_emoji': '🇫🇷'},
            {'name': 'German', 'code': 'de', 'flag_emoji': '🇩🇪'},
            {'name': 'Italian', 'code': 'it', 'flag_emoji': '🇮🇹'},
            {'name': 'Portuguese', 'code': 'pt', 'flag_emoji': '🇵🇹'},
            {'name': 'Russian', 'code': 'ru', 'flag_emoji': '🇷🇺'},
            {'name': 'Dutch', 'code': 'nl', 'flag_emoji': '🇳🇱'},
            {'name': 'Swedish', 'code': 'sv', 'flag_emoji': '🇸🇪'},
            {'name': 'Norwegian', 'code': 'no', 'flag_emoji': '🇳🇴'},
            {'name': 'Danish', 'code': 'da', 'flag_emoji': '🇩🇰'},
            {'name': 'Finnish', 'code': 'fi', 'flag_emoji': '🇫🇮'},
            {'name': 'Polish', 'code': 'pl', 'flag_emoji': '🇵🇱'},
            {'name': 'Czech', 'code': 'cs', 'flag_emoji': '🇨🇿'},
            {'name': 'Hungarian', 'code': 'hu', 'flag_emoji': '🇭🇺'},
            {'name': 'Greek', 'code': 'el', 'flag_emoji': '🇬🇷'},
            {'name': 'Romanian', 'code': 'ro', 'flag_emoji': '🇷🇴'},
            {'name': 'Bulgarian', 'code': 'bg', 'flag_emoji': '🇧🇬'},
            {'name': 'Croatian', 'code': 'hr', 'flag_emoji': '🇭🇷'},
            {'name': 'Serbian', 'code': 'sr', 'flag_emoji': '🇷🇸'},
            {'name': 'Ukrainian', 'code': 'uk', 'flag_emoji': '🇺🇦'},
            {'name': 'Slovak', 'code': 'sk', 'flag_emoji': '🇸🇰'},
            {'name': 'Slovenian', 'code': 'sl', 'flag_emoji': '🇸🇮'},
            {'name': 'Estonian', 'code': 'et', 'flag_emoji': '🇪🇪'},
            {'name': 'Latvian', 'code': 'lv', 'flag_emoji': '🇱🇻'},
            {'name': 'Lithuanian', 'code': 'lt', 'flag_emoji': '🇱🇹'},
            {'name': 'Irish', 'code': 'ga', 'flag_emoji': '🇮🇪'},
            {'name': 'Welsh', 'code': 'cy', 'flag_emoji': '🏴󠁧󠁢󠁷󠁬󠁳󠁿'},
            {'name': 'Icelandic', 'code': 'is', 'flag_emoji': '🇮🇸'},
            
            # Asian Languages
            {'name': 'Chinese (Mandarin)', 'code': 'zh', 'flag_emoji': '🇨🇳'},
            {'name': 'Japanese', 'code': 'ja', 'flag_emoji': '🇯🇵'},
            {'name': 'Korean', 'code': 'ko', 'flag_emoji': '🇰🇷'},
            {'name': 'Hindi', 'code': 'hi', 'flag_emoji': '🇮🇳'},
            {'name': 'Thai', 'code': 'th', 'flag_emoji': '🇹🇭'},
            {'name': 'Vietnamese', 'code': 'vi', 'flag_emoji': '🇻🇳'},
            {'name': 'Indonesian', 'code': 'id', 'flag_emoji': '🇮🇩'},
            {'name': 'Malay', 'code': 'ms', 'flag_emoji': '🇲🇾'},
            {'name': 'Filipino', 'code': 'fil', 'flag_emoji': '🇵🇭'},
            {'name': 'Bengali', 'code': 'bn', 'flag_emoji': '🇧🇩'},
            {'name': 'Urdu', 'code': 'ur', 'flag_emoji': '🇵🇰'},
            {'name': 'Punjabi', 'code': 'pa', 'flag_emoji': '🇮🇳'},
            {'name': 'Tamil', 'code': 'ta', 'flag_emoji': '🇮🇳'},
            {'name': 'Telugu', 'code': 'te', 'flag_emoji': '🇮🇳'},
            {'name': 'Marathi', 'code': 'mr', 'flag_emoji': '🇮🇳'},
            {'name': 'Gujarati', 'code': 'gu', 'flag_emoji': '🇮🇳'},
            {'name': 'Kannada', 'code': 'kn', 'flag_emoji': '🇮🇳'},
            {'name': 'Malayalam', 'code': 'ml', 'flag_emoji': '🇮🇳'},
            {'name': 'Sinhalese', 'code': 'si', 'flag_emoji': '🇱🇰'},
            {'name': 'Burmese', 'code': 'my', 'flag_emoji': '🇲🇲'},
            {'name': 'Khmer', 'code': 'km', 'flag_emoji': '🇰🇭'},
            {'name': 'Lao', 'code': 'lo', 'flag_emoji': '🇱🇦'},
            {'name': 'Mongolian', 'code': 'mn', 'flag_emoji': '🇲🇳'},
            {'name': 'Nepali', 'code': 'ne', 'flag_emoji': '🇳🇵'},
            
            # Middle Eastern Languages
            {'name': 'Arabic', 'code': 'ar', 'flag_emoji': '🇸🇦'},
            {'name': 'Hebrew', 'code': 'he', 'flag_emoji': '🇮🇱'},
            {'name': 'Persian (Farsi)', 'code': 'fa', 'flag_emoji': '🇮🇷'},
            {'name': 'Turkish', 'code': 'tr', 'flag_emoji': '🇹🇷'},
            {'name': 'Kurdish', 'code': 'ku', 'flag_emoji': '🇮🇶'},
            {'name': 'Armenian', 'code': 'hy', 'flag_emoji': '🇦🇲'},
            {'name': 'Georgian', 'code': 'ka', 'flag_emoji': '🇬🇪'},
            {'name': 'Azerbaijani', 'code': 'az', 'flag_emoji': '🇦🇿'},
            
            # African Languages
            {'name': 'Swahili', 'code': 'sw', 'flag_emoji': '🇰🇪'},
            {'name': 'Amharic', 'code': 'am', 'flag_emoji': '🇪🇹'},
            {'name': 'Yoruba', 'code': 'yo', 'flag_emoji': '🇳🇬'},
            {'name': 'Igbo', 'code': 'ig', 'flag_emoji': '🇳🇬'},
            {'name': 'Hausa', 'code': 'ha', 'flag_emoji': '🇳🇬'},
            {'name': 'Zulu', 'code': 'zu', 'flag_emoji': '🇿🇦'},
            {'name': 'Xhosa', 'code': 'xh', 'flag_emoji': '🇿🇦'},
            {'name': 'Afrikaans', 'code': 'af', 'flag_emoji': '🇿🇦'},
            {'name': 'Somali', 'code': 'so', 'flag_emoji': '🇸🇴'},
            
            # Americas Languages
            {'name': 'Portuguese (Brazilian)', 'code': 'pt-br', 'flag_emoji': '🇧🇷'},
            {'name': 'Quechua', 'code': 'qu', 'flag_emoji': '🇵🇪'},
            {'name': 'Guarani', 'code': 'gn', 'flag_emoji': '🇵🇾'},
            {'name': 'Nahuatl', 'code': 'nah', 'flag_emoji': '🇲🇽'},
            {'name': 'French (Canadian)', 'code': 'fr-ca', 'flag_emoji': '🇨🇦'},
            
            # Pacific Languages
            {'name': 'Maori', 'code': 'mi', 'flag_emoji': '🇳🇿'},
            {'name': 'Hawaiian', 'code': 'haw', 'flag_emoji': '🇺🇸'},
            {'name': 'Samoan', 'code': 'sm', 'flag_emoji': '🇼🇸'},
            {'name': 'Tongan', 'code': 'to', 'flag_emoji': '🇹🇴'},
            {'name': 'Fijian', 'code': 'fj', 'flag_emoji': '🇫🇯'},
            
            # Additional European Languages
            {'name': 'Basque', 'code': 'eu', 'flag_emoji': '🇪🇸'},
            {'name': 'Catalan', 'code': 'ca', 'flag_emoji': '🇪🇸'},
            {'name': 'Galician', 'code': 'gl', 'flag_emoji': '🇪🇸'},
            {'name': 'Maltese', 'code': 'mt', 'flag_emoji': '🇲🇹'},
            {'name': 'Luxembourgish', 'code': 'lb', 'flag_emoji': '🇱🇺'},
            {'name': 'Albanian', 'code': 'sq', 'flag_emoji': '🇦🇱'},
            {'name': 'Macedonian', 'code': 'mk', 'flag_emoji': '🇲🇰'},
            {'name': 'Bosnian', 'code': 'bs', 'flag_emoji': '🇧🇦'},
            {'name': 'Montenegrin', 'code': 'cnr', 'flag_emoji': '🇲🇪'},
            
            # Central Asian Languages
            {'name': 'Kazakh', 'code': 'kk', 'flag_emoji': '🇰🇿'},
            {'name': 'Uzbek', 'code': 'uz', 'flag_emoji': '🇺🇿'},
            {'name': 'Kyrgyz', 'code': 'ky', 'flag_emoji': '🇰🇬'},
            {'name': 'Tajik', 'code': 'tg', 'flag_emoji': '🇹🇯'},
            {'name': 'Turkmen', 'code': 'tk', 'flag_emoji': '🇹🇲'},
            
            # Sign Languages
            {'name': 'American Sign Language', 'code': 'asl', 'flag_emoji': '🤟'},
            {'name': 'British Sign Language', 'code': 'bsl', 'flag_emoji': '🤟'},
            
            # Constructed Languages
            {'name': 'Esperanto', 'code': 'eo', 'flag_emoji': '🟢'},
            {'name': 'Latin', 'code': 'la', 'flag_emoji': '🏛️'},
        ]

        created_count = 0
        updated_count = 0
        
        for lang_data in languages_data:
            language, created = Language.objects.get_or_create(
                code=lang_data['code'],
                defaults={
                    'name': lang_data['name'],
                    'flag_emoji': lang_data['flag_emoji']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created language: {language.name}')
                )
            else:
                # Update existing language if name or emoji changed
                if language.name != lang_data['name'] or language.flag_emoji != lang_data['flag_emoji']:
                    language.name = lang_data['name']
                    language.flag_emoji = lang_data['flag_emoji']
                    language.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Updated language: {language.name}')
                    )

        total_languages = Language.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Language population complete!\n'
                f'Created: {created_count} new languages\n'
                f'Updated: {updated_count} existing languages\n'
                f'Total languages in database: {total_languages}'
            )
        ) 