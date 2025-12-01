"""
Admin Dashboard Widgets
Provides reusable widgets for the admin dashboard
"""

from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta


class StatisticsCard:
    """Base class for statistics cards"""
    
    def __init__(self, title, value, icon='📊', color='blue', url=None, subtitle=None):
        self.title = title
        self.value = value
        self.icon = icon
        self.color = color
        self.url = url
        self.subtitle = subtitle
    
    def render(self):
        """Render the statistics card"""
        card_class = f"stat-card stat-card-{self.color}"
        value_html = format_html('<div class="stat-value">{}</div>', self.value)
        title_html = format_html('<div class="stat-title">{}</div>', self.title)
        
        if self.subtitle:
            subtitle_html = format_html('<div class="stat-subtitle">{}</div>', self.subtitle)
        else:
            subtitle_html = ''
        
        icon_html = format_html('<div class="stat-icon">{}</div>', self.icon)
        
        if self.url:
            return format_html(
                '<a href="{}" class="{}">{}{}{}{}</a>',
                self.url,
                card_class,
                icon_html,
                value_html,
                title_html,
                subtitle_html
            )
        else:
            return format_html(
                '<div class="{}">{}{}{}{}</div>',
                card_class,
                icon_html,
                value_html,
                title_html,
                subtitle_html
            )


class QuickActionButton:
    """Quick action button widget"""
    
    def __init__(self, label, url, icon='⚡', color='primary'):
        self.label = label
        self.url = url
        self.icon = icon
        self.color = color
    
    def render(self):
        """Render the quick action button"""
        return format_html(
            '<a href="{}" class="quick-action-btn btn-{}"><span class="btn-icon">{}</span><span class="btn-label">{}</span></a>',
            self.url,
            self.color,
            self.icon,
            self.label
        )


class ActivityFeedItem:
    """Activity feed item"""
    
    def __init__(self, message, time, url=None, type='info'):
        self.message = message
        self.time = time
        self.url = url
        self.type = type
    
    def render(self):
        """Render activity feed item"""
        time_ago = self._get_time_ago()
        type_class = f"activity-{self.type}"
        
        if self.url:
            message_html = format_html('<a href="{}">{}</a>', self.url, self.message)
        else:
            message_html = self.message
        
        return format_html(
            '<div class="activity-item {}"><div class="activity-message">{}</div><div class="activity-time">{}</div></div>',
            type_class,
            message_html,
            time_ago
        )
    
    def _get_time_ago(self):
        """Get relative time string"""
        now = timezone.now()
        delta = now - self.time
        
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                minutes = delta.seconds // 60
                return f"{minutes}m ago" if minutes > 0 else "just now"
            return f"{hours}h ago"
        elif delta.days < 7:
            return f"{delta.days}d ago"
        else:
            return self.time.strftime('%Y-%m-%d')


def get_statistics_cards(stats):
    """Generate statistics cards from stats dictionary"""
    cards = []
    
    # Users card
    users_card = StatisticsCard(
        title='Total Users',
        value=stats['users']['total'],
        icon='👥',
        color='blue',
        url=reverse('admin:auth_user_changelist'),
        subtitle=f"+{stats['users']['this_week']} this week"
    )
    cards.append(users_card)
    
    # Active Subscriptions card
    subscriptions_card = StatisticsCard(
        title='Active Subscriptions',
        value=stats['subscriptions']['active'],
        icon='💳',
        color='green',
        url=reverse('admin:subscription_userprofile_changelist') + '?subscription_status__exact=active',
        subtitle=f"{stats['subscriptions']['trial']} on trial"
    )
    cards.append(subscriptions_card)
    
    # Revenue card
    revenue_card = StatisticsCard(
        title='Monthly Revenue',
        value=f"${stats['revenue']['monthly']:,.2f}",
        icon='💰',
        color='gold',
        url=reverse('admin:subscription_payment_changelist'),
        subtitle=f"Total: ${stats['revenue']['total']:,.2f}"
    )
    cards.append(revenue_card)
    
    # Signals card
    signals_card = StatisticsCard(
        title='Signals Generated',
        value=stats['signals']['total'],
        icon='📈',
        color='purple',
        url=reverse('admin:signals_tradingsignal_changelist'),
        subtitle=f"{stats['signals']['today']} today, {stats['signals']['this_week']} this week"
    )
    cards.append(signals_card)
    
    # Alerts card
    alerts_card = StatisticsCard(
        title='Unread Alerts',
        value=stats['alerts']['unread'],
        icon='🔔',
        color='red' if stats['alerts']['unread'] > 0 else 'gray',
        url=reverse('admin:signals_signalalert_changelist') + '?is_read__exact=0',
        subtitle='Requires attention' if stats['alerts']['unread'] > 0 else 'All clear'
    )
    cards.append(alerts_card)
    
    return cards


def get_quick_actions():
    """Generate quick action buttons"""
    actions = []
    
    # Create subscription plan
    actions.append(QuickActionButton(
        label='New Plan',
        url=reverse('admin:subscription_subscriptionplan_add'),
        icon='➕',
        color='primary'
    ))
    
    # View signals
    actions.append(QuickActionButton(
        label='View Signals',
        url=reverse('admin:signals_tradingsignal_changelist'),
        icon='📊',
        color='info'
    ))
    
    # View users
    actions.append(QuickActionButton(
        label='Manage Users',
        url=reverse('admin:auth_user_changelist'),
        icon='👥',
        color='success'
    ))
    
    # View payments
    actions.append(QuickActionButton(
        label='Payments',
        url=reverse('admin:subscription_payment_changelist'),
        icon='💳',
        color='warning'
    ))
    
    return actions













