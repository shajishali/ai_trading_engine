"""
Email Verification Service
Handles email verification logic for user signup
"""
import logging
import re
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ValidationError
from datetime import timedelta
from .models import EmailVerificationToken, UserProfile

logger = logging.getLogger(__name__)


class EmailVerificationService:
    """Service class to handle email verification operations"""
    
    # Token expiration time (24 hours)
    TOKEN_EXPIRY_HOURS = getattr(settings, 'EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS', 24)
    
    # Rate limiting settings
    RESEND_COOLDOWN_MINUTES = getattr(settings, 'EMAIL_VERIFICATION_RESEND_COOLDOWN_MINUTES', 5)
    MAX_RESEND_ATTEMPTS = getattr(settings, 'EMAIL_VERIFICATION_MAX_ATTEMPTS', 3)
    
    # Email validation regex
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    def __init__(self):
        self.site = Site.objects.get_current()
    
    def _get_rate_limit_key(self, user_id, action='send_email'):
        """Generate cache key for rate limiting"""
        return f'email_verification:{action}:{user_id}'
    
    def _check_rate_limit(self, user_id, action='send_email'):
        """
        Check if user has exceeded rate limit
        
        Returns:
            tuple: (allowed, message)
        """
        cache_key = self._get_rate_limit_key(user_id, action)
        attempts = cache.get(cache_key, 0)
        
        if attempts >= self.MAX_RESEND_ATTEMPTS:
            remaining_time = cache.ttl(cache_key)
            if remaining_time > 0:
                minutes = remaining_time // 60
                return False, f'Too many requests. Please wait {minutes} minutes before requesting another verification email.'
            else:
                # Reset if expired
                cache.delete(cache_key)
        
        return True, None
    
    def _increment_rate_limit(self, user_id, action='send_email'):
        """Increment rate limit counter"""
        cache_key = self._get_rate_limit_key(user_id, action)
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, self.RESEND_COOLDOWN_MINUTES * 60)
        return attempts
    
    def _validate_email(self, email):
        """
        Validate email address format and security
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If email is invalid
        """
        if not email:
            raise ValidationError('Email address is required.')
        
        # Normalize email
        email = email.lower().strip()
        
        # Check format
        if not self.EMAIL_REGEX.match(email):
            raise ValidationError('Invalid email address format.')
        
        # Check for email injection attempts
        dangerous_chars = ['\r', '\n', '\0', '\x00']
        for char in dangerous_chars:
            if char in email:
                raise ValidationError('Invalid email address.')
        
        # Check length
        if len(email) > 254:  # RFC 5321 limit
            raise ValidationError('Email address is too long.')
        
        return email
    
    def generate_verification_token(self, user, email):
        """
        Generate a new verification token for a user
        
        Args:
            user: User instance
            email: Email address to verify
            
        Returns:
            EmailVerificationToken instance
        """
        # Invalidate any existing unused tokens for this user
        EmailVerificationToken.objects.filter(
            user=user,
            email=email,
            is_used=False
        ).update(is_used=True)
        
        # Generate new token
        token = EmailVerificationToken.generate_token()
        expires_at = timezone.now() + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        
        verification_token = EmailVerificationToken.objects.create(
            user=user,
            token=token,
            email=email,
            expires_at=expires_at
        )
        
        logger.info(
            "Generated verification token",
            extra={
                'user_id': user.id,
                'username': user.username,
                'email_domain': email.split('@')[1] if '@' in email else 'unknown',
                'action': 'token_generated'
            }
        )
        return verification_token
    
    def send_verification_email(self, user):
        """
        Send verification email to user with rate limiting
        
        Args:
            user: User instance
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            if not user.email:
                logger.error(
                    "User has no email address",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'action': 'verification_email_no_email'
                    }
                )
                return False
            
            # Validate email
            try:
                validated_email = self._validate_email(user.email)
            except ValidationError as e:
                logger.error(
                    "Invalid email address",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'error': str(e),
                        'action': 'verification_email_invalid'
                    }
                )
                return False
            
            # Check rate limit
            allowed, message = self._check_rate_limit(user.id, 'send_email')
            if not allowed:
                logger.warning(
                    "Rate limit exceeded for email sending",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'action': 'verification_email_rate_limited'
                    }
                )
                return False
            
            # Generate verification token
            verification_token = self.generate_verification_token(user, validated_email)
            
            # Build verification URL
            verification_url = self._build_verification_url(verification_token.token)
            
            # Prepare email context
            context = {
                'user': user,
                'verification_url': verification_url,
                'token': verification_token.token,
                'expires_at': verification_token.expires_at,
                'site_name': self.site.name,
                'site_domain': self.site.domain,
            }
            
            # Render email templates
            subject = f'Verify your email address for {self.site.name}'
            html_message = render_to_string(
                'subscription/emails/verification_email.html',
                context
            )
            plain_message = render_to_string(
                'subscription/emails/verification_email.txt',
                context
            )
            
            # Send email with security headers
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[validated_email],  # Use validated email
                html_message=html_message,
                fail_silently=False,
            )
            
            # Increment rate limit counter
            self._increment_rate_limit(user.id, 'send_email')
            
            # Log successful email send (without sensitive data)
            logger.info(
                f"Verification email sent successfully",
                extra={
                    'user_id': user.id,
                    'username': user.username,
                    'email_domain': validated_email.split('@')[1] if '@' in validated_email else 'unknown',
                    'action': 'verification_email_sent'
                }
            )
            return True
            
        except Exception as e:
            # Log error without exposing sensitive information
            logger.error(
                f"Error sending verification email",
                extra={
                    'user_id': user.id,
                    'username': user.username,
                    'error': str(e),
                    'action': 'verification_email_failed'
                },
                exc_info=True
            )
            return False
    
    def verify_email_token(self, token):
        """
        Verify an email token and activate the user account
        
        Args:
            token: Verification token string
            
        Returns:
            dict: {
                'success': bool,
                'user': User instance or None,
                'message': str
            }
        """
        try:
            # Validate token format (basic check)
            if not token or len(token) < 20:
                logger.warning(
                    "Invalid token format attempted",
                    extra={'action': 'token_verification_failed', 'reason': 'invalid_format'}
                )
                return {
                    'success': False,
                    'user': None,
                    'message': 'Invalid verification token.'
                }
            
            # Look up token
            verification_token = EmailVerificationToken.objects.filter(
                token=token
            ).first()
            
            if not verification_token:
                logger.warning(
                    "Token not found",
                    extra={'action': 'token_verification_failed', 'reason': 'token_not_found'}
                )
                return {
                    'success': False,
                    'user': None,
                    'message': 'Invalid verification token.'
                }
            
            # Check if token is valid
            if not verification_token.is_valid():
                if verification_token.is_used:
                    logger.warning(
                        "Token already used",
                        extra={
                            'user_id': verification_token.user.id,
                            'action': 'token_verification_failed',
                            'reason': 'already_used'
                        }
                    )
                    return {
                        'success': False,
                        'user': None,
                        'message': 'This verification link has already been used.'
                    }
                else:
                    logger.warning(
                        "Token expired",
                        extra={
                            'user_id': verification_token.user.id,
                            'action': 'token_verification_failed',
                            'reason': 'expired'
                        }
                    )
                    return {
                        'success': False,
                        'user': None,
                        'message': 'This verification link has expired. Please request a new one.'
                    }
            
            # Verify email matches
            user = verification_token.user
            if user.email != verification_token.email:
                return {
                    'success': False,
                    'user': None,
                    'message': 'Email address mismatch.'
                }
            
            # Activate user account
            user.is_active = True
            user.save()
            
            # Mark token as used
            verification_token.mark_as_used()
            
            # Update user profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.email_verified = True
            profile.save()
            
            # Log successful verification (without sensitive data)
            logger.info(
                "Email verified successfully",
                extra={
                    'user_id': user.id,
                    'username': user.username,
                    'email_domain': user.email.split('@')[1] if '@' in user.email else 'unknown',
                    'action': 'email_verified_success'
                }
            )
            
            return {
                'success': True,
                'user': user,
                'message': 'Email verified successfully! Your account has been activated.'
            }
            
        except Exception as e:
            # Log error without exposing sensitive information
            logger.error(
                "Error verifying email token",
                extra={
                    'error': str(e),
                    'action': 'token_verification_error'
                },
                exc_info=True
            )
            return {
                'success': False,
                'user': None,
                'message': 'An error occurred during verification. Please try again.'
            }
    
    def resend_verification_email(self, user):
        """
        Resend verification email to user with enhanced rate limiting
        
        Args:
            user: User instance
            
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            # Check if user is already verified
            profile, created = UserProfile.objects.get_or_create(user=user)
            if profile.email_verified and user.is_active:
                logger.info(
                    "Resend requested for already verified user",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'action': 'resend_verification_already_verified'
                    }
                )
                return {
                    'success': False,
                    'message': 'Your email is already verified.'
                }
            
            # Check rate limiting using cache (more efficient)
            allowed, message = self._check_rate_limit(user.id, 'resend_email')
            if not allowed:
                logger.warning(
                    "Rate limit exceeded for resend",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'action': 'resend_verification_rate_limited'
                    }
                )
                return {
                    'success': False,
                    'message': message
                }
            
            # Send verification email
            email_sent = self.send_verification_email(user)
            
            if email_sent:
                # Increment resend rate limit
                self._increment_rate_limit(user.id, 'resend_email')
                
                logger.info(
                    "Verification email resent",
                    extra={
                        'user_id': user.id,
                        'username': user.username,
                        'action': 'verification_email_resent'
                    }
                )
                return {
                    'success': True,
                    'message': 'Verification email has been sent. Please check your inbox.'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to send verification email. Please try again later.'
                }
                
        except Exception as e:
            logger.error(
                "Error resending verification email",
                extra={
                    'user_id': user.id if hasattr(user, 'id') else None,
                    'error': str(e),
                    'action': 'resend_verification_error'
                },
                exc_info=True
            )
            return {
                'success': False,
                'message': 'An error occurred. Please try again later.'
            }
    
    def _build_verification_url(self, token):
        """
        Build the verification URL with security considerations
        
        Args:
            token: Verification token string
            
        Returns:
            str: Full verification URL
        """
        # Priority: 1. SITE_DOMAIN setting, 2. Site model domain, 3. ALLOWED_HOSTS first entry
        domain = getattr(settings, 'SITE_DOMAIN', None)
        
        if not domain:
            domain = self.site.domain
        
        # Ensure domain doesn't contain protocol (security)
        domain = domain.replace('http://', '').replace('https://', '').split('/')[0]
        
        # If domain is an IP address, try to get domain name from settings
        import re
        ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        if ip_pattern.match(domain):
            # Domain is an IP, try to get domain name from settings
            domain_override = getattr(settings, 'EMAIL_DOMAIN', None)
            if domain_override:
                domain = domain_override
            else:
                # Try to get from ALLOWED_HOSTS (prefer domain over IP)
                allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
                for host in allowed_hosts:
                    if not ip_pattern.match(host) and '.' in host and not host.startswith('*'):
                        domain = host
                        break
        
        # Check if we should force HTTPS (production setting)
        force_https = getattr(settings, 'FORCE_HTTPS_IN_EMAILS', None)
        if force_https is None:
            # Auto-detect: Use HTTPS if SECURE_SSL_REDIRECT is enabled (production indicator)
            # But allow override via USE_HTTP_IN_PRODUCTION setting
            use_http_in_production = getattr(settings, 'USE_HTTP_IN_PRODUCTION', False)
            if use_http_in_production:
                force_https = False
            else:
                force_https = getattr(settings, 'SECURE_SSL_REDIRECT', False)
        
        # Check if domain is localhost/private IP (development only)
        is_localhost = (
            'localhost' in domain.lower() or 
            '127.0.0.1' in domain or 
            domain.startswith('192.168.') or
            domain.startswith('10.') or
            domain.startswith('172.')
        )
        
        # Determine protocol:
        # - Use HTTPS if explicitly forced (and not using HTTP in production)
        # - Use HTTP for localhost or if USE_HTTP_IN_PRODUCTION is True
        # - Use HTTPS for production domains (not localhost/IP)
        if is_localhost or getattr(settings, 'USE_HTTP_IN_PRODUCTION', False):
            protocol = 'http'
        elif force_https or (not is_localhost and not ip_pattern.match(domain)):
            # Use HTTPS for production domains (non-IP, non-localhost)
            protocol = 'https'
        else:
            protocol = 'http'
        
        return f"{protocol}://{domain}/subscription/verify-email/{token}/"

