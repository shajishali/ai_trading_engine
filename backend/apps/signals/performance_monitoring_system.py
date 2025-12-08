"""
Performance Monitoring and Alerting System
Phase 5: Advanced performance monitoring, alerting, and system health assessment
"""

import logging
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, F
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData
from apps.signals.models import TradingSignal, SignalAlert
from apps.signals.database_data_utils import get_database_health_status

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System performance metrics data structure"""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_mb: float
    memory_usage_percent: float
    disk_usage_percent: float
    network_io_bytes: int
    database_connections: int
    cache_hit_rate: float
    response_time_ms: float
    throughput_per_second: float


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric: str
    threshold: float
    operator: str  # 'gt', 'lt', 'eq', 'gte', 'lte'
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    enabled: bool = True
    cooldown_minutes: int = 15


class PerformanceMonitoringSystem:
    """Advanced performance monitoring and alerting system"""
    
    def __init__(self):
        self.monitoring_interval = 60  # 1 minute
        self.alert_cooldown = 900  # 15 minutes
        self.metrics_history = []
        self.alert_rules = self._initialize_alert_rules()
        
        # Performance thresholds
        self.thresholds = {
            'cpu_usage_critical': 90.0,
            'cpu_usage_warning': 80.0,
            'memory_usage_critical': 90.0,
            'memory_usage_warning': 80.0,
            'disk_usage_critical': 95.0,
            'disk_usage_warning': 85.0,
            'response_time_critical': 10.0,
            'response_time_warning': 5.0,
            'error_rate_critical': 0.1,
            'error_rate_warning': 0.05
        }
    
    def _initialize_alert_rules(self) -> List[AlertRule]:
        """Initialize alert rules for monitoring"""
        return [
            AlertRule(
                name="High CPU Usage",
                metric="cpu_usage_percent",
                threshold=80.0,
                operator="gt",
                severity="WARNING",
                cooldown_minutes=15
            ),
            AlertRule(
                name="Critical CPU Usage",
                metric="cpu_usage_percent",
                threshold=90.0,
                operator="gt",
                severity="CRITICAL",
                cooldown_minutes=5
            ),
            AlertRule(
                name="High Memory Usage",
                metric="memory_usage_percent",
                threshold=80.0,
                operator="gt",
                severity="WARNING",
                cooldown_minutes=15
            ),
            AlertRule(
                name="Critical Memory Usage",
                metric="memory_usage_percent",
                threshold=90.0,
                operator="gt",
                severity="CRITICAL",
                cooldown_minutes=5
            ),
            AlertRule(
                name="High Disk Usage",
                metric="disk_usage_percent",
                threshold=85.0,
                operator="gt",
                severity="WARNING",
                cooldown_minutes=30
            ),
            AlertRule(
                name="Critical Disk Usage",
                metric="disk_usage_percent",
                threshold=95.0,
                operator="gt",
                severity="CRITICAL",
                cooldown_minutes=10
            ),
            AlertRule(
                name="Slow Response Time",
                metric="response_time_ms",
                threshold=5000.0,
                operator="gt",
                severity="WARNING",
                cooldown_minutes=10
            ),
            AlertRule(
                name="Critical Response Time",
                metric="response_time_ms",
                threshold=10000.0,
                operator="gt",
                severity="CRITICAL",
                cooldown_minutes=5
            )
        ]
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect comprehensive system performance metrics"""
        try:
            logger.debug("Collecting system performance metrics...")
            
            # Get system resource usage
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get network I/O
            network_io = psutil.net_io_counters()
            
            # Get database performance
            db_metrics = self._get_database_metrics()
            
            # Get cache performance
            cache_metrics = self._get_cache_metrics()
            
            # Get response time
            response_time = self._measure_response_time()
            
            # Get throughput
            throughput = self._calculate_throughput()
            
            metrics = SystemMetrics(
                timestamp=timezone.now(),
                cpu_usage_percent=cpu_usage,
                memory_usage_mb=memory.used / (1024 * 1024),  # Convert to MB
                memory_usage_percent=memory.percent,
                disk_usage_percent=disk.percent,
                network_io_bytes=network_io.bytes_sent + network_io.bytes_recv,
                database_connections=db_metrics.get('connection_count', 0),
                cache_hit_rate=cache_metrics.get('hit_rate', 0.0),
                response_time_ms=response_time,
                throughput_per_second=throughput
            )
            
            # Store in history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > 1000:  # Keep last 1000 records
                self.metrics_history = self.metrics_history[-1000:]
            
            logger.debug(f"System metrics collected - CPU: {cpu_usage:.1f}%, Memory: {memory.percent:.1f}%")
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=timezone.now(),
                cpu_usage_percent=0.0,
                memory_usage_mb=0.0,
                memory_usage_percent=0.0,
                disk_usage_percent=0.0,
                network_io_bytes=0,
                database_connections=0,
                cache_hit_rate=0.0,
                response_time_ms=0.0,
                throughput_per_second=0.0
            )
    
    def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics"""
        try:
            # This would be implemented with actual database monitoring
            return {
                'connection_count': 5,
                'avg_query_time': 0.1,
                'slow_queries': 0,
                'active_connections': 3
            }
            
        except Exception as e:
            logger.error(f"Error getting database metrics: {e}")
            return {'connection_count': 0, 'avg_query_time': 0.0, 'slow_queries': 0, 'active_connections': 0}
    
    def _get_cache_metrics(self) -> Dict[str, float]:
        """Get cache performance metrics"""
        try:
            # This would be implemented with actual cache monitoring
            return {
                'hit_rate': 0.85,
                'miss_rate': 0.15,
                'eviction_rate': 0.05,
                'memory_usage': 0.1
            }
            
        except Exception as e:
            logger.error(f"Error getting cache metrics: {e}")
            return {'hit_rate': 0.0, 'miss_rate': 0.0, 'eviction_rate': 0.0, 'memory_usage': 0.0}
    
    def _measure_response_time(self) -> float:
        """Measure system response time"""
        try:
            # Simulate response time measurement
            start_time = time.time()
            
            # Perform a simple operation to measure response time
            TradingSignal.objects.count()
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            return response_time
            
        except Exception as e:
            logger.error(f"Error measuring response time: {e}")
            return 0.0
    
    def _calculate_throughput(self) -> float:
        """Calculate system throughput"""
        try:
            # Get signals generated in the last minute
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).count()
            
            return float(recent_signals)
            
        except Exception as e:
            logger.error(f"Error calculating throughput: {e}")
            return 0.0
    
    def check_performance_alerts(self, metrics: SystemMetrics) -> List[Dict[str, Any]]:
        """Check for performance alerts based on metrics"""
        try:
            alerts = []
            
            # Check each alert rule
            for rule in self.alert_rules:
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if self._is_alert_in_cooldown(rule.name):
                    continue
                
                # Get metric value
                metric_value = getattr(metrics, rule.metric, 0)
                
                # Check if alert condition is met
                if self._evaluate_alert_condition(metric_value, rule.threshold, rule.operator):
                    alert = {
                        'rule_name': rule.name,
                        'metric': rule.metric,
                        'value': metric_value,
                        'threshold': rule.threshold,
                        'severity': rule.severity,
                        'timestamp': timezone.now().isoformat(),
                        'message': f"{rule.name}: {metric_value:.2f} {rule.operator} {rule.threshold:.2f}"
                    }
                    
                    alerts.append(alert)
                    
                    # Create alert in database
                    self._create_performance_alert(alert)
                    
                    # Set cooldown
                    self._set_alert_cooldown(rule.name, rule.cooldown_minutes)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
            return []
    
    def _evaluate_alert_condition(self, value: float, threshold: float, operator: str) -> bool:
        """Evaluate alert condition"""
        try:
            if operator == 'gt':
                return value > threshold
            elif operator == 'lt':
                return value < threshold
            elif operator == 'eq':
                return value == threshold
            elif operator == 'gte':
                return value >= threshold
            elif operator == 'lte':
                return value <= threshold
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating alert condition: {e}")
            return False
    
    def _is_alert_in_cooldown(self, rule_name: str) -> bool:
        """Check if alert is in cooldown period"""
        try:
            cooldown_key = f"alert_cooldown_{rule_name}"
            last_alert_time = cache.get(cooldown_key, 0)
            current_time = time.time()
            
            return current_time - last_alert_time < self.alert_cooldown
            
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
    
    def _create_performance_alert(self, alert_data: Dict[str, Any]):
        """Create performance alert in database"""
        try:
            SignalAlert.objects.create(
                title=alert_data['rule_name'],
                message=alert_data['message'],
                priority=alert_data['severity'],
                alert_type='PERFORMANCE_ALERT',
                is_read=False
            )
            
            logger.warning(f"Performance alert created: {alert_data['rule_name']}")
            
        except Exception as e:
            logger.error(f"Error creating performance alert: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        try:
            logger.info("Generating performance report...")
            
            # Collect current metrics
            current_metrics = self.collect_system_metrics()
            
            # Check for alerts
            alerts = self.check_performance_alerts(current_metrics)
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(current_metrics)
            
            # Analyze trends
            trends = self._analyze_performance_trends()
            
            # Generate recommendations
            recommendations = self._generate_performance_recommendations(current_metrics, alerts)
            
            report = {
                'timestamp': timezone.now().isoformat(),
                'current_metrics': current_metrics.__dict__,
                'performance_score': performance_score,
                'alerts': alerts,
                'trends': trends,
                'recommendations': recommendations,
                'system_health': self._assess_system_health(current_metrics),
                'next_actions': self._generate_next_actions(performance_score, alerts)
            }
            
            logger.info(f"Performance report generated - Score: {performance_score:.1f}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {'error': str(e)}
    
    def _calculate_performance_score(self, metrics: SystemMetrics) -> float:
        """Calculate overall performance score"""
        try:
            score = 100.0
            
            # CPU usage penalty
            if metrics.cpu_usage_percent > self.thresholds['cpu_usage_critical']:
                score -= 40
            elif metrics.cpu_usage_percent > self.thresholds['cpu_usage_warning']:
                score -= 20
            
            # Memory usage penalty
            if metrics.memory_usage_percent > self.thresholds['memory_usage_critical']:
                score -= 30
            elif metrics.memory_usage_percent > self.thresholds['memory_usage_warning']:
                score -= 15
            
            # Disk usage penalty
            if metrics.disk_usage_percent > self.thresholds['disk_usage_critical']:
                score -= 20
            elif metrics.disk_usage_percent > self.thresholds['disk_usage_warning']:
                score -= 10
            
            # Response time penalty
            if metrics.response_time_ms > self.thresholds['response_time_critical']:
                score -= 25
            elif metrics.response_time_ms > self.thresholds['response_time_warning']:
                score -= 10
            
            # Cache hit rate bonus
            if metrics.cache_hit_rate < 0.7:
                score -= 10
            elif metrics.cache_hit_rate > 0.9:
                score += 5
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return 0.0
    
    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        try:
            if len(self.metrics_history) < 10:
                return {'trend': 'INSUFFICIENT_DATA'}
            
            # Get recent metrics (last 10 records)
            recent_metrics = self.metrics_history[-10:]
            
            # Analyze CPU trend
            cpu_trend = self._analyze_metric_trend([m.cpu_usage_percent for m in recent_metrics])
            
            # Analyze memory trend
            memory_trend = self._analyze_metric_trend([m.memory_usage_percent for m in recent_metrics])
            
            # Analyze response time trend
            response_trend = self._analyze_metric_trend([m.response_time_ms for m in recent_metrics])
            
            # Determine overall trend
            if cpu_trend == 'INCREASING' or memory_trend == 'INCREASING' or response_trend == 'INCREASING':
                overall_trend = 'DEGRADING'
            elif cpu_trend == 'DECREASING' and memory_trend == 'DECREASING' and response_trend == 'DECREASING':
                overall_trend = 'IMPROVING'
            else:
                overall_trend = 'STABLE'
            
            return {
                'overall_trend': overall_trend,
                'cpu_trend': cpu_trend,
                'memory_trend': memory_trend,
                'response_trend': response_trend,
                'data_points': len(recent_metrics)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing performance trends: {e}")
            return {'trend': 'ERROR'}
    
    def _analyze_metric_trend(self, values: List[float]) -> str:
        """Analyze trend for a specific metric"""
        try:
            if len(values) < 3:
                return 'INSUFFICIENT_DATA'
            
            # Calculate trend using simple linear regression
            n = len(values)
            x = list(range(n))
            
            # Calculate slope
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(x[i] * values[i] for i in range(n))
            sum_x2 = sum(xi * xi for xi in x)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Determine trend based on slope
            if slope > 0.1:
                return 'INCREASING'
            elif slope < -0.1:
                return 'DECREASING'
            else:
                return 'STABLE'
                
        except Exception as e:
            logger.error(f"Error analyzing metric trend: {e}")
            return 'ERROR'
    
    def _assess_system_health(self, metrics: SystemMetrics) -> str:
        """Assess overall system health"""
        try:
            # Check critical conditions
            if (metrics.cpu_usage_percent > self.thresholds['cpu_usage_critical'] or
                metrics.memory_usage_percent > self.thresholds['memory_usage_critical'] or
                metrics.disk_usage_percent > self.thresholds['disk_usage_critical'] or
                metrics.response_time_ms > self.thresholds['response_time_critical']):
                return "CRITICAL"
            
            # Check warning conditions
            if (metrics.cpu_usage_percent > self.thresholds['cpu_usage_warning'] or
                metrics.memory_usage_percent > self.thresholds['memory_usage_warning'] or
                metrics.disk_usage_percent > self.thresholds['disk_usage_warning'] or
                metrics.response_time_ms > self.thresholds['response_time_warning']):
                return "WARNING"
            
            # Check if all metrics are excellent
            if (metrics.cpu_usage_percent < 50 and
                metrics.memory_usage_percent < 60 and
                metrics.disk_usage_percent < 70 and
                metrics.response_time_ms < 1000):
                return "EXCELLENT"
            
            return "HEALTHY"
            
        except Exception as e:
            logger.error(f"Error assessing system health: {e}")
            return "UNKNOWN"
    
    def _generate_performance_recommendations(self, metrics: SystemMetrics, alerts: List[Dict[str, Any]]) -> List[str]:
        """Generate performance improvement recommendations"""
        try:
            recommendations = []
            
            # CPU recommendations
            if metrics.cpu_usage_percent > self.thresholds['cpu_usage_warning']:
                recommendations.append("High CPU usage - consider optimizing algorithms or scaling resources")
            
            # Memory recommendations
            if metrics.memory_usage_percent > self.thresholds['memory_usage_warning']:
                recommendations.append("High memory usage - review memory leaks and optimize data structures")
            
            # Disk recommendations
            if metrics.disk_usage_percent > self.thresholds['disk_usage_warning']:
                recommendations.append("High disk usage - clean up old data and optimize storage")
            
            # Response time recommendations
            if metrics.response_time_ms > self.thresholds['response_time_warning']:
                recommendations.append("Slow response time - optimize database queries and caching")
            
            # Cache recommendations
            if metrics.cache_hit_rate < 0.7:
                recommendations.append("Low cache hit rate - optimize caching strategy and increase cache size")
            
            # Throughput recommendations
            if metrics.throughput_per_second < 1:
                recommendations.append("Low throughput - check system resources and processing efficiency")
            
            # Alert-based recommendations
            critical_alerts = [alert for alert in alerts if alert['severity'] == 'CRITICAL']
            if critical_alerts:
                recommendations.append("Critical performance issues detected - immediate attention required")
            
            if not recommendations:
                recommendations.append("System performance is within acceptable parameters")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _generate_next_actions(self, performance_score: float, alerts: List[Dict[str, Any]]) -> List[str]:
        """Generate next actions based on performance score and alerts"""
        try:
            actions = []
            
            if performance_score < 50:
                actions.append("Immediate system review required")
                actions.append("Check all performance alerts")
                actions.append("Review system logs for errors")
                actions.append("Consider system restart or maintenance")
            elif performance_score < 70:
                actions.append("Schedule system maintenance")
                actions.append("Review performance metrics")
                actions.append("Update monitoring thresholds")
                actions.append("Plan system optimizations")
            else:
                actions.append("Continue monitoring")
                actions.append("Review optimization opportunities")
                actions.append("Plan system improvements")
            
            # Alert-specific actions
            critical_alerts = [alert for alert in alerts if alert['severity'] == 'CRITICAL']
            if critical_alerts:
                actions.append("Address critical performance alerts immediately")
            
            warning_alerts = [alert for alert in alerts if alert['severity'] == 'WARNING']
            if warning_alerts:
                actions.append("Monitor warning alerts and plan corrective actions")
            
            return actions
            
        except Exception as e:
            logger.error(f"Error generating next actions: {e}")
            return ["Error generating next actions"]
    
    def get_historical_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical performance metrics"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            historical_data = []
            for metrics in self.metrics_history:
                if metrics.timestamp >= cutoff_time:
                    historical_data.append({
                        'timestamp': metrics.timestamp.isoformat(),
                        'cpu_usage_percent': metrics.cpu_usage_percent,
                        'memory_usage_percent': metrics.memory_usage_percent,
                        'disk_usage_percent': metrics.disk_usage_percent,
                        'response_time_ms': metrics.response_time_ms,
                        'throughput_per_second': metrics.throughput_per_second
                    })
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical metrics: {e}")
            return []
    
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
performance_monitoring_system = PerformanceMonitoringSystem()














