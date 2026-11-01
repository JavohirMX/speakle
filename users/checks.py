"""System checks for deploy-time email configuration."""
from django.conf import settings
from django.core.checks import Warning, register

CONSOLE_BACKEND = 'django.core.mail.backends.console.EmailBackend'


@register()
def console_email_backend_outside_debug(app_configs, **kwargs):
    """Warn (never fail) when a non-debug deploy still prints email to the console.

    Verification and reset emails then "send" without error but never reach
    anyone, and Quick match stays locked behind email verification.
    """
    if settings.DEBUG or getattr(settings, 'EMAIL_BACKEND', '') != CONSOLE_BACKEND:
        return []
    return [Warning(
        'EMAIL_BACKEND is the console backend while DEBUG is off.',
        hint='Verification and reset emails are printed to the log, not delivered. '
             'Set EMAIL_BACKEND and the EMAIL_* variables to a real SMTP server '
             '(see DEPLOYMENT.md).',
        id='users.W001',
    )]
