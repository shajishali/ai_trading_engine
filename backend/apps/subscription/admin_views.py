from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from datetime import timedelta

from .models import UserProfile, Payment, SubscriptionPlan, SubscriptionHistory


class SubscriptionStatisticsMixin:
    """Mixin for subscription statistics views"""
    
    def get_subscription_stats(self):
        """Get subscription statistics"""
        now = timezone.now()
        
        # User counts by status
        total_users = UserProfile.objects.count()
        active_subscriptions = UserProfile.objects.filter(
            Q(subscription_status='active', subscription_end_date__gt=now) |
            Q(subscription_status='trial', trial_end_date__gt=now)
        ).count()
        trial_users = UserProfile.objects.filter(
            subscription_status='trial',
            trial_end_date__gt=now
        ).count()
        expired_subscriptions = UserProfile.objects.filter(
            Q(subscription_status='active', subscription_end_date__lt=now) |
            Q(subscription_status='trial', trial_end_date__lt=now)
        ).count()
        
        # Plan distribution
        plan_distribution = SubscriptionPlan.objects.annotate(
            user_count=Count('userprofile')
        ).values('name', 'tier', 'user_count', 'price')
        
        # Revenue statistics
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_revenue = Payment.objects.filter(
            status='completed',
            created_at__gte=now - timedelta(days=30)
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Payment statistics
        total_payments = Payment.objects.count()
        completed_payments = Payment.objects.filter(status='completed').count()
        pending_payments = Payment.objects.filter(status='pending').count()
        failed_payments = Payment.objects.filter(status='failed').count()
        
        # Recent activity
        recent_subscriptions = SubscriptionHistory.objects.select_related(
            'user', 'old_plan', 'new_plan'
        ).order_by('-created_at')[:10]
        
        return {
            'total_users': total_users,
            'active_subscriptions': active_subscriptions,
            'trial_users': trial_users,
            'expired_subscriptions': expired_subscriptions,
            'plan_distribution': plan_distribution,
            'total_revenue': float(total_revenue),
            'monthly_revenue': float(monthly_revenue),
            'total_payments': total_payments,
            'completed_payments': completed_payments,
            'pending_payments': pending_payments,
            'failed_payments': failed_payments,
            'recent_subscriptions': recent_subscriptions,
        }


class SubscriptionStatisticsAdmin(SubscriptionStatisticsMixin, admin.ModelAdmin):
    """Admin view for subscription statistics"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('statistics/', self.admin_site.admin_view(self.statistics_view), name='subscription_statistics'),
        ]
        return custom_urls + urls
    
    def statistics_view(self, request):
        """Display subscription statistics"""
        context = {
            **self.admin_site.each_context(request),
            'title': 'Subscription Statistics',
            'stats': self.get_subscription_stats(),
        }
        return TemplateResponse(request, 'admin/subscription/statistics.html', context)


class UserStatisticsAdmin(SubscriptionStatisticsMixin, admin.ModelAdmin):
    """Admin view for user statistics"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('user-statistics/', self.admin_site.admin_view(self.user_statistics_view), name='user_statistics'),
        ]
        return custom_urls + urls
    
    def user_statistics_view(self, request):
        """Display user statistics"""
        now = timezone.now()
        
        # User growth
        total_users = UserProfile.objects.count()
        users_this_month = UserProfile.objects.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()
        users_this_week = UserProfile.objects.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        
        # Email verification stats
        verified_users = UserProfile.objects.filter(email_verified=True).count()
        unverified_users = UserProfile.objects.filter(email_verified=False).count()
        
        # Signal usage stats
        avg_signals_used = UserProfile.objects.aggregate(
            avg=Avg('signals_used_today')
        )['avg'] or 0
        
        # Social auth stats
        social_auth_users = UserProfile.objects.exclude(
            social_provider__isnull=True
        ).count()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'User Statistics',
            'total_users': total_users,
            'users_this_month': users_this_month,
            'users_this_week': users_this_week,
            'verified_users': verified_users,
            'unverified_users': unverified_users,
            'avg_signals_used': round(avg_signals_used, 2),
            'social_auth_users': social_auth_users,
            'stats': self.get_subscription_stats(),
        }
        return TemplateResponse(request, 'admin/subscription/user_statistics.html', context)













