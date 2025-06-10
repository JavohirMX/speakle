from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Language, UserLanguage

class UserRegistrationForm(UserCreationForm):
    """Extended user registration form with additional fields."""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
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
            user.save()
            
            # Create UserLanguage entries for the new system
            # Add native language
            UserLanguage.objects.create(
                user=user,
                language=self.cleaned_data['native_language'],
                proficiency='native',
                language_type='native'
            )
            
            # Add target language
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
        fields = ['first_name', 'last_name', 'email', 'bio', 'profile_picture', 'interests']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'interests': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
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