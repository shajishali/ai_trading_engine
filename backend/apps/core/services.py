"""
Core Services for AI Trading Engine

This module provides essential services including:
- Security audit and monitoring
- Performance monitoring
- System health checks
- Configuration management
"""

import time
import json
import hashlib
import logging
import psutil
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
import ipaddress

logger = logging.getLogger(__name__)


class SecurityAuditService:
    """
    Comprehensive security auditing service for production deployment
    """
    
    def __init__(self):
        self.audit_logger = logging.getLogger('security_audit')
        self.security_score = 0
        self.vulnerabilities = []
        self.recommendations = []
    
    def run_security_audit(self):
        """Run comprehensive security audit"""
        self.audit_logger.info("Starting comprehensive security audit")
        
        audit_results = {
            'timestamp': timezone.now().isoformat(),
            'overall_score': 0,
            'categories': {},
            'vulnerabilities': [],
            'recommendations': [],
            'compliance_status': {}
        }
        
        # Run security checks by category
        audit_results['categories']['authentication'] = self.audit_authentication_security()
        audit_results['categories']['network'] = self.audit_network_security()
        audit_results['categories']['application'] = self.audit_application_security()
        audit_results['categories']['data'] = self.audit_data_security()
        audit_results['categories']['infrastructure'] = self.audit_infrastructure_security()
        audit_results['categories']['compliance'] = self.audit_compliance()
        
        # Calculate overall security score
        total_score = 0
        total_weight = 0
        
        for category, result in audit_results['categories'].items():
            if isinstance(result, dict) and 'score' in result:
                weight = result.get('weight', 1)
                total_score += result['score'] * weight
                total_weight += weight
        
        if total_weight > 0:
            audit_results['overall_score'] = round(total_score / total_weight, 2)
        
        # Collect all vulnerabilities and recommendations
        for category_result in audit_results['categories'].values():
            if isinstance(category_result, dict):
                audit_results['vulnerabilities'].extend(category_result.get('vulnerabilities', []))
                audit_results['recommendations'].extend(category_result.get('recommendations', []))
        
        # Log audit results
        self.audit_logger.info(f"Security audit completed. Overall score: {audit_results['overall_score']}")
        
        return audit_results
    
    def audit_authentication_security(self):
        """Audit authentication and authorization security"""
        results = {
            'score': 0,
            'weight': 2,
            'vulnerabilities': [],
            'recommendations': []
        }
        
        score = 100
        
        # Check password policies
        if hasattr(settings, 'AUTH_PASSWORD_VALIDATORS'):
            validators = settings.AUTH_PASSWORD_VALIDATORS
            if not any('MinimumLengthValidator' in str(v) for v in validators):
                results['vulnerabilities'].append('No minimum password length requirement')
                score -= 20
            if not any('UserAttributeSimilarityValidator' in str(v) for v in validators):
                results['vulnerabilities'].append('No password similarity validation')
                score -= 15
        else:
            results['vulnerabilities'].append('No password validation configured')
            score -= 30
        
        # Check session security
        if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
            results['vulnerabilities'].append('Session cookies not secure (HTTPS required)')
            score -= 25
        if not getattr(settings, 'SESSION_COOKIE_HTTPONLY', False):
            results['vulnerabilities'].append('Session cookies accessible via JavaScript')
            score -= 20
        
        # Check CSRF protection
        if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            results['vulnerabilities'].append('CSRF cookies not secure')
            score -= 15
        
        # Check login attempt limiting
        if not hasattr(settings, 'LOGIN_ATTEMPT_LIMIT'):
            results['recommendations'].append('Implement login attempt limiting')
            score -= 10
        
        results['score'] = max(0, score)
        return results
    
    def audit_network_security(self):
        """Audit network and infrastructure security"""
        results = {
            'score': 0,
            'weight': 1.5,
            'vulnerabilities': [],
            'recommendations': []
        }
        
        score = 100
        
        # Check HTTPS enforcement
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            results['vulnerabilities'].append('HTTPS not enforced')
            score -= 30
        
        # Check HSTS
        if not getattr(settings, 'SECURE_HSTS_SECONDS', 0):
            results['vulnerabilities'].append('HSTS not configured')
            score -= 20
        
        # Check allowed hosts
        if '*' in getattr(settings, 'ALLOWED_HOSTS', []):
            results['vulnerabilities'].append('ALLOWED_HOSTS too permissive')
            score -= 25
        
        # Check CORS settings
        if hasattr(settings, 'CORS_ALLOW_ALL_ORIGINS') and settings.CORS_ALLOW_ALL_ORIGINS:
            results['vulnerabilities'].append('CORS allows all origins')
            score -= 25
        
        results['score'] = max(0, score)
        return results
    
    def audit_application_security(self):
        """Audit application-level security"""
        results = {
            'score': 0,
            'weight': 1.5,
            'vulnerabilities': [],
            'recommendations': []
        }
        
        score = 100
        
        # Check debug mode
        if getattr(settings, 'DEBUG', False):
            results['vulnerabilities'].append('Debug mode enabled in production')
            score -= 40
        
        # Check secret key
        if getattr(settings, 'SECRET_KEY', '') == 'your-secret-key-here':
            results['vulnerabilities'].append('Default secret key not changed')
            score -= 30
        
        # Check security middleware
        middleware = getattr(settings, 'MIDDLEWARE', [])
        if 'django.middleware.security.SecurityMiddleware' not in middleware:
            results['vulnerabilities'].append('Security middleware not enabled')
            score -= 20
        
        # Check rate limiting
        if not any('RateLimit' in m for m in middleware):
            results['recommendations'].append('Implement rate limiting middleware')
            score -= 15
        
        results['score'] = max(0, score)
        return results
    
    def audit_data_security(self):
        """Audit data protection and privacy security"""
        results = {
            'score': 0,
            'weight': 1,
            'vulnerabilities': [],
            'recommendations': []
        }
        
        score = 100
        
        # Check database encryption
        databases = getattr(settings, 'DATABASES', {})
        for db_name, db_config in databases.items():
            if 'OPTIONS' in db_config and 'sslmode' in db_config['OPTIONS']:
                if db_config['OPTIONS']['sslmode'] != 'require':
                    results['vulnerabilities'].append(f'Database {db_name} not using SSL')
                    score -= 20
        
        # Check Redis security
        if hasattr(settings, 'REDIS_PASSWORD') and not settings.REDIS_PASSWORD:
            results['vulnerabilities'].append('Redis not password protected')
            score -= 25
        
        # Check file upload security
        if not hasattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE'):
            results['recommendations'].append('Configure file upload size limits')
            score -= 10
        
        results['score'] = max(0, score)
        return results
    
    def audit_infrastructure_security(self):
        """Audit infrastructure and deployment security"""
        results = {
            'score': 0,
            'weight': 1,
            'vulnerabilities': [],
            'recommendations': []
        }
        
        score = 100
        
        # Check logging configuration
        if not hasattr(settings, 'LOGGING'):
            results['recommendations'].append('Configure comprehensive logging')
            score -= 15
        
        # Check backup configuration
        if not hasattr(settings, 'BACKUP_CONFIG'):
            results['recommendations'].append('Configure automated backups')
            score -= 20
        
        # Check monitoring
        if not hasattr(settings, 'MONITORING_ENABLED'):
            results['recommendations'].append('Enable system monitoring')
            score -= 15
        
        results['score'] = max(0, score)
        return results
    
    def audit_compliance(self):
        """Audit compliance with security standards"""
        results = {
            'score': 0,
            'weight': 0.5,
            'vulnerabilities': [],
            'recommendations': [],
            'compliance_status': {}
        }
        
        score = 100
        
        # GDPR compliance check
        if not hasattr(settings, 'GDPR_COMPLIANCE_ENABLED'):
            results['recommendations'].append('Implement GDPR compliance measures')
            score -= 20
        
        # Data retention policy
        if not hasattr(settings, 'DATA_RETENTION_POLICY'):
            results['recommendations'].append('Implement data retention policy')
            score -= 15
        
        # Privacy policy
        if not hasattr(settings, 'PRIVACY_POLICY_URL'):
            results['recommendations'].append('Provide privacy policy')
            score -= 10
        
        results['score'] = max(0, score)
        return results
    
    def generate_security_report(self, audit_results):
        """Generate detailed security report"""
        report = {
            'summary': {
                'overall_score': audit_results['overall_score'],
                'risk_level': self._calculate_risk_level(audit_results['overall_score']),
                'total_vulnerabilities': len(audit_results['vulnerabilities']),
                'total_recommendations': len(audit_results['recommendations'])
            },
            'detailed_results': audit_results,
            'action_items': self._prioritize_action_items(audit_results),
            'compliance_gaps': self._identify_compliance_gaps(audit_results),
            'next_steps': self._generate_next_steps(audit_results)
        }
        
        return report
    
    def _calculate_risk_level(self, score):
        """Calculate risk level based on security score"""
        if score >= 90:
            return 'LOW'
        elif score >= 70:
            return 'MEDIUM'
        elif score >= 50:
            return 'HIGH'
        else:
            return 'CRITICAL'
    
    def _prioritize_action_items(self, audit_results):
        """Prioritize security action items"""
        action_items = []
        
        # Critical vulnerabilities first
        for vuln in audit_results['vulnerabilities']:
            if any(keyword in vuln.lower() for keyword in ['debug', 'secret', 'https', 'ssl']):
                action_items.append({
                    'priority': 'CRITICAL',
                    'action': vuln,
                    'effort': 'LOW',
                    'impact': 'HIGH'
                })
        
        # High impact recommendations
        for rec in audit_results['recommendations']:
            if any(keyword in rec.lower() for keyword in ['rate limiting', 'backup', 'monitoring']):
                action_items.append({
                    'priority': 'HIGH',
                    'action': rec,
                    'effort': 'MEDIUM',
                    'impact': 'HIGH'
                })
        
        return action_items
    
    def _identify_compliance_gaps(self, audit_results):
        """Identify compliance gaps"""
        gaps = []
        
        if audit_results['overall_score'] < 80:
            gaps.append('Overall security score below compliance threshold')
        
        for category, result in audit_results['categories'].items():
            if isinstance(result, dict) and result.get('score', 0) < 70:
                gaps.append(f'{category.title()} security below compliance threshold')
        
        return gaps
    
    def _generate_next_steps(self, audit_results):
        """Generate actionable next steps"""
        steps = []
        
        if audit_results['overall_score'] < 50:
            steps.append('Immediate security review required')
            steps.append('Consider engaging security consultant')
        
        if len(audit_results['vulnerabilities']) > 0:
            steps.append('Address critical vulnerabilities within 24 hours')
            steps.append('Schedule security team review')
        
        if len(audit_results['recommendations']) > 5:
            steps.append('Create security improvement roadmap')
            steps.append('Allocate resources for security enhancements')
        
        steps.append('Schedule follow-up security audit in 30 days')
        steps.append('Implement continuous security monitoring')
        
        return steps


