import re
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import UserLanguage, Language
from .models import PotentialMatch, Match, MatchRequest

User = get_user_model()

class MatchingService:
    """Service class to handle user matching logic."""
    
    @staticmethod
    def _tokenize_interests(text):
        """Split free-text interests on commas, spaces, semicolons etc. (min 2 chars)."""
        return {t for t in re.split(r'[^\w+#]+', (text or '').lower()) if len(t) > 1}

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
            user_interests = MatchingService._tokenize_interests(user.interests)
            partner_interests = MatchingService._tokenize_interests(potential_partner.interests)
            common_interests = user_interests & partner_interests
            score += min(len(common_interests), 6) * 5.0
        
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
        
        # Users we should not suggest: self, active/pending matches, pending requests either way
        excluded = {user.id}
        for u1, u2 in Match.objects.filter(
            Q(user1=user) | Q(user2=user), status__in=['active', 'pending', 'accepted']
        ).values_list('user1_id', 'user2_id'):
            excluded.update((u1, u2))
        for s_id, r_id in MatchRequest.objects.filter(
            Q(sender=user) | Q(receiver=user), status='pending'
        ).values_list('sender_id', 'receiver_id'):
            excluded.update((s_id, r_id))

        from users.models import UserBlock
        for b1, b2 in UserBlock.objects.filter(
            Q(blocker=user) | Q(blocked=user)
        ).values_list('blocker_id', 'blocked_id'):
            excluded.update((b1, b2))

        existing = set(PotentialMatch.objects.filter(user=user).values_list('potential_partner_id', flat=True))
        languages = {l.id: l for l in Language.objects.filter(id__in=set(user_can_teach) | set(user_wants_to_learn))}

        # Keep only the BEST scoring language pairing per partner
        best = {}
        for teach_lang in set(user_can_teach):
            for learn_lang in set(user_wants_to_learn):
                if teach_lang == learn_lang:
                    continue
                partners = User.objects.filter(
                    userlanguage__language=teach_lang,
                    userlanguage__language_type='learning'
                ).filter(
                    userlanguage__language=learn_lang,
                    userlanguage__language_type__in=['native', 'fluent']
                ).filter(is_active=True).exclude(id__in=excluded).exclude(id__in=existing).distinct()
                for partner in partners:
                    score = MatchingService.calculate_compatibility_score(
                        user, partner, teach_lang, learn_lang
                    )
                    cur = best.get(partner.id)
                    if cur is None or score > cur[0]:
                        best[partner.id] = (score, partner, teach_lang, learn_lang)

        potential_matches = []
        for score, partner, teach_lang, learn_lang in best.values():
            potential_matches.append(PotentialMatch.objects.create(
                user=user,
                potential_partner=partner,
                user_teaches=languages[teach_lang],
                user_learns=languages[learn_lang],
                compatibility_score=score,
            ))
        potential_matches.sort(key=lambda m: -m.compatibility_score)
        return potential_matches

    @staticmethod
    def send_match_request(sender, receiver, sender_teaches_lang, sender_learns_lang, message=""):
        """Send a match request. Returns (request_or_None, created).

        - Self requests and already-matched pairs return (None, False).
        - A pending request already sent returns (existing, False).
        - If the receiver already asked the sender, that request is left for the
          sender to accept (returned with created=False) to avoid duplicate matches.
        - A previously declined/cancelled request is re-opened.
        """
        if sender.id == receiver.id or not receiver.is_active:
            return None, False
        from users.models import UserBlock
        if UserBlock.either_way(sender, receiver):
            return None, False
        with transaction.atomic():
            if Match.objects.filter(
                Q(user1=sender, user2=receiver) | Q(user1=receiver, user2=sender),
                status__in=['active', 'pending', 'accepted'],
            ).exists():
                return None, False

            reverse = MatchRequest.objects.filter(
                sender=receiver, receiver=sender, status='pending'
            ).first()
            if reverse:
                return reverse, False

            existing = MatchRequest.objects.select_for_update().filter(
                sender=sender, receiver=receiver
            ).first()
            if existing:
                if existing.status == 'pending':
                    return existing, False
                existing.status = 'pending'
                existing.sender_teaches = sender_teaches_lang
                existing.sender_learns = sender_learns_lang
                existing.message = message
                existing.responded_at = None
                existing.save()
                return existing, True

            match_request = MatchRequest.objects.create(
                sender=sender,
                receiver=receiver,
                sender_teaches=sender_teaches_lang,
                sender_learns=sender_learns_lang,
                message=message,
            )
            return match_request, True

    @staticmethod
    def respond_to_match_request(match_request, accept=True):
        """Accept or decline a pending request. Idempotent: a non-pending request is a no-op."""
        with transaction.atomic():
            match_request = MatchRequest.objects.select_for_update().get(pk=match_request.pk)
            if match_request.status != 'pending':
                return None
            if accept and not match_request.sender.is_active:
                match_request.status = 'cancelled'
                match_request.responded_at = timezone.now()
                match_request.save()
                return None
            match_request.status = 'accepted' if accept else 'declined'
            match_request.responded_at = timezone.now()
            match_request.save()
            if not accept:
                return None
            match, created = Match.objects.get_or_create(
                user1=match_request.sender,
                user2=match_request.receiver,
                defaults=dict(
                    user1_teaches=match_request.sender_teaches,
                    user1_learns=match_request.sender_learns,
                    status='active',
                ),
            )
            if not created and match.status != 'active':
                match.status = 'active'
                match.user1_teaches = match_request.sender_teaches
                match.user1_learns = match_request.sender_learns
                match.ended_at = None
                match.save()
            return match

    @staticmethod
    def get_user_matches(user, status='active'):
        """Get all matches for a user with a specific status."""
        return Match.objects.filter(
            Q(user1=user) | Q(user2=user),
            status=status
        ).select_related('user1', 'user2', 'user1_teaches', 'user1_learns').order_by('-created_at')