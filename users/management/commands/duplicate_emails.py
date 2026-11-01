from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'List accounts that share an email address (case-insensitive). Read-only: nothing is changed or deleted.'

    def handle(self, *args, **options):
        groups = defaultdict(list)
        for u in get_user_model().objects.exclude(email='').order_by('date_joined'):
            groups[u.email.strip().lower()].append(u)
        dupes = {e: us for e, us in groups.items() if len(us) > 1}
        if not dupes:
            self.stdout.write('No duplicate emails.')
            return
        self.stdout.write(f'{len(dupes)} email(s) used by more than one account:')
        for email, users in sorted(dupes.items()):
            names = ', '.join(f'{u.username} (id {u.id}, joined {u.date_joined:%Y-%m-%d}, active={u.is_active})' for u in users)
            self.stdout.write(f'  {email}: {names}')
        self.stdout.write('Nothing was changed. Ask those people to change one address from their profile.')