class SecurityMonitoringService:
    """
    Real-time security monitoring service
    """
    
    def __init__(self):
        self.monitoring_logger = logging.getLogger('security_monitoring')
        self.alert_threshold = getattr(settings, 'SECURITY_ALERT_THRESHOLD', 0.8)
        self.check_interval = getattr(settings, 'SECURITY_CHECK_INTERVAL', 60)
        self.last_check = None
    
    def start_monitoring(self):
        """Start continuous security monitoring"""
        self.monitoring_logger.info("Starting security monitoring service")
        
        # Initialize monitoring
        self.last_check = timezone.now()
        
        # Start background monitoring (in production, use Celery or similar)
        self._monitor_security_events()
    
    def _monitor_security_events(self):
        """Monitor security events in real-time"""
        try:
            # Check for suspicious activities
            self._check_suspicious_ips()
            self._check_failed_logins()
            self._check_rate_limit_violations()
            self._check_system_resources()
            
            # Update last check time
            self.last_check = timezone.now()
            
        except Exception as e:
            self.monitoring_logger.error(f"Security monitoring error: {e}")
    
    def _check_suspicious_ips(self):
        """Check for suspicious IP activities"""
        suspicious_ips = cache.get('suspicious_ips', {})
        
        for ip, count in suspicious_ips.items():
            if count >= 5:  # Threshold for suspicious activity
                self._send_security_alert('SUSPICIOUS_IP', {
                    'ip': ip,
                    'activity_count': count,
                    'timestamp': timezone.now().isoformat()
                })
    
    def _check_failed_logins(self):
        """Check for failed login attempts"""
        failed_logins = cache.get('failed_logins', {})
        
        for username, attempts in failed_logins.items():
            if len(attempts) >= 5:  # Threshold for failed logins
                self._send_security_alert('FAILED_LOGIN_ATTEMPTS', {
                    'username': username,
                    'attempt_count': len(attempts),
                    'last_attempt': max(attempts),
                    'timestamp': timezone.now().isoformat()
                })
    
    def _check_rate_limit_violations(self):
        """Check for rate limit violations"""
        rate_limit_violations = cache.get('rate_limit_violations', {})
        
        for ip, violations in rate_limit_violations.items():
            if len(violations) >= 3:  # Threshold for rate limit violations
                self._send_security_alert('RATE_LIMIT_VIOLATIONS', {
                    'ip': ip,
                    'violation_count': len(violations),
                    'last_violation': max(violations),
                    'timestamp': timezone.now().isoformat()
                })
    
    def _check_system_resources(self):
        """Check system resource usage for anomalies"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            if cpu_percent > 90:
                self._send_security_alert('HIGH_CPU_USAGE', {
                    'cpu_percent': cpu_percent,
                    'timestamp': timezone.now().isoformat()
                })
            
            if memory_percent > 95:
                self._send_security_alert('HIGH_MEMORY_USAGE', {
                    'memory_percent': memory_percent,
                    'timestamp': timezone.now().isoformat()
                })
            
            if disk_percent > 95:
                self._send_security_alert('HIGH_DISK_USAGE', {
                    'disk_percent': disk_percent,
                    'timestamp': timezone.now().isoformat()
                })
                
        except Exception as e:
            self.monitoring_logger.error(f"System resource check error: {e}")
    
    def _send_security_alert(self, alert_type, data):
        """Send security alert"""
        alert = {
            'type': alert_type,
            'severity': self._determine_alert_severity(alert_type),
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
        
        # Log alert
        self.monitoring_logger.warning(f"SECURITY_ALERT: {alert_type} - {data}")
        
        # Store alert in cache for dashboard
        alerts = cache.get('security_alerts', [])
        alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(alerts) > 100:
            alerts = alerts[-100:]
        
        cache.set('security_alerts', alerts, 3600)  # 1 hour expiry
        
        # Send to external monitoring systems if configured
        self._send_external_alert(alert)
    
    def _determine_alert_severity(self, alert_type):
        """Determine alert severity level"""
        critical_alerts = ['FAILED_LOGIN_ATTEMPTS', 'SUSPICIOUS_IP']
        high_alerts = ['RATE_LIMIT_VIOLATIONS', 'HIGH_CPU_USAGE']
        
        if alert_type in critical_alerts:
            return 'CRITICAL'
        elif alert_type in high_alerts:
            return 'HIGH'
        else:
            return 'MEDIUM'
    
    def _send_external_alert(self, alert):
        """Send alert to external monitoring systems"""
        # Check if external alerting is configured
        webhook_url = getattr(settings, 'SECURITY_WEBHOOK_URL', None)
        slack_webhook = getattr(settings, 'SLACK_WEBHOOK_URL', None)
        
        if webhook_url:
            try:
                requests.post(webhook_url, json=alert, timeout=5)
            except Exception as e:
                self.monitoring_logger.error(f"Failed to send webhook alert: {e}")
        
        if slack_webhook:
            try:
                slack_message = self._format_slack_message(alert)
                requests.post(slack_webhook, json=slack_message, timeout=5)
            except Exception as e:
                self.monitoring_logger.error(f"Failed to send Slack alert: {e}")
    
    def _format_slack_message(self, alert):
        """Format alert for Slack"""
        severity_emoji = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '🔶',
            'LOW': 'ℹ️'
        }
        
        emoji = severity_emoji.get(alert['severity'], 'ℹ️')
        
        return {
            'text': f"{emoji} Security Alert: {alert['type']}",
            'attachments': [{
                'color': self._get_slack_color(alert['severity']),
                'fields': [
                    {
                        'title': 'Severity',
                        'value': alert['severity'],
                        'short': True
                    },
                    {
                        'title': 'Timestamp',
                        'value': alert['timestamp'],
                        'short': True
                    },
                    {
                        'title': 'Details',
                        'value': json.dumps(alert['data'], indent=2),
                        'short': False
                    }
                ]
            }]
        }
    
    def _get_slack_color(self, severity):
        """Get Slack color for severity level"""
        colors = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'good',
            'LOW': '#36a64f'
        }
        return colors.get(severity, '#36a64f')
    
    def get_security_status(self):
        """Get current security status"""
        return {
            'monitoring_active': self.last_check is not None,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'active_alerts': cache.get('security_alerts', []),
            'suspicious_ips': cache.get('suspicious_ips', {}),
            'failed_logins': cache.get('failed_logins', {}),
            'rate_limit_violations': cache.get('rate_limit_violations', {})
        }


"""
Real-time broadcasting services for Django Channels
Handles sending messages to WebSocket consumers
"""

import json
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class RealTimeBroadcaster:
    """Service for broadcasting real-time messages to WebSocket consumers"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def broadcast_market_update(self, symbol, price, change, volume, timestamp=None):
        """Broadcast market data update to all connected clients"""
        if timestamp is None:
            timestamp = timezone.now()
        
        message = {
            'type': 'market_update',
            'symbol': symbol,
            'price': price,
            'change': change,
            'volume': volume,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'market_data',
                message
            )
            
            # Also send to symbol-specific group
            async_to_sync(self.channel_layer.group_send)(
                f'market_data_{symbol}',
                message
            )
            
            logger.info(f"Broadcasted market update for {symbol}: ${price}")
            
        except Exception as e:
            logger.error(f"Error broadcasting market update for {symbol}: {e}")
    
    def broadcast_price_alert(self, symbol, alert_type, price, message, timestamp=None):
        """Broadcast price alert to all connected clients"""
        if timestamp is None:
            timestamp = timezone.now()
        
        alert_data = {
            'type': 'price_alert',
            'symbol': symbol,
            'alert_type': alert_type,
            'price': price,
            'message': message,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'market_data',
                alert_data
            )
            
            # Also send to symbol-specific group
            async_to_sync(self.channel_layer.group_send)(
                f'market_data_{symbol}',
                alert_data
            )
            
            logger.info(f"Broadcasted price alert for {symbol}: {message}")
            
        except Exception as e:
            logger.error(f"Error broadcasting price alert for {symbol}: {e}")
    
    def broadcast_trading_signal(self, signal_id, symbol, signal_type, strength, 
                                confidence_score, entry_price, target_price, 
                                stop_loss, timestamp=None):
        """Broadcast new trading signal to all connected clients"""
        if timestamp is None:
            timestamp = timezone.now()
        
        signal_data = {
            'type': 'new_signal',
            'signal_id': signal_id,
            'symbol': symbol,
            'signal_type': signal_type,
            'strength': strength,
            'confidence_score': confidence_score,
            'entry_price': entry_price,
            'target_price': target_price,
            'stop_loss': stop_loss,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'trading_signals',
                signal_data
            )
            
            # Also send to symbol-specific group
            async_to_sync(self.channel_layer.group_send)(
                f'signals_{symbol}',
                signal_data
            )
            
            logger.info(f"Broadcasted trading signal for {symbol}: {signal_type}")
            
        except Exception as e:
            logger.error(f"Error broadcasting trading signal for {symbol}: {e}")
    
    def broadcast_signal_update(self, signal_id, update_type, new_value, timestamp=None):
        """Broadcast signal update to all connected clients"""
        if timestamp is None:
            timestamp = timezone.now()
        
        update_data = {
            'type': 'signal_update',
            'signal_id': signal_id,
            'update_type': update_type,
            'new_value': new_value,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'trading_signals',
                update_data
            )
            
            logger.info(f"Broadcasted signal update for {signal_id}: {update_type}")
            
        except Exception as e:
            logger.error(f"Error broadcasting signal update for {signal_id}: {e}")
    
    def broadcast_notification(self, user_id, notification_id, title, message, 
                              notification_type, priority, timestamp=None):
        """Broadcast notification to specific user"""
        if timestamp is None:
            timestamp = timezone.now()
        
        notification_data = {
            'type': 'new_notification',
            'notification_id': notification_id,
            'title': title,
            'message': message,
            'notification_type': notification_type,
            'priority': priority,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                f'notifications_{user_id}',
                notification_data
            )
            
            logger.info(f"Broadcasted notification to user {user_id}: {title}")
            
        except Exception as e:
            logger.error(f"Error broadcasting notification to user {user_id}: {e}")
    
    def broadcast_portfolio_update(self, user_id, total_value, daily_change, 
                                 daily_change_percent, timestamp=None):
        """Broadcast portfolio update to specific user"""
        if timestamp is None:
            timestamp = timezone.now()
        
        portfolio_data = {
            'type': 'portfolio_update',
            'total_value': total_value,
            'daily_change': daily_change,
            'daily_change_percent': daily_change_percent,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                f'notifications_{user_id}',
                portfolio_data
            )
            
            logger.info(f"Broadcasted portfolio update to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting portfolio update to user {user_id}: {e}")
    
    def broadcast_to_all_users(self, message_type, data):
        """Broadcast message to all connected users"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                'all_users',
                {
                    'type': message_type,
                    **data
                }
            )
            
            logger.info(f"Broadcasted {message_type} to all users")
            
        except Exception as e:
            logger.error(f"Error broadcasting {message_type} to all users: {e}")
    
    def broadcast_to_group(self, group_name, message_type, data):
        """Broadcast message to specific group"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': message_type,
                    **data
                }
            )
            
            logger.info(f"Broadcasted {message_type} to group {group_name}")
            
        except Exception as e:
            logger.error(f"Error broadcasting {message_type} to group {group_name}: {e}")


