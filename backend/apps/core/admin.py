from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from datetime import timedelta

from apps.subscription.models import UserProfile, Payment, SubscriptionHistory
from apps.core.admin_exports import export_queryset
from apps.core.admin_search import EnhancedSearchMixin


class SubscriptionHistoryInline(admin.TabularInline):
    """Inline admin for subscription history"""
    model = SubscriptionHistory
    extra = 0
    readonly_fields = ['action', 'old_plan', 'new_plan', 'payment', 'created_at']
    fields = ['action', 'old_plan', 'new_plan', 'payment', 'created_at']
    can_delete = False
    can_add = False
    max_num = 10
    ordering = ['-created_at']
    fk_name = 'user'


# Unregister the default User admin
admin.site.unregister(User)


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = (
        'subscription_plan', 'subscription_status', 
        'subscription_start_date', 'subscription_end_date', 'trial_end_date',
        'signals_used_today', 'email_verified'
    )


class PaymentInline(admin.TabularInline):
    """Inline admin for Payment history"""
    model = Payment
    extra = 0
    readonly_fields = ['subscription_plan', 'amount', 'currency', 'status', 'provider', 'created_at']
    fields = ['subscription_plan', 'amount', 'currency', 'status', 'provider', 'created_at']
    can_delete = False
    can_add = False
    max_num = 10
    ordering = ['-created_at']


@admin.register(User)
class UserAdmin(EnhancedSearchMixin, BaseUserAdmin):
    """Enhanced User Admin with subscription information"""
    
    inlines = [UserProfileInline, PaymentInline, SubscriptionHistoryInline]
    
    list_display = [
        'username', 'email', 'first_name', 'last_name', 
        'subscription_status_display', 'signals_used_today_display',
        'last_login_display', 'account_age_display', 'is_active', 'date_joined'
    ]
    
    list_filter = [
        'is_active', 'is_staff', 'is_superuser', 'date_joined',
        'profile__subscription_status',  # CharField with choices - Django auto-creates filter
        ('profile__subscription_plan', admin.RelatedFieldListFilter),  # ForeignKey - relation field
    ]
    
    search_fields = ['username', 'email', 'first_name', 'last_name']
    date_hierarchy = 'date_joined'
    ordering = ['-date_joined']
    
    # Use BaseUserAdmin fieldsets as-is (already includes date_joined and last_login)
    fieldsets = BaseUserAdmin.fieldsets
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('profile', 'profile__subscription_plan')
    
    def subscription_status_display(self, obj):
        """Display subscription status with color coding"""
        try:
            profile = obj.profile
            status = profile.subscription_status
            is_active = profile.is_subscription_active
            
            status_colors = {
                'active': 'green' if is_active else 'orange',
                'trial': 'blue',
                'inactive': 'gray',
                'cancelled': 'red'
            }
            color = status_colors.get(status, 'gray')
            
            plan_name = profile.subscription_plan.name if profile.subscription_plan else 'No Plan'
            status_label = status.title()
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} ({})</span>',
                color,
                status_label,
                plan_name
            )
        except UserProfile.DoesNotExist:
            return format_html('<span style="color: gray;">No Profile</span>')
    subscription_status_display.short_description = 'Subscription Status'
    
    def signals_used_today_display(self, obj):
        """Display signals used today with limit"""
        try:
            profile = obj.profile
            used = profile.signals_used_today
            limit = profile.subscription_plan.max_signals_per_day if profile.subscription_plan else 0
            
            if limit > 0:
                percentage = (used / limit) * 100
                percentage_str = f"{percentage:.0f}"
                color = 'green' if percentage < 70 else 'orange' if percentage < 90 else 'red'
                return format_html(
                    '<span style="color: {};">{}/{} ({}%)</span>',
                    color,
                    used,
                    limit,
                    percentage_str
                )
            return format_html('<span style="color: gray;">{}/-</span>', used)
        except UserProfile.DoesNotExist:
            return '-'
    signals_used_today_display.short_description = 'Signals Used'
    
    def last_login_display(self, obj):
        """Display last login with relative time"""
        if obj.last_login:
            delta = timezone.now() - obj.last_login
            if delta.days == 0:
                hours = delta.seconds // 3600
                if hours == 0:
                    minutes = delta.seconds // 60
                    return f"{minutes}m ago"
                return f"{hours}h ago"
            elif delta.days < 7:
                return f"{delta.days}d ago"
            else:
                return obj.last_login.strftime('%Y-%m-%d')
        return format_html('<span style="color: gray;">Never</span>')
    last_login_display.short_description = 'Last Login'
    
    def account_age_display(self, obj):
        """Display account age"""
        delta = timezone.now() - obj.date_joined
        if delta.days < 30:
            return f"{delta.days} days"
        elif delta.days < 365:
            months = delta.days // 30
            return f"{months} months"
        else:
            years = delta.days // 365
            months = (delta.days % 365) // 30
            return f"{years}y {months}m"
    account_age_display.short_description = 'Account Age'
    
    # Bulk actions
    actions = ['activate_users', 'deactivate_users', 'export_user_list']
    
    def activate_users(self, request, queryset):
        """Activate selected users"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} user(s) activated successfully.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} user(s) deactivated successfully.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def export_user_list(self, request, queryset):
        """Export user list to CSV/Excel/JSON/PDF"""
        format_type = request.GET.get('export_format', 'csv')
        
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'date_joined', 'last_login',
            'profile__subscription_status', 'profile__subscription_plan__name',
            'profile__signals_used_today'
        ]
        headers = [
            'Username', 'Email', 'First Name', 'Last Name',
            'Is Active', 'Is Staff', 'Date Joined', 'Last Login',
            'Subscription Status', 'Subscription Plan', 'Signals Used Today'
        ]
        
        filename = f"users_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        return export_queryset(
            queryset=queryset.select_related('profile', 'profile__subscription_plan'),
            format=format_type,
            fields=fields,
            headers=headers,
            filename=filename
        )
    export_user_list.short_description = 'Export selected users'
