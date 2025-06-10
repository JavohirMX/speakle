from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import Language, UserLanguage
from .models import PotentialMatch, Match, MatchRequest
import json

User = get_user_model()

class MatchesAPITestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Set up user languages
        UserLanguage.objects.create(
            user=self.user1,
            language=self.english,
            language_type='native',
            proficiency='native'
        )
        UserLanguage.objects.create(
            user=self.user1,
            language=self.korean,
            language_type='learning',
            proficiency='beginner'
        )
        
        UserLanguage.objects.create(
            user=self.user2,
            language=self.korean,
            language_type='native',
            proficiency='native'
        )
        UserLanguage.objects.create(
            user=self.user2,
            language=self.english,
            language_type='learning',
            proficiency='intermediate'
        )
        
        self.client = Client()
        
    def test_get_potential_matches_api(self):
        """Test getting potential matches via API"""
        # Create a potential match
        PotentialMatch.objects.create(
            user=self.user1,
            potential_partner=self.user2,
            user_teaches=self.english,
            user_learns=self.korean,
            compatibility_score=85.5
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get('/matches/api/potential-matches/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['potential_matches']), 1)
        self.assertEqual(data['potential_matches'][0]['partner']['username'], 'user2')
        
    def test_send_match_request_api(self):
        """Test sending a match request via API"""
        # Create a potential match
        potential_match = PotentialMatch.objects.create(
            user=self.user1,
            potential_partner=self.user2,
            user_teaches=self.english,
            user_learns=self.korean,
            compatibility_score=85.5
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/send-request/{potential_match.id}/', {
            'message': 'Hi! Would love to practice languages with you!'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('request_id', data)
        
        # Verify the request was created
        request = MatchRequest.objects.get(id=data['request_id'])
        self.assertEqual(request.sender, self.user1)
        self.assertEqual(request.receiver, self.user2)
        self.assertEqual(request.message, 'Hi! Would love to practice languages with you!')
        
    def test_respond_to_request_api(self):
        """Test responding to a match request via API"""
        # Create a match request
        match_request = MatchRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            sender_teaches=self.korean,
            sender_learns=self.english,
            message='Hello!'
        )
        
        self.client.login(username='user1', password='testpass123')
        
        # Test accepting the request
        response = self.client.post(f'/matches/api/respond-request/{match_request.id}/', {
            'action': 'accept'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'accepted')
        self.assertIn('match_id', data)
        
        # Verify the match was created
        match = Match.objects.get(id=data['match_id'])
        self.assertIn(self.user1, [match.user1, match.user2])
        self.assertIn(self.user2, [match.user1, match.user2])
        
        # Verify the request status was updated
        match_request.refresh_from_db()
        self.assertEqual(match_request.status, 'accepted')
        
    def test_cancel_match_request_api(self):
        """Test cancelling a match request via API"""
        # Create a match request
        match_request = MatchRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            sender_teaches=self.english,
            sender_learns=self.korean,
            message='Hello!',
            status='pending'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/cancel-request/{match_request.id}/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Verify the request status was updated
        match_request.refresh_from_db()
        self.assertEqual(match_request.status, 'cancelled')
        
    def test_get_pending_requests_api(self):
        """Test getting pending requests via API"""
        # Create incoming and outgoing requests
        incoming_request = MatchRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            sender_teaches=self.korean,
            sender_learns=self.english,
            message='Hi from user2!',
            status='pending'
        )
        
        outgoing_request = MatchRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            sender_teaches=self.english,
            sender_learns=self.korean,
            message='Hi from user1!',
            status='pending'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get('/matches/api/pending-requests/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check incoming requests
        self.assertEqual(len(data['incoming_requests']), 1)
        self.assertEqual(data['incoming_requests'][0]['sender'], 'user2')
        
        # Check outgoing requests
        self.assertEqual(len(data['outgoing_requests']), 1)
        self.assertEqual(data['outgoing_requests'][0]['receiver'], 'user2')
        
    def test_get_my_matches_api(self):
        """Test getting user's matches via API"""
        # Create a match
        match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get('/matches/api/my-matches/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['matches']), 1)
        
        match_data = data['matches'][0]
        self.assertEqual(match_data['id'], match.id)
        self.assertEqual(match_data['partner']['username'], 'user2')
        self.assertEqual(match_data['status'], 'active')
        
    def test_end_match_api(self):
        """Test ending a match via API"""
        # Create a match
        match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/end-match/{match.id}/', {
            'reason': 'No longer interested in language exchange'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('ended_at', data)
        
        # Verify the match was ended
        match.refresh_from_db()
        self.assertEqual(match.status, 'ended')
        self.assertEqual(match.ended_by, self.user1)
        self.assertEqual(match.end_reason, 'No longer interested in language exchange')
        self.assertIsNotNone(match.ended_at)
        
    def test_get_match_statistics_api(self):
        """Test getting match statistics via API"""
        # Create a match
        match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active',
            created_at=timezone.now() - timezone.timedelta(days=10)
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(f'/matches/api/match-statistics/{match.id}/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        stats = data['statistics']
        self.assertEqual(stats['days_active'], 10)
        self.assertEqual(stats['status'], 'active')
        self.assertEqual(stats['partner']['username'], 'user2')
        
    def test_refresh_potential_matches_api(self):
        """Test refreshing potential matches via API"""
        self.client.login(username='user1', password='testpass123')
        response = self.client.post('/matches/api/refresh-matches/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('message', data)
        
    def test_unauthorized_access(self):
        """Test that API endpoints require authentication"""
        endpoints = [
            '/matches/api/potential-matches/',
            '/matches/api/my-matches/',
            '/matches/api/pending-requests/',
            '/matches/api/refresh-matches/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should redirect to login or return 403/401
            self.assertIn(response.status_code, [302, 401, 403])
            
    def test_access_control(self):
        """Test that users can only access their own data"""
        # Create a match request between user2 and another user
        user3 = User.objects.create_user(
            username='user3',
            email='user3@test.com',
            password='testpass123'
        )
        
        match_request = MatchRequest.objects.create(
            sender=self.user2,
            receiver=user3,
            sender_teaches=self.korean,
            sender_learns=self.english,
            message='Hi!'
        )
        
        # User1 should not be able to respond to this request
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/respond-request/{match_request.id}/', {
            'action': 'accept'
        })
        
        self.assertEqual(response.status_code, 404)  # Should not find the request
