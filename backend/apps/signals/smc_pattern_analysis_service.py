"""
Phase 5.2: SMC Pattern Analysis Service
Provides statistics and insights for detected SMC patterns
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.db import models

from apps.trading.models import Symbol
from apps.signals.models import ChartImage, ChartPattern, EntryPoint

logger = logging.getLogger(__name__)


class SMCPatternAnalysisService:
    """Service for analyzing SMC pattern statistics and insights"""
    
    def __init__(self):
        self.pattern_types = [
            'BOS', 'CHOCH', 'ORDER_BLOCK', 'FAIR_VALUE_GAP', 'LIQUIDITY_SWEEP'
        ]
    
    def get_pattern_statistics(self, symbol: Optional[Symbol] = None, 
                             timeframe: Optional[str] = None,
                             days_back: int = 30) -> Dict[str, any]:
        """
        Get comprehensive pattern statistics
        
        Args:
            symbol: Specific symbol to analyze (None for all)
            timeframe: Specific timeframe to analyze (None for all)
            days_back: Number of days back to analyze
            
        Returns:
            Dictionary with pattern statistics
        """
        try:
            logger.info(f"Generating pattern statistics for {symbol.symbol if symbol else 'all symbols'}")
            
            # Base queryset
            patterns = ChartPattern.objects.all()
            
            # Apply filters
            if symbol:
                patterns = patterns.filter(chart_image__symbol=symbol)
            
            if timeframe:
                patterns = patterns.filter(chart_image__timeframe=timeframe)
            
            # Date filter
            start_date = timezone.now() - timedelta(days=days_back)
            patterns = patterns.filter(detected_at__gte=start_date)
            
            # Overall statistics
            total_patterns = patterns.count()
            validated_patterns = patterns.filter(is_validated=True).count()
            validation_rate = (validated_patterns / total_patterns * 100) if total_patterns > 0 else 0
            
            # Pattern type breakdown
            pattern_breakdown = {}
            for pattern_type in self.pattern_types:
                count = patterns.filter(pattern_type=pattern_type).count()
                avg_confidence = patterns.filter(pattern_type=pattern_type).aggregate(
                    avg_conf=Avg('confidence_score')
                )['avg_conf'] or 0
                
                pattern_breakdown[pattern_type] = {
                    'count': count,
                    'percentage': (count / total_patterns * 100) if total_patterns > 0 else 0,
                    'avg_confidence': round(avg_confidence, 3)
                }
            
            # Confidence distribution
            confidence_stats = patterns.aggregate(
                avg_confidence=Avg('confidence_score'),
                max_confidence=Max('confidence_score'),
                min_confidence=Min('confidence_score')
            )
            
            # Strength distribution
            strength_distribution = {}
            for strength in ['WEAK', 'MODERATE', 'STRONG', 'VERY_STRONG']:
                count = patterns.filter(strength=strength).count()
                strength_distribution[strength] = {
                    'count': count,
                    'percentage': (count / total_patterns * 100) if total_patterns > 0 else 0
                }
            
            # Time-based analysis
            time_analysis = self._analyze_patterns_over_time(patterns)
            
            # Symbol analysis (if not filtering by symbol)
            symbol_analysis = {}
            if not symbol:
                symbol_analysis = self._analyze_patterns_by_symbol(patterns)
            
            # Timeframe analysis (if not filtering by timeframe)
            timeframe_analysis = {}
            if not timeframe:
                timeframe_analysis = self._analyze_patterns_by_timeframe(patterns)
            
            statistics = {
                'overview': {
                    'total_patterns': total_patterns,
                    'validated_patterns': validated_patterns,
                    'validation_rate': round(validation_rate, 2),
                    'analysis_period_days': days_back
                },
                'pattern_breakdown': pattern_breakdown,
                'confidence_stats': {
                    'avg_confidence': round(confidence_stats['avg_confidence'] or 0, 3),
                    'max_confidence': round(confidence_stats['max_confidence'] or 0, 3),
                    'min_confidence': round(confidence_stats['min_confidence'] or 0, 3)
                },
                'strength_distribution': strength_distribution,
                'time_analysis': time_analysis,
                'symbol_analysis': symbol_analysis,
                'timeframe_analysis': timeframe_analysis
            }
            
            logger.info(f"Pattern statistics generated: {total_patterns} patterns analyzed")
            return statistics
            
        except Exception as e:
            logger.error(f"Error generating pattern statistics: {e}")
            return {}
    
    def get_pattern_performance_metrics(self, symbol: Optional[Symbol] = None,
                                      timeframe: Optional[str] = None) -> Dict[str, any]:
        """
        Get pattern performance metrics
        
        Args:
            symbol: Specific symbol to analyze
            timeframe: Specific timeframe to analyze
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            logger.info(f"Generating pattern performance metrics")
            
            # Base queryset
            patterns = ChartPattern.objects.all()
            
            if symbol:
                patterns = patterns.filter(chart_image__symbol=symbol)
            
            if timeframe:
                patterns = patterns.filter(chart_image__timeframe=timeframe)
            
            # Performance metrics by pattern type
            performance_metrics = {}
            
            for pattern_type in self.pattern_types:
                type_patterns = patterns.filter(pattern_type=pattern_type)
                
                if type_patterns.exists():
                    # Validation rate
                    validated_count = type_patterns.filter(is_validated=True).count()
                    validation_rate = (validated_count / type_patterns.count()) * 100
                    
                    # Average confidence
                    avg_confidence = type_patterns.aggregate(
                        avg_conf=Avg('confidence_score')
                    )['avg_conf'] or 0
                    
                    # Confidence distribution
                    high_confidence_count = type_patterns.filter(confidence_score__gte=0.8).count()
                    medium_confidence_count = type_patterns.filter(
                        confidence_score__gte=0.6, confidence_score__lt=0.8
                    ).count()
                    low_confidence_count = type_patterns.filter(confidence_score__lt=0.6).count()
                    
                    # Strength distribution
                    strength_counts = {}
                    for strength in ['WEAK', 'MODERATE', 'STRONG', 'VERY_STRONG']:
                        strength_counts[strength] = type_patterns.filter(strength=strength).count()
                    
                    performance_metrics[pattern_type] = {
                        'total_count': type_patterns.count(),
                        'validation_rate': round(validation_rate, 2),
                        'avg_confidence': round(avg_confidence, 3),
                        'confidence_distribution': {
                            'high': high_confidence_count,
                            'medium': medium_confidence_count,
                            'low': low_confidence_count
                        },
                        'strength_distribution': strength_counts
                    }
            
            return performance_metrics
            
        except Exception as e:
            logger.error(f"Error generating performance metrics: {e}")
            return {}
    
    def get_pattern_trends(self, symbol: Optional[Symbol] = None,
                          timeframe: Optional[str] = None,
                          days_back: int = 30) -> Dict[str, List]:
        """
        Get pattern trends over time
        
        Args:
            symbol: Specific symbol to analyze
            timeframe: Specific timeframe to analyze
            days_back: Number of days back to analyze
            
        Returns:
            Dictionary with trend data
        """
        try:
            logger.info(f"Generating pattern trends")
            
            # Base queryset
            patterns = ChartPattern.objects.all()
            
            if symbol:
                patterns = patterns.filter(chart_image__symbol=symbol)
            
            if timeframe:
                patterns = patterns.filter(chart_image__timeframe=timeframe)
            
            # Date filter
            start_date = timezone.now() - timedelta(days=days_back)
            patterns = patterns.filter(detected_at__gte=start_date)
            
            # Group by day
            daily_patterns = patterns.extra(
                select={'day': 'DATE(detected_at)'}
            ).values('day').annotate(
                total_count=Count('id'),
                avg_confidence=Avg('confidence_score'),
                validated_count=Count('id', filter=Q(is_validated=True))
            ).order_by('day')
            
            # Pattern type trends
            pattern_trends = {}
            for pattern_type in self.pattern_types:
                type_patterns = patterns.filter(pattern_type=pattern_type)
                daily_type_patterns = type_patterns.extra(
                    select={'day': 'DATE(detected_at)'}
                ).values('day').annotate(
                    count=Count('id'),
                    avg_confidence=Avg('confidence_score')
                ).order_by('day')
                
                pattern_trends[pattern_type] = list(daily_type_patterns)
            
            return {
                'daily_overview': list(daily_patterns),
                'pattern_trends': pattern_trends
            }
            
        except Exception as e:
            logger.error(f"Error generating pattern trends: {e}")
            return {}
    
    def get_top_performing_patterns(self, limit: int = 10) -> List[Dict]:
        """
        Get top performing patterns by confidence and validation
        
        Args:
            limit: Number of top patterns to return
            
        Returns:
            List of top performing patterns
        """
        try:
            logger.info(f"Getting top {limit} performing patterns")
            
            # Get patterns with high confidence and validation
            top_patterns = ChartPattern.objects.filter(
                confidence_score__gte=0.8,
                is_validated=True
            ).order_by('-confidence_score')[:limit]
            
            result = []
            for pattern in top_patterns:
                result.append({
                    'id': pattern.id,
                    'symbol': pattern.chart_image.symbol.symbol,
                    'timeframe': pattern.chart_image.timeframe,
                    'pattern_type': pattern.pattern_type,
                    'confidence_score': pattern.confidence_score,
                    'strength': pattern.strength,
                    'price_low': float(pattern.pattern_price_low),
                    'price_high': float(pattern.pattern_price_high),
                    'detected_at': pattern.detected_at
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting top performing patterns: {e}")
            return []
    
    def _analyze_patterns_over_time(self, patterns) -> Dict[str, any]:
        """Analyze patterns over time"""
        try:
            # Group by hour of day
            hourly_patterns = patterns.extra(
                select={'hour': 'EXTRACT(hour FROM detected_at)'}
            ).values('hour').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score')
            ).order_by('hour')
            
            # Group by day of week
            daily_patterns = patterns.extra(
                select={'day_of_week': 'EXTRACT(dow FROM detected_at)'}
            ).values('day_of_week').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score')
            ).order_by('day_of_week')
            
            return {
                'hourly_distribution': list(hourly_patterns),
                'daily_distribution': list(daily_patterns)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing patterns over time: {e}")
            return {}
    
    def _analyze_patterns_by_symbol(self, patterns) -> Dict[str, any]:
        """Analyze patterns by symbol"""
        try:
            symbol_stats = patterns.values('chart_image__symbol__symbol').annotate(
                total_count=Count('id'),
                avg_confidence=Avg('confidence_score'),
                validated_count=Count('id', filter=Q(is_validated=True))
            ).order_by('-total_count')
            
            return list(symbol_stats)
            
        except Exception as e:
            logger.error(f"Error analyzing patterns by symbol: {e}")
            return {}
    
    def _analyze_patterns_by_timeframe(self, patterns) -> Dict[str, any]:
        """Analyze patterns by timeframe"""
        try:
            timeframe_stats = patterns.values('chart_image__timeframe').annotate(
                total_count=Count('id'),
                avg_confidence=Avg('confidence_score'),
                validated_count=Count('id', filter=Q(is_validated=True))
            ).order_by('-total_count')
            
            return list(timeframe_stats)
            
        except Exception as e:
            logger.error(f"Error analyzing patterns by timeframe: {e}")
            return {}
    
    def export_pattern_analysis(self, symbol: Optional[Symbol] = None,
                               timeframe: Optional[str] = None) -> str:
        """
        Export pattern analysis to CSV format
        
        Args:
            symbol: Specific symbol to export
            timeframe: Specific timeframe to export
            
        Returns:
            CSV formatted string
        """
        try:
            import csv
            import io
            
            # Get patterns
            patterns = ChartPattern.objects.all()
            
            if symbol:
                patterns = patterns.filter(chart_image__symbol=symbol)
            
            if timeframe:
                patterns = patterns.filter(chart_image__timeframe=timeframe)
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'Symbol', 'Timeframe', 'Pattern Type', 'Confidence Score',
                'Strength', 'Price Low', 'Price High', 'Detected At',
                'Validated', 'Validation Score'
            ])
            
            # Write data
            for pattern in patterns:
                writer.writerow([
                    pattern.chart_image.symbol.symbol,
                    pattern.chart_image.timeframe,
                    pattern.pattern_type,
                    pattern.confidence_score,
                    pattern.strength,
                    pattern.pattern_price_low,
                    pattern.pattern_price_high,
                    pattern.detected_at,
                    pattern.is_validated,
                    pattern.validation_score
                ])
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error exporting pattern analysis: {e}")
            return ""

