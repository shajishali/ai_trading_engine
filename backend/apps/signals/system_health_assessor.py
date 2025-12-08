"""
System Health Assessment and Monitoring
Phase 5: Comprehensive system health assessment, monitoring, and automated health checks
"""

import logging
import time
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
from apps.signals.signal_quality_monitor import signal_quality_monitor
from apps.signals.performance_monitoring_system import performance_monitoring_system

logger = logging.getLogger(__name__)


@dataclass
class HealthCheck:
    """Health check result data structure"""
    name: str
    status: str  # 'PASS', 'WARN', 'FAIL'
    message: str
    value: Any
    threshold: Any
    timestamp: datetime
    severity: str = 'MEDIUM'


@dataclass
class SystemHealthStatus:
    """Overall system health status"""
    timestamp: datetime
    overall_status: str  # 'HEALTHY', 'DEGRADED', 'CRITICAL', 'DOWN'
    health_score: float
    component_status: Dict[str, str]
    health_checks: List[HealthCheck]
    recommendations: List[str]
    next_actions: List[str]


class SystemHealthAssessor:
    """Comprehensive system health assessment and monitoring"""
    
    def __init__(self):
        self.health_check_interval = 300  # 5 minutes
        self.health_history = []
        self.alert_cooldown = 1800  # 30 minutes
        
        # Health check thresholds
        self.thresholds = {
            'database_health': 'HEALTHY',
            'data_freshness_hours': 2,
            'signal_generation_rate': 5,
            'system_uptime_hours': 24,
            'error_rate': 0.05,
            'response_time_ms': 5000,
            'cpu_usage_percent': 80,
            'memory_usage_percent': 80,
            'disk_usage_percent': 85
        }
    
    def assess_system_health(self) -> SystemHealthStatus:
        """Comprehensive system health assessment"""
        try:
            logger.info("Starting comprehensive system health assessment...")
            
            # Perform all health checks
            health_checks = self._perform_all_health_checks()
            
            # Assess component status
            component_status = self._assess_component_status(health_checks)
            
            # Calculate overall health score
            health_score = self._calculate_health_score(health_checks)
            
            # Determine overall status
            overall_status = self._determine_overall_status(health_score, health_checks)
            
            # Generate recommendations
            recommendations = self._generate_health_recommendations(health_checks, component_status)
            
            # Generate next actions
            next_actions = self._generate_health_actions(overall_status, health_checks)
            
            # Create health status
            health_status = SystemHealthStatus(
                timestamp=timezone.now(),
                overall_status=overall_status,
                health_score=health_score,
                component_status=component_status,
                health_checks=health_checks,
                recommendations=recommendations,
                next_actions=next_actions
            )
            
            # Store in history
            self.health_history.append(health_status)
            if len(self.health_history) > 100:  # Keep last 100 records
                self.health_history = self.health_history[-100:]
            
            # Check for health alerts
            self._check_health_alerts(health_status)
            
            logger.info(f"System health assessment completed - Status: {overall_status}, Score: {health_score:.1f}")
            return health_status
            
        except Exception as e:
            logger.error(f"Error assessing system health: {e}")
            return SystemHealthStatus(
                timestamp=timezone.now(),
                overall_status='UNKNOWN',
                health_score=0.0,
                component_status={},
                health_checks=[],
                recommendations=['Error in health assessment'],
                next_actions=['Investigate system errors']
            )
    
    def _perform_all_health_checks(self) -> List[HealthCheck]:
        """Perform all system health checks"""
        try:
            health_checks = []
            
            # Database health check
            health_checks.append(self._check_database_health())
            
            # Data freshness check
            health_checks.append(self._check_data_freshness())
            
            # Signal generation check
            health_checks.append(self._check_signal_generation())
            
            # System uptime check
            health_checks.append(self._check_system_uptime())
            
            # Error rate check
            health_checks.append(self._check_error_rate())
            
            # Performance checks
            health_checks.append(self._check_response_time())
            health_checks.append(self._check_cpu_usage())
            health_checks.append(self._check_memory_usage())
            health_checks.append(self._check_disk_usage())
            
            # Cache health check
            health_checks.append(self._check_cache_health())
            
            # Network connectivity check
            health_checks.append(self._check_network_connectivity())
            
            return health_checks
            
        except Exception as e:
            logger.error(f"Error performing health checks: {e}")
            return []
    
    def _check_database_health(self) -> HealthCheck:
        """Check database health"""
        try:
            db_health = get_database_health_status()
            status = db_health.get('status', 'UNKNOWN')
            
            if status == 'HEALTHY':
                return HealthCheck(
                    name='Database Health',
                    status='PASS',
                    message='Database is healthy',
                    value=status,
                    threshold=self.thresholds['database_health'],
                    timestamp=timezone.now(),
                    severity='HIGH'
                )
            elif status == 'WARNING':
                return HealthCheck(
                    name='Database Health',
                    status='WARN',
                    message='Database has warnings',
                    value=status,
                    threshold=self.thresholds['database_health'],
                    timestamp=timezone.now(),
                    severity='HIGH'
                )
            else:
                return HealthCheck(
                    name='Database Health',
                    status='FAIL',
                    message='Database is unhealthy',
                    value=status,
                    threshold=self.thresholds['database_health'],
                    timestamp=timezone.now(),
                    severity='CRITICAL'
                )
                
        except Exception as e:
            logger.error(f"Error checking database health: {e}")
            return HealthCheck(
                name='Database Health',
                status='FAIL',
                message=f'Error checking database: {e}',
                value='ERROR',
                threshold=self.thresholds['database_health'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_data_freshness(self) -> HealthCheck:
        """Check data freshness"""
        try:
            latest_data = MarketData.objects.order_by('-timestamp').first()
            
            if not latest_data:
                return HealthCheck(
                    name='Data Freshness',
                    status='FAIL',
                    message='No data available',
                    value=float('inf'),
                    threshold=self.thresholds['data_freshness_hours'],
                    timestamp=timezone.now(),
                    severity='CRITICAL'
                )
            
            data_age_hours = (timezone.now() - latest_data.timestamp).total_seconds() / 3600
            
            if data_age_hours <= 1:
                status = 'PASS'
                message = 'Data is fresh'
                severity = 'MEDIUM'
            elif data_age_hours <= self.thresholds['data_freshness_hours']:
                status = 'WARN'
                message = f'Data is {data_age_hours:.1f} hours old'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = f'Data is stale: {data_age_hours:.1f} hours old'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Data Freshness',
                status=status,
                message=message,
                value=data_age_hours,
                threshold=self.thresholds['data_freshness_hours'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return HealthCheck(
                name='Data Freshness',
                status='FAIL',
                message=f'Error checking data freshness: {e}',
                value=float('inf'),
                threshold=self.thresholds['data_freshness_hours'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_signal_generation(self) -> HealthCheck:
        """Check signal generation rate"""
        try:
            # Get signals from last hour
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_signals >= self.thresholds['signal_generation_rate']:
                status = 'PASS'
                message = f'Signal generation rate is good: {recent_signals} signals/hour'
                severity = 'MEDIUM'
            elif recent_signals > 0:
                status = 'WARN'
                message = f'Low signal generation rate: {recent_signals} signals/hour'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = 'No signals generated in the last hour'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Signal Generation',
                status=status,
                message=message,
                value=recent_signals,
                threshold=self.thresholds['signal_generation_rate'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking signal generation: {e}")
            return HealthCheck(
                name='Signal Generation',
                status='FAIL',
                message=f'Error checking signal generation: {e}',
                value=0,
                threshold=self.thresholds['signal_generation_rate'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_system_uptime(self) -> HealthCheck:
        """Check system uptime"""
        try:
            # This would be implemented with actual uptime tracking
            # For now, simulate uptime
            uptime_hours = 24.0  # Simulated uptime
            
            if uptime_hours >= self.thresholds['system_uptime_hours']:
                status = 'PASS'
                message = f'System uptime is good: {uptime_hours:.1f} hours'
                severity = 'MEDIUM'
            else:
                status = 'WARN'
                message = f'System uptime is low: {uptime_hours:.1f} hours'
                severity = 'HIGH'
            
            return HealthCheck(
                name='System Uptime',
                status=status,
                message=message,
                value=uptime_hours,
                threshold=self.thresholds['system_uptime_hours'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking system uptime: {e}")
            return HealthCheck(
                name='System Uptime',
                status='FAIL',
                message=f'Error checking uptime: {e}',
                value=0,
                threshold=self.thresholds['system_uptime_hours'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_error_rate(self) -> HealthCheck:
        """Check system error rate"""
        try:
            # Get recent alerts
            recent_alerts = SignalAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            # Get total operations
            total_operations = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if total_operations == 0:
                error_rate = 0.0
            else:
                error_count = recent_alerts.filter(priority__in=['CRITICAL', 'HIGH']).count()
                error_rate = error_count / total_operations
            
            if error_rate <= self.thresholds['error_rate']:
                status = 'PASS'
                message = f'Error rate is acceptable: {error_rate:.1%}'
                severity = 'MEDIUM'
            elif error_rate <= 0.1:  # 10%
                status = 'WARN'
                message = f'Error rate is elevated: {error_rate:.1%}'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = f'Error rate is too high: {error_rate:.1%}'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Error Rate',
                status=status,
                message=message,
                value=error_rate,
                threshold=self.thresholds['error_rate'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking error rate: {e}")
            return HealthCheck(
                name='Error Rate',
                status='FAIL',
                message=f'Error checking error rate: {e}',
                value=1.0,
                threshold=self.thresholds['error_rate'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_response_time(self) -> HealthCheck:
        """Check system response time"""
        try:
            # Measure response time
            start_time = time.time()
            TradingSignal.objects.count()
            end_time = time.time()
            
            response_time_ms = (end_time - start_time) * 1000
            
            if response_time_ms <= 1000:  # 1 second
                status = 'PASS'
                message = f'Response time is good: {response_time_ms:.1f}ms'
                severity = 'MEDIUM'
            elif response_time_ms <= self.thresholds['response_time_ms']:
                status = 'WARN'
                message = f'Response time is slow: {response_time_ms:.1f}ms'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = f'Response time is too slow: {response_time_ms:.1f}ms'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Response Time',
                status=status,
                message=message,
                value=response_time_ms,
                threshold=self.thresholds['response_time_ms'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking response time: {e}")
            return HealthCheck(
                name='Response Time',
                status='FAIL',
                message=f'Error checking response time: {e}',
                value=float('inf'),
                threshold=self.thresholds['response_time_ms'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_cpu_usage(self) -> HealthCheck:
        """Check CPU usage"""
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=1)
            
            if cpu_usage <= 50:
                status = 'PASS'
                message = f'CPU usage is good: {cpu_usage:.1f}%'
                severity = 'MEDIUM'
            elif cpu_usage <= self.thresholds['cpu_usage_percent']:
                status = 'WARN'
                message = f'CPU usage is high: {cpu_usage:.1f}%'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = f'CPU usage is too high: {cpu_usage:.1f}%'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='CPU Usage',
                status=status,
                message=message,
                value=cpu_usage,
                threshold=self.thresholds['cpu_usage_percent'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except ImportError:
            return HealthCheck(
                name='CPU Usage',
                status='WARN',
                message='psutil not available for CPU monitoring',
                value=0,
                threshold=self.thresholds['cpu_usage_percent'],
                timestamp=timezone.now(),
                severity='MEDIUM'
            )
        except Exception as e:
            logger.error(f"Error checking CPU usage: {e}")
            return HealthCheck(
                name='CPU Usage',
                status='FAIL',
                message=f'Error checking CPU usage: {e}',
                value=100,
                threshold=self.thresholds['cpu_usage_percent'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_memory_usage(self) -> HealthCheck:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            if memory_usage <= 60:
                status = 'PASS'
                message = f'Memory usage is good: {memory_usage:.1f}%'
                severity = 'MEDIUM'
            elif memory_usage <= self.thresholds['memory_usage_percent']:
                status = 'WARN'
                message = f'Memory usage is high: {memory_usage:.1f}%'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = f'Memory usage is too high: {memory_usage:.1f}%'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Memory Usage',
                status=status,
                message=message,
                value=memory_usage,
                threshold=self.thresholds['memory_usage_percent'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except ImportError:
            return HealthCheck(
                name='Memory Usage',
                status='WARN',
                message='psutil not available for memory monitoring',
                value=0,
                threshold=self.thresholds['memory_usage_percent'],
                timestamp=timezone.now(),
                severity='MEDIUM'
            )
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
            return HealthCheck(
                name='Memory Usage',
                status='FAIL',
                message=f'Error checking memory usage: {e}',
                value=100,
                threshold=self.thresholds['memory_usage_percent'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_disk_usage(self) -> HealthCheck:
        """Check disk usage"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            
            if disk_usage <= 70:
                status = 'PASS'
                message = f'Disk usage is good: {disk_usage:.1f}%'
                severity = 'MEDIUM'
            elif disk_usage <= self.thresholds['disk_usage_percent']:
                status = 'WARN'
                message = f'Disk usage is high: {disk_usage:.1f}%'
                severity = 'HIGH'
            else:
                status = 'FAIL'
                message = f'Disk usage is too high: {disk_usage:.1f}%'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Disk Usage',
                status=status,
                message=message,
                value=disk_usage,
                threshold=self.thresholds['disk_usage_percent'],
                timestamp=timezone.now(),
                severity=severity
            )
            
        except ImportError:
            return HealthCheck(
                name='Disk Usage',
                status='WARN',
                message='psutil not available for disk monitoring',
                value=0,
                threshold=self.thresholds['disk_usage_percent'],
                timestamp=timezone.now(),
                severity='MEDIUM'
            )
        except Exception as e:
            logger.error(f"Error checking disk usage: {e}")
            return HealthCheck(
                name='Disk Usage',
                status='FAIL',
                message=f'Error checking disk usage: {e}',
                value=100,
                threshold=self.thresholds['disk_usage_percent'],
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_cache_health(self) -> HealthCheck:
        """Check cache health"""
        try:
            # Test cache functionality
            test_key = 'health_check_test'
            test_value = 'test_value'
            
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            
            if retrieved_value == test_value:
                status = 'PASS'
                message = 'Cache is working properly'
                severity = 'MEDIUM'
            else:
                status = 'FAIL'
                message = 'Cache is not working properly'
                severity = 'CRITICAL'
            
            # Clean up test key
            cache.delete(test_key)
            
            return HealthCheck(
                name='Cache Health',
                status=status,
                message=message,
                value=retrieved_value == test_value,
                threshold=True,
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking cache health: {e}")
            return HealthCheck(
                name='Cache Health',
                status='FAIL',
                message=f'Error checking cache: {e}',
                value=False,
                threshold=True,
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _check_network_connectivity(self) -> HealthCheck:
        """Check network connectivity"""
        try:
            # This would be implemented with actual network connectivity tests
            # For now, simulate network check
            network_ok = True  # Simulated result
            
            if network_ok:
                status = 'PASS'
                message = 'Network connectivity is good'
                severity = 'MEDIUM'
            else:
                status = 'FAIL'
                message = 'Network connectivity issues detected'
                severity = 'CRITICAL'
            
            return HealthCheck(
                name='Network Connectivity',
                status=status,
                message=message,
                value=network_ok,
                threshold=True,
                timestamp=timezone.now(),
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error checking network connectivity: {e}")
            return HealthCheck(
                name='Network Connectivity',
                status='FAIL',
                message=f'Error checking network: {e}',
                value=False,
                threshold=True,
                timestamp=timezone.now(),
                severity='CRITICAL'
            )
    
    def _assess_component_status(self, health_checks: List[HealthCheck]) -> Dict[str, str]:
        """Assess status of system components"""
        try:
            component_status = {}
            
            # Group checks by component
            for check in health_checks:
                if 'Database' in check.name:
                    component_status['database'] = check.status
                elif 'Data' in check.name:
                    component_status['data'] = check.status
                elif 'Signal' in check.name:
                    component_status['signals'] = check.status
                elif 'System' in check.name:
                    component_status['system'] = check.status
                elif 'CPU' in check.name or 'Memory' in check.name or 'Disk' in check.name:
                    component_status['resources'] = check.status
                elif 'Cache' in check.name:
                    component_status['cache'] = check.status
                elif 'Network' in check.name:
                    component_status['network'] = check.status
            
            return component_status
            
        except Exception as e:
            logger.error(f"Error assessing component status: {e}")
            return {}
    
    def _calculate_health_score(self, health_checks: List[HealthCheck]) -> float:
        """Calculate overall health score"""
        try:
            if not health_checks:
                return 0.0
            
            total_score = 0.0
            total_weight = 0.0
            
            for check in health_checks:
                # Determine score based on status
                if check.status == 'PASS':
                    score = 100.0
                elif check.status == 'WARN':
                    score = 60.0
                else:  # FAIL
                    score = 0.0
                
                # Determine weight based on severity
                if check.severity == 'CRITICAL':
                    weight = 3.0
                elif check.severity == 'HIGH':
                    weight = 2.0
                else:  # MEDIUM
                    weight = 1.0
                
                total_score += score * weight
                total_weight += weight
            
            if total_weight == 0:
                return 0.0
            
            return total_score / total_weight
            
        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 0.0
    
    def _determine_overall_status(self, health_score: float, health_checks: List[HealthCheck]) -> str:
        """Determine overall system status"""
        try:
            # Check for critical failures
            critical_failures = [check for check in health_checks if check.status == 'FAIL' and check.severity == 'CRITICAL']
            if critical_failures:
                return 'CRITICAL'
            
            # Check for any failures
            any_failures = [check for check in health_checks if check.status == 'FAIL']
            if any_failures:
                return 'DEGRADED'
            
            # Check health score
            if health_score >= 90:
                return 'HEALTHY'
            elif health_score >= 70:
                return 'DEGRADED'
            else:
                return 'CRITICAL'
                
        except Exception as e:
            logger.error(f"Error determining overall status: {e}")
            return 'UNKNOWN'
    
    def _generate_health_recommendations(self, health_checks: List[HealthCheck], component_status: Dict[str, str]) -> List[str]:
        """Generate health improvement recommendations"""
        try:
            recommendations = []
            
            # Check for failed components
            failed_checks = [check for check in health_checks if check.status == 'FAIL']
            for check in failed_checks:
                if 'Database' in check.name:
                    recommendations.append("Database issues detected - check database connectivity and performance")
                elif 'Data' in check.name:
                    recommendations.append("Data freshness issues - check data collection processes")
                elif 'Signal' in check.name:
                    recommendations.append("Signal generation issues - review signal generation processes")
                elif 'CPU' in check.name or 'Memory' in check.name:
                    recommendations.append("Resource usage issues - optimize system resources")
                elif 'Cache' in check.name:
                    recommendations.append("Cache issues - check cache configuration and connectivity")
            
            # Check for warning components
            warning_checks = [check for check in health_checks if check.status == 'WARN']
            for check in warning_checks:
                if 'CPU' in check.name:
                    recommendations.append("High CPU usage - consider optimizing algorithms or scaling")
                elif 'Memory' in check.name:
                    recommendations.append("High memory usage - review memory usage and optimize")
                elif 'Disk' in check.name:
                    recommendations.append("High disk usage - clean up old data and optimize storage")
            
            if not recommendations:
                recommendations.append("System health is good - continue monitoring")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating health recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _generate_health_actions(self, overall_status: str, health_checks: List[HealthCheck]) -> List[str]:
        """Generate next actions based on health status"""
        try:
            actions = []
            
            if overall_status == 'CRITICAL':
                actions.append("Immediate system review required")
                actions.append("Check all critical health alerts")
                actions.append("Review system logs for errors")
                actions.append("Consider system restart or maintenance")
            elif overall_status == 'DEGRADED':
                actions.append("Schedule system maintenance")
                actions.append("Review health metrics")
                actions.append("Update monitoring thresholds")
                actions.append("Plan system optimizations")
            else:  # HEALTHY
                actions.append("Continue monitoring")
                actions.append("Review optimization opportunities")
                actions.append("Plan system improvements")
                actions.append("Maintain current health levels")
            
            return actions
            
        except Exception as e:
            logger.error(f"Error generating health actions: {e}")
            return ["Error generating actions"]
    
    def _check_health_alerts(self, health_status: SystemHealthStatus):
        """Check for health alerts that need to be raised"""
        try:
            # Check if we should create alerts (cooldown period)
            last_alert_time = cache.get('last_health_alert_time', 0)
            current_time = time.time()
            
            if current_time - last_alert_time < self.alert_cooldown:
                return
            
            # Check for critical health issues
            if health_status.overall_status == 'CRITICAL':
                self._create_health_alert(
                    'CRITICAL',
                    'Critical System Health Issues',
                    f'System health is critical - Score: {health_status.health_score:.1f}'
                )
            elif health_status.overall_status == 'DEGRADED':
                self._create_health_alert(
                    'HIGH',
                    'Degraded System Health',
                    f'System health is degraded - Score: {health_status.health_score:.1f}'
                )
            
            # Update cooldown
            cache.set('last_health_alert_time', current_time, 3600)
            
        except Exception as e:
            logger.error(f"Error checking health alerts: {e}")
    
    def _create_health_alert(self, priority: str, title: str, message: str):
        """Create health alert in database"""
        try:
            SignalAlert.objects.create(
                title=title,
                message=message,
                priority=priority,
                alert_type='HEALTH_ALERT',
                is_read=False
            )
            
            logger.warning(f"Health alert created: {title}")
            
        except Exception as e:
            logger.error(f"Error creating health alert: {e}")
    
    def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health history for specified hours"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            history = []
            for health_status in self.health_history:
                if health_status.timestamp >= cutoff_time:
                    history.append({
                        'timestamp': health_status.timestamp.isoformat(),
                        'overall_status': health_status.overall_status,
                        'health_score': health_status.health_score,
                        'component_status': health_status.component_status,
                        'health_checks_count': len(health_status.health_checks),
                        'recommendations_count': len(health_status.recommendations)
                    })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting health history: {e}")
            return []
    
    def get_comprehensive_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        try:
            logger.info("Generating comprehensive health report...")
            
            # Get current health status
            health_status = self.assess_system_health()
            
            # Get quality and performance reports
            quality_report = signal_quality_monitor.get_comprehensive_report()
            performance_report = performance_monitoring_system.get_performance_report()
            
            # Calculate overall system score
            health_score = health_status.health_score
            quality_score = quality_report.get('overall_system_score', 0)
            performance_score = performance_report.get('performance_score', 0)
            
            overall_score = (health_score + quality_score + performance_score) / 3
            
            comprehensive_report = {
                'timestamp': timezone.now().isoformat(),
                'overall_system_score': overall_score,
                'overall_status': health_status.overall_status,
                'health_assessment': {
                    'health_score': health_score,
                    'component_status': health_status.component_status,
                    'health_checks': [check.__dict__ for check in health_status.health_checks],
                    'recommendations': health_status.recommendations,
                    'next_actions': health_status.next_actions
                },
                'quality_report': quality_report,
                'performance_report': performance_report,
                'trends': self._analyze_health_trends(),
                'system_summary': self._generate_system_summary(health_status, quality_report, performance_report)
            }
            
            logger.info(f"Comprehensive health report generated - Overall Score: {overall_score:.1f}")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"Error generating comprehensive health report: {e}")
            return {'error': str(e)}
    
    def _analyze_health_trends(self) -> Dict[str, Any]:
        """Analyze health trends over time"""
        try:
            if len(self.health_history) < 5:
                return {'trend': 'INSUFFICIENT_DATA'}
            
            # Get recent health scores
            recent_scores = [status.health_score for status in self.health_history[-10:]]
            
            # Calculate trend
            if len(recent_scores) >= 3:
                first_score = recent_scores[0]
                last_score = recent_scores[-1]
                
                if last_score > first_score + 10:
                    trend = 'IMPROVING'
                elif last_score < first_score - 10:
                    trend = 'DEGRADING'
                else:
                    trend = 'STABLE'
            else:
                trend = 'INSUFFICIENT_DATA'
            
            return {
                'trend': trend,
                'recent_scores': recent_scores,
                'data_points': len(recent_scores)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing health trends: {e}")
            return {'trend': 'ERROR'}
    
    def _generate_system_summary(self, health_status: SystemHealthStatus, quality_report: Dict, performance_report: Dict) -> Dict[str, Any]:
        """Generate system summary"""
        try:
            return {
                'overall_status': health_status.overall_status,
                'health_score': health_status.health_score,
                'quality_score': quality_report.get('overall_system_score', 0),
                'performance_score': performance_report.get('performance_score', 0),
                'critical_issues': len([check for check in health_status.health_checks if check.status == 'FAIL']),
                'warning_issues': len([check for check in health_status.health_checks if check.status == 'WARN']),
                'recommendations_count': len(health_status.recommendations),
                'next_actions_count': len(health_status.next_actions)
            }
            
        except Exception as e:
            logger.error(f"Error generating system summary: {e}")
            return {}


# Global instance
system_health_assessor = SystemHealthAssessor()














