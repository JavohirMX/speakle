"""Quick match: pair two waiting users with a mirrored language pair, give them
a timed first call, then let both choose keep-in-touch or skip."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from users.models import UserBlock, UserLanguage
from .models import Match, QuickMatchEntry

TRIAL_MINUTES = 5
WAIT_TTL_MINUTES = 3  # a waiting entry older than this is treated as abandoned


class QuickMatchError(Exception):
    pass


def default_language_pair(user):
    """First language the user can teach and first they are learning, or None."""
    teach = UserLanguage.objects.filter(user=user, language_type__in=['native', 'fluent']).order_by('id').first()
    learn = UserLanguage.objects.filter(user=user, language_type='learning').order_by('id').first()
    if teach and learn and teach.language_id != learn.language_id:
        return teach.language, learn.language
    return None


def can_quick_match(user):
    """Single hook for gating (e.g. email verification) in one place."""
    return user.is_authenticated


def _already_connected(a, b):
    return Match.objects.filter(
        Q(user1=a, user2=b) | Q(user1=b, user2=a)
    ).exists()


@transaction.atomic
def join_queue(user):
    """Join the queue, or pair immediately. Returns (match_or_None)."""
    if not can_quick_match(user):
        raise QuickMatchError('Quick match is not available for your account.')
    pair = default_language_pair(user)
    if not pair:
        raise QuickMatchError('Add a language you can teach and one you are learning to your profile first.')
    teaches, learns = pair

    # drop my stale entry (and any already-paired leftover is handled in status())
    QuickMatchEntry.objects.filter(user=user, match__isnull=True).delete()

    cutoff = timezone.now() - timedelta(minutes=WAIT_TTL_MINUTES)
    candidates = (QuickMatchEntry.objects.select_for_update()
                  .filter(match__isnull=True, created_at__gte=cutoff,
                          teaches=learns, learns=teaches)
                  .exclude(user=user).select_related('user').order_by('created_at'))
    for entry in candidates:
        other = entry.user
        if UserBlock.either_way(user, other) or _already_connected(user, other):
            continue
        match = Match.objects.create(
            user1=other, user2=user,
            user1_teaches=entry.teaches, user1_learns=entry.learns,
            status='trial',
            trial_ends_at=timezone.now() + timedelta(minutes=TRIAL_MINUTES),
        )
        entry.match = match
        entry.save(update_fields=['match'])
        return match

    QuickMatchEntry.objects.update_or_create(
        user=user, defaults={'teaches': teaches, 'learns': learns, 'match': None})
    return None


def leave_queue(user):
    QuickMatchEntry.objects.filter(user=user, match__isnull=True).delete()


@transaction.atomic
def poll(user):
    """Return the paired Match for a waiting user (consuming the entry), else None."""
    entry = QuickMatchEntry.objects.select_for_update().filter(user=user).first()
    if entry and entry.match_id:
        match = entry.match
        entry.delete()
        return match
    return None


@transaction.atomic
def decide(match, user, keep):
    """Record a keep/skip choice. Only valid on a trial after its timer has run out."""
    match = Match.objects.select_for_update().get(pk=match.pk)
    if match.status != 'trial':
        return match
    if match.trial_ends_at and timezone.now() < match.trial_ends_at:
        raise QuickMatchError('The trial call is still running.')
    if user == match.user1:
        match.user1_keep = bool(keep)
    else:
        match.user2_keep = bool(keep)
    if match.user1_keep is False or match.user2_keep is False:
        match.status = 'ended'
        match.ended_at = timezone.now()
        match.ended_by = user
        match.end_reason = 'Quick match: skipped'
    elif match.user1_keep and match.user2_keep:
        match.status = 'active'
    match.save()
    return match
