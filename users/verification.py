"""Email verification with signed, expiring, address-bound tokens (no extra table)."""
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

SALT = 'users.email-verification'
MAX_AGE_SECONDS = 3 * 24 * 3600


def make_token(user):
    return signing.dumps({'uid': user.pk, 'email': user.email}, salt=SALT)


def check_token(token, user_model):
    """Return the user if the token is valid, unexpired and matches their current email."""
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    user = user_model.objects.filter(pk=data.get('uid')).first()
    if user and user.email and user.email == data.get('email'):
        return user
    return None


def send_verification_email(request, user):
    if not user.email:
        return False
    path = reverse('users:verify_email', args=[make_token(user)])
    base = getattr(settings, 'SITE_URL', '') or request.build_absolute_uri('/').rstrip('/')
    link = base + path
    send_mail(
        'Verify your Speakle email',
        f'Hi {user.username},\n\nConfirm your email to use Quick match:\n{link}\n\n'
        'The link works for 3 days. If you did not sign up, ignore this email.\n',
        None, [user.email], fail_silently=False,
    )
    return True
