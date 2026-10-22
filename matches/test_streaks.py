"""Partner streak / shared weekly goal logic."""
import datetime as dt

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chats.models import CallSession, VideoRoom
from matches.models import Match, MatchSession
from matches.streaks import current_streak, session_completed, week_start, weekly_progress
from users.models import Language, User

TZ = timezone.get_current_timezone()
MIN = dt.timedelta(minutes=1)


def aware(y, m, d, hh=12, mm=0):
    return dt.datetime(y, m, d, hh, mm, tzinfo=TZ)


class StreakBase(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user(username='anna2', password='pw', email='a2@x.com')
        self.boris = User.objects.create_user(username='boris2', password='pw', email='b2@x.com')
        self.en = Language.objects.create(code='en2', name='English')
        self.es = Language.objects.create(code='es2', name='Spanish')
        self.match = Match.objects.create(
            user1=self.anna, user2=self.boris,
            user1_teaches=self.en, user1_learns=self.es, status='active')
        self.room = VideoRoom.objects.create(match=self.match)

    def add_session(self, starts_at, status='accepted', duration=30):
        return MatchSession.objects.create(
            match=self.match, proposed_by=self.anna,
            starts_at=starts_at, duration_minutes=duration, status=status)

    def add_call(self, started_at, minutes=30):
        # started_at is auto_now_add: create, then set timestamps directly.
        call = CallSession.objects.create(
            room=self.room, status='ended', end_reason='normal')
        CallSession.objects.filter(id=call.id).update(
            started_at=started_at, ended_at=started_at + dt.timedelta(minutes=minutes))
        call.refresh_from_db()
        return call


class WeekStartTests(StreakBase):
    def test_monday_midnight_boundary(self):
        sun = aware(2026, 10, 18, 23, 59)   # Sunday
        mon = aware(2026, 10, 19, 0, 1)     # Monday
        self.assertEqual(week_start(sun), aware(2026, 10, 12, 0, 0))
        self.assertEqual(week_start(mon), aware(2026, 10, 19, 0, 0))


class CompletionTests(StreakBase):
    def test_overlapping_call_completes_session(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0))
        self.add_call(aware(2026, 10, 21, 18, 5), minutes=30)
        self.assertTrue(session_completed(s))

    def test_short_call_does_not_count(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0))
        self.add_call(aware(2026, 10, 21, 18, 5), minutes=3)
        self.assertFalse(session_completed(s))

    def test_call_outside_window_does_not_count(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0), duration=30)
        self.add_call(aware(2026, 10, 21, 20, 0), minutes=40)  # >45min after end
        self.assertFalse(session_completed(s))

    def test_call_within_grace_counts(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0), duration=30)
        self.add_call(aware(2026, 10, 21, 17, 50), minutes=30)  # 10min early
        self.assertTrue(session_completed(s))

    def test_cancelled_session_with_call_not_counted(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0), status='cancelled')
        self.add_call(aware(2026, 10, 21, 18, 5), minutes=30)
        self.assertEqual(weekly_progress(self.match, aware(2026, 10, 21, 20, 0))[0], 0)


class StreakTests(StreakBase):
    def test_no_sessions_zero_streak(self):
        self.assertEqual(current_streak(self.match, aware(2026, 10, 22, 12, 0)), 0)
        self.assertEqual(weekly_progress(self.match, aware(2026, 10, 22, 12, 0)), (0, 1))

    def test_current_week_met_counts(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0))  # Wed this week
        self.add_call(aware(2026, 10, 21, 18, 5), minutes=30)
        self.assertEqual(weekly_progress(self.match, aware(2026, 10, 22, 12, 0)), (1, 1))
        self.assertEqual(current_streak(self.match, aware(2026, 10, 22, 12, 0)), 1)

    def test_consecutive_weeks_and_gap(self):
        # weeks of Oct 5, Oct 12, Oct 19 (current); gap week of Sep 28
        for monday in (aware(2026, 10, 5, 18, 0), aware(2026, 10, 12, 18, 0), aware(2026, 10, 19, 18, 0)):
            s = self.add_session(monday)
            self.add_call(monday, minutes=30)
        s_gap = self.add_session(aware(2026, 9, 28, 18, 0))  # week with NO call
        self.assertEqual(current_streak(self.match, aware(2026, 10, 22, 12, 0)), 3)

    def test_goal_two_requires_two_calls(self):
        self.match.weekly_goal = 2
        self.match.save()
        s = self.add_session(aware(2026, 10, 21, 18, 0))
        self.add_call(aware(2026, 10, 21, 18, 5), minutes=30)
        self.assertEqual(weekly_progress(self.match, aware(2026, 10, 22, 12, 0)), (1, 2))
        self.assertEqual(current_streak(self.match, aware(2026, 10, 22, 12, 0)), 0)
        s2 = self.add_session(aware(2026, 10, 22, 18, 0))
        self.add_call(aware(2026, 10, 22, 18, 5), minutes=30)
        self.assertEqual(current_streak(self.match, aware(2026, 10, 23, 12, 0)), 1)

    def test_stored_completed_status_counted(self):
        s = self.add_session(aware(2026, 10, 21, 18, 0), status='completed')
        self.add_call(aware(2026, 10, 21, 18, 5), minutes=30)
        self.assertEqual(weekly_progress(self.match, aware(2026, 10, 22, 12, 0))[0], 1)


class WeeklyGoalViewTests(StreakBase):
    def test_member_can_set_goal(self):
        self.client.login(username='anna2', password='pw')
        r = self.client.post(reverse('matches:set_weekly_goal', args=[self.match.id]),
                             {'weekly_goal': '3'})
        self.assertRedirects(r, reverse('matches:match_detail', args=[self.match.id]))
        self.match.refresh_from_db()
        self.assertEqual(self.match.weekly_goal, 3)

    def test_invalid_goal_rejected(self):
        self.client.login(username='anna2', password='pw')
        self.client.post(reverse('matches:set_weekly_goal', args=[self.match.id]),
                         {'weekly_goal': '9'})
        self.match.refresh_from_db()
        self.assertEqual(self.match.weekly_goal, 1)

    def test_outsider_cannot_set_goal(self):
        outsider = User.objects.create_user(username='eve2', password='pw', email='e2@x.com')
        self.client.login(username='eve2', password='pw')
        self.client.post(reverse('matches:set_weekly_goal', args=[self.match.id]),
                         {'weekly_goal': '5'})
        self.match.refresh_from_db()
        self.assertEqual(self.match.weekly_goal, 1)

    def test_match_page_shows_streak_context(self):
        self.client.login(username='anna2', password='pw')
        r = self.client.get(reverse('matches:match_detail', args=[self.match.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Shared weekly goal')
        self.assertContains(r, 'This week: 0/1')
