"""
Phase 4 Subscription Tiers Service
Manages different subscription levels for signal access
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.contrib.auth.models import User

from apps.signals.models import SubscriptionTier, UserSubscription, SignalAccessLog, TradingSignal

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing subscriptions and signal access"""
    
    def get_subscription_tiers(self) -> List[SubscriptionTier]:
        """Get all active subscription tiers"""
        try:
            return SubscriptionTier.objects.filter(is_active=True).order_by('monthly_price')
        except Exception as e:
            logger.error(f"Error getting subscription tiers: {e}")
            return []
    
    def get_user_subscription(self, user: User) -> Optional[UserSubscription]:
        """Get user's active subscription"""
        try:
            return UserSubscription.objects.filter(
                user=user,
                status='ACTIVE',
                end_date__gt=timezone.now()
            ).first()
        except Exception as e:
            logger.error(f"Error getting user subscription: {e}")
            return None
    
    def create_subscription(self, user: User, tier_name: str, 
                           billing_cycle: str = 'MONTHLY') -> Optional[UserSubscription]:
        """Create a new subscription for user"""
        try:
            tier = SubscriptionTier.objects.get(name=tier_name, is_active=True)
            
            # Calculate dates
            start_date = timezone.now()
            if billing_cycle == 'YEARLY':
                end_date = start_date + timedelta(days=365)
            else:
                end_date = start_date + timedelta(days=30)
            
            next_billing_date = end_date
            
            subscription = UserSubscription.objects.create(
                user=user,
                tier=tier,
                status='ACTIVE',
                billing_cycle=billing_cycle,
                start_date=start_date,
                end_date=end_date,
                next_billing_date=next_billing_date
            )
            
            logger.info(f"Created subscription for user {user.username}: {tier_name}")
            return subscription
            
        except SubscriptionTier.DoesNotExist:
            logger.error(f"Subscription tier {tier_name} not found")
            return None
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return None
    
    def upgrade_subscription(self, user: User, new_tier_name: str, 
                           billing_cycle: str = 'MONTHLY') -> Optional[UserSubscription]:
        """Upgrade user's subscription to a higher tier"""
        try:
            # Cancel current subscription
            current_subscription = self.get_user_subscription(user)
            if current_subscription:
                current_subscription.status = 'CANCELLED'
                current_subscription.save()
            
            # Create new subscription
            return self.create_subscription(user, new_tier_name, billing_cycle)
            
        except Exception as e:
            logger.error(f"Error upgrading subscription: {e}")
            return None
    
    def can_user_access_signal(self, user: User, signal: TradingSignal) -> Dict[str, Any]:
        """Check if user can access a specific signal"""
        try:
            subscription = self.get_user_subscription(user)
            
            if not subscription:
                return {
                    'can_access': False,
                    'reason': 'No active subscription',
                    'tier': None
                }
            
            # Check signal type access
            if not subscription.can_access_signal_type(signal.signal_type.name):
                return {
                    'can_access': False,
                    'reason': f'Signal type {signal.signal_type.name} not available in {subscription.tier.name}',
                    'tier': subscription.tier.name
                }
            
            # Check hybrid signal access
            if signal.is_hybrid and not subscription.tier.has_hybrid_signals:
                return {
                    'can_access': False,
                    'reason': f'Hybrid signals not available in {subscription.tier.name}',
                    'tier': subscription.tier.name
                }
            
            # Check daily limit
            if subscription.has_daily_signal_limit():
                return {
                    'can_access': False,
                    'reason': 'Daily signal limit reached',
                    'tier': subscription.tier.name
                }
            
            return {
                'can_access': True,
                'reason': 'Access granted',
                'tier': subscription.tier.name
            }
            
        except Exception as e:
            logger.error(f"Error checking signal access: {e}")
            return {
                'can_access': False,
                'reason': f'Error: {str(e)}',
                'tier': None
            }
    
    def log_signal_access(self, user: User, signal: TradingSignal, 
                         access_type: str, ip_address: str = None, 
                         user_agent: str = None) -> bool:
        """Log signal access for monitoring and billing"""
        try:
            subscription = self.get_user_subscription(user)
            if not subscription:
                return False
            
            SignalAccessLog.objects.create(
                user=user,
                subscription=subscription,
                signal=signal,
                access_type=access_type,
                signal_type=signal.signal_type.name,
                is_hybrid=signal.is_hybrid,
                ml_model_used=signal.metadata.get('ml_model', '') if signal.metadata else '',
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Increment usage counter
            subscription.increment_signal_usage()
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging signal access: {e}")
            return False
    
    def get_user_usage_stats(self, user: User) -> Dict[str, Any]:
        """Get user's usage statistics"""
        try:
            subscription = self.get_user_subscription(user)
            if not subscription:
                return {'usage_stats': {}}
            
            # Get recent access logs
            recent_logs = SignalAccessLog.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=30)
            )
            
            # Calculate statistics
            total_accesses = recent_logs.count()
            hybrid_accesses = recent_logs.filter(is_hybrid=True).count()
            api_accesses = recent_logs.filter(access_type='API').count()
            
            return {
                'usage_stats': {
                    'signals_used_today': subscription.signals_used_today,
                    'signals_used_this_month': subscription.signals_used_this_month,
                    'daily_limit': subscription.tier.max_signals_per_day,
                    'total_accesses_30d': total_accesses,
                    'hybrid_accesses_30d': hybrid_accesses,
                    'api_accesses_30d': api_accesses,
                    'days_remaining': subscription.days_remaining
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            return {'usage_stats': {}}
    
    def reset_daily_usage(self, user: User) -> bool:
        """Reset daily usage counter for user"""
        try:
            subscription = self.get_user_subscription(user)
            if subscription:
                subscription.reset_daily_usage()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error resetting daily usage: {e}")
            return False
    
    def get_subscription_revenue_stats(self) -> Dict[str, Any]:
        """Get subscription revenue statistics"""
        try:
            active_subscriptions = UserSubscription.objects.filter(
                status='ACTIVE',
                end_date__gt=timezone.now()
            )
            
            total_revenue = 0
            tier_counts = {}
            
            for subscription in active_subscriptions:
                if subscription.billing_cycle == 'MONTHLY':
                    revenue = float(subscription.tier.monthly_price)
                else:
                    revenue = float(subscription.tier.yearly_price) / 12
                
                total_revenue += revenue
                
                tier_name = subscription.tier.name
                tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1
            
            return {
                'total_active_subscriptions': active_subscriptions.count(),
                'monthly_recurring_revenue': total_revenue,
                'tier_distribution': tier_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue stats: {e}")
            return {}
    
    def check_subscription_expiry(self) -> List[UserSubscription]:
        """Check for expiring subscriptions"""
        try:
            expiry_threshold = timezone.now() + timedelta(days=7)
            
            expiring_subscriptions = UserSubscription.objects.filter(
                status='ACTIVE',
                end_date__lte=expiry_threshold,
                end_date__gt=timezone.now()
            )
            
            return list(expiring_subscriptions)
            
        except Exception as e:
            logger.error(f"Error checking subscription expiry: {e}")
            return []
    
    def cancel_subscription(self, user: User) -> bool:
        """Cancel user's subscription"""
        try:
            subscription = self.get_user_subscription(user)
            if subscription:
                subscription.status = 'CANCELLED'
                subscription.save()
                logger.info(f"Cancelled subscription for user {user.username}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            return False