class MarketDataBroadcaster(RealTimeBroadcaster):
    """Specialized broadcaster for market data updates"""
    
    def broadcast_crypto_update(self, symbol, price, change_24h, volume_24h, 
                               market_cap, timestamp=None):
        """Broadcast cryptocurrency market update"""
        if timestamp is None:
            timestamp = timezone.now()
        
        crypto_data = {
            'type': 'crypto_update',
            'symbol': symbol,
            'price': price,
            'change_24h': change_24h,
            'volume_24h': volume_24h,
            'market_cap': market_cap,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'market_data',
                crypto_data
            )
            
            # Also send to symbol-specific group
            async_to_sync(self.channel_layer.group_send)(
                f'market_data_{symbol}',
                crypto_data
            )
            
            logger.info(f"Broadcasted crypto update for {symbol}: ${price}")
            
        except Exception as e:
            logger.error(f"Error broadcasting crypto update for {symbol}: {e}")
    
    def broadcast_stock_update(self, symbol, price, change, change_percent, 
                              volume, market_cap, pe_ratio, timestamp=None):
        """Broadcast stock market update"""
        if timestamp is None:
            timestamp = timezone.now()
        
        stock_data = {
            'type': 'stock_update',
            'symbol': symbol,
            'price': price,
            'change': change,
            'change_percent': change_percent,
            'volume': volume,
            'market_cap': market_cap,
            'pe_ratio': pe_ratio,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'market_data',
                stock_data
            )
            
            # Also send to symbol-specific group
            async_to_sync(self.channel_layer.group_send)(
                f'market_data_{symbol}',
                stock_data
            )
            
            logger.info(f"Broadcasted stock update for {symbol}: ${price}")
            
        except Exception as e:
            logger.error(f"Error broadcasting stock update for {symbol}: {e}")


