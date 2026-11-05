from django.db import transaction
from django import forms
from django.contrib.auth import password_validation
from .models import User, Language, UserLanguage

class UserRegistrationForm(forms.ModelForm):
    """Short sign-up form: the two languages, a public username, email and one password.

    Name fields and the "type it again" password box are gone (nothing in the app showed
    the name, and a Show button lets people check what they typed). The level in the
    language you want to learn is still saved, as Beginner unless the person changes it.
    """
    SELECT_CLASS = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'

    native_language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        empty_label="Select your native language",
        required=True,
        help_text="Your native/mother tongue language",
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    target_language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        empty_label="Select language you want to learn",
        required=True,
        help_text="Language you want to learn or practice",
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    target_proficiency = forms.ChoiceField(
        choices=UserLanguage.PROFICIENCY_CHOICES,
        required=False,
        initial='beginner',
        help_text="Your current level in the target language",
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    email = forms.EmailField(required=True)
    password1 = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    field_order = ['native_language', 'target_language', 'target_proficiency', 'username', 'email', 'password1']

    class Meta:
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('username', 'email', 'password1'):
            self.fields[field_name].widget.attrs['class'] = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('That email already has an account. Sign in, or reset your password.')
        return email

    def clean_target_proficiency(self):
        return self.cleaned_data.get('target_proficiency') or 'beginner'

    def clean(self):
        cleaned_data = super().clean()
        native_language = cleaned_data.get('native_language')
        target_language = cleaned_data.get('target_language')

        # Ensure native and target languages are different
        if native_language and target_language and native_language == target_language:
            raise forms.ValidationError("Native language and target language cannot be the same.")

        password = cleaned_data.get('password1')
        if password:
            candidate = User(username=cleaned_data.get('username', ''), email=cleaned_data.get('email', ''))
            try:
                password_validation.validate_password(password, candidate)
            except forms.ValidationError as exc:
                self.add_error('password1', exc)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password1'])

        # Keep legacy fields for backward compatibility
        user.native_language = self.cleaned_data['native_language'].name
        user.target_language = self.cleaned_data['target_language'].name
        user.proficiency = self.cleaned_data['target_proficiency']

        if commit:
            # All or nothing: never leave an account without its languages.
            with transaction.atomic():
                user.save()
                UserLanguage.objects.create(
                    user=user,
                    language=self.cleaned_data['native_language'],
                    proficiency='native',
                    language_type='native'
                )
                UserLanguage.objects.create(
                    user=user,
                    language=self.cleaned_data['target_language'],
                    proficiency=self.cleaned_data['target_proficiency'],
                    language_type='learning'
                )

        return user

class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'share_email_with_matches', 'bio', 'profile_picture', 'interests']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'interests': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('That email is already used by another account.')
        return email

    MAX_BIO = 1000
    MAX_INTERESTS = 500
    MAX_PICTURE_BYTES = 5 * 1024 * 1024

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '')
        if len(bio) > self.MAX_BIO:
            raise forms.ValidationError(f'Keep your bio under {self.MAX_BIO} characters.')
        return bio

    def clean_interests(self):
        text = self.cleaned_data.get('interests', '')
        if len(text) > self.MAX_INTERESTS:
            raise forms.ValidationError(f'Keep interests under {self.MAX_INTERESTS} characters.')
        return text

    def clean_profile_picture(self):
        pic = self.cleaned_data.get('profile_picture')
        size = getattr(pic, 'size', None)
        if pic and hasattr(pic, 'content_type') and size and size > self.MAX_PICTURE_BYTES:
            raise forms.ValidationError('Pick a picture under 5 MB.')
        return pic

    def save(self, commit=True):
        old_picture = None
        if 'profile_picture' in self.changed_data:
            old_picture = User.objects.filter(pk=self.instance.pk).values_list(
                'profile_picture', flat=True).first()
        user = super().save(commit=False)
        # A changed address is unverified until the new one is confirmed.
        if 'email' in self.changed_data:
            user.email_verified = False
        if commit:
            user.save()
            if old_picture and old_picture != (user.profile_picture.name or ''):
                # The replaced (or cleared) picture is no longer referenced.
                user.profile_picture.storage.delete(old_picture)
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
            else:
                field.widget.attrs['class'] = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'

class UserLanguageForm(forms.ModelForm):
    """Form for adding/editing user languages."""
    
    language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        empty_label="Select a language",
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    class Meta:
        model = UserLanguage
        fields = ['language', 'proficiency', 'language_type']
        widgets = {
            'proficiency': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
            'language_type': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Exclude languages the user already has
        if self.user:
            existing_languages = self.user.languages.all()
            if self.instance.pk:
                # If editing, exclude other languages but include current one
                existing_languages = existing_languages.exclude(pk=self.instance.language.pk)
            self.fields['language'].queryset = Language.objects.exclude(
                pk__in=existing_languages.values_list('pk', flat=True)
            )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.user = self.user
        if commit:
            instance.save()
        return instance 