from django.db import transaction
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Language, UserLanguage

class UserRegistrationForm(UserCreationForm):
    """Extended user registration form with additional fields."""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=False)
    
    # Updated to use Language model
    native_language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        empty_label="Select your native language",
        required=True,
        help_text="Your native/mother tongue language",
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    target_language = forms.ModelChoiceField(
        queryset=Language.objects.all(),
        empty_label="Select language you want to learn",
        required=True,
        help_text="Language you want to learn or practice",
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    target_proficiency = forms.ChoiceField(
        choices=UserLanguage.PROFICIENCY_CHOICES,
        required=True,
        help_text="Your current level in the target language",
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'native_language', 'target_language', 'target_proficiency', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling to other fields
        for field_name, field in self.fields.items():
            if field_name not in ['native_language', 'target_language', 'target_proficiency']:
                field.widget.attrs['class'] = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'
        
        # Add autofocus to first_name field
        self.fields['first_name'].widget.attrs['autofocus'] = True
    
    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('That email already has an account. Sign in, or reset your password.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        native_language = cleaned_data.get('native_language')
        target_language = cleaned_data.get('target_language')
        
        # Ensure native and target languages are different
        if native_language and target_language and native_language == target_language:
            raise forms.ValidationError("Native language and target language cannot be the same.")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
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
        fields = ['first_name', 'last_name', 'email', 'share_email_with_matches', 'timezone', 'bio', 'profile_picture', 'interests']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'interests': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_timezone(self):
        from zoneinfo import available_timezones
        tz = (self.cleaned_data.get('timezone') or '').strip()
        if tz and tz not in available_timezones():
            raise forms.ValidationError('Pick a time zone from the list.')
        return tz

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
        from zoneinfo import available_timezones
        zones = sorted(z for z in available_timezones() if '/' in z and not z.startswith(('Etc/', 'posix/', 'right/')))
        self.fields['timezone'] = forms.ChoiceField(
            required=False, label='Time zone',
            choices=[('', 'Not set')] + [(z, z.replace('_', ' ')) for z in zones],
            help_text=self.fields['timezone'].help_text)
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