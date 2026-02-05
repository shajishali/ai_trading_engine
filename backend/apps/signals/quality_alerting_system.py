"""
Quality Alerting System
Phase 5: Advanced alerting system for quality issues, automated notifications, and escalation
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings

from apps.signals.models import SignalAlert
from apps.signals.signal_quality_monitor import signal_quality_monitor
from apps.signals.performance_monitoring_system import performance_monitoring_system
from apps.signals.system_health_assessor import system_health_assessor
from apps.signals.quality_metrics_system import quality_metrics_system

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    """Alert types"""
    QUALITY = "QUALITY"
    PERFORMANCE = "PERFORMANCE"
    HEALTH = "HEALTH"
    SYSTEM = "SYSTEM"
    DATA = "DATA"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    condition: str
    severity: AlertSeverity
    alert_type: AlertType
    enabled: bool = True
    cooldown_minutes: int = 15
    escalation_minutes: int = 60
    notification_channels: List[str] = None


@dataclass
class AlertContext:
    """Alert context information"""
    timestamp: datetime
    source: str
    metric_name: str
    current_value: Any
    threshold: Any
    severity: AlertSeverity
    message: str
    recommendations: List[str]


class QualityAlertingSystem:
    """Advanced quality alerting system"""
    
    def __init__(self):
        self.alert_rules = self._initialize_alert_rules()
        self.notification_channels = {
            'email': self._send_email_notification,
            'database': self._create_database_alert,
            'log': self._log_alert
        }
        
        # Alert cooldowns
        self.alert_cooldowns = {}
        self.escalation_timers = {}
    
    def _initialize_alert_rules(self) -> List[AlertRule]:
        """Initialize alert rules for quality monitoring"""
        return [
            # Quality alerts
            AlertRule(
                name="Low Signal Quality",
                condition="signal_quality_score < 70",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.QUALITY,
                cooldown_minutes=30,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical Signal Quality",
                condition="signal_quality_score < 50",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.QUALITY,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            AlertRule(
                name="Low Success Rate",
                condition="success_rate < 60",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.QUALITY,
                cooldown_minutes=30,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical Success Rate",
                condition="success_rate < 40",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.QUALITY,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            
            # Performance alerts
            AlertRule(
                name="High CPU Usage",
                condition="cpu_usage > 80",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.PERFORMANCE,
                cooldown_minutes=15,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical CPU Usage",
                condition="cpu_usage > 90",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.PERFORMANCE,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            AlertRule(
                name="High Memory Usage",
                condition="memory_usage > 80",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.PERFORMANCE,
                cooldown_minutes=15,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical Memory Usage",
                condition="memory_usage > 90",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.PERFORMANCE,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            AlertRule(
                name="Slow Response Time",
                condition="response_time > 5000",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.PERFORMANCE,
                cooldown_minutes=10,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical Response Time",
                condition="response_time > 10000",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.PERFORMANCE,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            
            # Health alerts
            AlertRule(
                name="System Health Degraded",
                condition="system_health == 'DEGRADED'",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.HEALTH,
                cooldown_minutes=30,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="System Health Critical",
                condition="system_health == 'CRITICAL'",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.HEALTH,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            AlertRule(
                name="Database Health Warning",
                condition="database_health == 'WARNING'",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.HEALTH,
                cooldown_minutes=30,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Database Health Critical",
                condition="database_health == 'CRITICAL'",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.HEALTH,
                cooldown_minutes=5,
                notification_channels=['email', 'database', 'log']
            ),
            
            # Data alerts
            AlertRule(
                name="Stale Data",
                condition="data_age > 2",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.DATA,
                cooldown_minutes=60,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical Data Age",
                condition="data_age > 4",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.DATA,
                cooldown_minutes=15,
                notification_channels=['email', 'database', 'log']
            ),
            AlertRule(
                name="Low Data Coverage",
                condition="data_coverage < 80",
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.DATA,
                cooldown_minutes=60,
                notification_channels=['email', 'database']
            ),
            AlertRule(
                name="Critical Data Coverage",
                condition="data_coverage < 60",
                severity=AlertSeverity.CRITICAL,
                alert_type=AlertType.DATA,
                cooldown_minutes=15,
                notification_channels=['email', 'database', 'log']
            )
        ]
    
    def check_quality_alerts(self) -> List[Dict[str, Any]]:
        """Check for quality alerts based on current metrics"""
        try:
            logger.info("Checking quality alerts...")
            
            # Get current metrics from all systems
            quality_metrics = self._get_current_quality_metrics()
            performance_metrics = self._get_current_performance_metrics()
            health_metrics = self._get_current_health_metrics()
            
            # Combine all metrics
            all_metrics = {**quality_metrics, **performance_metrics, **health_metrics}
            
            # Check each alert rule
            triggered_alerts = []
            
            for rule in self.alert_rules:
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if self._is_alert_in_cooldown(rule.name):
                    continue
                
                # Evaluate rule condition
                if self._evaluate_alert_condition(rule.condition, all_metrics):
                    # Create alert context
                    alert_context = self._create_alert_context(rule, all_metrics)
                    
                    # Send notifications
                    self._send_alert_notifications(rule, alert_context)
                    
                    # Set cooldown
                    self._set_alert_cooldown(rule.name, rule.cooldown_minutes)
                    
                    # Set escalation timer
                    self._set_escalation_timer(rule.name, rule.escalation_minutes)
                    
                    triggered_alerts.append({
                        'rule_name': rule.name,
                        'severity': rule.severity.value,
                        'alert_type': rule.alert_type.value,
                        'context': alert_context.__dict__,
                        'timestamp': timezone.now().isoformat()
                    })
            
            logger.info(f"Quality alert check completed - {len(triggered_alerts)} alerts triggered")
            return triggered_alerts
            
        except Exception as e:
            logger.error(f"Error checking quality alerts: {e}")
            return []
    
    def _get_current_quality_metrics(self) -> Dict[str, Any]:
        """Get current quality metrics"""
        try:
            # Get quality report
            quality_report = signal_quality_monitor.get_comprehensive_report()
            
            return {
                'signal_quality_score': quality_report.get('overall_system_score', 0),
                'success_rate': quality_report.get('quality_monitoring', {}).get('signal_statistics', {}).get('profitability_rate', 0),
                'accuracy': quality_report.get('quality_monitoring', {}).get('signal_statistics', {}).get('avg_confidence', 0),
                'data_freshness': quality_report.get('data_freshness', {}).get('freshness_score', 0),
                'data_coverage': quality_report.get('data_freshness', {}).get('data_coverage_percentage', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting quality metrics: {e}")
            return {}
    
    def _get_current_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        try:
            # Get performance report
            performance_report = performance_monitoring_system.get_performance_report()
            
            return {
                'cpu_usage': performance_report.get('current_metrics', {}).get('cpu_usage_percent', 0),
                'memory_usage': performance_report.get('current_metrics', {}).get('memory_usage_percent', 0),
                'response_time': performance_report.get('current_metrics', {}).get('response_time_ms', 0),
                'throughput': performance_report.get('current_metrics', {}).get('throughput_per_second', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def _get_current_health_metrics(self) -> Dict[str, Any]:
        """Get current health metrics"""
        try:
            # Get health report
            health_report = system_health_assessor.get_comprehensive_health_report()
            
            return {
                'system_health': health_report.get('overall_status', 'UNKNOWN'),
                'database_health': health_report.get('health_assessment', {}).get('component_status', {}).get('database', 'UNKNOWN'),
                'health_score': health_report.get('overall_system_score', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting health metrics: {e}")
            return {}
    
    def _evaluate_alert_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        """Evaluate alert condition"""
        try:
            # Simple condition evaluation
            # In a production system, this would use a more sophisticated expression evaluator
            
            if 'signal_quality_score < 70' in condition:
                return metrics.get('signal_quality_score', 0) < 70
            elif 'signal_quality_score < 50' in condition:
                return metrics.get('signal_quality_score', 0) < 50
            elif 'success_rate < 60' in condition:
                return metrics.get('success_rate', 0) < 60
            elif 'success_rate < 40' in condition:
                return metrics.get('success_rate', 0) < 40
            elif 'cpu_usage > 80' in condition:
                return metrics.get('cpu_usage', 0) > 80
            elif 'cpu_usage > 90' in condition:
                return metrics.get('cpu_usage', 0) > 90
            elif 'memory_usage > 80' in condition:
                return metrics.get('memory_usage', 0) > 80
            elif 'memory_usage > 90' in condition:
                return metrics.get('memory_usage', 0) > 90
            elif 'response_time > 5000' in condition:
                return metrics.get('response_time', 0) > 5000
            elif 'response_time > 10000' in condition:
                return metrics.get('response_time', 0) > 10000
            elif "system_health == 'DEGRADED'" in condition:
                return metrics.get('system_health', '') == 'DEGRADED'
            elif "system_health == 'CRITICAL'" in condition:
                return metrics.get('system_health', '') == 'CRITICAL'
            elif "database_health == 'WARNING'" in condition:
                return metrics.get('database_health', '') == 'WARNING'
            elif "database_health == 'CRITICAL'" in condition:
                return metrics.get('database_health', '') == 'CRITICAL'
            elif 'data_age > 2' in condition:
                return metrics.get('data_age', 0) > 2
            elif 'data_age > 4' in condition:
                return metrics.get('data_age', 0) > 4
            elif 'data_coverage < 80' in condition:
                return metrics.get('data_coverage', 0) < 80
            elif 'data_coverage < 60' in condition:
                return metrics.get('data_coverage', 0) < 60
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating alert condition: {e}")
            return False
    
    def _create_alert_context(self, rule: AlertRule, metrics: Dict[str, Any]) -> AlertContext:
        """Create alert context"""
        try:
            # Get metric value and threshold
            metric_name = self._extract_metric_name(rule.condition)
            current_value = metrics.get(metric_name, 0)
            threshold = self._extract_threshold(rule.condition)
            
            # Generate message
            message = f"{rule.name}: {metric_name} is {current_value} (threshold: {threshold})"
            
            # Generate recommendations
            recommendations = self._generate_alert_recommendations(rule, current_value, threshold)
            
            return AlertContext(
                timestamp=timezone.now(),
                source=rule.alert_type.value,
                metric_name=metric_name,
                current_value=current_value,
                threshold=threshold,
                severity=rule.severity,
                message=message,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error creating alert context: {e}")
            return AlertContext(
                timestamp=timezone.now(),
                source='UNKNOWN',
                metric_name='unknown',
                current_value=0,
                threshold=0,
                severity=AlertSeverity.LOW,
                message=f"Error creating alert context: {e}",
                recommendations=[]
            )
    
    def _extract_metric_name(self, condition: str) -> str:
        """Extract metric name from condition"""
        # Simple extraction - in production, use proper parsing
        if 'signal_quality_score' in condition:
            return 'signal_quality_score'
        elif 'success_rate' in condition:
            return 'success_rate'
        elif 'cpu_usage' in condition:
            return 'cpu_usage'
        elif 'memory_usage' in condition:
            return 'memory_usage'
        elif 'response_time' in condition:
            return 'response_time'
        elif 'system_health' in condition:
            return 'system_health'
        elif 'database_health' in condition:
            return 'database_health'
        elif 'data_age' in condition:
            return 'data_age'
        elif 'data_coverage' in condition:
            return 'data_coverage'
        else:
            return 'unknown'
    
    def _extract_threshold(self, condition: str) -> Any:
        """Extract threshold from condition"""
        # Simple extraction - in production, use proper parsing
        import re
        
        # Extract number from condition
        numbers = re.findall(r'\d+', condition)
        if numbers:
            return int(numbers[0])
        else:
            return 0
    
    def _generate_alert_recommendations(self, rule: AlertRule, current_value: Any, threshold: Any) -> List[str]:
        """Generate recommendations for alert"""
        try:
            recommendations = []
            
            if 'signal_quality' in rule.name.lower():
                recommendations.append("Review signal generation algorithms")
                recommendations.append("Check data quality and freshness")
                recommendations.append("Validate signal parameters and thresholds")
            elif 'success_rate' in rule.name.lower():
                recommendations.append("Analyze failed signals and identify patterns")
                recommendations.append("Review signal validation logic")
                recommendations.append("Check market conditions and data quality")
            elif 'cpu_usage' in rule.name.lower():
                recommendations.append("Optimize algorithms and database queries")
                recommendations.append("Consider scaling resources")
                recommendations.append("Review system load and processes")
            elif 'memory_usage' in rule.name.lower():
                recommendations.append("Check for memory leaks")
                recommendations.append("Optimize data structures and caching")
                recommendations.append("Review memory allocation patterns")
            elif 'response_time' in rule.name.lower():
                recommendations.append("Optimize database queries")
                recommendations.append("Improve caching strategies")
                recommendations.append("Review system performance bottlenecks")
            elif 'system_health' in rule.name.lower():
                recommendations.append("Check all system components")
                recommendations.append("Review system logs for errors")
                recommendations.append("Consider system maintenance")
            elif 'database_health' in rule.name.lower():
                recommendations.append("Check database connectivity")
                recommendations.append("Review database performance")
                recommendations.append("Check database logs for errors")
            elif 'data' in rule.name.lower():
                recommendations.append("Check data collection processes")
                recommendations.append("Review data synchronization")
                recommendations.append("Validate data sources")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating alert recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _send_alert_notifications(self, rule: AlertRule, context: AlertContext):
        """Send alert notifications through configured channels"""
        try:
            if not rule.notification_channels:
                return
            
            for channel in rule.notification_channels:
                if channel in self.notification_channels:
                    self.notification_channels[channel](rule, context)
                    
        except Exception as e:
            logger.error(f"Error sending alert notifications: {e}")
    
    def _send_email_notification(self, rule: AlertRule, context: AlertContext):
        """Send email notification"""
        try:
            subject = f"[{rule.severity.value}] {rule.name} - CryptAI"
            
            message = f"""
