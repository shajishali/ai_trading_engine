"""
Management command to verify Google OAuth configuration
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Verify Google OAuth configuration'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Verifying Google OAuth Configuration...\n'))
        
        # Check environment variables
        client_id = getattr(settings, 'GOOGLE_OAUTH2_CLIENT_ID', None)
        client_secret = getattr(settings, 'GOOGLE_OAUTH2_CLIENT_SECRET', None)
        
        # Check if using config from environment
        if not client_id:
            try:
                from decouple import config
                client_id = config('GOOGLE_OAUTH2_CLIENT_ID', default='')
                client_secret = config('GOOGLE_OAUTH2_CLIENT_SECRET', default='')
            except:
                pass
        
        # Verify Client ID
        if client_id:
            if client_id.endswith('.apps.googleusercontent.com'):
                self.stdout.write(self.style.SUCCESS(f'✓ Client ID: {client_id[:20]}...{client_id[-20:]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Client ID format may be incorrect: {client_id[:30]}...'))
        else:
            self.stdout.write(self.style.ERROR('✗ Client ID not found'))
            self.stdout.write(self.style.WARNING('  Add GOOGLE_OAUTH2_CLIENT_ID to your .env file'))
        
        # Verify Client Secret
        if client_secret:
            if client_secret.startswith('GOCSPX-'):
                self.stdout.write(self.style.SUCCESS(f'✓ Client Secret: {client_secret[:10]}...{client_secret[-5:]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Client Secret format may be incorrect'))
        else:
            self.stdout.write(self.style.ERROR('✗ Client Secret not found'))
            self.stdout.write(self.style.WARNING('  Add GOOGLE_OAUTH2_CLIENT_SECRET to your .env file'))
        
        # Check AllAuth settings
        self.stdout.write('\n' + self.style.SUCCESS('Checking AllAuth Configuration...\n'))
        
        # Check if allauth is installed
        if 'allauth' in settings.INSTALLED_APPS:
            self.stdout.write(self.style.SUCCESS('✓ django-allauth is installed'))
        else:
            self.stdout.write(self.style.ERROR('✗ django-allauth is not installed'))
        
        if 'allauth.socialaccount' in settings.INSTALLED_APPS:
            self.stdout.write(self.style.SUCCESS('✓ allauth.socialaccount is installed'))
        else:
            self.stdout.write(self.style.ERROR('✗ allauth.socialaccount is not installed'))
        
        if 'allauth.socialaccount.providers.google' in settings.INSTALLED_APPS:
            self.stdout.write(self.style.SUCCESS('✓ Google provider is installed'))
        else:
            self.stdout.write(self.style.ERROR('✗ Google provider is not installed'))
        
        # Check SOCIALACCOUNT_PROVIDERS
        social_providers = getattr(settings, 'SOCIALACCOUNT_PROVIDERS', {})
        if 'google' in social_providers:
            self.stdout.write(self.style.SUCCESS('✓ Google provider is configured'))
            google_config = social_providers['google']
            if 'APP' in google_config:
                app_config = google_config['APP']
                if app_config.get('client_id'):
                    self.stdout.write(self.style.SUCCESS('  ✓ Client ID in provider config'))
                else:
                    self.stdout.write(self.style.WARNING('  ⚠ Client ID not in provider config (will use env var)'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Google provider not in SOCIALACCOUNT_PROVIDERS'))
        
        # Check Site configuration
        self.stdout.write('\n' + self.style.SUCCESS('Checking Site Configuration...\n'))
        try:
            site = Site.objects.get(id=settings.SITE_ID)
            self.stdout.write(self.style.SUCCESS(f'✓ Site domain: {site.domain}'))
            self.stdout.write(self.style.SUCCESS(f'✓ Site name: {site.name}'))
            
            # Check redirect URI
            if 'localhost' in site.domain or '127.0.0.1' in site.domain:
                redirect_uri = f'http://{site.domain}/accounts/google/login/callback/'
                self.stdout.write(self.style.SUCCESS(f'\n✓ Redirect URI for Google Console:'))
                self.stdout.write(self.style.SUCCESS(f'  {redirect_uri}'))
            else:
                redirect_uri_http = f'http://{site.domain}/accounts/google/login/callback/'
                redirect_uri_https = f'https://{site.domain}/accounts/google/login/callback/'
                self.stdout.write(self.style.SUCCESS(f'\n✓ Redirect URIs for Google Console:'))
                self.stdout.write(self.style.SUCCESS(f'  {redirect_uri_http}'))
                self.stdout.write(self.style.SUCCESS(f'  {redirect_uri_https}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Site configuration error: {str(e)}'))
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        if client_id and client_secret:
            self.stdout.write(self.style.SUCCESS('✓ Google OAuth configuration looks good!'))
            self.stdout.write(self.style.SUCCESS('\nNext steps:'))
            self.stdout.write('  1. Ensure redirect URI is added to Google Console')
            self.stdout.write('  2. Test the OAuth flow')
            self.stdout.write('  3. Proceed to Phase 2: Backend Configuration')
        else:
            self.stdout.write(self.style.WARNING('⚠ Google OAuth not fully configured'))
            self.stdout.write(self.style.WARNING('\nPlease:'))
            self.stdout.write('  1. Follow GOOGLE_OAUTH_SETUP_GUIDE.md')
            self.stdout.write('  2. Add credentials to .env file')
            self.stdout.write('  3. Run this command again to verify')
        self.stdout.write('=' * 60)

