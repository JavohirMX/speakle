from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import Language, UserLanguage
from matches.models import PotentialMatch, Match, MatchRequest
from matches.services import MatchingService
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Generate test data for the Speakle language exchange platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Number of test users to create (default: 20)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data before generating new data'
        )

    def handle(self, *args, **options):
        users_count = options['users']
        clear_data = options['clear']

        if clear_data:
            self.stdout.write(self.style.WARNING('Clearing existing test data...'))
            self.clear_test_data()

        self.stdout.write(self.style.HTTP_INFO('🚀 Generating test data for Speakle...'))
        
        # Create languages
        languages = self.create_languages()
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(languages)} languages'))
        
        # Create test users
        users = self.create_test_users(users_count, languages)
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(users)} test users'))
        
        # Generate matches
        matches_created = self.generate_matches(users)
        self.stdout.write(self.style.SUCCESS(f'✅ Generated {matches_created} potential matches'))
        
        # Create some match requests
        requests_created = self.create_match_requests(users)
        self.stdout.write(self.style.SUCCESS(f'✅ Created {requests_created} match requests'))
        
        # Create some confirmed matches
        confirmed_matches = self.create_confirmed_matches(users)
        self.stdout.write(self.style.SUCCESS(f'✅ Created {confirmed_matches} confirmed matches'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Test data generation completed!'))
        self.stdout.write(self.style.HTTP_INFO('\n📝 Test Users Created:'))
        for user in users[:10]:  # Show first 10 users
            user_langs = user.userlanguage_set.all()
            teaches = [ul.language.name for ul in user_langs if ul.language_type in ['native', 'fluent']]
            learns = [ul.language.name for ul in user_langs if ul.language_type == 'learning']
            self.stdout.write(f'  👤 {user.username} - Teaches: {", ".join(teaches)} | Learns: {", ".join(learns)}')
        
        if len(users) > 10:
            self.stdout.write(f'  ... and {len(users) - 10} more users')

    def clear_test_data(self):
        """Clear existing test data"""
        # Clear matches data
        PotentialMatch.objects.all().delete()
        Match.objects.all().delete()
        MatchRequest.objects.all().delete()
        
        # Clear test users (keep admin users)
        User.objects.filter(is_superuser=False, is_staff=False).delete()

    def create_languages(self):
        """Create language data"""
        languages_data = [
            ('English', 'en', '🇺🇸'),
            ('Spanish', 'es', '🇪🇸'),
            ('French', 'fr', '🇫🇷'),
            ('German', 'de', '🇩🇪'),
            ('Japanese', 'ja', '🇯🇵'),
            ('Korean', 'ko', '🇰🇷'),
            ('Chinese', 'zh', '🇨🇳'),
            ('Italian', 'it', '🇮🇹'),
            ('Portuguese', 'pt', '🇵🇹'),
            ('Russian', 'ru', '🇷🇺'),
            ('Arabic', 'ar', '🇸🇦'),
            ('Hindi', 'hi', '🇮🇳'),
            ('Dutch', 'nl', '🇳🇱'),
            ('Swedish', 'sv', '🇸🇪'),
            ('Polish', 'pl', '🇵🇱'),
        ]
        
        languages = []
        for name, code, flag in languages_data:
            language, created = Language.objects.get_or_create(
                code=code,
                defaults={'name': name, 'flag_emoji': flag}
            )
            languages.append(language)
        
        return languages

    def create_test_users(self, count, languages):
        """Create test users with diverse language profiles"""
        users = []
        
        # Sample user data
        first_names = ['Alex', 'Maria', 'John', 'Anna', 'Mike', 'Sara', 'David', 'Emma', 'James', 'Lisa',
                      'Carlos', 'Sophie', 'Ahmed', 'Nina', 'Yuki', 'Pierre', 'Elena', 'Marco', 'Kai', 'Luna']
        
        last_names = ['Smith', 'Garcia', 'Johnson', 'Brown', 'Williams', 'Jones', 'Miller', 'Davis',
                     'Rodriguez', 'Martinez', 'Anderson', 'Taylor', 'Thomas', 'Hernandez', 'Moore',
                     'Martin', 'Jackson', 'Thompson', 'White', 'Lopez']
        
        interests_pool = [
            'travel, photography, cooking', 'music, movies, reading', 'sports, fitness, hiking',
            'art, painting, museums', 'technology, gaming, programming', 'food, restaurants, culture',
            'books, writing, literature', 'nature, outdoors, camping', 'history, politics, news',
            'fashion, design, shopping', 'yoga, meditation, wellness', 'dancing, parties, socializing',
            'science, research, learning', 'business, entrepreneurship', 'volunteering, charity work'
        ]
        
        bios = [
            "I'm passionate about languages and love meeting people from different cultures!",
            "Traveling the world and learning new languages is my biggest passion.",
            "I believe language exchange is the best way to truly understand a culture.",
            "Looking forward to helping others learn my language while improving my own skills!",
            "I'm a language enthusiast who enjoys deep conversations about life and culture.",
            "Love sharing my culture through language and learning about others.",
            "Professional looking to improve language skills for career advancement.",
            "Student studying international relations, passionate about multilingual communication.",
            "I enjoy cooking traditional food from my country and sharing recipes!",
            "Language learning has opened so many doors for me, excited to help others too!"
        ]
        
        for i in range(count):
            # Generate username
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"{first_name.lower()}{last_name.lower()}{random.randint(10, 99)}"
            
            # Ensure unique username
            while User.objects.filter(username=username).exists():
                username = f"{first_name.lower()}{last_name.lower()}{random.randint(100, 999)}"
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password='testpass123',
                first_name=first_name,
                last_name=last_name,
                bio=random.choice(bios),
                interests=random.choice(interests_pool)
            )
            
            # Add languages to user
            self.add_user_languages(user, languages)
            users.append(user)
        
        return users

    def add_user_languages(self, user, languages):
        """Add random language combinations to a user"""
        available_languages = list(languages)
        
        # Each user has 1-2 native/fluent languages
        native_count = random.randint(1, 2)
        native_languages = random.sample(available_languages, native_count)
        
        for lang in native_languages:
            UserLanguage.objects.create(
                user=user,
                language=lang,
                proficiency='native' if random.random() > 0.3 else 'advanced',
                language_type='native' if random.random() > 0.2 else 'fluent'
            )
            available_languages.remove(lang)
        
        # Each user wants to learn 1-3 languages
        if available_languages:
            learning_count = random.randint(1, min(3, len(available_languages)))
            learning_languages = random.sample(available_languages, learning_count)
            
            for lang in learning_languages:
                proficiency_levels = ['beginner', 'intermediate', 'advanced']
                UserLanguage.objects.create(
                    user=user,
                    language=lang,
                    proficiency=random.choice(proficiency_levels),
                    language_type='learning'
                )

    def generate_matches(self, users):
        """Generate potential matches for users"""
        matches_created = 0
        
        for user in users:
            # Generate matches for each user
            potential_matches = MatchingService.find_potential_matches(user, refresh=True)
            matches_created += len(potential_matches)
        
        return matches_created

    def create_match_requests(self, users):
        """Create some match requests between users"""
        requests_created = 0
        request_messages = [
            "Hi! I'd love to practice languages with you. Let's help each other learn!",
            "Hello! I noticed we can help each other with our target languages. Interested in chatting?",
            "Hey there! I'm looking for a language exchange partner. Would you like to practice together?",
            "Hi! I'm excited to learn your language and help you with mine. Let's connect!",
            "Hello! I think we'd make great language exchange partners. What do you think?",
        ]
        
        # Create requests for about 30% of users
        for user in random.sample(users, len(users) // 3):
            potential_matches = PotentialMatch.objects.filter(user=user)[:3]
            
            for potential_match in potential_matches:
                if random.random() > 0.5:  # 50% chance to send request
                    message = random.choice(request_messages)
                    match_request, created = MatchingService.send_match_request(
                        sender=user,
                        receiver=potential_match.potential_partner,
                        sender_teaches_lang=potential_match.user_teaches,
                        sender_learns_lang=potential_match.user_learns,
                        message=message
                    )
                    if created:
                        requests_created += 1
        
        return requests_created

    def create_confirmed_matches(self, users):
        """Create some confirmed matches by accepting requests"""
        confirmed_matches = 0
        
        # Accept some pending requests
        pending_requests = MatchRequest.objects.filter(status='pending')
        
        for request in random.sample(list(pending_requests), min(len(pending_requests), len(users) // 4)):
            if random.random() > 0.3:  # 70% chance to accept
                match = MatchingService.respond_to_match_request(request, accept=True)
                if match:
                    confirmed_matches += 1
            else:
                # Some get declined
                MatchingService.respond_to_match_request(request, accept=False)
        
        return confirmed_matches 