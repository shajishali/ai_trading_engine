"""
Database Signal Monitoring Service
Phase 4: Monitor signal quality and system performance for database-driven signals
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, F

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import TradingSignal, SignalAlert, SignalPerformance
from apps.signals.database_data_utils import get_database_health_status

logger = logging.getLogger(__name__)


class DatabaseSignalMonitor:
    """Monitor database-driven signal generation performance"""
    
    def __init__(self):
        self.monitoring_interval = 300  # 5 minutes
        self.quality_thresholds = {
            'min_signal_count_per_hour': 5,
            'max_data_age_hours': 2,
            'min_confidence_score': 0.6,
            'max_error_rate': 0.1,
            'min_success_rate': 0.7
        }
    
    def monitor_signal_quality(self) -> Dict[str, Any]:
        """Monitor signal quality metrics"""
        try:
            logger.info("Monitoring database signal quality...")
            
            # Get recent signals
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            # Check data freshness
            latest_data = MarketData.objects.order_by('-timestamp').first()
            data_age_hours = 0
            if latest_data:
                data_age_hours = (timezone.now() - latest_data.timestamp).total_seconds() / 3600
            
            # Check signal accuracy
            performance_metrics = self._calculate_signal_performance()
            
            # Assess system health
            system_health = self._assess_system_health()
            
            # Generate quality report
            quality_report = {
                'timestamp': timezone.now().isoformat(),
                'signals_generated': recent_signals.count(),
                'data_age_hours': data_age_hours,
                'signal_accuracy': performance_metrics.get('accuracy', 0),
                'system_health': system_health,
                'quality_score': self._calculate_quality_score(
                    recent_signals.count(),
                    data_age_hours,
                    performance_metrics.get('accuracy', 0)
                ),
                'recommendations': self._generate_quality_recommendations(
                    recent_signals.count(),
                    data_age_hours,
                    performance_metrics.get('accuracy', 0)
                )
            }
            
            logger.info(f"Signal quality monitoring completed - Score: {quality_report['quality_score']:.2f}")
            return quality_report
            
        except Exception as e:
            logger.error(f"Error monitoring signal quality: {e}")
            return {'error': str(e)}
    
    def _calculate_signal_performance(self) -> Dict[str, float]:
        """Calculate signal performance metrics"""
        try:
            # Get signals from last 24 hours
            signals_24h = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            if not signals_24h.exists():
                return {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0}
            
            # Calculate accuracy based on profitable signals
            profitable_signals = signals_24h.filter(is_profitable=True).count()
            total_signals = signals_24h.count()
            accuracy = profitable_signals / total_signals if total_signals > 0 else 0.0
            
            # Calculate average confidence
            avg_confidence = signals_24h.aggregate(
                avg_confidence=Avg('confidence_score')
            )['avg_confidence'] or 0.0
            
            # Calculate average quality
            avg_quality = signals_24h.aggregate(
                avg_quality=Avg('quality_score')
            )['avg_quality'] or 0.0
            
            return {
                'accuracy': accuracy,
                'precision': accuracy,  # Simplified
                'recall': accuracy,     # Simplified
                'avg_confidence': float(avg_confidence),
                'avg_quality': float(avg_quality)
            }
            
        except Exception as e:
            logger.error(f"Error calculating signal performance: {e}")
            return {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0}
    
    def _assess_system_health(self) -> str:
        """Assess overall system health"""
        try:
            # Check data completeness
            total_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True).count()
            symbols_with_data = Symbol.objects.filter(
                is_active=True,
                is_crypto_symbol=True,
                marketdata__timestamp__gte=timezone.now() - timedelta(hours=24)
            ).distinct().count()
            
            data_coverage = symbols_with_data / total_symbols if total_symbols > 0 else 0
            
            # Check signal generation frequency
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            # Check error rates
            error_rate = self._calculate_error_rate()
            
            # Determine health status
            if data_coverage < 0.5 or recent_signals < 5 or error_rate > 0.1:
                return "CRITICAL"
            elif data_coverage < 0.8 or recent_signals < 10 or error_rate > 0.05:
                return "DEGRADED"
            else:
                return "HEALTHY"
                
        except Exception as e:
            logger.error(f"Error assessing system health: {e}")
            return "UNKNOWN"
    
    def _calculate_error_rate(self) -> float:
        """Calculate system error rate"""
        try:
            # Get recent alerts
            recent_alerts = SignalAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            # Get total operations (signals generated)
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
    
    def _calculate_quality_score(self, signal_count: int, data_age: float, accuracy: float) -> float:
        """Calculate overall quality score"""
        try:
            score = 100.0
            
            # Signal count penalty
            if signal_count < self.quality_thresholds['min_signal_count_per_hour']:
                score -= 30
            
            # Data age penalty
            if data_age > self.quality_thresholds['max_data_age_hours']:
                score -= 40
            
            # Accuracy penalty
            if accuracy < self.quality_thresholds['min_success_rate']:
                score -= 30
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 0.0
    
    def _generate_quality_recommendations(self, signal_count: int, data_age: float, accuracy: float) -> List[str]:
        """Generate quality improvement recommendations"""
        try:
            recommendations = []
            
            if signal_count < self.quality_thresholds['min_signal_count_per_hour']:
                recommendations.append("Low signal generation rate - check data collection and processing")
            
            if data_age > self.quality_thresholds['max_data_age_hours']:
                recommendations.append(f"Data is {data_age:.1f} hours old - check data synchronization")
            
            if accuracy < self.quality_thresholds['min_success_rate']:
                recommendations.append("Low signal accuracy - review signal generation algorithms")
            
            if not recommendations:
                recommendations.append("System performing within acceptable parameters")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Error generating recommendations"]
    
    def monitor_data_freshness(self) -> Dict[str, Any]:
        """Monitor data freshness across all symbols"""
        try:
            logger.info("Monitoring data freshness...")
            
            # Get all active symbols
            symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True)
            
            freshness_report = {
                'timestamp': timezone.now().isoformat(),
                'total_symbols': symbols.count(),
                'symbols_with_fresh_data': 0,
                'symbols_with_stale_data': 0,
                'average_data_age_hours': 0,
                'stale_symbols': [],
                'freshness_score': 0.0
            }
            
            total_age = 0
            fresh_count = 0
            stale_count = 0
            
            for symbol in symbols:
                try:
                    # Get latest data for symbol
                    latest_data = MarketData.objects.filter(
                        symbol=symbol
                    ).order_by('-timestamp').first()
                    
                    if latest_data:
                        data_age = (timezone.now() - latest_data.timestamp).total_seconds() / 3600
                        total_age += data_age
                        
                        if data_age <= self.quality_thresholds['max_data_age_hours']:
                            fresh_count += 1
                        else:
                            stale_count += 1
                            freshness_report['stale_symbols'].append({
                                'symbol': symbol.symbol,
                                'data_age_hours': data_age,
                                'last_update': latest_data.timestamp.isoformat()
                            })
                    else:
                        stale_count += 1
                        freshness_report['stale_symbols'].append({
                            'symbol': symbol.symbol,
                            'data_age_hours': float('inf'),
                            'last_update': None
                        })
                        
                except Exception as e:
                    logger.error(f"Error checking freshness for {symbol.symbol}: {e}")
                    stale_count += 1
            
            # Calculate metrics
            freshness_report['symbols_with_fresh_data'] = fresh_count
            freshness_report['symbols_with_stale_data'] = stale_count
            freshness_report['average_data_age_hours'] = total_age / symbols.count() if symbols.count() > 0 else 0
            freshness_report['freshness_score'] = (fresh_count / symbols.count() * 100) if symbols.count() > 0 else 0
            
            logger.info(f"Data freshness monitoring completed - Score: {freshness_report['freshness_score']:.1f}%")
            return freshness_report
            
        except Exception as e:
            logger.error(f"Error monitoring data freshness: {e}")
            return {'error': str(e)}
    
    def monitor_signal_generation_performance(self) -> Dict[str, Any]:
        """Monitor signal generation performance"""
        try:
            logger.info("Monitoring signal generation performance...")
            
            # Get signals from last hour
            recent_signals = TradingSignal.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            )
            
            # Calculate performance metrics
            total_signals = recent_signals.count()
            database_signals = recent_signals.filter(data_source='database').count()
            live_api_signals = recent_signals.filter(data_source='live_api').count()
            
            # Calculate processing time (simplified)
            processing_times = []
            for signal in recent_signals[:10]:  # Sample first 10 signals
                # This would be calculated from actual processing logs
                processing_times.append(0.5)  # Placeholder
            
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # Calculate success rate
            successful_signals = recent_signals.filter(is_profitable=True).count()
            success_rate = successful_signals / total_signals if total_signals > 0 else 0
            
            performance_report = {
                'timestamp': timezone.now().isoformat(),
                'total_signals': total_signals,
                'database_signals': database_signals,
                'live_api_signals': live_api_signals,
                'database_percentage': (database_signals / total_signals * 100) if total_signals > 0 else 0,
                'average_processing_time': avg_processing_time,
                'success_rate': success_rate,
                'performance_score': self._calculate_performance_score(
                    total_signals,
                    avg_processing_time,
                    success_rate
                ),
                'recommendations': self._generate_performance_recommendations(
                    total_signals,
                    avg_processing_time,
                    success_rate
                )
            }
            
            logger.info(f"Signal generation performance monitoring completed")
            return performance_report
            
        except Exception as e:
            logger.error(f"Error monitoring signal generation performance: {e}")
            return {'error': str(e)}
    
    def _calculate_performance_score(self, signal_count: int, processing_time: float, success_rate: float) -> float:
        """Calculate performance score"""
        try:
            score = 100.0
            
            # Signal count score
            if signal_count < 5:
                score -= 20
            elif signal_count < 10:
                score -= 10
            
            # Processing time score
            if processing_time > 2.0:
                score -= 30
            elif processing_time > 1.0:
                score -= 15
            
            # Success rate score
            if success_rate < 0.5:
                score -= 40
            elif success_rate < 0.7:
                score -= 20
            
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return 0.0
    
    def _generate_performance_recommendations(self, signal_count: int, processing_time: float, success_rate: float) -> List[str]:
        """Generate performance improvement recommendations"""
        try:
            recommendations = []
            
            if signal_count < 5:
                recommendations.append("Low signal generation rate - check system resources and data availability")
            
            if processing_time > 2.0:
                recommendations.append("High processing time - optimize algorithms and database queries")
            
            if success_rate < 0.7:
                recommendations.append("Low success rate - review signal generation logic and parameters")
            
            if not recommendations:
                recommendations.append("Performance within acceptable parameters")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating performance recommendations: {e}")
            return ["Error generating recommendations"]
    
    def get_comprehensive_monitoring_report(self) -> Dict[str, Any]:
        """Get comprehensive monitoring report"""
        try:
            logger.info("Generating comprehensive monitoring report...")
            
            # Get all monitoring data
            quality_report = self.monitor_signal_quality()
            freshness_report = self.monitor_data_freshness()
            performance_report = self.monitor_signal_generation_performance()
            
            # Get database health
            db_health = get_database_health_status()
            
            # Calculate overall system score
            quality_score = quality_report.get('quality_score', 0)
            freshness_score = freshness_report.get('freshness_score', 0)
            performance_score = performance_report.get('performance_score', 0)
            
            overall_score = (quality_score + freshness_score + performance_score) / 3
            
            comprehensive_report = {
                'timestamp': timezone.now().isoformat(),
                'overall_system_score': overall_score,
                'system_status': self._determine_system_status(overall_score),
                'quality_monitoring': quality_report,
                'data_freshness': freshness_report,
                'performance_monitoring': performance_report,
                'database_health': db_health,
                'recommendations': self._generate_comprehensive_recommendations(
                    quality_report,
                    freshness_report,
                    performance_report
                ),
                'next_actions': self._generate_next_actions(overall_score)
            }
            
            logger.info(f"Comprehensive monitoring report generated - Overall Score: {overall_score:.1f}")
            return comprehensive_report
            
        except Exception as e:
            logger.error(f"Error generating comprehensive monitoring report: {e}")
            return {'error': str(e)}
    
    def _determine_system_status(self, overall_score: float) -> str:
        """Determine overall system status based on score"""
        if overall_score >= 90:
            return "EXCELLENT"
        elif overall_score >= 80:
            return "GOOD"
        elif overall_score >= 70:
            return "WARNING"
        elif overall_score >= 50:
            return "CRITICAL"
        else:
            return "DOWN"
    
    def _generate_comprehensive_recommendations(self, quality_report: Dict, freshness_report: Dict, performance_report: Dict) -> List[str]:
        """Generate comprehensive recommendations"""
        try:
            recommendations = []
            
            # Quality recommendations
            quality_recommendations = quality_report.get('recommendations', [])
            recommendations.extend(quality_recommendations)
            
            # Freshness recommendations
            if freshness_report.get('freshness_score', 0) < 80:
                recommendations.append("Data freshness below optimal - check data collection processes")
            
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
        """Generate next actions based on system score"""
        try:
            actions = []
            
            if overall_score < 70:
                actions.append("Immediate system review required")
                actions.append("Check all monitoring alerts")
                actions.append("Review system logs for errors")
            
            if overall_score < 80:
                actions.append("Schedule system maintenance")
                actions.append("Review performance metrics")
                actions.append("Update monitoring thresholds")
            
            if overall_score >= 80:
                actions.append("Continue monitoring")
                actions.append("Review optimization opportunities")
                actions.append("Plan system improvements")
            
            return actions
            
        except Exception as e:
            logger.error(f"Error generating next actions: {e}")
            return ["Error generating next actions"]


# Global instance
database_signal_monitor = DatabaseSignalMonitor()