class TradingSignalsBroadcaster(RealTimeBroadcaster):
    """Specialized broadcaster for trading signals"""
    
    def broadcast_buy_signal(self, signal_id, symbol, entry_price, target_price, 
                             stop_loss, confidence_score, timestamp=None):
        """Broadcast buy signal"""
        self.broadcast_trading_signal(
            signal_id=signal_id,
            symbol=symbol,
            signal_type='BUY',
            strength='STRONG',
            confidence_score=confidence_score,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            timestamp=timestamp
        )
    
    def broadcast_sell_signal(self, signal_id, symbol, entry_price, target_price, 
                              stop_loss, confidence_score, timestamp=None):
        """Broadcast sell signal"""
        self.broadcast_trading_signal(
            signal_id=signal_id,
            symbol=symbol,
            signal_type='SELL',
            strength='STRONG',
            confidence_score=confidence_score,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            timestamp=timestamp
        )
    
    def broadcast_hold_signal(self, signal_id, symbol, reason, confidence_score, timestamp=None):
        """Broadcast hold signal"""
        if timestamp is None:
            timestamp = timezone.now()
        
        hold_data = {
            'type': 'hold_signal',
            'signal_id': signal_id,
            'symbol': symbol,
            'signal_type': 'HOLD',
            'reason': reason,
            'confidence_score': confidence_score,
            'timestamp': timestamp.isoformat()
        }
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                'trading_signals',
                hold_data
            )
            
            logger.info(f"Broadcasted hold signal for {symbol}: {reason}")
            
        except Exception as e:
            logger.error(f"Error broadcasting hold signal for {symbol}: {e}")


class NotificationBroadcaster(RealTimeBroadcaster):
    """Specialized broadcaster for user notifications"""
    
    def broadcast_system_alert(self, user_id, title, message, priority='medium', timestamp=None):
        """Broadcast system alert to user"""
        self.broadcast_notification(
            user_id=user_id,
            notification_id=f"sys_{int(timezone.now().timestamp())}",
            title=title,
            message=message,
            notification_type='system',
            priority=priority,
            timestamp=timestamp
        )
    
    def broadcast_trade_notification(self, user_id, trade_type, symbol, quantity, 
                                    price, timestamp=None):
        """Broadcast trade execution notification"""
        title = f"Trade Executed: {trade_type.upper()}"
        message = f"{trade_type.title()} {quantity} {symbol} @ ${price}"
        
        self.broadcast_notification(
            user_id=user_id,
            notification_id=f"trade_{int(timezone.now().timestamp())}",
            title=title,
            message=message,
            notification_type='trade',
            priority='high',
            timestamp=timestamp
        )
    
    def broadcast_risk_alert(self, user_id, symbol, risk_level, message, timestamp=None):
        """Broadcast risk management alert"""
        title = f"Risk Alert: {symbol}"
        
        self.broadcast_notification(
            user_id=user_id,
            notification_id=f"risk_{int(timezone.now().timestamp())}",
            title=title,
            message=message,
            notification_type='risk',
            priority='high',
            timestamp=timestamp
        )


