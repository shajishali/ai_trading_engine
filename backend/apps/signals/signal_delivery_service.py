"""
Phase 4 Signal Delivery Service
Delivers signals via API, dashboard, webhooks, and alerts
"""

import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from apps.signals.models import TradingSignal, SignalAlert
from apps.signals.subscription_service import SubscriptionService
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class SignalDeliveryService:
    """Service for delivering signals through various channels"""
    
    def __init__(self):
        self.logger = logger
        self.subscription_service = SubscriptionService()
    
    def deliver_signal(self, signal: TradingSignal, user: Optional[object] = None,
                      delivery_channels: List[str] = None) -> Dict[str, Any]:
        """
        Deliver signal through specified channels
        
        Args:
            signal: TradingSignal to deliver
            user: User requesting the signal (for subscription checks)
            delivery_channels: List of channels ['api', 'dashboard', 'webhook', 'email', 'telegram']
            
        Returns:
            Dictionary with delivery results
        """
        try:
            if delivery_channels is None:
                delivery_channels = ['api', 'dashboard']
            
            delivery_results = {
                'signal_id': signal.id,
                'delivery_channels': delivery_channels,
                'results': {},
                'timestamp': timezone.now().isoformat()
            }
            
            # Check user access if user provided
            if user:
                access_check = self.subscription_service.can_user_access_signal(user, signal)
                if not access_check['can_access']:
                    return {
                        'error': 'Access denied',
                        'reason': access_check['reason'],
                        'tier': access_check.get('tier')
                    }
            
            # Deliver through each channel
            for channel in delivery_channels:
                try:
                    if channel == 'api':
                        result = self._deliver_via_api(signal, user)
                    elif channel == 'dashboard':
                        result = self._deliver_via_dashboard(signal)
                    elif channel == 'webhook':
                        result = self._deliver_via_webhook(signal, user)
                    elif channel == 'email':
                        result = self._deliver_via_email(signal, user)
                    elif channel == 'telegram':
                        result = self._deliver_via_telegram(signal, user)
                    else:
                        result = {'error': f'Unknown channel: {channel}'}
                    
                    delivery_results['results'][channel] = result
                    
                except Exception as e:
                    self.logger.error(f"Error delivering via {channel}: {e}")
                    delivery_results['results'][channel] = {'error': str(e)}
            
            # Log signal access if user provided
            if user:
                self.subscription_service.log_signal_access(
                    user=user,
                    signal=signal,
                    access_type='API' if 'api' in delivery_channels else 'Dashboard'
                )
            
            return delivery_results
            
        except Exception as e:
            self.logger.error(f"Error delivering signal: {e}")
            return {'error': str(e)}
    
    def _deliver_via_api(self, signal: TradingSignal, user: Optional[object] = None) -> Dict[str, Any]:
        """Deliver signal via API response"""
        try:
            # Prepare API response data
            signal_data = {
                'id': signal.id,
                'symbol': signal.symbol.symbol,
                'signal_type': signal.signal_type.name,
                'timeframe': signal.timeframe,
                'price': float(signal.price) if signal.price else None,
                'strength': signal.strength_score,
                'confidence': signal.confidence_score,
                'is_hybrid': signal.is_hybrid,
                'created_at': signal.created_at.isoformat(),
                'metadata': signal.metadata or {}
            }
            
            # Add hybrid-specific data
            if signal.is_hybrid and signal.metadata:
                signal_data['hybrid_data'] = {
                    'rule_strength': signal.metadata.get('rule_strength'),
                    'ml_strength': signal.metadata.get('ml_strength'),
                    'agreement_level': signal.metadata.get('agreement_level'),
                    'position_size': signal.metadata.get('position_size'),
                    'ml_model': signal.metadata.get('ml_model')
                }
            
            return {
                'status': 'success',
                'data': signal_data,
                'delivery_method': 'api_response'
            }
            
        except Exception as e:
            self.logger.error(f"Error delivering via API: {e}")
            return {'error': str(e)}
    
    def _deliver_via_dashboard(self, signal: TradingSignal) -> Dict[str, Any]:
        """Deliver signal via dashboard (WebSocket or real-time update)"""
        try:
            # This would typically trigger a WebSocket message or real-time update
            # For now, we'll just log the delivery
            
            dashboard_data = {
                'signal_id': signal.id,
                'symbol': signal.symbol.symbol,
                'signal_type': signal.signal_type.name,
                'strength': signal.strength_score,
                'confidence': signal.confidence_score,
                'is_hybrid': signal.is_hybrid,
                'timestamp': signal.created_at.isoformat()
            }
            
            # In a real implementation, this would send via WebSocket
            # await websocket.send(json.dumps(dashboard_data))
            
            return {
                'status': 'success',
                'data': dashboard_data,
                'delivery_method': 'dashboard_websocket'
            }
            
        except Exception as e:
            self.logger.error(f"Error delivering via dashboard: {e}")
            return {'error': str(e)}
    
    def _deliver_via_webhook(self, signal: TradingSignal, user: Optional[object] = None) -> Dict[str, Any]:
        """Deliver signal via webhook"""
        try:
            if not user:
                return {'error': 'User required for webhook delivery'}
            
            # Get user's webhook URL (this would be stored in user profile)
            webhook_url = getattr(user, 'webhook_url', None)
            
            if not webhook_url:
                return {'error': 'No webhook URL configured for user'}
            
            # Prepare webhook payload
            payload = {
                'signal_id': signal.id,
                'symbol': signal.symbol.symbol,
                'signal_type': signal.signal_type.name,
                'timeframe': signal.timeframe,
                'price': float(signal.price) if signal.price else None,
                'strength': signal.strength_score,
                'confidence': signal.confidence_score,
                'is_hybrid': signal.is_hybrid,
                'timestamp': signal.created_at.isoformat(),
                'metadata': signal.metadata or {}
            }
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'webhook_url': webhook_url,
                    'response_status': response.status_code,
                    'delivery_method': 'webhook'
                }
            else:
                return {
                    'status': 'failed',
                    'webhook_url': webhook_url,
                    'response_status': response.status_code,
                    'error': response.text,
                    'delivery_method': 'webhook'
                }
                
        except Exception as e:
            self.logger.error(f"Error delivering via webhook: {e}")
            return {'error': str(e)}
    
    def _deliver_via_email(self, signal: TradingSignal, user: Optional[object] = None) -> Dict[str, Any]:
        """Deliver signal via email"""
        try:
            if not user:
                return {'error': 'User required for email delivery'}
            
            # Get user's email
            user_email = getattr(user, 'email', None)
            
            if not user_email:
                return {'error': 'No email address for user'}
            
            # Prepare email content
            subject = f"Trading Signal Alert: {signal.symbol.symbol} {signal.signal_type.name}"
            
            # Create email body
            body = self._create_email_body(signal)
            
            # Send email
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                fail_silently=False
            )
            
            return {
                'status': 'success',
                'email': user_email,
                'subject': subject,
                'delivery_method': 'email'
            }
            
        except Exception as e:
            self.logger.error(f"Error delivering via email: {e}")
            return {'error': str(e)}
    
    def _deliver_via_telegram(self, signal: TradingSignal, user: Optional[object] = None) -> Dict[str, Any]:
        """Deliver signal via Telegram"""
        try:
            if not user:
                return {'error': 'User required for Telegram delivery'}
            
            # Get user's Telegram chat ID
            telegram_chat_id = getattr(user, 'telegram_chat_id', None)
            
            if not telegram_chat_id:
                return {'error': 'No Telegram chat ID for user'}
            
            # Get Telegram bot token
            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
            
            if not bot_token:
                return {'error': 'Telegram bot token not configured'}
            
            # Prepare Telegram message
            message = self._create_telegram_message(signal)
            
            # Send Telegram message
            telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                'chat_id': telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(telegram_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'telegram_chat_id': telegram_chat_id,
                    'delivery_method': 'telegram'
                }
            else:
                return {
                    'status': 'failed',
                    'telegram_chat_id': telegram_chat_id,
                    'response_status': response.status_code,
                    'error': response.text,
                    'delivery_method': 'telegram'
                }
                
        except Exception as e:
            self.logger.error(f"Error delivering via Telegram: {e}")
            return {'error': str(e)}
    
    def _create_email_body(self, signal: TradingSignal) -> str:
        """Create email body for signal"""
        try:
            body = f"""
Trading Signal Alert

Symbol: {signal.symbol.symbol}
Signal Type: {signal.signal_type.name}
Timeframe: {signal.timeframe}
Price: {signal.price if signal.price else 'N/A'}
Strength: {signal.strength_score:.2f}
Confidence: {signal.confidence_score:.2f}
Timestamp: {signal.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

"""
            
            if signal.is_hybrid and signal.metadata:
                metadata = signal.metadata
                body += f"""
Hybrid Signal Details:
- Rule-based Strength: {metadata.get('rule_strength', 'N/A')}
- ML Strength: {metadata.get('ml_strength', 'N/A')}
- Agreement Level: {metadata.get('agreement_level', 'N/A')}
- Position Size: {metadata.get('position_size', 'N/A')}
- ML Model: {metadata.get('ml_model', 'N/A')}

"""
            
            body += """
This is an automated signal from the AI Trading Engine.
Please do your own research before making trading decisions.

Best regards,
AI Trading Engine Team
"""
            
            return body
            
        except Exception as e:
            self.logger.error(f"Error creating email body: {e}")
            return "Trading signal alert - check dashboard for details."
    
    def _create_telegram_message(self, signal: TradingSignal) -> str:
        """Create Telegram message for signal"""
        try:
            # Telegram message with HTML formatting
            message = f"""
🚨 <b>Trading Signal Alert</b>

📊 <b>Symbol:</b> {signal.symbol.symbol}
📈 <b>Signal:</b> {signal.signal_type.name}
⏰ <b>Timeframe:</b> {signal.timeframe}
💰 <b>Price:</b> {signal.price if signal.price else 'N/A'}
💪 <b>Strength:</b> {signal.strength_score:.2f}
🎯 <b>Confidence:</b> {signal.confidence_score:.2f}
🕐 <b>Time:</b> {signal.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            
            if signal.is_hybrid and signal.metadata:
                metadata = signal.metadata
                message += f"""
