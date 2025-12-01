"""
Signal Quality and Performance Monitoring System
Phase 5: Advanced signal quality monitoring, performance tracking, and system health assessment
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, F, Sum
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal, SignalAlert, SignalPerformance
from apps.signals.database_data_utils import get_database_health_status

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Signal quality metrics data structure"""
    timestamp: datetime
    signal_count: int
    success_rate: float
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    average_confidence: float
    average_quality: float
    data_freshness_hours: float
    system_health_score: float


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: datetime
    processing_time_seconds: float
    signals_per_minute: float
    database_query_time: float
    cache_hit_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_rate: float
    throughput: float


class SignalQualityMonitor:
    """Advanced signal quality and performance monitoring system"""
    
    def __init__(self):
        self.monitoring_interval = 300  # 5 minutes
        self.quality_thresholds = {
            'min_success_rate': 0.7,      # 70% minimum success rate
            'min_accuracy': 0.8,           # 80% minimum accuracy
            'max_data_age_hours': 2,       # 2 hours maximum data age
            'min_confidence': 0.6,         # 60% minimum confidence
            'max_processing_time': 300,    # 5 minutes maximum processing time
            'min_throughput': 10,          # 10 signals per minute minimum
            'max_error_rate': 0.05         # 5% maximum error rate
        }
        
        self.alert_cooldown = 900  # 15 minutes between alerts
        self.quality_history = []
        self.performance_history = []
    
    def monitor_signal_quality(self) -> Dict[str, Any]:
        """Monitor signal quality metrics"""
        try:
            logger.info("Monitoring signal quality...")
            
            # Get recent signals (last hour)
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(recent_signals)
            
            # Check data freshness
            data_freshness = self._check_data_freshness()
            
            # Assess system health
            system_health = self._assess_system_health(quality_metrics, data_freshness)
            
            # Generate quality report
            quality_report = {
                'timestamp': timezone.now().isoformat(),
                'quality_metrics': quality_metrics.__dict__,
                'data_freshness': data_freshness,
                'system_health': system_health,
                'quality_score': self._calculate_quality_score(quality_metrics),
                'recommendations': self._generate_quality_recommendations(quality_metrics),
                'alerts': self._check_quality_alerts(quality_metrics, data_freshness)
            }
            
            # Store in history
            self.quality_history.append(quality_metrics)
            if len(self.quality_history) > 100:  # Keep last 100 records
                self.quality_history = self.quality_history[-100:]
            
            logger.info(f"Signal quality monitoring completed - Score: {quality_report['quality_score']:.2f}")
            return quality_report
            
        except Exception as e:
            logger.error(f"Error monitoring signal quality: {e}")
            return {'error': str(e)}
    
    def _calculate_quality_metrics(self, signals: List[TradingSignal]) -> QualityMetrics:
        """Calculate comprehensive quality metrics"""
        try:
            signal_count = signals.count()
            
            if signal_count == 0:
                return QualityMetrics(
                    timestamp=timezone.now(),
                    signal_count=0,
                    success_rate=0.0,
                    accuracy=0.0,
                    precision=0.0,
                    recall=0.0,
                    f1_score=0.0,
                    average_confidence=0.0,
                    average_quality=0.0,
                    data_freshness_hours=0.0,
                    system_health_score=0.0
                )
            
            # Calculate success rate
            successful_signals = signals.filter(is_profitable=True).count()
            success_rate = successful_signals / signal_count if signal_count > 0 else 0.0
            
            # Calculate accuracy metrics
            accuracy_metrics = self._calculate_accuracy_metrics(signals)
            
            # Calculate average confidence and quality
            avg_confidence = signals.aggregate(
                avg_confidence=Avg('confidence_score')
            )['avg_confidence'] or 0.0
            
            avg_quality = signals.aggregate(
                avg_quality=Avg('quality_score')
            )['avg_quality'] or 0.0
            
            # Check data freshness
            data_freshness = self._get_data_freshness_hours()
            
            # Calculate system health score
            system_health_score = self._calculate_system_health_score(
                success_rate, accuracy_metrics['accuracy'], data_freshness
            )
            
            return QualityMetrics(
                timestamp=timezone.now(),
                signal_count=signal_count,
                success_rate=success_rate,
                accuracy=accuracy_metrics['accuracy'],
                precision=accuracy_metrics['precision'],
                recall=accuracy_metrics['recall'],
                f1_score=accuracy_metrics['f1_score'],
                average_confidence=float(avg_confidence),
                average_quality=float(avg_quality),
                data_freshness_hours=data_freshness,
                system_health_score=system_health_score
            )
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
            return QualityMetrics(
                timestamp=timezone.now(),
                signal_count=0,
                success_rate=0.0,
                accuracy=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                average_confidence=0.0,
                average_quality=0.0,
                data_freshness_hours=0.0,
                system_health_score=0.0
            )
    
    def _calculate_accuracy_metrics(self, signals: List[TradingSignal]) -> Dict[str, float]:
        """Calculate accuracy, precision, recall, and F1 score"""
        try:
            total_signals = signals.count()
            if total_signals == 0:
                return {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0}
            
            # Get signal performance data
            profitable_signals = signals.filter(is_profitable=True).count()
            executed_signals = signals.filter(is_executed=True).count()
            
            # Calculate accuracy (simplified)
            accuracy = profitable_signals / total_signals if total_signals > 0 else 0.0
            
            # Calculate precision (profitable signals / executed signals)
            precision = profitable_signals / executed_signals if executed_signals > 0 else 0.0
            
            # Calculate recall (simplified - same as accuracy for this use case)
            recall = accuracy
            
            # Calculate F1 score
            if precision + recall > 0:
                f1_score = 2 * (precision * recall) / (precision + recall)
            else:
                f1_score = 0.0
            
            return {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating accuracy metrics: {e}")
            return {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0}
    
    def _check_data_freshness(self) -> Dict[str, Any]:
        """Check data freshness across all symbols"""
        try:
            # Get latest data timestamp
            latest_data = MarketData.objects.order_by('-timestamp').first()
            
            if not latest_data:
                return {
                    'status': 'NO_DATA',
                    'age_hours': float('inf'),
                    'freshness_score': 0.0
                }
            
            # Calculate data age
            data_age = (timezone.now() - latest_data.timestamp).total_seconds() / 3600
            
            # Calculate freshness score
            if data_age <= 1:
                freshness_score = 100.0
                status = 'FRESH'
            elif data_age <= 2:
                freshness_score = 80.0
                status = 'ACCEPTABLE'
            elif data_age <= 4:
                freshness_score = 60.0
                status = 'STALE'
            else:
                freshness_score = 0.0
                status = 'CRITICAL'
            
            return {
                'status': status,
                'age_hours': data_age,
                'freshness_score': freshness_score,
                'latest_timestamp': latest_data.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return {
                'status': 'ERROR',
                'age_hours': float('inf'),
                'freshness_score': 0.0
            }
    
    def _get_data_freshness_hours(self) -> float:
        """Get data freshness in hours"""
        try:
            latest_data = MarketData.objects.order_by('-timestamp').first()
            if not latest_data:
                return float('inf')
            
            return (timezone.now() - latest_data.timestamp).total_seconds() / 3600
            
        except Exception as e:
            logger.error(f"Error getting data freshness: {e}")
            return float('inf')
    
    def _assess_system_health(self, quality_metrics: QualityMetrics, data_freshness: Dict[str, Any]) -> str:
        """Assess overall system health"""
        try:
            # Check critical thresholds
            if (quality_metrics.success_rate < 0.5 or 
                quality_metrics.accuracy < 0.6 or 
                data_freshness.get('age_hours', 0) > 4):
                return "CRITICAL"
            
            # Check warning thresholds
            if (quality_metrics.success_rate < 0.7 or 
                quality_metrics.accuracy < 0.8 or 
                data_freshness.get('age_hours', 0) > 2):
                return "DEGRADED"
            
            # Check if all metrics are good
            if (quality_metrics.success_rate >= 0.8 and 
                quality_metrics.accuracy >= 0.9 and 
                data_freshness.get('age_hours', 0) <= 1):
                return "EXCELLENT"
            
            return "HEALTHY"
            
        except Exception as e:
            logger.error(f"Error assessing system health: {e}")
            return "UNKNOWN"
    
    def _calculate_system_health_score(self, success_rate: float, accuracy: float, data_freshness: float) -> float:
        """Calculate overall system health score"""
        try:
            score = 100.0
            
            # Success rate impact (40% weight)
            if success_rate < 0.5:
                score -= 40
            elif success_rate < 0.7:
                score -= 20
            elif success_rate < 0.8:
                score -= 10
            
            # Accuracy impact (30% weight)
            if accuracy < 0.6:
                score -= 30
            elif accuracy < 0.8:
                score -= 15
            elif accuracy < 0.9:
                score -= 5
            
            # Data freshness impact (30% weight)
            if data_freshness > 4:
                score -= 30
            elif data_freshness > 2:
                score -= 15
            elif data_freshness > 1:
                score -= 5
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating system health score: {e}")
            return 0.0
    
    def _calculate_quality_score(self, quality_metrics: QualityMetrics) -> float:
        """Calculate overall quality score"""
        try:
            score = 100.0
            
            # Success rate penalty
            if quality_metrics.success_rate < self.quality_thresholds['min_success_rate']:
                score -= 30
            
            # Accuracy penalty
            if quality_metrics.accuracy < self.quality_thresholds['min_accuracy']:
                score -= 25
            
            # Data freshness penalty
            if quality_metrics.data_freshness_hours > self.quality_thresholds['max_data_age_hours']:
                score -= 20
            
            # Confidence penalty
            if quality_metrics.average_confidence < self.quality_thresholds['min_confidence']:
                score -= 15
            
            # Signal count bonus
            if quality_metrics.signal_count < 5:
                score -= 10
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 0.0
    
    def _generate_quality_recommendations(self, quality_metrics: QualityMetrics) -> List[str]:
        """Generate quality improvement recommendations"""
        try:
            recommendations = []
            
            if quality_metrics.success_rate < self.quality_thresholds['min_success_rate']:
                recommendations.append(
                    f"Success rate is {quality_metrics.success_rate:.1%} - review signal generation algorithms"
                )
            
            if quality_metrics.accuracy < self.quality_thresholds['min_accuracy']:
                recommendations.append(
                    f"Accuracy is {quality_metrics.accuracy:.1%} - improve signal validation logic"
                )
            
            if quality_metrics.data_freshness_hours > self.quality_thresholds['max_data_age_hours']:
                recommendations.append(
                    f"Data is {quality_metrics.data_freshness_hours:.1f} hours old - check data collection"
                )
            
            if quality_metrics.average_confidence < self.quality_thresholds['min_confidence']:
                recommendations.append(
                    f"Average confidence is {quality_metrics.average_confidence:.1%} - review confidence calculation"
                )
            
            if quality_metrics.signal_count < 5:
                recommendations.append(
                    f"Low signal count ({quality_metrics.signal_count}) - check signal generation process"
                )
            
            if not recommendations:
                recommendations.append("Signal quality is within acceptable parameters")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating quality recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _check_quality_alerts(self, quality_metrics: QualityMetrics, data_freshness: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for quality alerts that need to be raised"""
        try:
            alerts = []
            
            # Check if we should create alerts (cooldown period)
            last_alert_time = cache.get('last_quality_alert_time', 0)
            current_time = time.time()
            
            if current_time - last_alert_time < self.alert_cooldown:
                return alerts
            
            # Critical alerts
            if quality_metrics.success_rate < 0.5:
                alerts.append({
                    'type': 'CRITICAL',
                    'title': 'Low Success Rate',
                    'message': f'Signal success rate is {quality_metrics.success_rate:.1%}',
                    'metric': 'success_rate',
                    'value': quality_metrics.success_rate,
                    'threshold': self.quality_thresholds['min_success_rate']
                })
            
            if quality_metrics.accuracy < 0.6:
                alerts.append({
                    'type': 'CRITICAL',
                    'title': 'Low Accuracy',
                    'message': f'Signal accuracy is {quality_metrics.accuracy:.1%}',
                    'metric': 'accuracy',
                    'value': quality_metrics.accuracy,
                    'threshold': self.quality_thresholds['min_accuracy']
                })
            
            if data_freshness.get('age_hours', 0) > 4:
                alerts.append({
                    'type': 'CRITICAL',
                    'title': 'Stale Data',
                    'message': f'Data is {data_freshness.get("age_hours", 0):.1f} hours old',
                    'metric': 'data_freshness',
                    'value': data_freshness.get('age_hours', 0),
                    'threshold': self.quality_thresholds['max_data_age_hours']
                })
            
            # Warning alerts
            if quality_metrics.success_rate < 0.7:
                alerts.append({
                    'type': 'WARNING',
                    'title': 'Success Rate Warning',
                    'message': f'Signal success rate is {quality_metrics.success_rate:.1%}',
                    'metric': 'success_rate',
                    'value': quality_metrics.success_rate,
                    'threshold': self.quality_thresholds['min_success_rate']
                })
            
            if quality_metrics.accuracy < 0.8:
                alerts.append({
                    'type': 'WARNING',
                    'title': 'Accuracy Warning',
                    'message': f'Signal accuracy is {quality_metrics.accuracy:.1%}',
                    'metric': 'accuracy',
                    'value': quality_metrics.accuracy,
                    'threshold': self.quality_thresholds['min_accuracy']
                })
            
            # Create alerts in database
            for alert in alerts:
                self._create_quality_alert(alert)
            
            # Update cooldown
            if alerts:
                cache.set('last_quality_alert_time', current_time, 3600)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking quality alerts: {e}")
            return []
    
    def _create_quality_alert(self, alert_data: Dict[str, Any]):
        """Create quality alert in database"""
        try:
            SignalAlert.objects.create(
                title=alert_data['title'],
                message=alert_data['message'],
                priority=alert_data['type'],
                alert_type='QUALITY_ALERT',
                is_read=False
            )
            
            logger.warning(f"Quality alert created: {alert_data['title']}")
            
        except Exception as e:
            logger.error(f"Error creating quality alert: {e}")
    
    def monitor_performance(self) -> Dict[str, Any]:
        """Monitor system performance metrics"""
        try:
            logger.info("Monitoring system performance...")
            
            # Get performance metrics
            performance_metrics = self._calculate_performance_metrics()
            
            # Check performance thresholds
            performance_alerts = self._check_performance_alerts(performance_metrics)
            
            # Generate performance report
            performance_report = {
                'timestamp': timezone.now().isoformat(),
                'performance_metrics': performance_metrics.__dict__,
                'performance_score': self._calculate_performance_score(performance_metrics),
                'alerts': performance_alerts,
                'recommendations': self._generate_performance_recommendations(performance_metrics)
            }
            
            # Store in history
            self.performance_history.append(performance_metrics)
            if len(self.performance_history) > 100:  # Keep last 100 records
                self.performance_history = self.performance_history[-100:]
            
            logger.info(f"Performance monitoring completed - Score: {performance_report['performance_score']:.2f}")
            return performance_report
            
        except Exception as e:
            logger.error(f"Error monitoring performance: {e}")
            return {'error': str(e)}
    
    def _calculate_performance_metrics(self) -> PerformanceMetrics:
        """Calculate system performance metrics"""
        try:
            # Get recent signals for throughput calculation
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(minutes=10)
            )
            
            # Calculate processing time (simplified)
            processing_time = self._estimate_processing_time()
            
            # Calculate throughput
            signals_per_minute = recent_signals.count() / 10  # 10-minute window
            
            # Get database performance
            db_performance = self._get_database_performance()
            
            # Get cache performance
            cache_performance = self._get_cache_performance()
            
            # Get system resources
            system_resources = self._get_system_resources()
            
            # Calculate error rate
            error_rate = self._calculate_error_rate()
            
            return PerformanceMetrics(
                timestamp=timezone.now(),
                processing_time_seconds=processing_time,
                signals_per_minute=signals_per_minute,
                database_query_time=db_performance.get('avg_query_time', 0.0),
                cache_hit_rate=cache_performance.get('hit_rate', 0.0),
                memory_usage_mb=system_resources.get('memory_usage', 0.0),
                cpu_usage_percent=system_resources.get('cpu_usage', 0.0),
                error_rate=error_rate,
                throughput=signals_per_minute
            )
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return PerformanceMetrics(
                timestamp=timezone.now(),
                processing_time_seconds=0.0,
                signals_per_minute=0.0,
                database_query_time=0.0,
                cache_hit_rate=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                error_rate=0.0,
                throughput=0.0
            )
    
    def _estimate_processing_time(self) -> float:
        """Estimate signal processing time"""
        try:
            # This would be calculated from actual processing logs
            # For now, return a simulated value
            return 2.5  # 2.5 seconds average processing time
            
        except Exception as e:
            logger.error(f"Error estimating processing time: {e}")
            return 0.0
    
    def _get_database_performance(self) -> Dict[str, float]:
        """Get database performance metrics"""
        try:
            # This would be implemented with actual database monitoring
            return {
                'avg_query_time': 0.1,  # 100ms average query time
                'slow_queries': 0,
                'connection_count': 5
            }
            
        except Exception as e:
            logger.error(f"Error getting database performance: {e}")
            return {'avg_query_time': 0.0, 'slow_queries': 0, 'connection_count': 0}
    
    def _get_cache_performance(self) -> Dict[str, float]:
        """Get cache performance metrics"""
        try:
            # This would be implemented with actual cache monitoring
            return {
                'hit_rate': 0.85,  # 85% cache hit rate
                'miss_rate': 0.15,
                'eviction_rate': 0.05
            }
            
        except Exception as e:
            logger.error(f"Error getting cache performance: {e}")
            return {'hit_rate': 0.0, 'miss_rate': 0.0, 'eviction_rate': 0.0}
    
    def _get_system_resources(self) -> Dict[str, float]:
        """Get system resource usage"""
        try:
            # This would be implemented with actual system monitoring
            return {
                'memory_usage': 512.0,  # 512 MB memory usage
                'cpu_usage': 45.0,       # 45% CPU usage
                'disk_usage': 30.0       # 30% disk usage
            }
            
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {'memory_usage': 0.0, 'cpu_usage': 0.0, 'disk_usage': 0.0}
    
    def _calculate_error_rate(self) -> float:
        """Calculate system error rate"""
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
                return 0.0
            
            error_count = recent_alerts.filter(priority__in=['CRITICAL', 'HIGH']).count()
            return error_count / total_operations
            
        except Exception as e:
            logger.error(f"Error calculating error rate: {e}")
            return 0.0
    
    def _calculate_performance_score(self, performance_metrics: PerformanceMetrics) -> float:
        """Calculate overall performance score"""
        try:
            score = 100.0
            
            # Processing time penalty
            if performance_metrics.processing_time_seconds > self.quality_thresholds['max_processing_time']:
                score -= 40
            
            # Throughput penalty
            if performance_metrics.signals_per_minute < self.quality_thresholds['min_throughput']:
                score -= 30
            
            # Error rate penalty
            if performance_metrics.error_rate > self.quality_thresholds['max_error_rate']:
                score -= 20
            
            # Cache hit rate bonus
            if performance_metrics.cache_hit_rate < 0.7:
                score -= 10
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return 0.0
    
    def _check_performance_alerts(self, performance_metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """Check for performance alerts"""
        try:
            alerts = []
            
            # Check processing time
            if performance_metrics.processing_time_seconds > self.quality_thresholds['max_processing_time']:
                alerts.append({
                    'type': 'WARNING',
                    'title': 'High Processing Time',
                    'message': f'Processing time is {performance_metrics.processing_time_seconds:.1f}s',
                    'metric': 'processing_time',
                    'value': performance_metrics.processing_time_seconds,
                    'threshold': self.quality_thresholds['max_processing_time']
                })
            
            # Check throughput
            if performance_metrics.signals_per_minute < self.quality_thresholds['min_throughput']:
                alerts.append({
                    'type': 'WARNING',
                    'title': 'Low Throughput',
                    'message': f'Throughput is {performance_metrics.signals_per_minute:.1f} signals/min',
                    'metric': 'throughput',
                    'value': performance_metrics.signals_per_minute,
                    'threshold': self.quality_thresholds['min_throughput']
                })
            
            # Check error rate
            if performance_metrics.error_rate > self.quality_thresholds['max_error_rate']:
                alerts.append({
                    'type': 'CRITICAL',
                    'title': 'High Error Rate',
                    'message': f'Error rate is {performance_metrics.error_rate:.1%}',
                    'metric': 'error_rate',
                    'value': performance_metrics.error_rate,
                    'threshold': self.quality_thresholds['max_error_rate']
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
            return []
    
    def _generate_performance_recommendations(self, performance_metrics: PerformanceMetrics) -> List[str]:
        """Generate performance improvement recommendations"""
        try:
            recommendations = []
            
            if performance_metrics.processing_time_seconds > self.quality_thresholds['max_processing_time']:
                recommendations.append("High processing time - optimize algorithms and database queries")
            
            if performance_metrics.signals_per_minute < self.quality_thresholds['min_throughput']:
                recommendations.append("Low throughput - check system resources and processing efficiency")
            
            if performance_metrics.error_rate > self.quality_thresholds['max_error_rate']:
                recommendations.append("High error rate - review error handling and system stability")
            
            if performance_metrics.cache_hit_rate < 0.7:
                recommendations.append("Low cache hit rate - optimize caching strategy")
            
            if not recommendations:
                recommendations.append("Performance is within acceptable parameters")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
            return ["Error generating recommendations"]
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive quality and performance report"""
        try:
            logger.info("Generating comprehensive quality and performance report...")
            
            # Get quality report
            quality_report = self.monitor_signal_quality()
            
            # Get performance report
            performance_report = self.monitor_performance()
            
            # Calculate overall score
            quality_score = quality_report.get('quality_score', 0)
            performance_score = performance_report.get('performance_score', 0)
            overall_score = (quality_score + performance_score) / 2
            
            # Determine overall status
            if overall_score >= 90:
                status = "EXCELLENT"
            elif overall_score >= 80:
                status = "GOOD"
            elif overall_score >= 70:
                status = "WARNING"
            elif overall_score >= 50:
                status = "CRITICAL"
            else:
                status = "DOWN"
            
            comprehensive_report = {
                'timestamp': timezone.now().isoformat(),
                'overall_score': overall_score,
                'overall_status': status,
                'quality_report': quality_report,
                'performance_report': performance_report,
                'trends': self._analyze_trends(),
                'recommendations': self._generate_comprehensive_recommendations(quality_report, performance_report),
                'next_actions': self._generate_next_actions(overall_score)
            }
            
            logger.info(f"Comprehensive report generated - Overall Score: {overall_score:.1f}")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report: {e}")
            return {'error': str(e)}
    
    def _analyze_trends(self) -> Dict[str, Any]:
        """Analyze quality and performance trends"""
        try:
            if len(self.quality_history) < 2:
                return {'trend': 'INSUFFICIENT_DATA'}
            
            # Analyze quality trends
            recent_quality = self.quality_history[-5:]  # Last 5 records
            quality_trend = 'STABLE'
            
            if len(recent_quality) >= 2:
                first_score = recent_quality[0].system_health_score
                last_score = recent_quality[-1].system_health_score
                
                if last_score > first_score + 10:
                    quality_trend = 'IMPROVING'
                elif last_score < first_score - 10:
                    quality_trend = 'DEGRADING'
            
            # Analyze performance trends
            if len(self.performance_history) < 2:
                performance_trend = 'INSUFFICIENT_DATA'
            else:
                recent_performance = self.performance_history[-5:]
                performance_trend = 'STABLE'
                
                if len(recent_performance) >= 2:
                    first_throughput = recent_performance[0].throughput
                    last_throughput = recent_performance[-1].throughput
                    
                    if last_throughput > first_throughput * 1.2:
                        performance_trend = 'IMPROVING'
                    elif last_throughput < first_throughput * 0.8:
                        performance_trend = 'DEGRADING'
            
            return {
                'quality_trend': quality_trend,
                'performance_trend': performance_trend,
                'overall_trend': 'STABLE'  # Simplified
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {'trend': 'ERROR'}
    
    def _generate_comprehensive_recommendations(self, quality_report: Dict, performance_report: Dict) -> List[str]:
        """Generate comprehensive recommendations"""
        try:
            recommendations = []
            
            # Quality recommendations
            quality_recommendations = quality_report.get('recommendations', [])
            recommendations.extend(quality_recommendations)
            
            # Performance recommendations
            performance_recommendations = performance_report.get('recommendations', [])
            recommendations.extend(performance_recommendations)
            
            # Remove duplicates
            recommendations = list(set(recommendations))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating comprehensive recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _generate_next_actions(self, overall_score: float) -> List[str]:
        """Generate next actions based on overall score"""
        try:
            actions = []
            
            if overall_score < 70:
                actions.append("Immediate system review required")
                actions.append("Check all quality and performance alerts")
                actions.append("Review system logs for errors")
                actions.append("Consider system restart or maintenance")
            
            elif overall_score < 80:
                actions.append("Schedule system maintenance")
                actions.append("Review performance metrics")
                actions.append("Update monitoring thresholds")
                actions.append("Plan system optimizations")
            
            else:
                actions.append("Continue monitoring")
                actions.append("Review optimization opportunities")
                actions.append("Plan system improvements")
                actions.append("Maintain current performance levels")
            
            return actions
            
        except Exception as e:
            logger.error(f"Error generating next actions: {e}")
            return ["Error generating next actions"]


# Global instance
signal_quality_monitor = SignalQualityMonitor()