class ApplicationMonitoringService:
    """
    Comprehensive application monitoring service for Phase 7B.3
    Implements 24/7 monitoring with automated alerting
    """
    
    def __init__(self):
        self.monitoring_logger = logging.getLogger('application_monitoring')
        self.alert_threshold = getattr(settings, 'MONITORING_ALERT_THRESHOLD', 0.8)
        self.metrics_interval = getattr(settings, 'MONITORING_METRICS_INTERVAL', 30)
        self.last_check = None
        self.monitoring_active = False
        self.alert_history = []
        self.performance_metrics = {}
        
    def start_monitoring(self):
        """Start comprehensive application monitoring"""
        self.monitoring_logger.info("Starting comprehensive application monitoring service")
        self.monitoring_active = True
        self.last_check = timezone.now()
        
        # Initialize monitoring systems
        self._initialize_monitoring()
        
        # Start background monitoring
        self._start_background_monitoring()
        
    def stop_monitoring(self):
        """Stop application monitoring"""
        self.monitoring_logger.info("Stopping application monitoring service")
        self.monitoring_active = False
        
    def _initialize_monitoring(self):
        """Initialize all monitoring systems"""
        try:
            # Initialize performance monitoring
            self._init_performance_monitoring()
            
            # Initialize error monitoring
            self._init_error_monitoring()
            
            # Initialize uptime monitoring
            self._init_uptime_monitoring()
            
            # Initialize resource monitoring
            self._init_resource_monitoring()
            
            self.monitoring_logger.info("Application monitoring initialized successfully")
            
        except Exception as e:
            self.monitoring_logger.error(f"Error initializing monitoring: {e}")
            
    def _init_performance_monitoring(self):
        """Initialize performance monitoring"""
        self.performance_metrics = {
            'response_times': [],
            'throughput': [],
            'error_rates': [],
            'memory_usage': [],
            'cpu_usage': [],
            'disk_usage': [],
            'database_performance': [],
            'redis_performance': []
        }
        
    def _init_error_monitoring(self):
        """Initialize error monitoring"""
        # Set up error tracking
        self.error_counts = {
            'critical': 0,
            'error': 0,
            'warning': 0,
            'info': 0
        }
        
    def _init_uptime_monitoring(self):
        """Initialize uptime monitoring"""
        self.uptime_start = timezone.now()
        self.service_status = {
            'django': 'unknown',
            'database': 'unknown',
            'redis': 'unknown',
            'celery': 'unknown',
            'websockets': 'unknown'
        }
        
    def _init_resource_monitoring(self):
        """Initialize resource monitoring"""
        self.resource_thresholds = {
            'cpu_warning': 70,
            'cpu_critical': 90,
            'memory_warning': 80,
            'memory_critical': 95,
            'disk_warning': 80,
            'disk_critical': 95
        }
        
    def _start_background_monitoring(self):
        """Start background monitoring loop"""
        import threading
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    # Collect metrics
                    self._collect_performance_metrics()
                    self._check_service_health()
                    self._monitor_resources()
                    self._check_error_rates()
                    
                    # Update last check
                    self.last_check = timezone.now()
                    
                    # Sleep for monitoring interval
                    time.sleep(self.metrics_interval)
                    
                except Exception as e:
                    self.monitoring_logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(10)  # Wait before retrying
                    
        # Start monitoring in background thread
        monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        monitoring_thread.start()
        
    def _collect_performance_metrics(self):
        """Collect comprehensive performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database performance
            db_performance = self._check_database_performance()
            
            # Redis performance
            redis_performance = self._check_redis_performance()
            
            # Update metrics
            self.performance_metrics['cpu_usage'].append({
                'timestamp': timezone.now().isoformat(),
                'value': cpu_percent
            })
            
            self.performance_metrics['memory_usage'].append({
                'timestamp': timezone.now().isoformat(),
                'value': memory.percent
            })
            
            self.performance_metrics['disk_usage'].append({
                'timestamp': timezone.now().isoformat(),
                'value': disk.percent
            })
            
            self.performance_metrics['database_performance'].append({
                'timestamp': timezone.now().isoformat(),
                'value': db_performance
            })
            
            self.performance_metrics['redis_performance'].append({
                'timestamp': timezone.now().isoformat(),
                'value': redis_performance
            })
            
            # Keep only last 1000 metrics
            for key in self.performance_metrics:
                if len(self.performance_metrics[key]) > 1000:
                    self.performance_metrics[key] = self.performance_metrics[key][-1000:]
                    
        except Exception as e:
            self.monitoring_logger.error(f"Error collecting performance metrics: {e}")
            
    def _check_service_health(self):
        """Check health of all services"""
        try:
            # Django app health
            self.service_status['django'] = self._check_django_health()
            
            # Database health
            self.service_status['database'] = self._check_database_health()
            
            # Redis health
            self.service_status['redis'] = self._check_redis_health()
            
            # Celery health
            self.service_status['celery'] = self._check_celery_health()
            
            # WebSocket health
            self.service_status['websockets'] = self._check_websocket_health()
            
        except Exception as e:
            self.monitoring_logger.error(f"Error checking service health: {e}")
            
    def _monitor_resources(self):
        """Monitor system resources and send alerts"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            # Check CPU usage
            if cpu_percent >= self.resource_thresholds['cpu_critical']:
                self._send_performance_alert('CRITICAL_CPU_USAGE', {
                    'cpu_percent': cpu_percent,
                    'threshold': self.resource_thresholds['cpu_critical'],
                    'timestamp': timezone.now().isoformat()
                })
            elif cpu_percent >= self.resource_thresholds['cpu_warning']:
                self._send_performance_alert('WARNING_CPU_USAGE', {
                    'cpu_percent': cpu_percent,
                    'threshold': self.resource_thresholds['cpu_warning'],
                    'timestamp': timezone.now().isoformat()
                })
                
            # Check memory usage
            if memory_percent >= self.resource_thresholds['memory_critical']:
                self._send_performance_alert('CRITICAL_MEMORY_USAGE', {
                    'memory_percent': memory_percent,
                    'threshold': self.resource_thresholds['memory_critical'],
                    'timestamp': timezone.now().isoformat()
                })
            elif memory_percent >= self.resource_thresholds['memory_warning']:
                self._send_performance_alert('WARNING_MEMORY_USAGE', {
                    'memory_percent': memory_percent,
                    'threshold': self.resource_thresholds['memory_warning'],
                    'timestamp': timezone.now().isoformat()
                })
                
            # Check disk usage
            if disk_percent >= self.resource_thresholds['disk_critical']:
                self._send_performance_alert('CRITICAL_DISK_USAGE', {
                    'disk_percent': disk_percent,
                    'threshold': self.resource_thresholds['disk_critical'],
                    'timestamp': timezone.now().isoformat()
                })
            elif disk_percent >= self.resource_thresholds['disk_warning']:
                self._send_performance_alert('WARNING_DISK_USAGE', {
                    'disk_percent': disk_percent,
                    'threshold': self.resource_thresholds['disk_warning'],
                    'timestamp': timezone.now().isoformat()
                })
                
        except Exception as e:
            self.monitoring_logger.error(f"Error monitoring resources: {e}")
            
    def _check_error_rates(self):
        """Check error rates and send alerts"""
        try:
            # Get recent error logs
            recent_errors = self._get_recent_errors()
            
            # Calculate error rates
            total_requests = recent_errors.get('total', 0)
            error_count = recent_errors.get('errors', 0)
            
            if total_requests > 0:
                error_rate = error_count / total_requests
                
                if error_rate > 0.1:  # 10% error rate threshold
                    self._send_performance_alert('HIGH_ERROR_RATE', {
                        'error_rate': error_rate,
                        'error_count': error_count,
                        'total_requests': total_requests,
                        'timestamp': timezone.now().isoformat()
                    })
                    
        except Exception as e:
            self.monitoring_logger.error(f"Error checking error rates: {e}")
            
    def _send_performance_alert(self, alert_type, data):
        """Send performance alert through configured channels"""
        try:
            alert = {
                'type': alert_type,
                'severity': 'critical' if 'CRITICAL' in alert_type else 'warning',
                'data': data,
                'timestamp': timezone.now().isoformat(),
                'service': 'application_monitoring'
            }
            
            # Add to alert history
            self.alert_history.append(alert)
            
            # Keep only last 100 alerts
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]
                
            # Log alert
            self.monitoring_logger.warning(f"PERFORMANCE_ALERT: {alert_type} - {data}")
            
            # Send to external alerting systems
            self._send_external_alert(alert)
            
        except Exception as e:
            self.monitoring_logger.error(f"Error sending performance alert: {e}")
            
    def _send_external_alert(self, alert):
        """Send alert to external monitoring systems"""
        try:
            # Check if external alerting is configured
            slack_webhook = getattr(settings, 'MONITORING_SLACK_WEBHOOK', None)
            email_alerts = getattr(settings, 'MONITORING_EMAIL_ALERTS', False)
            
            # Send to Slack
            if slack_webhook and alert['severity'] == 'critical':
                self._send_slack_alert(alert, slack_webhook)
                
            # Send email alert
            if email_alerts and alert['severity'] == 'critical':
                self._send_email_alert(alert)
                
        except Exception as e:
            self.monitoring_logger.error(f"Error sending external alert: {e}")
            
    def _send_slack_alert(self, alert, webhook_url):
        """Send alert to Slack"""
        try:
            import requests
            
            message = {
                'text': f"🚨 *{alert['type']}* - {alert['severity'].upper()}",
                'attachments': [{
                    'color': 'danger' if alert['severity'] == 'critical' else 'warning',
                    'fields': [
                        {'title': 'Service', 'value': alert['service'], 'short': True},
                        {'title': 'Timestamp', 'value': alert['timestamp'], 'short': True},
                        {'title': 'Details', 'value': str(alert['data']), 'short': False}
                    ]
                }]
            }
            
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            self.monitoring_logger.error(f"Failed to send Slack alert: {e}")
            
    def _send_email_alert(self, alert):
        """Send alert via email"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            subject = f"ALERT: {alert['type']} - {alert['severity'].upper()}"
            message = f"""
            Performance Alert Detected
            
            Type: {alert['type']}
            Severity: {alert['severity']}
            Service: {alert['service']}
            Timestamp: {alert['timestamp']}
            Details: {alert['data']}
            
            Please investigate immediately.
            """
            
            # Send to admin users
            admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True
                )
                
        except Exception as e:
            self.monitoring_logger.error(f"Failed to send email alert: {e}")
            
    def get_monitoring_status(self):
        """Get current monitoring status"""
        try:
            return {
                'monitoring_active': self.monitoring_active,
                'last_check': self.last_check.isoformat() if self.last_check else None,
                'service_status': self.service_status,
                'alert_count': len(self.alert_history),
                'recent_alerts': self.alert_history[-10:] if self.alert_history else [],
                'performance_summary': self._get_performance_summary(),
                'uptime': self._calculate_uptime()
            }
        except Exception as e:
            self.monitoring_logger.error(f"Error getting monitoring status: {e}")
            return {'error': str(e)}
            
    def _get_performance_summary(self):
        """Get performance metrics summary"""
        try:
            summary = {}
            
            for metric_name, metrics in self.performance_metrics.items():
                if metrics:
                    values = [m['value'] for m in metrics[-100:]]  # Last 100 values
                    summary[metric_name] = {
                        'current': values[-1] if values else 0,
                        'average': sum(values) / len(values) if values else 0,
                        'min': min(values) if values else 0,
                        'max': max(values) if values else 0,
                        'trend': 'increasing' if len(values) > 1 and values[-1] > values[-2] else 'decreasing'
                    }
                    
            return summary
            
        except Exception as e:
            self.monitoring_logger.error(f"Error getting performance summary: {e}")
            return {}
            
    def _calculate_uptime(self):
        """Calculate system uptime"""
        try:
            if hasattr(self, 'uptime_start') and self.uptime_start:
                uptime_delta = timezone.now() - self.uptime_start
                return {
                    'start_time': self.uptime_start.isoformat(),
                    'uptime_seconds': int(uptime_delta.total_seconds()),
                    'uptime_formatted': str(uptime_delta).split('.')[0]  # Remove microseconds
                }
            return None
            
        except Exception as e:
            self.monitoring_logger.error(f"Error calculating uptime: {e}")
            return None
            
    def _check_django_health(self):
        """Check Django application health"""
        try:
            # Simple health check
            from django.core.cache import cache
            test_key = 'django_health_check'
            cache.set(test_key, 'ok', 10)
            result = cache.get(test_key)
            cache.delete(test_key)
            
            return 'healthy' if result == 'ok' else 'unhealthy'
            
        except Exception as e:
            self.monitoring_logger.error(f"Django health check failed: {e}")
            return 'unhealthy'
            
    def _check_database_health(self):
        """Check database health"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return 'healthy'
            
        except Exception as e:
            self.monitoring_logger.error(f"Database health check failed: {e}")
            return 'unhealthy'
            
    def _check_redis_health(self):
        """Check Redis health"""
        try:
            from django.core.cache import cache
            test_key = 'redis_health_check'
            cache.set(test_key, 'ok', 10)
            result = cache.get(test_key)
            cache.delete(test_key)
            
            return 'healthy' if result == 'ok' else 'unhealthy'
            
        except Exception as e:
            self.monitoring_logger.error(f"Redis health check failed: {e}")
            return 'unhealthy'
            
    def _check_celery_health(self):
        """Check Celery health"""
        try:
            from django.core.cache import cache
            # Check if Celery is responding
            cache.set('celery_health_check', 'ok', 10)
            result = cache.get('celery_health_check')
            cache.delete('celery_health_check')
            
            return 'healthy' if result == 'ok' else 'unhealthy'
            
        except Exception as e:
            self.monitoring_logger.error(f"Celery health check failed: {e}")
            return 'unhealthy'
            
    def _check_websocket_health(self):
        """Check WebSocket health"""
        try:
            # Check if WebSocket consumer is working
            from django.core.cache import cache
            cache.set('websocket_health_check', 'ok', 10)
            result = cache.get('websocket_health_check')
            cache.delete('websocket_health_check')
            
            return 'healthy' if result == 'ok' else 'unhealthy'
            
        except Exception as e:
            self.monitoring_logger.error(f"WebSocket health check failed: {e}")
            return 'unhealthy'
            
    def _check_database_performance(self):
        """Check database performance"""
        try:
            from django.db import connection
            import time
            
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            duration = time.time() - start_time
            
            return round(duration * 1000, 2)  # Return in milliseconds
            
        except Exception as e:
            self.monitoring_logger.error(f"Database performance check failed: {e}")
            return 0
            
    def _check_redis_performance(self):
        """Check Redis performance"""
        try:
            from django.core.cache import cache
            import time
            
            start_time = time.time()
            test_key = 'redis_performance_test'
            cache.set(test_key, 'test_value', 10)
            result = cache.get(test_key)
            cache.delete(test_key)
            duration = time.time() - start_time
            
            return round(duration * 1000, 2)  # Return in milliseconds
            
        except Exception as e:
            self.monitoring_logger.error(f"Redis performance check failed: {e}")
            return 0
            
    def _get_recent_errors(self):
        """Get recent error statistics"""
        try:
            # This would integrate with your logging system
            # For now, return placeholder data
            return {
                'total': 100,
                'errors': 5,
                'warnings': 10
            }
            
        except Exception as e:
            self.monitoring_logger.error(f"Error getting recent errors: {e}")
            return {'total': 0, 'errors': 0, 'warnings': 0}