🤖 <b>Hybrid Signal Details:</b>
• Rule Strength: {metadata.get('rule_strength', 'N/A')}
• ML Strength: {metadata.get('ml_strength', 'N/A')}
• Agreement: {metadata.get('agreement_level', 'N/A')}
• Position Size: {metadata.get('position_size', 'N/A')}
• ML Model: {metadata.get('ml_model', 'N/A')}
"""
            
            message += """
⚠️ <i>Automated signal - please do your own research before trading.</i>

🤖 AI Trading Engine
"""
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error creating Telegram message: {e}")
            return f"Trading Signal: {signal.symbol.symbol} {signal.signal_type.name}"
    
    def create_signal_alert(self, signal: TradingSignal, user: object,
                          alert_type: str = 'email') -> Optional[SignalAlert]:
        """Create a signal alert for user"""
        try:
            alert = SignalAlert.objects.create(
                user=user,
                signal=signal,
                alert_type=alert_type,
                status='PENDING',
                message=f"Signal alert for {signal.symbol.symbol} {signal.signal_type.name}"
            )
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error creating signal alert: {e}")
            return None
    
    def process_pending_alerts(self) -> Dict[str, Any]:
        """Process all pending signal alerts"""
        try:
            pending_alerts = SignalAlert.objects.filter(
                status='PENDING',
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            results = {
                'total_alerts': pending_alerts.count(),
                'processed': 0,
                'failed': 0,
                'errors': []
            }
            
            for alert in pending_alerts:
                try:
                    # Determine delivery channel based on alert type
                    if alert.alert_type == 'email':
                        delivery_result = self._deliver_via_email(alert.signal, alert.user)
                    elif alert.alert_type == 'telegram':
                        delivery_result = self._deliver_via_telegram(alert.signal, alert.user)
                    elif alert.alert_type == 'webhook':
                        delivery_result = self._deliver_via_webhook(alert.signal, alert.user)
                    else:
                        delivery_result = {'error': f'Unknown alert type: {alert.alert_type}'}
                    
                    # Update alert status
                    if delivery_result.get('status') == 'success':
                        alert.status = 'SENT'
                        alert.sent_at = timezone.now()
                        results['processed'] += 1
                    else:
                        alert.status = 'FAILED'
                        alert.error_message = delivery_result.get('error', 'Unknown error')
                        results['failed'] += 1
                        results['errors'].append(f"Alert {alert.id}: {delivery_result.get('error')}")
                    
                    alert.save()
                    
                except Exception as e:
                    alert.status = 'FAILED'
                    alert.error_message = str(e)
                    alert.save()
                    
                    results['failed'] += 1
                    results['errors'].append(f"Alert {alert.id}: {str(e)}")
            
            self.logger.info(f"Processed {results['processed']} alerts, {results['failed']} failed")
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing pending alerts: {e}")
            return {'error': str(e)}
    
    def get_delivery_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get delivery statistics for the specified period"""
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # Get signal alerts in the period
            alerts = SignalAlert.objects.filter(created_at__gte=start_date)
            
            # Calculate statistics
            total_alerts = alerts.count()
            sent_alerts = alerts.filter(status='SENT').count()
            failed_alerts = alerts.filter(status='FAILED').count()
            pending_alerts = alerts.filter(status='PENDING').count()
            
            # Alert type breakdown
            alert_types = {}
            for alert in alerts:
                alert_type = alert.alert_type
                alert_types[alert_type] = alert_types.get(alert_type, 0) + 1
            
            # Daily breakdown
            daily_stats = {}
            for alert in alerts:
                date = alert.created_at.date()
                if date not in daily_stats:
                    daily_stats[date] = {'total': 0, 'sent': 0, 'failed': 0}
                
                daily_stats[date]['total'] += 1
                if alert.status == 'SENT':
                    daily_stats[date]['sent'] += 1
                elif alert.status == 'FAILED':
                    daily_stats[date]['failed'] += 1
            
            return {
                'period_days': days,
                'total_alerts': total_alerts,
                'sent_alerts': sent_alerts,
                'failed_alerts': failed_alerts,
                'pending_alerts': pending_alerts,
                'success_rate': (sent_alerts / total_alerts * 100) if total_alerts > 0 else 0,
                'alert_types': alert_types,
                'daily_stats': daily_stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting delivery statistics: {e}")
            return {'error': str(e)}

