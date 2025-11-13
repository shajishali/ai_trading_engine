# Google Sign-In Implementation Plan

## Overview
This document outlines a comprehensive plan to implement Google OAuth sign-in functionality for the AI Trading Engine. Users will be able to sign up and log in using their Google accounts, with automatic email verification for social accounts.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Implementation Phases](#implementation-phases)
4. [Configuration](#configuration)
5. [Testing Plan](#testing-plan)
6. [Security Considerations](#security-considerations)

---

## Prerequisites

### Required Packages
- ✅ django-allauth (already installed)
- ✅ allauth.socialaccount (already installed)
- ✅ allauth.socialaccount.providers.google (already installed)

### Google Cloud Console Setup
1. **Google Cloud Project**
   - Create or select a Google Cloud Project
   - Enable Google+ API (if required)
   - Enable Google Identity API

2. **OAuth 2.0 Credentials**
   - Create OAuth 2.0 Client ID
   - Configure authorized redirect URIs
   - Get Client ID and Client Secret

3. **Consent Screen**
   - Configure OAuth consent screen
   - Set application name, logo, support email
   - Add scopes (email, profile)

---

## Architecture Overview

### Flow Diagram
```
User Clicks "Sign in with Google" → Google OAuth → Callback → Create/Login User → Redirect to Dashboard
     ↓                    ↓              ↓              ↓                    ↓
  Signup Page      Google Login    OAuth Callback   User Created      Subscription Choice
```

### Components
1. **Backend Components**
   - Google OAuth configuration
   - Social account adapter (custom)
   - User creation/login logic
   - Email verification handling for social accounts
   - Profile synchronization

2. **Frontend Components**
   - Updated signup page with Google button
   - OAuth callback handling
   - Error handling pages

3. **Database Changes**
   - SocialAccount model (already exists via allauth)
   - UserProfile updates for social accounts

---

## Implementation Phases

### Phase 1: Google Cloud Console Setup

#### Step 1.1: Create Google Cloud Project
**Action:** Set up Google Cloud Project

**Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable required APIs:
   - Google+ API (if needed)
   - Google Identity API

**Note:** Keep the project ID for later use

---

#### Step 1.2: Configure OAuth Consent Screen
**Action:** Set up OAuth consent screen

**Steps:**
1. Navigate to "APIs & Services" → "OAuth consent screen"
2. Choose User Type (External for public app)
3. Fill in required information:
   - App name: "AI Trading Engine"
   - User support email: Your email
   - Developer contact: Your email
4. Add scopes:
   - `email`
   - `profile`
   - `openid`
5. Add test users (for development)
6. Save and continue

---

#### Step 1.3: Create OAuth 2.0 Credentials
**Action:** Generate Client ID and Secret

**Steps:**
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Web application"
4. Configure:
   - Name: "AI Trading Engine Web Client"
   - Authorized JavaScript origins:
     - `http://localhost:8000` (development)
     - `https://yourdomain.com` (production)
   - Authorized redirect URIs:
     - `http://localhost:8000/accounts/google/login/callback/` (development)
     - `https://yourdomain.com/accounts/google/login/callback/` (production)
5. Click "Create"
6. **Copy Client ID and Client Secret** (save securely)

---

### Phase 2: Backend Configuration

#### Step 2.1: Configure Google OAuth Settings
**File:** `backend/ai_trading_engine/settings.py`

**Action:** Update SOCIALACCOUNT_PROVIDERS configuration

**Current Configuration:**
```python
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    },
}
```

**Updated Configuration:**
```python
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
            'openid',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': config('GOOGLE_OAUTH2_CLIENT_ID', default=''),
            'secret': config('GOOGLE_OAUTH2_CLIENT_SECRET', default=''),
            'key': ''
        },
        'OAUTH_PKCE_ENABLED': True,  # Enhanced security
    },
}
```

---

#### Step 2.2: Add Environment Variables
**File:** `backend/.env` or `backend/env.local`

**Action:** Add Google OAuth credentials

**Variables to Add:**
```bash
# Google OAuth Configuration
GOOGLE_OAUTH2_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
```

---

#### Step 2.3: Configure AllAuth Settings for Social Accounts
**File:** `backend/ai_trading_engine/settings.py`

**Action:** Update AllAuth settings for social login

**Settings to Add/Update:**
```python
# Social Account Settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'  # Google emails are pre-verified
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = False  # Don't store OAuth tokens (security)

# Account adapter settings
ACCOUNT_ADAPTER = 'apps.subscription.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.subscription.adapters.CustomSocialAccountAdapter'
```

---

#### Step 2.4: Create Custom Social Account Adapter
**File:** `backend/apps/subscription/adapters.py` (new file)

**Action:** Create custom adapters to handle social account flow

**Key Functions:**
- `pre_social_login()` - Handle before social login
- `save_user()` - Customize user creation
- `populate_user()` - Populate user data from Google
- Handle email verification for social accounts
- Create UserProfile automatically

**Implementation:**
- Auto-verify email for Google accounts (Google emails are verified)
- Create UserProfile on social signup
- Sync profile picture from Google
- Handle existing users linking Google account

---

#### Step 2.5: Update Social Signup Callback View
**File:** `backend/apps/subscription/views.py`

**Action:** Enhance `social_signup_callback()` view

**Enhancements:**
- Better error handling
- Profile picture sync
- Email verification status (auto-verified for Google)
- Redirect logic improvements
- Logging for social signups

---

### Phase 3: Frontend Updates

#### Step 3.1: Update Signup Page
**File:** `frontend/templates/subscription/signup.html`

**Action:** Replace placeholder Google button with actual OAuth link

**Changes:**
- Remove "Coming Soon" text
- Add proper Google OAuth URL
- Update button styling
- Add loading state
- Add error handling

**Google OAuth URL:**
```django
<a href="{% url 'google_login' %}" class="btn-social btn-google">
    <i class="fab fa-google" style="color: #ea4335;"></i>
    Continue with Google
</a>
```

---

#### Step 3.2: Create Social Login Success Page
**File:** `frontend/templates/subscription/social_login_success.html` (new file)

**Action:** Create page shown after successful Google login

**Content:**
- Welcome message
- Account created/logged in confirmation
- Auto-redirect to subscription choice
- Profile information display

---

#### Step 3.3: Create Social Login Error Page
**File:** `frontend/templates/subscription/social_login_error.html` (new file)

**Action:** Handle OAuth errors

**Error Cases:**
- OAuth denied by user
- OAuth error
- Account linking errors
- Email already exists

---

#### Step 3.4: Update Login Page
**File:** `frontend/templates/dashboard/login.html`

**Action:** Add Google sign-in option to login page

**Changes:**
- Add Google button
- Style consistently with signup page
- Handle both traditional and social login

---

### Phase 4: Email Verification for Social Accounts

#### Step 4.1: Auto-Verify Google Emails
**Action:** Automatically verify emails from Google accounts

**Rationale:**
- Google emails are already verified by Google
- No need for additional email verification
- Better user experience

**Implementation:**
- In CustomSocialAccountAdapter, set `email_verified = True`
- Set `user.is_active = True` for Google accounts
- Skip email verification flow for social accounts

---

#### Step 4.2: Handle Email Conflicts
**Action:** Handle cases where Google email already exists

**Scenarios:**
1. Google email matches existing account → Link accounts
2. Google email is different → Create new account
3. User wants to link Google to existing account → Provide option

**Implementation:**
- Check for existing email in `pre_social_login()`
- Offer account linking
- Handle conflicts gracefully

---

### Phase 5: Profile Synchronization

#### Step 5.1: Sync Profile Data from Google
**Action:** Automatically sync user data from Google

**Data to Sync:**
- Profile picture
- First name
- Last name
- Email (already synced)
- Locale/language preferences

**Implementation:**
- In `populate_user()` method
- Update UserProfile with Google data
- Store profile picture URL

---

#### Step 5.2: Update UserProfile Model
**File:** `backend/apps/subscription/models.py`

**Action:** Ensure UserProfile supports social account data

**Fields Already Present:**
- `social_provider` ✅
- `social_id` ✅
- `profile_picture` ✅
- `email_verified` ✅

**No changes needed** - Model already supports social accounts

---

### Phase 6: URL Configuration

#### Step 6.1: Verify AllAuth URLs
**File:** `backend/ai_trading_engine/urls.py`

**Action:** Ensure allauth URLs are included

**Current Status:**
```python
path('accounts/', include('allauth.urls')),
```

**Verification:**
- ✅ AllAuth URLs already included
- Google login URL: `/accounts/google/login/`
- Google callback: `/accounts/google/login/callback/`

**No changes needed** - URLs already configured

---

#### Step 6.2: Add Custom Social URLs (if needed)
**File:** `backend/apps/subscription/urls.py`

**Action:** Add custom social account URLs

**URLs to Add:**
```python
path('social/callback/', views.social_signup_callback, name='social_callback'),
path('social/error/', views.social_login_error, name='social_error'),
```

---

### Phase 7: Testing and Error Handling

#### Step 7.1: Test Google OAuth Flow
**Test Cases:**
1. New user signs up with Google
2. Existing user logs in with Google
3. User with existing email links Google account
4. OAuth denied by user
5. OAuth error handling
6. Profile data synchronization

---

#### Step 7.2: Error Handling
**Error Scenarios:**
- OAuth denied
- OAuth errors
- Email conflicts
- Network errors
- Invalid credentials

**Implementation:**
- Try-except blocks in adapters
- User-friendly error messages
- Logging for debugging
- Fallback to traditional signup

---

## Configuration

### Environment Variables

**Development (.env):**
```bash
# Google OAuth Configuration
GOOGLE_OAUTH2_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
```

**Production:**
```bash
GOOGLE_OAUTH2_CLIENT_ID=your-production-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-production-client-secret
```

---

### Settings Configuration

**Required Settings:**
```python
# Social Account Settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = False

# Custom Adapters
ACCOUNT_ADAPTER = 'apps.subscription.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.subscription.adapters.CustomSocialAccountAdapter'
```

---

## Testing Plan

### Unit Tests
**File:** `backend/apps/subscription/tests.py`

**Test Cases:**
1. Google OAuth configuration
2. Custom adapter methods
3. User creation from social account
4. Profile synchronization
5. Email verification for social accounts
6. Account linking

### Integration Tests
**Test Cases:**
1. Complete Google signup flow
2. Google login flow
3. Account linking
4. Error handling
5. Profile data sync

### Manual Testing Checklist
- [ ] Click "Sign in with Google" button
- [ ] Complete Google OAuth flow
- [ ] Account created successfully
- [ ] Profile data synced
- [ ] Email auto-verified
- [ ] Redirect to subscription choice
- [ ] Login with Google works
- [ ] Link Google to existing account
- [ ] Handle OAuth denial
- [ ] Handle OAuth errors

---

## Security Considerations

### Best Practices
1. **OAuth Tokens** - Don't store OAuth tokens (set `SOCIALACCOUNT_STORE_TOKENS = False`)
2. **HTTPS Only** - Use HTTPS in production for OAuth callbacks
3. **Client Secret** - Store in environment variables, never in code
4. **Redirect URIs** - Whitelist only authorized domains
5. **Email Verification** - Auto-verify Google emails (already verified by Google)
6. **Account Linking** - Secure account linking process
7. **CSRF Protection** - AllAuth handles CSRF automatically

### Potential Vulnerabilities
1. **OAuth Token Theft** - Mitigated by not storing tokens
2. **Account Hijacking** - Mitigated by secure OAuth flow
3. **Email Spoofing** - Mitigated by Google's verification
4. **CSRF Attacks** - Mitigated by AllAuth's CSRF protection

---

## Implementation Checklist

### Phase 1: Google Cloud Setup
- [ ] Create Google Cloud Project
- [ ] Configure OAuth consent screen
- [ ] Create OAuth 2.0 credentials
- [ ] Get Client ID and Secret
- [ ] Configure redirect URIs

### Phase 2: Backend Configuration
- [ ] Update SOCIALACCOUNT_PROVIDERS settings
- [ ] Add environment variables
- [ ] Configure AllAuth settings
- [ ] Create CustomSocialAccountAdapter
- [ ] Create CustomAccountAdapter
- [ ] Update social_signup_callback view

### Phase 3: Frontend Updates
- [ ] Update signup.html with Google button
- [ ] Create social_login_success.html
- [ ] Create social_login_error.html
- [ ] Update login.html with Google button
- [ ] Add loading states
- [ ] Add error handling

### Phase 4: Email Verification
- [ ] Auto-verify Google emails
- [ ] Handle email conflicts
- [ ] Implement account linking

### Phase 5: Profile Synchronization
- [ ] Sync profile picture
- [ ] Sync name fields
- [ ] Update UserProfile on login

### Phase 6: URL Configuration
- [ ] Verify AllAuth URLs
- [ ] Add custom social URLs (if needed)

### Phase 7: Testing
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Manual testing
- [ ] Error scenario testing

---

## Deployment Steps

### Pre-Deployment
1. Create production OAuth credentials
2. Update redirect URIs for production domain
3. Test OAuth flow in staging
4. Verify environment variables

### Deployment
1. Set production OAuth credentials
2. Update Site domain
3. Restart application
4. Test Google sign-in

### Post-Deployment
1. Monitor OAuth success rates
2. Check error logs
3. Verify profile synchronization
4. Test account linking

---

## Troubleshooting

### Common Issues

#### Issue: "Redirect URI mismatch"
**Solution:**
- Check authorized redirect URIs in Google Console
- Ensure exact match: `http://localhost:8000/accounts/google/login/callback/`
- Check for trailing slashes

#### Issue: "Invalid client"
**Solution:**
- Verify Client ID and Secret in environment variables
- Check for typos
- Ensure credentials match the project

#### Issue: "Access blocked"
**Solution:**
- Check OAuth consent screen configuration
- Verify test users are added (for development)
- Check app verification status

#### Issue: Email not syncing
**Solution:**
- Verify scopes include 'email'
- Check SOCIALACCOUNT_QUERY_EMAIL setting
- Verify Google account has email

---

## Future Enhancements

### Potential Improvements
1. **Facebook Sign-In** - Add Facebook OAuth (already configured)
2. **Account Linking** - Allow linking multiple social accounts
3. **Profile Picture Upload** - Allow custom profile pictures
4. **Social Account Management** - Let users manage linked accounts
5. **Two-Factor Authentication** - Add 2FA for social accounts
6. **Social Sharing** - Share trading signals on social media

---

## References

### Documentation
- [Django AllAuth Documentation](https://django-allauth.readthedocs.io/)
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)

### AllAuth Social Providers
- [AllAuth Google Provider](https://django-allauth.readthedocs.io/en/latest/providers.html#google)

---

## Notes

- Google emails are automatically verified (no need for email verification flow)
- OAuth tokens are not stored for security (SOCIALACCOUNT_STORE_TOKENS = False)
- Profile data is synced on each login to keep it up to date
- Account linking allows users to connect Google to existing accounts

---

**Last Updated:** [Current Date]
**Version:** 1.0
**Status:** Planning Phase

