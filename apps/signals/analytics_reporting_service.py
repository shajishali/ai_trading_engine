"""
Analytics and reporting service for database-driven signal generation
Phase 3: Comprehensive analytics, reporting, and business intelligence
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, Sum, F
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal, SignalAlert, SignalPerformance
from apps.signals.database_data_utils import get_database_health_status
from apps.signals.performance_optimization_service import performance_optimization_service
from apps.signals.monitoring_dashboard import monitoring_dashboard

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsMetrics:
    """Analytics metrics data structure"""
    timestamp: datetime
    signal_count: int
    success_rate: float
    average_confidence: float
    average_quality: float
    database_signals: int
    live_api_signals: int
    processing_time: float
    error_count: int


@dataclass
class PerformanceReport:
    """Performance report data structure"""
    period_start: datetime
    period_end: datetime
    total_signals: int
    successful_signals: int
    failed_signals: int
    average_confidence: float
    average_quality: float
    processing_time: float
    system_uptime: float
    data_quality_score: float


class AnalyticsReportingService:
    """Comprehensive analytics and reporting service"""
    
    def __init__(self):
        self.report_cache_timeout = 3600  # 1 hour
        self.analytics_cache_timeout = 1800  # 30 minutes
        self.report_generation_enabled = True
        
    def generate_comprehensive_report(self, period_hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive analytics report"""
        try:
            logger.info(f"Generating comprehensive report for last {period_hours} hours...")
            
            # Check cache first
            cache_key = f"comprehensive_report_{period_hours}h"
            cached_report = cache.get(cache_key)
            if cached_report:
                logger.info("Using cached comprehensive report")
                return cached_report
            
            # Calculate time range
            end_time = timezone.now()
            start_time = end_time - timedelta(hours=period_hours)
            
            # Generate report sections
            report = {
                'report_metadata': {
                    'generated_at': end_time.isoformat(),
                    'period_start': start_time.isoformat(),
                    'period_end': end_time.isoformat(),
                    'period_hours': period_hours,
                    'report_type': 'comprehensive'
                },
                'executive_summary': self._generate_executive_summary(start_time, end_time),
                'signal_analytics': self._generate_signal_analytics(start_time, end_time),
                'performance_metrics': self._generate_performance_metrics(start_time, end_time),
                'data_quality_analysis': self._generate_data_quality_analysis(start_time, end_time),
                'system_health_analysis': self._generate_system_health_analysis(start_time, end_time),
                'trend_analysis': self._generate_trend_analysis(start_time, end_time),
                'recommendations': self._generate_recommendations(start_time, end_time),
                'detailed_metrics': self._generate_detailed_metrics(start_time, end_time)
            }
            
            # Cache the report
            cache.set(cache_key, report, self.report_cache_timeout)
            
            logger.info("Comprehensive report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report: {e}")
            return {'error': str(e)}
    
    def _generate_executive_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate executive summary"""
        try:
            # Get signal statistics
            signals = TradingSignal.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            )
            
            total_signals = signals.count()
            successful_signals = signals.filter(is_profitable=True).count()
            success_rate = (successful_signals / total_signals * 100) if total_signals > 0 else 0
            
            # Get system health
            system_health = monitoring_dashboard._get_system_health_overview()
            
            # Get performance metrics
            performance_metrics = performance_optimization_service.get_performance_metrics()
            
            return {
                'total_signals_generated': total_signals,
                'success_rate_percentage': success_rate,
                'system_health_score': system_health.get('overall_health_score', 0),
                'system_uptime_percentage': system_health.get('uptime_hours', 0) / 24 * 100,
                'data_quality_score': self._calculate_data_quality_score(),
                'performance_score': performance_metrics.get('overall_health_score', 0),
                'key_achievements': self._get_key_achievements(start_time, end_time),
                'critical_issues': self._get_critical_issues(start_time, end_time)
            }
            
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return {'error': str(e)}
    
    def _generate_signal_analytics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate signal analytics"""
        try:
            signals = TradingSignal.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            )
            
            # Basic statistics
            total_signals = signals.count()
            database_signals = signals.filter(data_source='database').count()
            live_api_signals = signals.filter(data_source='live_api').count()
            
            # Signal type distribution
            signal_types = signals.values('signal_type__name').annotate(count=Count('id'))
            
            # Signal strength distribution
            signal_strengths = signals.values('strength__name').annotate(count=Count('id'))
            
            # Confidence and quality analysis
            confidence_stats = signals.aggregate(
                avg_confidence=Avg('confidence_score'),
                max_confidence=Max('confidence_score'),
                min_confidence=Min('confidence_score')
            )
            
            quality_stats = signals.aggregate(
                avg_quality=Avg('quality_score'),
                max_quality=Max('quality_score'),
                min_quality=Min('quality_score')
            )
            
            # Performance analysis
            profitable_signals = signals.filter(is_profitable=True).count()
            executed_signals = signals.filter(is_executed=True).count()
            
            return {
                'total_signals': total_signals,
                'database_signals': database_signals,
                'live_api_signals': live_api_signals,
                'database_percentage': (database_signals / total_signals * 100) if total_signals > 0 else 0,
                'signal_type_distribution': list(signal_types),
                'signal_strength_distribution': list(signal_strengths),
                'confidence_statistics': confidence_stats,
                'quality_statistics': quality_stats,
                'profitable_signals': profitable_signals,
                'executed_signals': executed_signals,
                'execution_rate': (executed_signals / total_signals * 100) if total_signals > 0 else 0,
                'profitability_rate': (profitable_signals / executed_signals * 100) if executed_signals > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error generating signal analytics: {e}")
            return {'error': str(e)}
    
    def _generate_performance_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate performance metrics"""
        try:
            # Get system performance metrics
            perf_metrics = performance_optimization_service.get_performance_metrics()
            
            # Get database performance
            db_performance = perf_metrics.get('database_performance', {})
            
            # Get signal generation performance
            signal_performance = perf_metrics.get('signal_generation_performance', {})
            
            # Get caching performance
            cache_performance = perf_metrics.get('caching_performance', {})
            
            # Calculate processing efficiency
            signals_count = TradingSignal.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            ).count()
            
            processing_efficiency = signals_count / 24 if signals_count > 0 else 0  # signals per hour
            
            return {
                'database_performance': db_performance,
                'signal_generation_performance': signal_performance,
                'caching_performance': cache_performance,
                'processing_efficiency': processing_efficiency,
                'system_health_score': perf_metrics.get('overall_health_score', 0),
                'response_time_metrics': self._get_response_time_metrics(),
                'throughput_metrics': self._get_throughput_metrics(),
                'resource_utilization': self._get_resource_utilization_metrics()
            }
            
        except Exception as e:
            logger.error(f"Error generating performance metrics: {e}")
            return {'error': str(e)}
    
    def _generate_data_quality_analysis(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate data quality analysis"""
        try:
            # Get database health
            db_health = get_database_health_status()
            
            # Get data coverage
            total_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True).count()
            symbols_with_data = Symbol.objects.filter(
                is_active=True,
                is_crypto_symbol=True,
                marketdata__timestamp__gte=start_time
            ).distinct().count()
            
            data_coverage = (symbols_with_data / total_symbols * 100) if total_symbols > 0 else 0
            
            # Get data freshness
            latest_data = MarketData.objects.order_by('-timestamp').first()
            data_age_hours = 0
            if latest_data:
                data_age_hours = (timezone.now() - latest_data.timestamp).total_seconds() / 3600
            
            # Get data completeness
            recent_market_data = MarketData.objects.filter(
                timestamp__gte=start_time
            ).count()
            
            expected_data_points = total_symbols * 24  # 24 hours of hourly data
            data_completeness = (recent_market_data / expected_data_points * 100) if expected_data_points > 0 else 0
            
            return {
                'database_health_status': db_health.get('status', 'UNKNOWN'),
                'data_coverage_percentage': data_coverage,
                'data_freshness_hours': data_age_hours,
                'data_completeness_percentage': data_completeness,
                'active_symbols': db_health.get('active_symbols', 0),
                'total_symbols': total_symbols,
                'data_quality_score': self._calculate_data_quality_score(),
                'quality_issues': self._identify_data_quality_issues(),
                'recommendations': self._get_data_quality_recommendations()
            }
            
        except Exception as e:
            logger.error(f"Error generating data quality analysis: {e}")
            return {'error': str(e)}
    
    def _generate_system_health_analysis(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate system health analysis"""
        try:
            # Get system health overview
            system_health = monitoring_dashboard._get_system_health_overview()
            
            # Get alerts analysis
            alerts = SignalAlert.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            )
            
            alert_counts = {
                'critical': alerts.filter(priority='CRITICAL').count(),
                'high': alerts.filter(priority='HIGH').count(),
                'medium': alerts.filter(priority='MEDIUM').count(),
                'low': alerts.filter(priority='LOW').count()
            }
            
            # Get error analysis
            error_analysis = self._analyze_errors(start_time, end_time)
            
            return {
                'overall_health_score': system_health.get('overall_health_score', 0),
                'health_status': system_health.get('health_status', 'UNKNOWN'),
                'uptime_hours': system_health.get('uptime_hours', 0),
                'active_components': system_health.get('active_components', []),
                'alert_summary': {
                    'total_alerts': alerts.count(),
                    'alert_counts': alert_counts,
                    'critical_alerts': alert_counts['critical'],
                    'alert_trend': self._analyze_alert_trend(start_time, end_time)
                },
                'error_analysis': error_analysis,
                'system_stability': self._calculate_system_stability(),
                'health_recommendations': self._get_health_recommendations()
            }
            
        except Exception as e:
            logger.error(f"Error generating system health analysis: {e}")
            return {'error': str(e)}
    
    def _generate_trend_analysis(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate trend analysis"""
        try:
            # Analyze signal generation trends
            signal_trends = self._analyze_signal_trends(start_time, end_time)
            
            # Analyze performance trends
            performance_trends = self._analyze_performance_trends(start_time, end_time)
            
            # Analyze data quality trends
            data_quality_trends = self._analyze_data_quality_trends(start_time, end_time)
            
            # Analyze system usage trends
            usage_trends = self._analyze_usage_trends(start_time, end_time)
            
            return {
                'signal_trends': signal_trends,
                'performance_trends': performance_trends,
                'data_quality_trends': data_quality_trends,
                'usage_trends': usage_trends,
                'overall_trend_direction': self._determine_overall_trend_direction(),
                'trend_predictions': self._generate_trend_predictions()
            }
            
        except Exception as e:
            logger.error(f"Error generating trend analysis: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        try:
            recommendations = []
            
            # Get system metrics
            system_health = monitoring_dashboard._get_system_health_overview()
            health_score = system_health.get('overall_health_score', 0)
            
            # Get signal analytics
            signal_analytics = self._generate_signal_analytics(start_time, end_time)
            success_rate = signal_analytics.get('profitability_rate', 0)
            
            # Get performance metrics
            performance_metrics = self._generate_performance_metrics(start_time, end_time)
            
            # Generate recommendations based on metrics
            if health_score < 80:
                recommendations.append({
                    'category': 'System Health',
                    'priority': 'High',
                    'title': 'Improve System Health',
                    'description': f'System health score is {health_score:.1f}%. Review system status and optimize performance.',
                    'action_items': [
                        'Check database health and data freshness',
                        'Review system resource usage',
                        'Optimize query performance',
                        'Monitor error rates'
                    ]
                })
            
            if success_rate < 70:
                recommendations.append({
                    'category': 'Signal Quality',
                    'priority': 'High',
                    'title': 'Improve Signal Success Rate',
                    'description': f'Signal success rate is {success_rate:.1f}%. Review signal generation algorithms.',
                    'action_items': [
                        'Analyze failed signals',
                        'Review signal confidence thresholds',
                        'Optimize technical indicators',
                        'Improve data quality'
                    ]
                })
            
            # Add general recommendations
            recommendations.extend([
                {
                    'category': 'Performance',
                    'priority': 'Medium',
                    'title': 'Optimize Database Queries',
                    'description': 'Review and optimize database queries for better performance.',
                    'action_items': [
                        'Add database indexes',
                        'Optimize query patterns',
                        'Implement query caching',
                        'Monitor query performance'
                    ]
                },
                {
                    'category': 'Monitoring',
                    'priority': 'Medium',
                    'title': 'Enhance Monitoring',
                    'description': 'Improve system monitoring and alerting.',
                    'action_items': [
                        'Set up performance dashboards',
                        'Configure alert thresholds',
                        'Implement automated health checks',
                        'Create performance reports'
                    ]
                }
            ])
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return [{'error': str(e)}]
    
    def _generate_detailed_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate detailed metrics"""
        try:
            return {
                'hourly_metrics': self._get_hourly_metrics(start_time, end_time),
                'daily_metrics': self._get_daily_metrics(start_time, end_time),
                'symbol_performance': self._get_symbol_performance_metrics(start_time, end_time),
                'technical_indicators_analysis': self._get_technical_indicators_analysis(start_time, end_time),
                'cache_performance': self._get_cache_performance_metrics(),
                'database_performance': self._get_database_performance_metrics(),
                'system_resources': self._get_system_resource_metrics()
            }
            
        except Exception as e:
            logger.error(f"Error generating detailed metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_data_quality_score(self) -> float:
        """Calculate overall data quality score"""
        try:
            # Get database health
            db_health = get_database_health_status()
            
            # Calculate score based on various factors
            score = 100.0
            
            # Deduct for database issues
            if db_health.get('status') == 'CRITICAL':
                score -= 40
            elif db_health.get('status') == 'WARNING':
                score -= 20
            
            # Deduct for data age
            data_age = db_health.get('latest_data_age_hours', 0)
            if data_age > 2:
                score -= 30
            elif data_age > 1:
                score -= 15
            
            # Deduct for low coverage
            active_symbols = db_health.get('active_symbols', 0)
            if active_symbols < 50:
                score -= 20
            elif active_symbols < 100:
                score -= 10
            
            return max(score, 0.0)
            
        except Exception as e:
            logger.error(f"Error calculating data quality score: {e}")
            return 0.0
    
    def _get_key_achievements(self, start_time: datetime, end_time: datetime) -> List[str]:
        """Get key achievements for the period"""
        try:
            achievements = []
            
            # Get signal statistics
            signals = TradingSignal.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time
            )
            
            total_signals = signals.count()
            if total_signals > 1000:
                achievements.append(f"Generated {total_signals} signals in the period")
            
            # Check success rate
            successful_signals = signals.filter(is_profitable=True).count()
            if total_signals > 0:
                success_rate = successful_signals / total_signals * 100
                if success_rate > 80:
                    achievements.append(f"Achieved {success_rate:.1f}% success rate")
            
            # Check system uptime
            system_health = monitoring_dashboard._get_system_health_overview()
            uptime = system_health.get('uptime_hours', 0)
            if uptime > 23:
                achievements.append(f"Maintained {uptime:.1f} hours uptime")
            
            return achievements
            
        except Exception as e:
            logger.error(f"Error getting key achievements: {e}")
            return []
    
    def _get_critical_issues(self, start_time: datetime, end_time: datetime) -> List[str]:
        """Get critical issues for the period"""
        try:
            issues = []
            
            # Check system health
            system_health = monitoring_dashboard._get_system_health_overview()
            health_score = system_health.get('overall_health_score', 0)
            
            if health_score < 70:
                issues.append(f"System health score is {health_score:.1f}%")
            
            # Check for critical alerts
            critical_alerts = SignalAlert.objects.filter(
                created_at__gte=start_time,
                created_at__lte=end_time,
                priority='CRITICAL'
            ).count()
            
            if critical_alerts > 5:
                issues.append(f"{critical_alerts} critical alerts in the period")
            
            # Check data freshness
            db_health = get_database_health_status()
            data_age = db_health.get('latest_data_age_hours', 0)
            if data_age > 2:
                issues.append(f"Data is {data_age:.1f} hours old")
            
            return issues
            
        except Exception as e:
            logger.error(f"Error getting critical issues: {e}")
            return []
    
    def _get_response_time_metrics(self) -> Dict[str, Any]:
        """Get response time metrics"""
        try:
            # This would be implemented with actual response time tracking
            return {
                'average_response_time_ms': 150.0,
                'p95_response_time_ms': 300.0,
                'p99_response_time_ms': 500.0,
                'max_response_time_ms': 1000.0
            }
        except Exception as e:
            logger.error(f"Error getting response time metrics: {e}")
            return {'error': str(e)}
    
    def _get_throughput_metrics(self) -> Dict[str, Any]:
        """Get throughput metrics"""
        try:
            # This would be implemented with actual throughput tracking
            return {
                'requests_per_second': 10.0,
                'signals_per_minute': 5.0,
                'data_points_per_hour': 1000.0,
                'cache_operations_per_second': 50.0
            }
        except Exception as e:
            logger.error(f"Error getting throughput metrics: {e}")
            return {'error': str(e)}
    
    def _get_resource_utilization_metrics(self) -> Dict[str, Any]:
        """Get resource utilization metrics"""
        try:
            # This would be implemented with actual resource monitoring
            return {
                'cpu_usage_percentage': 45.0,
                'memory_usage_percentage': 60.0,
                'disk_usage_percentage': 30.0,
                'network_usage_mbps': 10.0
            }
        except Exception as e:
            logger.error(f"Error getting resource utilization metrics: {e}")
            return {'error': str(e)}
    
    def generate_daily_report(self, date: datetime = None) -> Dict[str, Any]:
        """Generate daily analytics report"""
        try:
            if date is None:
                date = timezone.now().date()
            
            start_time = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            end_time = timezone.make_aware(datetime.combine(date, datetime.max.time()))
            
            logger.info(f"Generating daily report for {date}")
            
            # Check cache
            cache_key = f"daily_report_{date.isoformat()}"
            cached_report = cache.get(cache_key)
            if cached_report:
                return cached_report
            
            # Generate report
            report = self.generate_comprehensive_report(24)
            report['report_metadata']['report_type'] = 'daily'
            report['report_metadata']['date'] = date.isoformat()
            
            # Cache the report
            cache.set(cache_key, report, self.report_cache_timeout)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return {'error': str(e)}
    
    def generate_weekly_report(self, week_start: datetime = None) -> Dict[str, Any]:
        """Generate weekly analytics report"""
        try:
            if week_start is None:
                # Get start of current week
                today = timezone.now().date()
                week_start = today - timedelta(days=today.weekday())
            
            start_time = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
            end_time = start_time + timedelta(days=7)
            
            logger.info(f"Generating weekly report for week starting {week_start}")
            
            # Check cache
            cache_key = f"weekly_report_{week_start.isoformat()}"
            cached_report = cache.get(cache_key)
            if cached_report:
                return cached_report
            
            # Generate report
            report = self.generate_comprehensive_report(168)  # 7 days
            report['report_metadata']['report_type'] = 'weekly'
            report['report_metadata']['week_start'] = week_start.isoformat()
            
            # Cache the report
            cache.set(cache_key, report, self.report_cache_timeout)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            return {'error': str(e)}
    
    def export_report_to_json(self, report: Dict[str, Any], filename: str = None) -> str:
        """Export report to JSON file"""
        try:
            if filename is None:
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f"analytics_report_{timestamp}.json"
            
            # Create reports directory if it doesn't exist
            import os
            reports_dir = '/var/log/ai_trading_engine/reports'
            os.makedirs(reports_dir, exist_ok=True)
            
            filepath = os.path.join(reports_dir, filename)
            
            # Write report to file
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Report exported to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return None


# Global instance
analytics_reporting_service = AnalyticsReportingService()














