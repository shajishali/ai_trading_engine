"""
Management command to clean up expired email verification tokens
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.subscription.models import EmailVerificationToken


class Command(BaseCommand):
    help = 'Clean up expired and used email verification tokens'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete tokens older than this many days (default: 7)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        # Find expired and used tokens older than cutoff_date
        expired_tokens = EmailVerificationToken.objects.filter(
            expires_at__lt=cutoff_date,
            is_used=True
        )
        
        count = expired_tokens.count()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would delete {count} expired and used token(s)'))
            if count > 0:
                self.stdout.write('\nTokens that would be deleted:')
                for token in expired_tokens[:10]:  # Show first 10
                    self.stdout.write(f'  - {token.user.username} ({token.email}) - Created: {token.created_at}')
                if count > 10:
                    self.stdout.write(f'  ... and {count - 10} more')
        else:
            deleted_count = expired_tokens.delete()[0]
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {deleted_count} expired and used token(s)'))
        
        # Also find expired but unused tokens (shouldn't happen often, but clean them up too)
        expired_unused = EmailVerificationToken.objects.filter(
            expires_at__lt=timezone.now(),
            is_used=False
        )
        
        expired_unused_count = expired_unused.count()
        
        if expired_unused_count > 0:
            if dry_run:
                self.stdout.write(self.style.WARNING(f'DRY RUN: Would delete {expired_unused_count} expired but unused token(s)'))
            else:
                deleted_unused = expired_unused.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'✓ Deleted {deleted_unused} expired but unused token(s)'))
        
        total = count + expired_unused_count
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✓ No expired tokens to clean up'))

