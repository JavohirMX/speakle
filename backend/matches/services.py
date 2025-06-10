from django.db.models import Q
from django.contrib.auth import get_user_model
from users.models import UserLanguage, Language
from .models import PotentialMatch, Match, MatchRequest

User = get_user_model()

class MatchingService:
    """Service class to handle user matching logic."""
    
    @staticmethod
    def calculate_compatibility_score(user, potential_partner, user_teaches_lang, user_learns_lang):
        """Calculate compatibility score between two users."""
        score = 0.0
        
        # Base score for language compatibility
        score += 50.0
        
        # Proficiency level matching bonus
        user_teach_proficiency = UserLanguage.objects.filter(
            user=user, 
            language=user_teaches_lang,
            language_type__in=['native', 'fluent']
        ).first()
        
        partner_learn_proficiency = UserLanguage.objects.filter(
            user=potential_partner,
            language=user_teaches_lang,
            language_type='learning'
        ).first()
        
        if user_teach_proficiency and partner_learn_proficiency:
            # Better match if teacher is native/advanced and learner is beginner/intermediate
            teach_level = user_teach_proficiency.proficiency
            learn_level = partner_learn_proficiency.proficiency
            
            if teach_level in ['native', 'advanced'] and learn_level in ['beginner', 'intermediate']:
                score += 30.0
            elif teach_level in ['advanced'] and learn_level in ['intermediate', 'advanced']:
                score += 20.0
            else:
                score += 10.0
        
        # Interest matching bonus
        if user.interests and potential_partner.interests:
            user_interests = set(user.interests.lower().split())
            partner_interests = set(potential_partner.interests.lower().split())
            common_interests = user_interests.intersection(partner_interests)
            score += len(common_interests) * 5.0
        
        # Bio length bonus (users with detailed bios are more serious)
        if len(user.bio) > 50 and len(potential_partner.bio) > 50:
            score += 10.0
        
        return min(score, 100.0)  # Cap at 100
    
    @staticmethod
    def find_potential_matches(user, refresh=False):
        """Find potential matches for a user based on language preferences."""
        if refresh:
            # Clear existing potential matches for this user
            PotentialMatch.objects.filter(user=user).delete()
        
        # Get user's teaching languages (native + fluent)
        user_can_teach = UserLanguage.objects.filter(
            user=user,
            language_type__in=['native', 'fluent']
        ).values_list('language', flat=True)
        
        # Get user's learning languages
        user_wants_to_learn = UserLanguage.objects.filter(
            user=user,
            language_type='learning'
        ).values_list('language', flat=True)
        
        if not user_can_teach or not user_wants_to_learn:
            return []
        
        potential_matches = []
        
        # Find users who want to learn what this user can teach
        # AND can teach what this user wants to learn
        for teach_lang in user_can_teach:
            for learn_lang in user_wants_to_learn:
                # Find users who:
                # 1. Want to learn what user can teach (teach_lang)
                # 2. Can teach what user wants to learn (learn_lang)
                # 3. Are not the same user
                potential_partners = User.objects.filter(
                    userlanguage__language=teach_lang,
                    userlanguage__language_type='learning'
                ).filter(
                    userlanguage__language=learn_lang,
                    userlanguage__language_type__in=['native', 'fluent']
                ).exclude(id=user.id).distinct()
                
                for partner in potential_partners:
                    # Check if match already exists
                    existing_match = PotentialMatch.objects.filter(
                        user=user,
                        potential_partner=partner
                    ).exists()
                    
                    if not existing_match:
                        # Calculate compatibility score
                        score = MatchingService.calculate_compatibility_score(
                            user, partner, teach_lang, learn_lang
                        )
                        
                        # Create potential match
                        potential_match = PotentialMatch.objects.create(
                            user=user,
                            potential_partner=partner,
                            user_teaches=Language.objects.get(id=teach_lang),
                            user_learns=Language.objects.get(id=learn_lang),
                            compatibility_score=score
                        )
                        potential_matches.append(potential_match)
        
        return potential_matches
    
    @staticmethod
    def send_match_request(sender, receiver, sender_teaches_lang, sender_learns_lang, message=""):
        """Send a match request from sender to receiver."""
        # Check if request already exists
        existing_request = MatchRequest.objects.filter(
            sender=sender,
            receiver=receiver
        ).first()
        
        if existing_request:
            return existing_request, False  # Already exists
        
        # Check if there's already a match between these users
        existing_match = Match.objects.filter(
            Q(user1=sender, user2=receiver) | Q(user1=receiver, user2=sender)
        ).first()
        
        if existing_match:
            return None, False  # Already matched
        
        # Create new match request
        match_request = MatchRequest.objects.create(
            sender=sender,
            receiver=receiver,
            sender_teaches=sender_teaches_lang,
            sender_learns=sender_learns_lang,
            message=message
        )
        
        return match_request, True
    
    @staticmethod
    def respond_to_match_request(match_request, accept=True):
        """Respond to a match request (accept or decline)."""
        from django.utils import timezone
        
        if accept:
            match_request.status = 'accepted'
            match_request.responded_at = timezone.now()
            match_request.save()
            
            # Create a confirmed match
            match = Match.objects.create(
                user1=match_request.sender,
                user2=match_request.receiver,
                user1_teaches=match_request.sender_teaches,
                user1_learns=match_request.sender_learns,
                status='active'
            )
            
            return match
        else:
            match_request.status = 'declined'
            match_request.responded_at = timezone.now()
            match_request.save()
            
            return None
    
    @staticmethod
    def get_user_matches(user, status='active'):
        """Get all matches for a user with a specific status."""
        return Match.objects.filter(
            Q(user1=user) | Q(user2=user),
            status=status
        ).order_by('-created_at') 