from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.urls import reverse
from datetime import timedelta
from .models import SubscriptionPlan, UserProfile, Payment, SubscriptionHistory, EmailVerificationToken
from .admin_filters import (
    ActiveSubscriptionFilter, SubscriptionExpiryFilter,
    PaymentStatusFilter, RecentPaymentFilter
)
from apps.core.admin_exports import export_queryset
from apps.core.admin_search import EnhancedSearchMixin
from apps.core.admin_filters import DateRangeFilter


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Enhanced Subscription Plan Admin with usage statistics"""
    
    list_display = [
        'name', 'tier', 'price', 'currency', 'billing_cycle', 
        'user_count_display', 'is_active', 'max_signals_per_day'
    ]
    list_filter = ['tier', 'billing_cycle', 'is_active', 'has_ml_predictions', 'has_api_access']
    search_fields = ['name', 'tier']
    ordering = ['price']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'tier', 'price', 'currency', 'billing_cycle', 'is_active')
        }),
        ('Feature Limits', {
            'fields': ('max_signals_per_day', 'max_portfolios', 'has_ml_predictions', 'has_api_access', 'has_priority_support')
        }),
        ('Trial Settings', {
            'fields': ('trial_days',)
        }),
        ('Statistics', {
            'fields': ('user_count_display', 'revenue_display'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['user_count_display', 'revenue_display']
    
    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        qs = super().get_queryset(request)
        return qs.annotate(
            user_count=Count('userprofile', distinct=True)
        )
    
    def user_count_display(self, obj):
        """Display number of users on this plan"""
        count = obj.userprofile_set.count()
        if count > 0:
            return format_html(
                '<span style="font-weight: bold; color: blue;">{} users</span>',
                count
            )
        return format_html('<span style="color: gray;">0 users</span>')
    user_count_display.short_description = 'Active Users'
    
    def revenue_display(self, obj):
        """Display total revenue from this plan"""
        total = Payment.objects.filter(
            subscription_plan=obj,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return format_html(
            '<span style="font-weight: bold; color: green;">${:,.2f}</span>',
            float(total)
        )
    revenue_display.short_description = 'Total Revenue'

@admin.register(UserProfile)
class UserProfileAdmin(EnhancedSearchMixin, admin.ModelAdmin):
    """Enhanced User Profile Admin with subscription management"""
    
    list_display = [
        'user', 'subscription_plan', 'subscription_status_display', 
        'is_subscription_active', 'signals_used_today_display', 
        'subscription_end_date_display', 'email_verified', 'created_at'
    ]
    list_filter = [
        ActiveSubscriptionFilter, SubscriptionExpiryFilter, DateRangeFilter,
        'subscription_plan', 'email_verified', 'social_provider', 'created_at'
    ]
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'user__username']
    readonly_fields = [
        'created_at', 'updated_at', 'last_signal_reset',
        'subscription_timeline', 'payment_history_link', 'subscription_history_link'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'email_verified', 'profile_picture')
        }),
        ('Subscription Information', {
            'fields': (
                'subscription_plan', 'subscription_status', 
                'subscription_start_date', 'subscription_end_date', 'trial_end_date',
                'subscription_timeline'
            )
        }),
        ('Usage Tracking', {
            'fields': ('signals_used_today', 'last_signal_reset'),
        }),
        ('Social Authentication', {
            'fields': ('social_provider', 'social_id'),
            'classes': ('collapse',)
        }),
        ('Payment History', {
            'fields': ('payment_history_link', 'subscription_history_link'),
        }),
        ('Preferences', {
            'fields': ('notification_preferences',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'subscription_plan')
    
    def subscription_status_display(self, obj):
        """Display subscription status with color coding"""
        status = obj.subscription_status
        status_colors = {
            'active': 'green',
            'trial': 'blue',
            'inactive': 'gray',
            'cancelled': 'red'
        }
        color = status_colors.get(status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status.title()
        )
    subscription_status_display.short_description = 'Status'
    
    def is_subscription_active(self, obj):
        """Display subscription active status"""
        if obj.is_subscription_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactive</span>')
    is_subscription_active.short_description = 'Active'
    is_subscription_active.boolean = True
    
    def signals_used_today_display(self, obj):
        """Display signals used with limit"""
        used = obj.signals_used_today
        limit = obj.subscription_plan.max_signals_per_day if obj.subscription_plan else 0
        
        if limit > 0:
            percentage = (used / limit) * 100
            color = 'green' if percentage < 70 else 'orange' if percentage < 90 else 'red'
            return format_html(
                '<span style="color: {};">{}/{} ({:.0f}%)</span>',
                color,
                used,
                limit,
                percentage
            )
        return format_html('<span style="color: gray;">{}/-</span>', used)
    signals_used_today_display.short_description = 'Signals Used'
    
    def subscription_end_date_display(self, obj):
        """Display subscription end date with time remaining"""
        if obj.subscription_status == 'trial' and obj.trial_end_date:
            end_date = obj.trial_end_date
        elif obj.subscription_end_date:
            end_date = obj.subscription_end_date
        else:
            return '-'
        
        now = timezone.now()
        if end_date > now:
            delta = end_date - now
            days = delta.days
            if days == 0:
                hours = delta.seconds // 3600
                return format_html(
                    '<span style="color: orange;">{} ({}h left)</span>',
                    end_date.strftime('%Y-%m-%d'),
                    hours
                )
            elif days < 7:
                return format_html(
                    '<span style="color: orange;">{} ({}d left)</span>',
                    end_date.strftime('%Y-%m-%d'),
                    days
                )
            else:
                return end_date.strftime('%Y-%m-%d')
        else:
            return format_html(
                '<span style="color: red;">{} (Expired)</span>',
                end_date.strftime('%Y-%m-%d')
            )
    subscription_end_date_display.short_description = 'Expires'
    
    def subscription_timeline(self, obj):
        """Display subscription timeline"""
        timeline = []
        if obj.subscription_start_date:
            timeline.append(f"Started: {obj.subscription_start_date.strftime('%Y-%m-%d')}")
        if obj.trial_end_date:
            timeline.append(f"Trial ends: {obj.trial_end_date.strftime('%Y-%m-%d')}")
        if obj.subscription_end_date:
            timeline.append(f"Ends: {obj.subscription_end_date.strftime('%Y-%m-%d')}")
        
        if timeline:
            return format_html('<br>'.join(timeline))
        return '-'
    subscription_timeline.short_description = 'Timeline'
    
    def payment_history_link(self, obj):
        """Link to payment history"""
        count = Payment.objects.filter(user=obj.user).count()
        if count > 0:
            url = reverse('admin:subscription_payment_changelist')
            url += f'?user__id__exact={obj.user.id}'
            return format_html(
                '<a href="{}">View {} payment(s)</a>',
                url,
                count
            )
        return 'No payments'
    payment_history_link.short_description = 'Payments'
    
    def subscription_history_link(self, obj):
        """Link to subscription history"""
        count = SubscriptionHistory.objects.filter(user=obj.user).count()
        if count > 0:
            url = reverse('admin:subscription_subscriptionhistory_changelist')
            url += f'?user__id__exact={obj.user.id}'
            return format_html(
                '<a href="{}">View {} history record(s)</a>',
                url,
                count
            )
        return 'No history'
    subscription_history_link.short_description = 'Subscription History'
    
    # Bulk actions
    actions = [
        'extend_trial_7_days', 'extend_trial_30_days',
        'activate_subscriptions', 'cancel_subscriptions',
        'upgrade_to_pro', 'downgrade_to_basic',
        'export_profiles_csv', 'export_profiles_excel'
    ]
    
    def extend_trial_7_days(self, request, queryset):
        """Extend trial by 7 days"""
        now = timezone.now()
        extended = 0
        for profile in queryset.filter(subscription_status='trial'):
            if profile.trial_end_date:
                profile.trial_end_date += timedelta(days=7)
            else:
                profile.trial_end_date = now + timedelta(days=7)
            profile.save()
            extended += 1
        self.message_user(request, f'{extended} trial(s) extended by 7 days.')
    extend_trial_7_days.short_description = 'Extend trial by 7 days'
    
    def extend_trial_30_days(self, request, queryset):
        """Extend trial by 30 days"""
        now = timezone.now()
        extended = 0
        for profile in queryset.filter(subscription_status='trial'):
            if profile.trial_end_date:
                profile.trial_end_date += timedelta(days=30)
            else:
                profile.trial_end_date = now + timedelta(days=30)
            profile.save()
            extended += 1
        self.message_user(request, f'{extended} trial(s) extended by 30 days.')
    extend_trial_30_days.short_description = 'Extend trial by 30 days'
    
    def activate_subscriptions(self, request, queryset):
        """Activate selected subscriptions"""
        now = timezone.now()
        activated = 0
        for profile in queryset:
            profile.subscription_status = 'active'
            if not profile.subscription_start_date:
                profile.subscription_start_date = now
            if not profile.subscription_end_date:
                profile.subscription_end_date = now + timedelta(days=30)
            profile.save()
            activated += 1
        self.message_user(request, f'{activated} subscription(s) activated.')
    activate_subscriptions.short_description = 'Activate subscriptions'
    
    def cancel_subscriptions(self, request, queryset):
        """Cancel selected subscriptions"""
        cancelled = queryset.update(subscription_status='cancelled')
        self.message_user(request, f'{cancelled} subscription(s) cancelled.')
    cancel_subscriptions.short_description = 'Cancel subscriptions'
    
    def upgrade_to_pro(self, request, queryset):
        """Upgrade to Pro plan"""
        try:
            pro_plan = SubscriptionPlan.objects.get(tier='pro')
            upgraded = queryset.update(subscription_plan=pro_plan)
            self.message_user(request, f'{upgraded} subscription(s) upgraded to Pro.')
        except SubscriptionPlan.DoesNotExist:
            self.message_user(request, 'Pro plan not found.', level='error')
    upgrade_to_pro.short_description = 'Upgrade to Pro plan'
    
    def downgrade_to_basic(self, request, queryset):
        """Downgrade to Basic plan"""
        try:
            basic_plan = SubscriptionPlan.objects.get(tier='basic')
            downgraded = queryset.update(subscription_plan=basic_plan)
            self.message_user(request, f'{downgraded} subscription(s) downgraded to Basic.')
        except SubscriptionPlan.DoesNotExist:
            self.message_user(request, 'Basic plan not found.', level='error')
    downgrade_to_basic.short_description = 'Downgrade to Basic plan'
    
    def export_profiles_csv(self, request, queryset):
        """Export user profiles to CSV"""
        fields = [
            'user__username', 'user__email', 'user__first_name', 'user__last_name',
            'subscription_plan__name', 'subscription_status',
            'subscription_start_date', 'subscription_end_date', 'trial_end_date',
            'signals_used_today', 'email_verified', 'created_at'
        ]
        headers = [
            'Username', 'Email', 'First Name', 'Last Name',
            'Subscription Plan', 'Status',
            'Start Date', 'End Date', 'Trial End Date',
            'Signals Used Today', 'Email Verified', 'Created At'
        ]
        filename = f"user_profiles_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('user', 'subscription_plan'), 'csv', fields, headers, filename)
    export_profiles_csv.short_description = 'Export selected profiles to CSV'
    
    def export_profiles_excel(self, request, queryset):
        """Export user profiles to Excel"""
        fields = [
            'user__username', 'user__email', 'user__first_name', 'user__last_name',
            'subscription_plan__name', 'subscription_status',
            'subscription_start_date', 'subscription_end_date', 'trial_end_date',
            'signals_used_today', 'email_verified', 'created_at'
        ]
        headers = [
            'Username', 'Email', 'First Name', 'Last Name',
            'Subscription Plan', 'Status',
            'Start Date', 'End Date', 'Trial End Date',
            'Signals Used Today', 'Email Verified', 'Created At'
        ]
        filename = f"user_profiles_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('user', 'subscription_plan'), 'excel', fields, headers, filename)
    export_profiles_excel.short_description = 'Export selected profiles to Excel'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Enhanced Payment Admin with analytics and status indicators"""
    
    list_display = [
        'user', 'subscription_plan', 'amount_display', 'currency', 
        'status_display', 'provider', 'created_at', 'payment_link'
    ]
    list_filter = [
        PaymentStatusFilter, RecentPaymentFilter,
        'provider', 'currency', 'created_at'
    ]
    search_fields = ['user__email', 'user__username', 'provider_payment_id']
    readonly_fields = ['created_at', 'updated_at', 'revenue_contribution']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('user', 'subscription_plan', 'amount', 'currency', 'status')
        }),
        ('Provider Information', {
            'fields': ('provider', 'provider_payment_id')
        }),
        ('Analytics', {
            'fields': ('revenue_contribution',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'subscription_plan')
    
    def amount_display(self, obj):
        """Display amount with formatting"""
        return format_html(
            '<span style="font-weight: bold;">${:,.2f}</span>',
            float(obj.amount)
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'completed': 'green',
            'pending': 'orange',
            'failed': 'red',
            'refunded': 'gray'
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status.title()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def payment_link(self, obj):
        """Link to payment provider if available"""
        if obj.provider_payment_id:
            if obj.provider == 'stripe':
                url = f"https://dashboard.stripe.com/payments/{obj.provider_payment_id}"
                return format_html('<a href="{}" target="_blank">View in Stripe</a>', url)
            elif obj.provider == 'paypal':
                return format_html('<span>{}</span>', obj.provider_payment_id)
        return '-'
    payment_link.short_description = 'Provider Link'
    
    def revenue_contribution(self, obj):
        """Show revenue contribution if completed"""
        if obj.status == 'completed':
            total_revenue = Payment.objects.filter(
                status='completed',
                created_at__year=obj.created_at.year,
                created_at__month=obj.created_at.month
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            if total_revenue > 0:
                percentage = (float(obj.amount) / float(total_revenue)) * 100
                return format_html(
                    '{:.2f}% of monthly revenue',
                    percentage
                )
        return '-'
    revenue_contribution.short_description = 'Revenue Contribution'
    
    # Bulk actions
    actions = [
        'mark_as_completed', 'mark_as_failed', 'mark_as_refunded',
        'export_payments_csv', 'export_payments_excel'
    ]
    
    def mark_as_completed(self, request, queryset):
        """Mark selected payments as completed"""
        count = queryset.update(status='completed')
        self.message_user(request, f'{count} payment(s) marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected payments as failed"""
        count = queryset.update(status='failed')
        self.message_user(request, f'{count} payment(s) marked as failed.')
    mark_as_failed.short_description = 'Mark as failed'
    
    def mark_as_refunded(self, request, queryset):
        """Mark selected payments as refunded"""
        count = queryset.update(status='refunded')
        self.message_user(request, f'{count} payment(s) marked as refunded.')
    mark_as_refunded.short_description = 'Mark as refunded'
    
    def export_payments_csv(self, request, queryset):
        """Export payments to CSV"""
        fields = [
            'user__email', 'subscription_plan__name', 'amount', 'currency',
            'status', 'provider', 'provider_payment_id', 'created_at'
        ]
        headers = [
            'User Email', 'Subscription Plan', 'Amount', 'Currency',
            'Status', 'Provider', 'Provider Payment ID', 'Created At'
        ]
        filename = f"payments_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('user', 'subscription_plan'), 'csv', fields, headers, filename)
    export_payments_csv.short_description = 'Export selected payments to CSV'
    
    def export_payments_excel(self, request, queryset):
        """Export payments to Excel"""
        fields = [
            'user__email', 'subscription_plan__name', 'amount', 'currency',
            'status', 'provider', 'provider_payment_id', 'created_at'
        ]
        headers = [
            'User Email', 'Subscription Plan', 'Amount', 'Currency',
            'Status', 'Provider', 'Provider Payment ID', 'Created At'
        ]
        filename = f"payments_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        return export_queryset(queryset.select_related('user', 'subscription_plan'), 'excel', fields, headers, filename)
    export_payments_excel.short_description = 'Export selected payments to Excel'

@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'old_plan', 'new_plan', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Subscription Change', {
            'fields': ('user', 'action', 'old_plan', 'new_plan', 'payment')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'email', 'token_preview', 'is_valid_status', 'is_used', 'created_at', 'expires_at']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'email', 'token']
    readonly_fields = ['token', 'created_at', 'expires_at', 'is_valid_status']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Token Information', {
            'fields': ('user', 'email', 'token')
        }),
        ('Status', {
            'fields': ('is_used', 'is_valid_status', 'created_at', 'expires_at')
        }),
    )
    
    def token_preview(self, obj):
        """Show first 20 characters of token"""
        if obj.token:
            return f"{obj.token[:20]}..."
        return "-"
    token_preview.short_description = 'Token Preview'
    
    def is_valid_status(self, obj):
        """Show if token is valid"""
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            if obj.is_used:
                return format_html('<span style="color: orange;">✗ Used</span>')
            else:
                return format_html('<span style="color: red;">✗ Expired</span>')
    is_valid_status.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    actions = ['mark_as_used', 'delete_expired_tokens']
    
    def mark_as_used(self, request, queryset):
        """Mark selected tokens as used"""
        count = queryset.update(is_used=True)
        self.message_user(request, f'{count} token(s) marked as used.')
    mark_as_used.short_description = 'Mark selected tokens as used'
    
    def delete_expired_tokens(self, request, queryset):
        """Delete expired tokens"""
        now = timezone.now()
        expired = queryset.filter(expires_at__lt=now, is_used=True)
        count = expired.count()
        expired.delete()
        self.message_user(request, f'{count} expired and used token(s) deleted.')
    delete_expired_tokens.short_description = 'Delete expired and used tokens'
