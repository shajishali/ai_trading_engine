from django.contrib import admin
from django.utils import timezone
from datetime import timedelta


class ActiveSubscriptionFilter(admin.SimpleListFilter):
    """Filter users by active subscription status"""
    title = 'Subscription Status'
    parameter_name = 'subscription_status'
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Active Subscriptions'),
            ('trial', 'Trial Users'),
            ('expired', 'Expired Subscriptions'),
            ('inactive', 'Inactive'),
            ('cancelled', 'Cancelled'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'active':
            return queryset.filter(
                subscription_status='active',
                subscription_end_date__gt=now
            )
        elif self.value() == 'trial':
            return queryset.filter(
                subscription_status='trial',
                trial_end_date__gt=now
            )
        elif self.value() == 'expired':
            return queryset.filter(
                subscription_status__in=['active', 'trial'],
                subscription_end_date__lt=now
            ) | queryset.filter(
                subscription_status='trial',
                trial_end_date__lt=now
            )
        elif self.value() == 'inactive':
            return queryset.filter(subscription_status='inactive')
        elif self.value() == 'cancelled':
            return queryset.filter(subscription_status='cancelled')
        return queryset


class SubscriptionExpiryFilter(admin.SimpleListFilter):
    """Filter subscriptions by expiry date"""
    title = 'Expires In'
    parameter_name = 'expires_in'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Expires Today'),
            ('week', 'Expires This Week'),
            ('month', 'Expires This Month'),
            ('expired', 'Already Expired'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            tomorrow = now + timedelta(days=1)
            return queryset.filter(
                subscription_end_date__gte=now,
                subscription_end_date__lt=tomorrow
            )
        elif self.value() == 'week':
            next_week = now + timedelta(days=7)
            return queryset.filter(
                subscription_end_date__gte=now,
                subscription_end_date__lt=next_week
            )
        elif self.value() == 'month':
            next_month = now + timedelta(days=30)
            return queryset.filter(
                subscription_end_date__gte=now,
                subscription_end_date__lt=next_month
            )
        elif self.value() == 'expired':
            return queryset.filter(
                subscription_end_date__lt=now
            ) | queryset.filter(
                subscription_status='trial',
                trial_end_date__lt=now
            )
        return queryset


class PaymentStatusFilter(admin.SimpleListFilter):
    """Filter payments by status"""
    title = 'Payment Status'
    parameter_name = 'payment_status'
    
    def lookups(self, request, model_admin):
        return (
            ('completed', 'Completed'),
            ('pending', 'Pending'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
        )
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class RecentPaymentFilter(admin.SimpleListFilter):
    """Filter payments by date"""
    title = 'Payment Date'
    parameter_name = 'payment_date'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('year', 'This Year'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(created_at__date=now.date())
        elif self.value() == 'week':
            week_ago = now - timedelta(days=7)
            return queryset.filter(created_at__gte=week_ago)
        elif self.value() == 'month':
            month_ago = now - timedelta(days=30)
            return queryset.filter(created_at__gte=month_ago)
        elif self.value() == 'year':
            year_ago = now - timedelta(days=365)
            return queryset.filter(created_at__gte=year_ago)
        return queryset













