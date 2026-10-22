"""Partner practice streaks and shared weekly goals.

A week counts toward the streak when the partners complete at least
`match.weekly_goal` scheduled sessions in that week. A scheduled session
counts as completed when an ended call on the pair's video room overlaps
the session window and lasted at least MIN_CALL_MINUTES. Week boundaries
follow the project's current timezone (Monday-start ISO weeks); the UI
labels the timezone next to the streak.

Everything is computed on read: no scheduler or cron needed.
"""
from datetime import timedelta

from django.utils import timezone

MIN_CALL_MINUTES = 5
# A call counts for a session when it overlaps this window around it.
EARLY_GRACE = timedelta(minutes=15)
LATE_GRACE = timedelta(minutes=15)
# Safety bound so a streak walk always terminates.
MAX_LOOKBACK_WEEKS = 260


def week_start(dt):
    """Monday 00:00 (current timezone) of the week containing dt."""
    local = timezone.localtime(dt)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return monday


def session_window(session):
    """(start, end) window in which a call counts toward the session."""
    start = session.starts_at - EARLY_GRACE
    end = session.starts_at + timedelta(minutes=session.duration_minutes) + LATE_GRACE
    return start, end


def session_completed(session):
    """True when a qualifying ended call overlaps the session window."""
    from chats.models import CallSession
    try:
        room = session.match.video_room
    except Exception:
        return False
    start, end = session_window(session)
    min_len = timedelta(minutes=MIN_CALL_MINUTES)
    calls = (
        CallSession.objects
        .filter(room=room, status='ended', started_at__lt=end, ended_at__gt=start)
        .values_list('started_at', 'ended_at')
    )
    return any(e - s >= min_len for s, e in calls)


def completed_sessions_in_week(match, ws):
    """Accepted/completed sessions in the given week with a qualifying call."""
    we = ws + timedelta(days=7)
    sessions = match.sessions.filter(
        status__in=('accepted', 'completed'),
        starts_at__gte=ws,
        starts_at__lt=we,
    )
    return sum(1 for s in sessions if session_completed(s))


def weekly_progress(match, ref_dt=None):
    """(done, goal) for the current week."""
    ref_dt = ref_dt or timezone.now()
    return completed_sessions_in_week(match, week_start(ref_dt)), match.weekly_goal


def current_streak(match, ref_dt=None):
    """Consecutive Monday-start weeks meeting the weekly goal, including the
    current week when it is already met."""
    ref_dt = ref_dt or timezone.now()
    streak = 0
    ws = week_start(ref_dt)
    for _ in range(MAX_LOOKBACK_WEEKS):
        if completed_sessions_in_week(match, ws) >= match.weekly_goal:
            streak += 1
            ws -= timedelta(days=7)
        else:
            break
    return streak
