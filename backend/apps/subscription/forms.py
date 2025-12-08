"""
Custom forms for subscription app
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re


class CustomSignupForm(UserCreationForm):
    """Custom signup form with email field"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        }),
        help_text='Required. We will send a verification email to this address.'
    )
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'autocomplete': 'username'
        }),
        help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password',
            'autocomplete': 'new-password'
        }),
        help_text='Your password must contain at least 8 characters.'
    )
    
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        }),
        help_text='Enter the same password as before, for verification.'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set required fields
        self.fields['email'].required = True
        self.fields['username'].required = True
    
    def clean_email(self):
        """Validate email address"""
        email = self.cleaned_data.get('email')
        
        if not email:
            raise ValidationError('Email address is required.')
        
        # Check email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise ValidationError('Please enter a valid email address.')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise ValidationError(
                'This email address is already registered. '
                'Please use a different email or try logging in.'
            )
        
        return email.lower()  # Normalize email to lowercase
    
    def clean_username(self):
        """Validate username"""
        username = self.cleaned_data.get('username')
        
        if not username:
            raise ValidationError('Username is required.')
        
        # Check username format
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores.'
            )
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken. Please choose another.')
        
        return username
    
    def clean_password1(self):
        """Validate password strength"""
        password1 = self.cleaned_data.get('password1')
        
        if not password1:
            raise ValidationError('Password is required.')
        
        # Check minimum length
        if len(password1) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        
        # Check for at least one letter and one number
        if not re.search(r'[A-Za-z]', password1):
            raise ValidationError('Password must contain at least one letter.')
        
        if not re.search(r'[0-9]', password1):
            raise ValidationError('Password must contain at least one number.')
        
        return password1
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError({
                'password2': 'Passwords do not match. Please try again.'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save user with email"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False  # Inactive until email is verified
        
        if commit:
            user.save()
        
        return user

