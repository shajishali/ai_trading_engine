"""
Management command to manually verify a user's email address
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.subscription.models import UserProfile


class Command(BaseCommand):
    help = 'Manually verify a user\'s email address (admin only)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address of the user to verify',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username of the user to verify',
        )

    def handle(self, *args, **options):
        if not options['email'] and not options['username']:
            self.stdout.write(self.style.ERROR('Please specify --email or --username'))
            return
        
        try:
            if options['email']:
                user = User.objects.get(email=options['email'])
            else:
                user = User.objects.get(username=options['username'])
            
            # Verify the user
            user.is_active = True
            user.save()
            
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.email_verified = True
            profile.save()
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Email verified for user {user.username} ({user.email})'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'  - Account activated: {user.is_active}'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'  - Email verified: {profile.email_verified}'
            ))
            
        except User.DoesNotExist:
            identifier = options['email'] or options['username']
            self.stdout.write(self.style.ERROR(f'✗ User not found: {identifier}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))