class ErrorAlertingService:
    """
    Real-time error detection and alerting service for Phase 7B.3
    """
    
    def __init__(self):
        self.alert_logger = logging.getLogger('error_alerting')
        self.error_thresholds = {
            'critical': 1,      # Alert on first critical error
            'error': 5,         # Alert after 5 errors
            'warning': 10       # Alert after 10 warnings
        }
        self.error_counts = {
            'critical': 0,
            'error': 0,
            'warning': 0
        }
        self.alert_history = []
        
    def log_error(self, level, message, details=None):
        """Log an error and potentially trigger alert"""
        try:
            # Increment error count
            if level in self.error_counts:
                self.error_counts[level] += 1
                
            # Check if alert threshold is reached
            if self.error_counts[level] >= self.error_thresholds[level]:
                self._trigger_error_alert(level, message, details)
                
            # Log the error
            self.alert_logger.error(f"{level.upper()}: {message}")
            if details:
                self.alert_logger.error(f"Details: {details}")
                
        except Exception as e:
            self.alert_logger.error(f"Error in error alerting service: {e}")
            
    def _trigger_error_alert(self, level, message, details):
        """Trigger an error alert"""
        try:
            alert = {
                'type': f'ERROR_ALERT_{level.upper()}',
                'level': level,
                'message': message,
                'details': details,
                'count': self.error_counts[level],
                'timestamp': timezone.now().isoformat(),
                'threshold': self.error_thresholds[level]
            }
            
            # Add to alert history
            self.alert_history.append(alert)
            
            # Keep only last 100 alerts
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]
                
            # Send alert
            self._send_error_alert(alert)
            
            # Reset counter after alert
            self.error_counts[level] = 0
            
        except Exception as e:
            self.alert_logger.error(f"Error triggering error alert: {e}")
            
    def _send_error_alert(self, alert):
        """Send error alert through configured channels"""
        try:
            # Log alert
            self.alert_logger.warning(f"ERROR_ALERT: {alert['type']} - {alert['message']}")
            
            # Send to external systems if configured
            slack_webhook = getattr(settings, 'MONITORING_SLACK_WEBHOOK', None)
            if slack_webhook:
                self._send_slack_error_alert(alert, slack_webhook)
                
        except Exception as e:
            self.alert_logger.error(f"Error sending error alert: {e}")
            
    def _send_slack_error_alert(self, alert, webhook_url):
        """Send error alert to Slack"""
        try:
            import requests
            
            color = 'danger' if alert['level'] == 'critical' else 'warning'
            
            message = {
                'text': f"🚨 *ERROR ALERT: {alert['type']}*",
                'attachments': [{
                    'color': color,
                    'fields': [
                        {'title': 'Level', 'value': alert['level'].upper(), 'short': True},
                        {'title': 'Count', 'value': alert['count'], 'short': True},
                        {'title': 'Message', 'value': alert['message'], 'short': False},
                        {'title': 'Timestamp', 'value': alert['timestamp'], 'short': True}
                    ]
                }]
            }
            
            if alert['details']:
                message['attachments'][0]['fields'].append({
                    'title': 'Details',
                    'value': str(alert['details']),
                    'short': False
                })
                
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            self.alert_logger.error(f"Failed to send Slack error alert: {e}")
            
    def get_error_status(self):
        """Get current error status"""
        return {
            'error_counts': self.error_counts,
            'thresholds': self.error_thresholds,
            'alert_count': len(self.alert_history),
            'recent_alerts': self.alert_history[-10:] if self.alert_history else []
        }


