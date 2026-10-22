"""Partner practice streaks and shared weekly goals.

A week counts toward the streak when the partners complete at least the
goal in effect for that week (see MatchGoalChange) in scheduled sessions.
A scheduled session counts as completed when an ended call on the pair's
video room:

* overlaps the session window (EARLY_GRACE before start to
  duration + LATE_GRACE after start), and
* has at least MIN_CALL_MINUTES of JOINT presence: recorded
  CallParticipantInterval spans show both partners in the call at the
  same time for that long. Intervals are opened only when a user
  actually signals (call start/offer/answer/peer-ready) and closed on
  disconnect or call end, so they are the provenance for attendance.
  Note: this proves signaling-connected overlap, not actual audio or
  video engagement - a muted idle call still counts.
  Calls recorded before interval tracking existed have no intervals and
  never earn credit - legacy rows cannot prove attendance.

Each call credits at most one scheduled session (the earliest still
uncredited session it overlaps), so one call cannot satisfy two
overlapping sessions.

Week boundaries follow the project's current timezone (Monday-start
weeks); the UI labels the timezone next to the streak. Per-user timezone
handling is an open product decision.

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


def goal_for_week(match, ws):
    """The weekly goal in effect for the week starting at ws.

    Uses the latest MatchGoalChange effective on or before that week's
    Monday; weeks before the first recorded change use that first goal;
    with no recorded changes, falls back to match.weekly_goal.
    """
    changes = list(match.goal_changes.order_by('effective_week')
                   .values_list('effective_week', 'goal'))
    if not changes:
        return match.weekly_goal
    monday = ws.date()
    goal = changes[0][1]
    for effective, value in changes:
        if effective <= monday:
            goal = value
        else:
            break
    return goal


def _merge(spans):
    """Merge [(start, end)] spans into disjoint sorted spans."""
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def joint_presence_seconds(call, user_a_id, user_b_id):
    """Seconds both users were simultaneously present in the call,
    from recorded CallParticipantInterval spans. Open intervals are
    treated as ending at the call's end."""
    spans = {user_a_id: [], user_b_id: []}
    for iv in call.participant_intervals.all():
        if iv.user_id in spans:
            spans[iv.user_id].append((iv.joined_at, iv.left_at or call.ended_at))
    a, b = _merge(spans[user_a_id]), _merge(spans[user_b_id])
    total = 0.0
    i = j = 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            total += (hi - lo).total_seconds()
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def qualifying_call_for_session(session, used_call_ids):
    """The first unused ended call that qualifies for this session, or None.

    Qualifying: overlaps the session window and has >= MIN_CALL_MINUTES
    of joint presence by both partners, proven by recorded presence
    intervals. Calls without intervals (legacy rows) never qualify.
    """
    from chats.models import CallSession
    try:
        room = session.match.video_room
    except Exception:
        return None
    start, end = session_window(session)
    calls = (
        CallSession.objects
        .filter(room=room, status='ended', started_at__lt=end, ended_at__gt=start)
        .exclude(id__in=used_call_ids)
        .prefetch_related('participant_intervals')
        .order_by('started_at')
    )
    for call in calls:
        if call.ended_at is None or call.started_at is None:
            continue
        joint = joint_presence_seconds(
            call, session.match.user1_id, session.match.user2_id)
        if joint >= MIN_CALL_MINUTES * 60:
            return call
    return None


def session_completed(session):
    """True when a qualifying ended call overlaps the session window."""
    return qualifying_call_for_session(session, set()) is not None


def completed_sessions_in_week(match, ws, used_call_ids=None):
    """Accepted/completed sessions in the given week with a qualifying call.

    Each call credits at most one session; `used_call_ids` carries credit
    already given to other weeks/sessions and is updated in place.
    """
    if used_call_ids is None:
        used_call_ids = set()
    we = ws + timedelta(days=7)
    sessions = match.sessions.filter(
        status__in=('accepted', 'completed'),
        starts_at__gte=ws,
        starts_at__lt=we,
    ).order_by('starts_at')
    done = 0
    for s in sessions:
        call = qualifying_call_for_session(s, used_call_ids)
        if call is not None:
            used_call_ids.add(call.id)
            done += 1
    return done


def weekly_progress(match, ref_dt=None):
    """(done, goal) for the current week."""
    ref_dt = ref_dt or timezone.now()
    ws = week_start(ref_dt)
    return (completed_sessions_in_week(match, ws),
            goal_for_week(match, ws))


def current_streak(match, ref_dt=None):
    """Consecutive Monday-start weeks meeting their goal.

    The current week counts when it is already met; when it is not yet
    met the streak stays alive on the strength of prior weeks (a week
    that has not ended cannot break the streak). Each week is judged by
    the goal in effect for that week, so later goal changes never
    rewrite earned history.
    """
    ref_dt = ref_dt or timezone.now()
    ws = week_start(ref_dt)
    used_call_ids = set()
    streak = 0
    if completed_sessions_in_week(match, ws, used_call_ids) >= goal_for_week(match, ws):
        streak = 1
    ws -= timedelta(days=7)
    for _ in range(MAX_LOOKBACK_WEEKS):
        done = completed_sessions_in_week(match, ws, used_call_ids)
        if done >= goal_for_week(match, ws):
            streak += 1
            ws -= timedelta(days=7)
        else:
            break
    return streak
