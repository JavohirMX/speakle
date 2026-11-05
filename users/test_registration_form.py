"""Registration form: native and target language must differ."""
from django.test import TestCase

from .forms import UserRegistrationForm
from .models import Language


class RegistrationFormLanguageTests(TestCase):
    def setUp(self):
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')

    def _form(self, native, target):
        return UserRegistrationForm({
            'username': 'reg1', 'first_name': 'Reg',
            'email': 'reg1@x.com',
            'native_language': native.id, 'target_language': target.id,
            'target_proficiency': 'beginner',
            'password1': 'Str0ng!Pass', 'password2': 'Str0ng!Pass',
        })

    def test_same_native_and_target_rejected(self):
        form = self._form(self.en, self.en)
        self.assertFalse(form.is_valid())
        self.assertIn('cannot be the same', str(form.errors))

    def test_different_languages_accepted(self):
        form = self._form(self.en, self.ko)
        self.assertTrue(form.is_valid(), form.errors)
