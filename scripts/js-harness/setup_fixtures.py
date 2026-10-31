"""Idempotent demo-fixture setup for the js-harness scenarios.

Usage (from the repo root):
    SECRET_KEY=devsecret DEBUG=True python manage.py migrate
    SECRET_KEY=devsecret DEBUG=True python scripts/js-harness/setup_fixtures.py

Creates the users / languages / match / rooms / pending invitation the
scenarios need and writes scripts/js-harness/fixtures.json, which every
scenario script reads (falling back to built-in defaults).
"""
import json
import os
from datetime import timedelta
from pathlib import Path

import sys

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
from users.models import Language
from matches.models import Match
from chats.models import CallInvitation, ChatRoom, VideoRoom

HERE = Path(__file__).resolve().parent

USER = 'a11ydemo'
PARTNER = 'fixturepartner'
PASSWORD = 'fixture-pass-123'


def main():
    user, _ = User.objects.get_or_create(username=USER, defaults={'email': 'a11y@example.com'})
    user.set_password(PASSWORD)
    user.save()
    partner, _ = User.objects.get_or_create(username=PARTNER, defaults={'email': 'partner@example.com'})
    partner.set_password(PASSWORD)
    partner.save()

    en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
    ko, _ = Language.objects.get_or_create(code='ko', defaults={'name': 'Korean'})

    match = Match.objects.filter(user1=user, user2=partner).first() or Match.objects.filter(user1=partner, user2=user).first()
    if match is None:
        match = Match.objects.create(
            user1=user, user2=partner,
            user1_teaches=en, user1_learns=ko,
            status='active',
        )
    room, _ = VideoRoom.objects.get_or_create(match=match)
    chat_room = ChatRoom.objects.filter(match=match).first() or ChatRoom.objects.create(match=match)

    # A live pending invitation from partner to user (message-chip scenario).
    CallInvitation.objects.filter(room=room, caller=partner, receiver=user, status='pending').delete()
    invitation = CallInvitation.objects.create(
        room=room, caller=partner, receiver=user,
        status='pending', expires_at=timezone.now() + timedelta(minutes=10),
        message='hi',
    )

    data = {
        'base_url': os.environ.get('HARNESS_BASE_URL', 'http://127.0.0.1:8000'),
        'cdp_url': os.environ.get('HARNESS_CDP_URL', 'http://127.0.0.1:9223'),
        'user': USER,
        'partner': PARTNER,
        'password': PASSWORD,
        'match_id': match.id,
        'video_room_id': str(room.room_id),
        'chat_room_id': str(chat_room.room_id),
        'invitation_id': invitation.id,
    }
    (HERE / 'fixtures.json').write_text(json.dumps(data, indent=2))
    print('fixtures.json written:', json.dumps(data))


if __name__ == '__main__':
    main()