Alert: {rule.name}
Severity: {rule.severity.value}
Time: {context.timestamp.isoformat()}
Source: {context.source}

Details:
- Metric: {context.metric_name}
- Current Value: {context.current_value}
- Threshold: {context.threshold}
- Message: {context.message}

Recommendations:
{chr(10).join(f"- {rec}" for rec in context.recommendations)}

Please investigate and take appropriate action.
            """
            
            # Send email (configure email settings in Django)
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL] if hasattr(settings, 'ADMIN_EMAIL') else ['admin@example.com'],
                fail_silently=False
            )
            
            logger.info(f"Email notification sent for alert: {rule.name}")
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    def _create_database_alert(self, rule: AlertRule, context: AlertContext):
        """Create database alert"""
        try:
            SignalAlert.objects.create(
                title=rule.name,
                message=context.message,
                priority=rule.severity.value,
                alert_type=rule.alert_type.value,
                is_read=False
            )
            
            logger.info(f"Database alert created: {rule.name}")
            
        except Exception as e:
            logger.error(f"Error creating database alert: {e}")
    
    def _log_alert(self, rule: AlertRule, context: AlertContext):
        """Log alert"""
        try:
            logger.warning(f"ALERT [{rule.severity.value}] {rule.name}: {context.message}")
            
        except Exception as e:
            logger.error(f"Error logging alert: {e}")
    
    def _is_alert_in_cooldown(self, rule_name: str) -> bool:
        """Check if alert is in cooldown period"""
        try:
            cooldown_key = f"alert_cooldown_{rule_name}"
            last_alert_time = cache.get(cooldown_key, 0)
            current_time = time.time()
            
            return current_time - last_alert_time < 0  # Simplified cooldown check
            
        except Exception as e:
            logger.error(f"Error checking alert cooldown: {e}")
            return False
    
    def _set_alert_cooldown(self, rule_name: str, cooldown_minutes: int):
        """Set alert cooldown period"""
        try:
            cooldown_key = f"alert_cooldown_{rule_name}"
            cache.set(cooldown_key, time.time(), cooldown_minutes * 60)
            
        except Exception as e:
            logger.error(f"Error setting alert cooldown: {e}")
    
    def _set_escalation_timer(self, rule_name: str, escalation_minutes: int):
        """Set escalation timer"""
        try:
            escalation_key = f"escalation_timer_{rule_name}"
            cache.set(escalation_key, time.time(), escalation_minutes * 60)
            
        except Exception as e:
            logger.error(f"Error setting escalation timer: {e}")
    
    def check_escalations(self) -> List[Dict[str, Any]]:
        """Check for alerts that need escalation"""
        try:
            escalated_alerts = []
            
            for rule in self.alert_rules:
                escalation_key = f"escalation_timer_{rule.name}"
                escalation_time = cache.get(escalation_key, 0)
                
                if escalation_time > 0:
                    current_time = time.time()
                    if current_time - escalation_time >= 0:  # Escalation time reached
                        # Create escalation alert
                        escalation_alert = {
                            'rule_name': rule.name,
                            'escalation_time': escalation_time,
                            'message': f"Alert {rule.name} has not been resolved and requires escalation"
                        }
                        
                        escalated_alerts.append(escalation_alert)
                        
                        # Send escalation notification
                        self._send_escalation_notification(rule, escalation_alert)
                        
                        # Clear escalation timer
                        cache.delete(escalation_key)
            
            return escalated_alerts
            
        except Exception as e:
            logger.error(f"Error checking escalations: {e}")
            return []
    
    def _send_escalation_notification(self, rule: AlertRule, escalation_alert: Dict[str, Any]):
        """Send escalation notification"""
        try:
            # Create escalation alert in database
            SignalAlert.objects.create(
                title=f"ESCALATION: {rule.name}",
                message=escalation_alert['message'],
                priority='CRITICAL',
                alert_type='ESCALATION',
                is_read=False
            )
            
            logger.critical(f"Alert escalated: {rule.name}")
            
        except Exception as e:
            logger.error(f"Error sending escalation notification: {e}")
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary"""
        try:
            # Get recent alerts
            recent_alerts = SignalAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            # Count by severity
            severity_counts = {
                'LOW': recent_alerts.filter(priority='LOW').count(),
                'MEDIUM': recent_alerts.filter(priority='MEDIUM').count(),
                'HIGH': recent_alerts.filter(priority='HIGH').count(),
                'CRITICAL': recent_alerts.filter(priority='CRITICAL').count()
            }
            
            # Count by type
            type_counts = {
                'QUALITY': recent_alerts.filter(alert_type='QUALITY_ALERT').count(),
                'PERFORMANCE': recent_alerts.filter(alert_type='PERFORMANCE_ALERT').count(),
                'HEALTH': recent_alerts.filter(alert_type='HEALTH_ALERT').count(),
                'SYSTEM': recent_alerts.filter(alert_type='SYSTEM_ALERT').count(),
                'DATA': recent_alerts.filter(alert_type='DATA_ALERT').count()
            }
            
            # Get unread alerts
            unread_alerts = recent_alerts.filter(is_read=False).count()
            
            return {
                'timestamp': timezone.now().isoformat(),
                'total_alerts_24h': recent_alerts.count(),
                'unread_alerts': unread_alerts,
                'severity_counts': severity_counts,
                'type_counts': type_counts,
                'active_rules': len([rule for rule in self.alert_rules if rule.enabled]),
                'escalation_count': len(self.escalation_timers)
            }
            
        except Exception as e:
            logger.error(f"Error getting alert summary: {e}")
            return {'error': str(e)}
    
    def update_alert_rule(self, rule_name: str, **kwargs) -> bool:
        """Update alert rule configuration"""
        try:
            for rule in self.alert_rules:
                if rule.name == rule_name:
                    for key, value in kwargs.items():
                        if hasattr(rule, key):
                            setattr(rule, key, value)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
            return False
    
    def add_alert_rule(self, rule: AlertRule) -> bool:
        """Add new alert rule"""
        try:
            self.alert_rules.append(rule)
            return True
            
        except Exception as e:
            logger.error(f"Error adding alert rule: {e}")
            return False
    
    def remove_alert_rule(self, rule_name: str) -> bool:
        """Remove alert rule"""
        try:
            self.alert_rules = [rule for rule in self.alert_rules if rule.name != rule_name]
            return True
            
        except Exception as e:
            logger.error(f"Error removing alert rule: {e}")
            return False


# Global instance
quality_alerting_system = QualityAlertingSystem()