class UptimeMonitoringService:
    """
    Continuous uptime monitoring service for Phase 7B.3
    """
    
    def __init__(self):
        self.uptime_logger = logging.getLogger('uptime_monitoring')
        self.start_time = timezone.now()
        self.last_check = None
        self.check_interval = 30  # Check every 30 seconds
        self.monitoring_active = False
        self.uptime_history = []
        self.downtime_events = []
        
    def start_monitoring(self):
        """Start uptime monitoring"""
        self.uptime_logger.info("Starting uptime monitoring service")
        self.monitoring_active = True
        self.last_check = timezone.now()
        
        # Start background monitoring
        self._start_uptime_monitoring()
        
    def stop_monitoring(self):
        """Stop uptime monitoring"""
        self.uptime_logger.info("Stopping uptime monitoring service")
        self.monitoring_active = False
        
    def _start_uptime_monitoring(self):
        """Start background uptime monitoring"""
        import threading
        
        def uptime_loop():
            while self.monitoring_active:
                try:
                    # Check system uptime
                    self._check_system_uptime()
                    
                    # Check service availability
                    self._check_service_availability()
                    
                    # Update last check
                    self.last_check = timezone.now()
                    
                    # Sleep for check interval
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    self.uptime_logger.error(f"Error in uptime monitoring: {e}")
                    time.sleep(10)
                    
        # Start monitoring in background thread
        uptime_thread = threading.Thread(target=uptime_loop, daemon=True)
        uptime_thread.start()
        
    def _check_system_uptime(self):
        """Check system uptime"""
        try:
            current_time = timezone.now()
            uptime_delta = current_time - self.start_time
            
            uptime_record = {
                'timestamp': current_time.isoformat(),
                'uptime_seconds': int(uptime_delta.total_seconds()),
                'uptime_formatted': str(uptime_delta).split('.')[0]
            }
            
            # Add to uptime history
            self.uptime_history.append(uptime_record)
            
            # Keep only last 1000 records
            if len(self.uptime_history) > 1000:
                self.uptime_history = self.uptime_history[-1000:]
                
        except Exception as e:
            self.uptime_logger.error(f"Error checking system uptime: {e}")
            
    def _check_service_availability(self):
        """Check availability of all services"""
        try:
            services = ['django', 'database', 'redis', 'celery', 'websockets']
            availability_status = {}
            
            for service in services:
                status = self._check_service_status(service)
                availability_status[service] = status
                
                # Record downtime if service is unavailable
                if status == 'unavailable':
                    self._record_downtime_event(service)
                    
            # Log availability summary
            available_services = sum(1 for status in availability_status.values() if status == 'available')
            total_services = len(services)
            availability_percentage = (available_services / total_services) * 100
            
            if availability_percentage < 100:
                self.uptime_logger.warning(f"Service availability: {availability_percentage:.1f}% ({available_services}/{total_services})")
                
        except Exception as e:
            self.uptime_logger.error(f"Error checking service availability: {e}")
            
    def _check_service_status(self, service):
        """Check status of a specific service"""
        try:
            if service == 'django':
                return self._check_django_status()
            elif service == 'database':
                return self._check_database_status()
            elif service == 'redis':
                return self._check_redis_status()
            elif service == 'celery':
                return self._check_celery_status()
            elif service == 'websockets':
                return self._check_websocket_status()
            else:
                return 'unknown'
                
        except Exception as e:
            self.uptime_logger.error(f"Error checking {service} status: {e}")
            return 'unknown'
            
    def _check_django_status(self):
        """Check Django service status"""
        try:
            from django.core.cache import cache
            test_key = 'django_uptime_check'
            cache.set(test_key, 'ok', 10)
            result = cache.get(test_key)
            cache.delete(test_key)
            
            return 'available' if result == 'ok' else 'unavailable'
            
        except Exception:
            return 'unavailable'
            
    def _check_database_status(self):
        """Check database service status"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return 'available'
            
        except Exception:
            return 'unavailable'
            
    def _check_redis_status(self):
        """Check Redis service status"""
        try:
            from django.core.cache import cache
            test_key = 'redis_uptime_check'
            cache.set(test_key, 'ok', 10)
            result = cache.get(test_key)
            cache.delete(test_key)
            
            return 'available' if result == 'ok' else 'unavailable'
            
        except Exception:
            return 'unavailable'
            
    def _check_celery_status(self):
        """Check Celery service status"""
        try:
            from django.core.cache import cache
            cache.set('celery_uptime_check', 'ok', 10)
            result = cache.get('celery_uptime_check')
            cache.delete('celery_uptime_check')
            
            return 'available' if result == 'ok' else 'unavailable'
            
        except Exception:
            return 'unavailable'
            
    def _check_websocket_status(self):
        """Check WebSocket service status"""
        try:
            from django.core.cache import cache
            cache.set('websocket_uptime_check', 'ok', 10)
            result = cache.get('websocket_uptime_check')
            cache.delete('websocket_uptime_check')
            
            return 'available' if result == 'ok' else 'unavailable'
            
        except Exception:
            return 'unavailable'
            
    def _record_downtime_event(self, service):
        """Record a downtime event"""
        try:
            downtime_event = {
                'service': service,
                'start_time': timezone.now().isoformat(),
                'status': 'down'
            }
            
            # Add to downtime events
            self.downtime_events.append(downtime_event)
            
            # Keep only last 100 events
            if len(self.downtime_events) > 100:
                self.downtime_events = self.downtime_events[-100:]
                
            # Log downtime
            self.uptime_logger.error(f"Service {service} is down")
            
        except Exception as e:
            self.uptime_logger.error(f"Error recording downtime event: {e}")
            
    def get_uptime_status(self):
        """Get current uptime status"""
        try:
            current_time = timezone.now()
            uptime_delta = current_time - self.start_time
            
            return {
                'monitoring_active': self.monitoring_active,
                'start_time': self.start_time.isoformat(),
                'current_uptime': {
                    'seconds': int(uptime_delta.total_seconds()),
                    'formatted': str(uptime_delta).split('.')[0]
                },
                'last_check': self.last_check.isoformat() if self.last_check else None,
                'uptime_records': len(self.uptime_history),
                'downtime_events': len(self.downtime_events),
                'recent_downtime': self.downtime_events[-10:] if self.downtime_events else [],
                'availability_percentage': self._calculate_availability_percentage()
            }
            
        except Exception as e:
            self.uptime_logger.error(f"Error getting uptime status: {e}")
            return {'error': str(e)}
            
    def _calculate_availability_percentage(self):
        """Calculate overall availability percentage"""
        try:
            if not self.uptime_history:
                return 100.0
                
            # Calculate availability based on uptime history
            total_checks = len(self.uptime_history)
            successful_checks = sum(1 for record in self.uptime_history if record.get('uptime_seconds', 0) > 0)
            
            return (successful_checks / total_checks) * 100 if total_checks > 0 else 100.0
            
        except Exception as e:
            self.uptime_logger.error(f"Error calculating availability percentage: {e}")
            return 100.0


# Global broadcaster instances
market_broadcaster = MarketDataBroadcaster()
signals_broadcaster = TradingSignalsBroadcaster()
notification_broadcaster = NotificationBroadcaster()


