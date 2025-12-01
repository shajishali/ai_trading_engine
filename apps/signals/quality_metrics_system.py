"""
Comprehensive Quality Metrics and Scoring System
Phase 5: Advanced quality metrics, scoring algorithms, and quality assurance
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, F, StdDev, Variance
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData
from apps.signals.models import TradingSignal, SignalAlert, SignalPerformance
from apps.signals.database_data_utils import get_database_health_status

logger = logging.getLogger(__name__)


@dataclass
class QualityMetric:
    """Quality metric data structure"""
    name: str
    value: float
    weight: float
    threshold: float
    status: str  # 'EXCELLENT', 'GOOD', 'WARNING', 'CRITICAL'
    trend: str   # 'IMPROVING', 'STABLE', 'DEGRADING'
    timestamp: datetime


@dataclass
class QualityScore:
    """Quality score data structure"""
    overall_score: float
    component_scores: Dict[str, float]
    weighted_score: float
    grade: str  # 'A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F'
    recommendations: List[str]
    timestamp: datetime


class QualityMetricsSystem:
    """Comprehensive quality metrics and scoring system"""
    
    def __init__(self):
        self.metrics_cache_timeout = 1800  # 30 minutes
        self.scoring_weights = {
            'signal_quality': 0.25,
            'data_quality': 0.20,
            'system_performance': 0.20,
            'accuracy': 0.15,
            'reliability': 0.10,
            'efficiency': 0.10
        }
        
        # Quality thresholds
        self.thresholds = {
            'excellent': 90.0,
            'good': 80.0,
            'warning': 70.0,
            'critical': 50.0
        }
        
        self.metrics_history = []
        self.scores_history = []
    
    def calculate_comprehensive_quality_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive quality metrics"""
        try:
            logger.info("Calculating comprehensive quality metrics...")
            
            # Calculate all quality metrics
            signal_quality_metrics = self._calculate_signal_quality_metrics()
            data_quality_metrics = self._calculate_data_quality_metrics()
            system_performance_metrics = self._calculate_system_performance_metrics()
            accuracy_metrics = self._calculate_accuracy_metrics()
            reliability_metrics = self._calculate_reliability_metrics()
            efficiency_metrics = self._calculate_efficiency_metrics()
            
            # Combine all metrics
            all_metrics = {
                'signal_quality': signal_quality_metrics,
                'data_quality': data_quality_metrics,
                'system_performance': system_performance_metrics,
                'accuracy': accuracy_metrics,
                'reliability': reliability_metrics,
                'efficiency': efficiency_metrics
            }
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(all_metrics)
            
            # Generate recommendations
            recommendations = self._generate_quality_recommendations(all_metrics, quality_score)
            
            # Analyze trends
            trends = self._analyze_quality_trends()
            
            comprehensive_metrics = {
                'timestamp': timezone.now().isoformat(),
                'quality_metrics': all_metrics,
                'quality_score': quality_score.__dict__,
                'recommendations': recommendations,
                'trends': trends,
                'summary': self._generate_quality_summary(all_metrics, quality_score)
            }
            
            # Store in history
            self.metrics_history.append(all_metrics)
            if len(self.metrics_history) > 100:  # Keep last 100 records
                self.metrics_history = self.metrics_history[-100:]
            
            logger.info(f"Quality metrics calculated - Overall Score: {quality_score.overall_score:.1f}")
            return comprehensive_metrics
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_signal_quality_metrics(self) -> Dict[str, QualityMetric]:
        """Calculate signal quality metrics"""
        try:
            metrics = {}
            
            # Get recent signals
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            if not recent_signals.exists():
                return {}
            
            # Signal generation rate
            signal_count = recent_signals.count()
            expected_signals = 24 * 4  # 4 signals per hour expected
            generation_rate = min(signal_count / expected_signals * 100, 100) if expected_signals > 0 else 0
            
            metrics['generation_rate'] = QualityMetric(
                name='Signal Generation Rate',
                value=generation_rate,
                weight=0.3,
                threshold=80.0,
                status=self._determine_metric_status(generation_rate),
                trend=self._calculate_metric_trend('generation_rate', generation_rate),
                timestamp=timezone.now()
            )
            
            # Signal success rate
            successful_signals = recent_signals.filter(is_profitable=True).count()
            success_rate = (successful_signals / signal_count * 100) if signal_count > 0 else 0
            
            metrics['success_rate'] = QualityMetric(
                name='Signal Success Rate',
                value=success_rate,
                weight=0.4,
                threshold=70.0,
                status=self._determine_metric_status(success_rate),
                trend=self._calculate_metric_trend('success_rate', success_rate),
                timestamp=timezone.now()
            )
            
            # Average confidence
            avg_confidence = recent_signals.aggregate(
                avg_confidence=Avg('confidence_score')
            )['avg_confidence'] or 0.0
            confidence_percentage = float(avg_confidence) * 100
            
            metrics['confidence'] = QualityMetric(
                name='Average Confidence',
                value=confidence_percentage,
                weight=0.2,
                threshold=60.0,
                status=self._determine_metric_status(confidence_percentage),
                trend=self._calculate_metric_trend('confidence', confidence_percentage),
                timestamp=timezone.now()
            )
            
            # Signal diversity (different signal types)
            signal_types = recent_signals.values('signal_type__name').distinct().count()
            diversity_score = min(signal_types / 5 * 100, 100)  # 5 different types expected
            
            metrics['diversity'] = QualityMetric(
                name='Signal Diversity',
                value=diversity_score,
                weight=0.1,
                threshold=60.0,
                status=self._determine_metric_status(diversity_score),
                trend=self._calculate_metric_trend('diversity', diversity_score),
                timestamp=timezone.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating signal quality metrics: {e}")
            return {}
    
    def _calculate_data_quality_metrics(self) -> Dict[str, QualityMetric]:
        """Calculate data quality metrics"""
        try:
            metrics = {}
            
            # Data freshness
            latest_data = MarketData.objects.order_by('-timestamp').first()
            if latest_data:
                data_age_hours = (timezone.now() - latest_data.timestamp).total_seconds() / 3600
                freshness_score = max(100 - (data_age_hours * 10), 0)  # 10 points per hour
            else:
                freshness_score = 0
            
            metrics['freshness'] = QualityMetric(
                name='Data Freshness',
                value=freshness_score,
                weight=0.4,
                threshold=80.0,
                status=self._determine_metric_status(freshness_score),
                trend=self._calculate_metric_trend('freshness', freshness_score),
                timestamp=timezone.now()
            )
            
            # Data completeness
            total_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True).count()
            symbols_with_data = Symbol.objects.filter(
                is_active=True,
                is_crypto_symbol=True,
                marketdata__timestamp__gte=timezone.now() - timedelta(hours=24)
            ).distinct().count()
            completeness_score = (symbols_with_data / total_symbols * 100) if total_symbols > 0 else 0
            
            metrics['completeness'] = QualityMetric(
                name='Data Completeness',
                value=completeness_score,
                weight=0.3,
                threshold=80.0,
                status=self._determine_metric_status(completeness_score),
                trend=self._calculate_metric_trend('completeness', completeness_score),
                timestamp=timezone.now()
            )
            
            # Data consistency
            # Check for data gaps
            recent_data = MarketData.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).order_by('timestamp')
            
            if recent_data.count() > 1:
                # Calculate time gaps between consecutive data points
                gaps = []
                prev_timestamp = None
                for data_point in recent_data:
                    if prev_timestamp:
                        gap_hours = (data_point.timestamp - prev_timestamp).total_seconds() / 3600
                        if gap_hours > 2:  # Gap larger than 2 hours
                            gaps.append(gap_hours)
                    prev_timestamp = data_point.timestamp
                
                consistency_score = max(100 - (len(gaps) * 5), 0)  # 5 points per gap
            else:
                consistency_score = 0
            
            metrics['consistency'] = QualityMetric(
                name='Data Consistency',
                value=consistency_score,
                weight=0.3,
                threshold=90.0,
                status=self._determine_metric_status(consistency_score),
                trend=self._calculate_metric_trend('consistency', consistency_score),
                timestamp=timezone.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating data quality metrics: {e}")
            return {}
    
    def _calculate_system_performance_metrics(self) -> Dict[str, QualityMetric]:
        """Calculate system performance metrics"""
        try:
            metrics = {}
            
            # Response time
            start_time = timezone.now()
            TradingSignal.objects.count()
            end_time = timezone.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            response_score = max(100 - (response_time_ms / 100), 0)  # 100ms = 1 point
            
            metrics['response_time'] = QualityMetric(
                name='Response Time',
                value=response_score,
                weight=0.3,
                threshold=80.0,
                status=self._determine_metric_status(response_score),
                trend=self._calculate_metric_trend('response_time', response_score),
                timestamp=timezone.now()
            )
            
            # Throughput
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            throughput_score = min(recent_signals * 10, 100)  # 10 signals per hour = 100 points
            
            metrics['throughput'] = QualityMetric(
                name='Throughput',
                value=throughput_score,
                weight=0.3,
                threshold=70.0,
                status=self._determine_metric_status(throughput_score),
                trend=self._calculate_metric_trend('throughput', throughput_score),
                timestamp=timezone.now()
            )
            
            # Error rate
            recent_alerts = SignalAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            total_operations = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if total_operations > 0:
                error_count = recent_alerts.filter(priority__in=['CRITICAL', 'HIGH']).count()
                error_rate = error_count / total_operations
                error_score = max(100 - (error_rate * 1000), 0)  # 1% error = 1 point
            else:
                error_score = 100
            
            metrics['error_rate'] = QualityMetric(
                name='Error Rate',
                value=error_score,
                weight=0.4,
                threshold=90.0,
                status=self._determine_metric_status(error_score),
                trend=self._calculate_metric_trend('error_rate', error_score),
                timestamp=timezone.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating system performance metrics: {e}")
            return {}
    
    def _calculate_accuracy_metrics(self) -> Dict[str, QualityMetric]:
        """Calculate accuracy metrics"""
        try:
            metrics = {}
            
            # Get signals with performance data
            signals_with_performance = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24),
                is_executed=True
            )
            
            if not signals_with_performance.exists():
                return {}
            
            # Overall accuracy
            total_signals = signals_with_performance.count()
            accurate_signals = signals_with_performance.filter(is_profitable=True).count()
            accuracy = (accurate_signals / total_signals * 100) if total_signals > 0 else 0
            
            metrics['overall_accuracy'] = QualityMetric(
                name='Overall Accuracy',
                value=accuracy,
                weight=0.4,
                threshold=70.0,
                status=self._determine_metric_status(accuracy),
                trend=self._calculate_metric_trend('overall_accuracy', accuracy),
                timestamp=timezone.now()
            )
            
            # Precision (True Positives / (True Positives + False Positives))
            true_positives = signals_with_performance.filter(is_profitable=True).count()
            false_positives = signals_with_performance.filter(is_profitable=False).count()
            precision = (true_positives / (true_positives + false_positives) * 100) if (true_positives + false_positives) > 0 else 0
            
            metrics['precision'] = QualityMetric(
                name='Precision',
                value=precision,
                weight=0.3,
                threshold=70.0,
                status=self._determine_metric_status(precision),
                trend=self._calculate_metric_trend('precision', precision),
                timestamp=timezone.now()
            )
            
            # Recall (True Positives / (True Positives + False Negatives))
            # For trading signals, recall is same as accuracy
            recall = accuracy
            
            metrics['recall'] = QualityMetric(
                name='Recall',
                value=recall,
                weight=0.3,
                threshold=70.0,
                status=self._determine_metric_status(recall),
                trend=self._calculate_metric_trend('recall', recall),
                timestamp=timezone.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating accuracy metrics: {e}")
            return {}
    
    def _calculate_reliability_metrics(self) -> Dict[str, QualityMetric]:
        """Calculate reliability metrics"""
        try:
            metrics = {}
            
            # System uptime (simplified)
            uptime_hours = 24.0  # Simulated uptime
            uptime_score = min(uptime_hours / 24 * 100, 100)
            
            metrics['uptime'] = QualityMetric(
                name='System Uptime',
                value=uptime_score,
                weight=0.4,
                threshold=95.0,
                status=self._determine_metric_status(uptime_score),
                trend=self._calculate_metric_trend('uptime', uptime_score),
                timestamp=timezone.now()
            )
            
            # Consistency of signal generation
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).order_by('created_at')
            
            if recent_signals.count() > 1:
                # Calculate time intervals between signals
                intervals = []
                prev_time = None
                for signal in recent_signals:
                    if prev_time:
                        interval = (signal.created_at - prev_time).total_seconds() / 3600
                        intervals.append(interval)
                    prev_time = signal.created_at
                
                if intervals:
                    # Calculate coefficient of variation
                    mean_interval = np.mean(intervals)
                    std_interval = np.std(intervals)
                    cv = std_interval / mean_interval if mean_interval > 0 else 0
                    consistency_score = max(100 - (cv * 100), 0)
                else:
                    consistency_score = 0
            else:
                consistency_score = 0
            
            metrics['consistency'] = QualityMetric(
                name='Generation Consistency',
                value=consistency_score,
                weight=0.3,
                threshold=80.0,
                status=self._determine_metric_status(consistency_score),
                trend=self._calculate_metric_trend('consistency', consistency_score),
                timestamp=timezone.now()
            )
            
            # Error recovery
            recent_errors = SignalAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24),
                priority__in=['CRITICAL', 'HIGH']
            ).count()
            
            recovery_score = max(100 - (recent_errors * 10), 0)  # 10 points per error
            
            metrics['error_recovery'] = QualityMetric(
                name='Error Recovery',
                value=recovery_score,
                weight=0.3,
                threshold=90.0,
                status=self._determine_metric_status(recovery_score),
                trend=self._calculate_metric_trend('error_recovery', recovery_score),
                timestamp=timezone.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating reliability metrics: {e}")
            return {}
    
    def _calculate_efficiency_metrics(self) -> Dict[str, QualityMetric]:
        """Calculate efficiency metrics"""
        try:
            metrics = {}
            
            # Resource utilization efficiency
            # This would be calculated with actual system monitoring
            cpu_efficiency = 85.0  # Simulated
            memory_efficiency = 75.0  # Simulated
            resource_efficiency = (cpu_efficiency + memory_efficiency) / 2
            
            metrics['resource_efficiency'] = QualityMetric(
                name='Resource Efficiency',
                value=resource_efficiency,
                weight=0.4,
                threshold=80.0,
                status=self._determine_metric_status(resource_efficiency),
                trend=self._calculate_metric_trend('resource_efficiency', resource_efficiency),
                timestamp=timezone.now()
            )
            
            # Processing efficiency
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            processing_efficiency = min(recent_signals.count() * 20, 100)  # 5 signals = 100 points
            
            metrics['processing_efficiency'] = QualityMetric(
                name='Processing Efficiency',
                value=processing_efficiency,
                weight=0.3,
                threshold=70.0,
                status=self._determine_metric_status(processing_efficiency),
                trend=self._calculate_metric_trend('processing_efficiency', processing_efficiency),
                timestamp=timezone.now()
            )
            
            # Cache efficiency
            cache_hit_rate = 85.0  # Simulated
            cache_efficiency = cache_hit_rate
            
            metrics['cache_efficiency'] = QualityMetric(
                name='Cache Efficiency',
                value=cache_efficiency,
                weight=0.3,
                threshold=80.0,
                status=self._determine_metric_status(cache_efficiency),
                trend=self._calculate_metric_trend('cache_efficiency', cache_efficiency),
                timestamp=timezone.now()
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating efficiency metrics: {e}")
            return {}
    
    def _determine_metric_status(self, value: float) -> str:
        """Determine metric status based on value"""
        if value >= self.thresholds['excellent']:
            return 'EXCELLENT'
        elif value >= self.thresholds['good']:
            return 'GOOD'
        elif value >= self.thresholds['warning']:
            return 'WARNING'
        else:
            return 'CRITICAL'
    
    def _calculate_metric_trend(self, metric_name: str, current_value: float) -> str:
        """Calculate metric trend"""
        try:
            # Get historical values for this metric
            historical_values = []
            for metrics in self.metrics_history[-10:]:  # Last 10 records
                for category, category_metrics in metrics.items():
                    if metric_name in category_metrics:
                        historical_values.append(category_metrics[metric_name].value)
            
            if len(historical_values) < 3:
                return 'INSUFFICIENT_DATA'
            
            # Calculate trend using simple linear regression
            x = list(range(len(historical_values)))
            y = historical_values
            
            # Calculate slope
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(xi * xi for xi in x)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Determine trend
            if slope > 1:
                return 'IMPROVING'
            elif slope < -1:
                return 'DEGRADING'
            else:
                return 'STABLE'
                
        except Exception as e:
            logger.error(f"Error calculating metric trend: {e}")
            return 'UNKNOWN'
    
    def _calculate_quality_score(self, all_metrics: Dict[str, Dict[str, QualityMetric]]) -> QualityScore:
        """Calculate overall quality score"""
        try:
            component_scores = {}
            weighted_score = 0.0
            total_weight = 0.0
            
            # Calculate component scores
            for component, metrics in all_metrics.items():
                if not metrics:
                    component_scores[component] = 0.0
                    continue
                
                # Calculate weighted average for component
                component_score = 0.0
                component_weight = 0.0
                
                for metric in metrics.values():
                    component_score += metric.value * metric.weight
                    component_weight += metric.weight
                
                if component_weight > 0:
                    component_score = component_score / component_weight
                else:
                    component_score = 0.0
                
                component_scores[component] = component_score
                
                # Add to weighted score
                weight = self.scoring_weights.get(component, 0.1)
                weighted_score += component_score * weight
                total_weight += weight
            
            # Calculate overall score
            if total_weight > 0:
                overall_score = weighted_score / total_weight
            else:
                overall_score = 0.0
            
            # Determine grade
            grade = self._determine_grade(overall_score)
            
            # Generate recommendations
            recommendations = self._generate_score_recommendations(component_scores, overall_score)
            
            quality_score = QualityScore(
                overall_score=overall_score,
                component_scores=component_scores,
                weighted_score=weighted_score,
                grade=grade,
                recommendations=recommendations,
                timestamp=timezone.now()
            )
            
            # Store in history
            self.scores_history.append(quality_score)
            if len(self.scores_history) > 100:  # Keep last 100 records
                self.scores_history = self.scores_history[-100:]
            
            return quality_score
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return QualityScore(
                overall_score=0.0,
                component_scores={},
                weighted_score=0.0,
                grade='F',
                recommendations=['Error calculating quality score'],
                timestamp=timezone.now()
            )
    
    def _determine_grade(self, score: float) -> str:
        """Determine grade based on score"""
        if score >= 97:
            return 'A+'
        elif score >= 93:
            return 'A'
        elif score >= 90:
            return 'A-'
        elif score >= 87:
            return 'B+'
        elif score >= 83:
            return 'B'
        elif score >= 80:
            return 'B-'
        elif score >= 77:
            return 'C+'
        elif score >= 73:
            return 'C'
        elif score >= 70:
            return 'C-'
        elif score >= 67:
            return 'D+'
        elif score >= 63:
            return 'D'
        elif score >= 60:
            return 'D-'
        else:
            return 'F'
    
    def _generate_score_recommendations(self, component_scores: Dict[str, float], overall_score: float) -> List[str]:
        """Generate recommendations based on quality scores"""
        try:
            recommendations = []
            
            # Check component scores
            for component, score in component_scores.items():
                if score < 70:
                    if component == 'signal_quality':
                        recommendations.append("Improve signal generation algorithms and validation")
                    elif component == 'data_quality':
                        recommendations.append("Enhance data collection and validation processes")
                    elif component == 'system_performance':
                        recommendations.append("Optimize system performance and resource usage")
                    elif component == 'accuracy':
                        recommendations.append("Improve signal accuracy and validation")
                    elif component == 'reliability':
                        recommendations.append("Enhance system reliability and error handling")
                    elif component == 'efficiency':
                        recommendations.append("Optimize system efficiency and resource utilization")
            
            # Overall score recommendations
            if overall_score < 50:
                recommendations.append("Critical system issues - immediate attention required")
            elif overall_score < 70:
                recommendations.append("System quality needs improvement - review all components")
            elif overall_score < 85:
                recommendations.append("Good system quality - focus on optimization opportunities")
            else:
                recommendations.append("Excellent system quality - maintain current performance")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating score recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _generate_quality_recommendations(self, all_metrics: Dict[str, Dict[str, QualityMetric]], quality_score: QualityScore) -> List[str]:
        """Generate comprehensive quality recommendations"""
        try:
            recommendations = []
            
            # Check for critical metrics
            for component, metrics in all_metrics.items():
                for metric_name, metric in metrics.items():
                    if metric.status == 'CRITICAL':
                        recommendations.append(f"Critical issue in {component}: {metric.name} - {metric.message}")
                    elif metric.status == 'WARNING':
                        recommendations.append(f"Warning in {component}: {metric.name} - {metric.message}")
            
            # Add score-based recommendations
            recommendations.extend(quality_score.recommendations)
            
            # Remove duplicates
            recommendations = list(set(recommendations))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating quality recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _analyze_quality_trends(self) -> Dict[str, Any]:
        """Analyze quality trends over time"""
        try:
            if len(self.scores_history) < 5:
                return {'trend': 'INSUFFICIENT_DATA'}
            
            # Get recent scores
            recent_scores = [score.overall_score for score in self.scores_history[-10:]]
            
            # Calculate trend
            if len(recent_scores) >= 3:
                first_score = recent_scores[0]
                last_score = recent_scores[-1]
                
                if last_score > first_score + 5:
                    trend = 'IMPROVING'
                elif last_score < first_score - 5:
                    trend = 'DEGRADING'
                else:
                    trend = 'STABLE'
            else:
                trend = 'INSUFFICIENT_DATA'
            
            return {
                'trend': trend,
                'recent_scores': recent_scores,
                'data_points': len(recent_scores),
                'score_change': recent_scores[-1] - recent_scores[0] if len(recent_scores) > 1 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing quality trends: {e}")
            return {'trend': 'ERROR'}
    
    def _generate_quality_summary(self, all_metrics: Dict[str, Dict[str, QualityMetric]], quality_score: QualityScore) -> Dict[str, Any]:
        """Generate quality summary"""
        try:
            # Count metrics by status
            status_counts = {'EXCELLENT': 0, 'GOOD': 0, 'WARNING': 0, 'CRITICAL': 0}
            total_metrics = 0
            
            for component, metrics in all_metrics.items():
                for metric in metrics.values():
                    status_counts[metric.status] += 1
                    total_metrics += 1
            
            # Calculate percentages
            status_percentages = {}
            for status, count in status_counts.items():
                status_percentages[status] = (count / total_metrics * 100) if total_metrics > 0 else 0
            
            return {
                'overall_score': quality_score.overall_score,
                'grade': quality_score.grade,
                'total_metrics': total_metrics,
                'status_counts': status_counts,
                'status_percentages': status_percentages,
                'component_scores': quality_score.component_scores,
                'recommendations_count': len(quality_score.recommendations)
            }
            
        except Exception as e:
            logger.error(f"Error generating quality summary: {e}")
            return {}
    
    def get_quality_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get quality history for specified hours"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            history = []
            for score in self.scores_history:
                if score.timestamp >= cutoff_time:
                    history.append({
                        'timestamp': score.timestamp.isoformat(),
                        'overall_score': score.overall_score,
                        'grade': score.grade,
                        'component_scores': score.component_scores,
                        'recommendations_count': len(score.recommendations)
                    })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting quality history: {e}")
            return []
    
    def get_quality_dashboard(self) -> Dict[str, Any]:
        """Get quality dashboard data"""
        try:
            # Get current metrics
            current_metrics = self.calculate_comprehensive_quality_metrics()
            
            # Get trends
            trends = self._analyze_quality_trends()
            
            # Get history
            history = self.get_quality_history(24)
            
            dashboard = {
                'timestamp': timezone.now().isoformat(),
                'current_metrics': current_metrics,
                'trends': trends,
                'history': history,
                'summary': {
                    'overall_score': current_metrics.get('quality_score', {}).get('overall_score', 0),
                    'grade': current_metrics.get('quality_score', {}).get('grade', 'F'),
                    'trend': trends.get('trend', 'UNKNOWN'),
                    'recommendations_count': len(current_metrics.get('recommendations', []))
                }
            }
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Error getting quality dashboard: {e}")
            return {'error': str(e)}


# Global instance
quality_metrics_system = QualityMetricsSystem()














