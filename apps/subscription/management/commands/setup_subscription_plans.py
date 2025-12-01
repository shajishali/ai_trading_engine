from django.core.management.base import BaseCommand
from apps.subscription.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Set up default subscription plans for the AI Trading Engine'

    def handle(self, *args, **options):
        self.stdout.write('Setting up subscription plans...')
        
        # Create Free Trial Plan
        free_plan, created = SubscriptionPlan.objects.get_or_create(
            tier='free',
            defaults={
                'name': 'Free Trial',
                'price': 0.00,
                'currency': 'USD',
                'billing_cycle': 'monthly',
                'max_signals_per_day': 999,  # Unlimited during trial
                'max_portfolios': 5,
                'has_ml_predictions': True,
                'has_api_access': True,
                'has_priority_support': True,
                'trial_days': 7,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created Free Trial plan'))
        else:
            self.stdout.write('✓ Free Trial plan already exists')
        
        # Create Basic Plan
        basic_plan, created = SubscriptionPlan.objects.get_or_create(
            tier='basic',
            defaults={
                'name': 'Basic Plan',
                'price': 19.00,
                'currency': 'USD',
                'billing_cycle': 'monthly',
                'max_signals_per_day': 5,
                'max_portfolios': 1,
                'has_ml_predictions': False,
                'has_api_access': False,
                'has_priority_support': False,
                'trial_days': 0,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created Basic plan'))
        else:
            self.stdout.write('✓ Basic plan already exists')
        
        # Create Pro Plan
        pro_plan, created = SubscriptionPlan.objects.get_or_create(
            tier='pro',
            defaults={
                'name': 'Pro Plan',
                'price': 49.00,
                'currency': 'USD',
                'billing_cycle': 'monthly',
                'max_signals_per_day': 15,
                'max_portfolios': 3,
                'has_ml_predictions': True,
                'has_api_access': True,
                'has_priority_support': True,
                'trial_days': 0,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created Pro plan'))
        else:
            self.stdout.write('✓ Pro plan already exists')
        
        # Create Enterprise Plan
        enterprise_plan, created = SubscriptionPlan.objects.get_or_create(
            tier='enterprise',
            defaults={
                'name': 'Enterprise Plan',
                'price': 99.00,
                'currency': 'USD',
                'billing_cycle': 'monthly',
                'max_signals_per_day': 999,  # Unlimited
                'max_portfolios': 10,
                'has_ml_predictions': True,
                'has_api_access': True,
                'has_priority_support': True,
                'trial_days': 0,
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created Enterprise plan'))
        else:
            self.stdout.write('✓ Enterprise plan already exists')
        
        self.stdout.write(self.style.SUCCESS('\n🎉 All subscription plans have been set up successfully!'))
        self.stdout.write('\nPlans created:')
        self.stdout.write(f'  • {free_plan.name} - ${free_plan.price}/{free_plan.billing_cycle}')
        self.stdout.write(f'  • {basic_plan.name} - ${basic_plan.price}/{basic_plan.billing_cycle}')
        self.stdout.write(f'  • {pro_plan.name} - ${pro_plan.price}/{pro_plan.billing_cycle}')
        self.stdout.write(f'  • {enterprise_plan.name} - ${enterprise_plan.price}/{enterprise_plan.billing_cycle}')

