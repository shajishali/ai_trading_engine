"""
Data quality validation tasks for database-driven signal generation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from django.core.cache import cache

from apps.trading.models import Symbol
from apps.data.models import MarketData, TechnicalIndicator
from apps.signals.models import SignalAlert
from apps.signals.database_data_utils import (
    get_database_health_status, validate_data_quality,
    get_symbols_with_recent_data, get_data_gaps,
    get_data_statistics
)

logger = logging.getLogger(__name__)


@shared_task
def comprehensive_data_quality_validation():
    """Comprehensive data quality validation for all symbols"""
    try:
        logger.info("Starting comprehensive data quality validation...")
        
        # Get all active crypto symbols
        active_symbols = Symbol.objects.filter(
            is_active=True, 
            is_crypto_symbol=True
        )
        
        validation_results = {
            'total_symbols': active_symbols.count(),
            'valid_symbols': 0,
            'invalid_symbols': 0,
            'symbols_with_gaps': 0,
            'symbols_with_old_data': 0,
            'symbols_with_insufficient_data': 0,
            'overall_quality_score': 0.0,
            'validation_details': []
        }
        
        for symbol in active_symbols:
            try:
                # Validate individual symbol
                symbol_validation = validate_individual_symbol_quality(symbol)
                validation_results['validation_details'].append(symbol_validation)
                
                # Update counters
                if symbol_validation['is_valid']:
                    validation_results['valid_symbols'] += 1
                else:
                    validation_results['invalid_symbols'] += 1
                    
                    # Categorize issues
                    if symbol_validation['has_data_gaps']:
                        validation_results['symbols_with_gaps'] += 1
                    if symbol_validation['data_age_hours'] > 2:
                        validation_results['symbols_with_old_data'] += 1
                    if symbol_validation['data_points'] < 20:
                        validation_results['symbols_with_insufficient_data'] += 1
                
            except Exception as e:
                logger.error(f"Error validating {symbol.symbol}: {e}")
                validation_results['validation_details'].append({
                    'symbol': symbol.symbol,
                    'is_valid': False,
                    'error': str(e)
                })
                validation_results['invalid_symbols'] += 1
        
        # Calculate overall quality score
        if validation_results['total_symbols'] > 0:
            validation_results['overall_quality_score'] = (
                validation_results['valid_symbols'] / validation_results['total_symbols']
            )
        
        # Create alerts for quality issues
        alerts_created = create_data_quality_alerts(validation_results)
        validation_results['alerts_created'] = alerts_created
        
        logger.info(
            f"Comprehensive data quality validation completed: "
            f"{validation_results['valid_symbols']}/{validation_results['total_symbols']} "
            f"symbols valid ({validation_results['overall_quality_score']:.1%})"
        )
        
        return validation_results
        
    except Exception as e:
        logger.error(f"Error in comprehensive data quality validation: {e}")
        return {'error': str(e)}


@shared_task
def validate_individual_symbol_quality(symbol: Symbol) -> Dict[str, any]:
    """Validate data quality for an individual symbol"""
    try:
        # Basic data quality validation
        quality = validate_data_quality(symbol, hours_back=24)
        
        # Check for data gaps
        gaps = get_data_gaps(symbol, hours_back=168)  # 1 week
        has_gaps = len(gaps) > 0
        
        # Get data statistics
        stats = get_data_statistics(symbol, days_back=7)
        
        # Check technical indicators availability
        recent_indicators = TechnicalIndicator.objects.filter(
            symbol=symbol,
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).exists()
        
        # Calculate quality score
        quality_score = calculate_symbol_quality_score(
            quality, has_gaps, stats, recent_indicators
        )
        
        return {
            'symbol': symbol.symbol,
            'is_valid': quality['is_valid'],
            'quality_score': quality_score,
            'data_age_hours': quality.get('data_age_hours', 0),
            'data_points': quality.get('data_points', 0),
            'completeness': quality.get('completeness', 0),
            'has_data_gaps': has_gaps,
            'gaps_count': len(gaps),
            'recent_indicators': recent_indicators,
            'total_records_7d': stats.get('total_records', 0),
            'price_range': stats.get('price_range', {}),
            'volume_stats': stats.get('volume_stats', {})
        }
        
    except Exception as e:
        logger.error(f"Error validating symbol {symbol.symbol}: {e}")
        return {
            'symbol': symbol.symbol,
            'is_valid': False,
            'error': str(e),
            'quality_score': 0.0
        }


def calculate_symbol_quality_score(quality: Dict, has_gaps: bool, stats: Dict, has_indicators: bool) -> float:
    """Calculate quality score for a symbol (0-1)"""
    try:
        score = 0.0
        
        # Data validity (40% weight)
        if quality['is_valid']:
            score += 0.4
        
        # Data freshness (20% weight)
        data_age_hours = quality.get('data_age_hours', 999)
        if data_age_hours <= 1:
            score += 0.2
        elif data_age_hours <= 2:
            score += 0.15
        elif data_age_hours <= 4:
            score += 0.1
        
        # Data completeness (20% weight)
        completeness = quality.get('completeness', 0)
        score += (completeness * 0.2)
        
        # No data gaps (10% weight)
        if not has_gaps:
            score += 0.1
        
        # Technical indicators available (10% weight)
        if has_indicators:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
        
    except Exception as e:
        logger.error(f"Error calculating quality score: {e}")
        return 0.0


def create_data_quality_alerts(validation_results: Dict) -> int:
    """Create alerts for data quality issues"""
    alerts_created = 0
    
    try:
        # Alert for low overall quality
        if validation_results['overall_quality_score'] < 0.8:
            SignalAlert.objects.create(
                alert_type='DATA_QUALITY_ALERT',
                priority='HIGH',
                title="Low Overall Data Quality",
                message=f"Only {validation_results['overall_quality_score']:.1%} of symbols have valid data"
            )
            alerts_created += 1
        
        # Alert for symbols with gaps
        if validation_results['symbols_with_gaps'] > 10:
            SignalAlert.objects.create(
                alert_type='DATA_QUALITY_ALERT',
                priority='MEDIUM',
                title="Multiple Symbols with Data Gaps",
                message=f"{validation_results['symbols_with_gaps']} symbols have data gaps"
            )
            alerts_created += 1
        
        # Alert for old data
        if validation_results['symbols_with_old_data'] > 20:
            SignalAlert.objects.create(
                alert_type='DATA_QUALITY_ALERT',
                priority='HIGH',
                title="Multiple Symbols with Old Data",
                message=f"{validation_results['symbols_with_old_data']} symbols have data older than 2 hours"
            )
            alerts_created += 1
        
        # Alert for insufficient data
        if validation_results['symbols_with_insufficient_data'] > 15:
            SignalAlert.objects.create(
                alert_type='DATA_QUALITY_ALERT',
                priority='MEDIUM',
                title="Multiple Symbols with Insufficient Data",
                message=f"{validation_results['symbols_with_insufficient_data']} symbols have insufficient data"
            )
            alerts_created += 1
        
        return alerts_created
        
    except Exception as e:
        logger.error(f"Error creating data quality alerts: {e}")
        return 0


@shared_task
def monitor_data_freshness():
    """Monitor data freshness across all symbols"""
    try:
        logger.info("Starting data freshness monitoring...")
        
        # Get database health
        health_status = get_database_health_status()
        
        # Get symbols with recent data
        symbols_with_data = get_symbols_with_recent_data(hours_back=24, min_data_points=20)
        
        freshness_results = {
            'database_health': health_status,
            'symbols_with_recent_data': len(symbols_with_data),
            'data_age_hours': health_status.get('latest_data_age_hours', 0),
            'freshness_status': 'UNKNOWN'
        }
        
        # Determine freshness status
        data_age_hours = health_status.get('latest_data_age_hours', 999)
        if data_age_hours <= 1:
            freshness_status = 'EXCELLENT'
        elif data_age_hours <= 2:
            freshness_status = 'GOOD'
        elif data_age_hours <= 4:
            freshness_status = 'WARNING'
        else:
            freshness_status = 'CRITICAL'
        
        freshness_results['freshness_status'] = freshness_status
        
        # Create alerts for freshness issues
        if freshness_status in ['WARNING', 'CRITICAL']:
            priority = 'HIGH' if freshness_status == 'CRITICAL' else 'MEDIUM'
            SignalAlert.objects.create(
                alert_type='DATA_FRESHNESS_ALERT',
                priority=priority,
                title=f"Data Freshness {freshness_status}",
                message=f"Latest data is {data_age_hours:.1f} hours old"
            )
        
        logger.info(f"Data freshness monitoring completed: {freshness_status}")
        return freshness_results
        
    except Exception as e:
        logger.error(f"Error monitoring data freshness: {e}")
        return {'error': str(e)}


@shared_task
def detect_data_gaps():
    """Detect and report data gaps across all symbols"""
    try:
        logger.info("Starting data gap detection...")
        
        # Get symbols with recent data
        symbols_with_data = get_symbols_with_recent_data(hours_back=168, min_data_points=50)
        
        gap_results = {
            'symbols_checked': len(symbols_with_data),
            'symbols_with_gaps': 0,
            'total_gaps': 0,
            'gap_details': []
        }
        
        for symbol in symbols_with_data:
            try:
                # Check for gaps
                gaps = get_data_gaps(symbol, hours_back=168)
                
                if gaps:
                    gap_results['symbols_with_gaps'] += 1
                    gap_results['total_gaps'] += len(gaps)
                    
                    # Calculate total gap duration
                    total_gap_hours = sum(gap['duration_hours'] for gap in gaps)
                    
                    gap_results['gap_details'].append({
                        'symbol': symbol.symbol,
                        'gaps_count': len(gaps),
                        'total_gap_hours': total_gap_hours,
                        'gaps': gaps
                    })
                    
                    # Create alert for significant gaps
                    if total_gap_hours > 24:  # More than 24 hours of gaps
                        SignalAlert.objects.create(
                            alert_type='DATA_GAP_ALERT',
                            priority='HIGH',
                            title=f"Significant Data Gaps for {symbol.symbol}",
                            message=f"{len(gaps)} gaps totaling {total_gap_hours:.1f} hours"
                        )
                
            except Exception as e:
                logger.error(f"Error checking gaps for {symbol.symbol}: {e}")
        
        logger.info(
            f"Data gap detection completed: "
            f"{gap_results['symbols_with_gaps']}/{gap_results['symbols_checked']} "
            f"symbols have gaps, {gap_results['total_gaps']} total gaps"
        )
        
        return gap_results
        
    except Exception as e:
        logger.error(f"Error detecting data gaps: {e}")
        return {'error': str(e)}


@shared_task
def validate_technical_indicators_quality():
    """Validate quality of technical indicators"""
    try:
        logger.info("Starting technical indicators quality validation...")
        
        # Get symbols with recent indicators
        symbols_with_indicators = Symbol.objects.filter(
            is_active=True,
            is_crypto_symbol=True,
            technicalindicator__timestamp__gte=timezone.now() - timedelta(hours=24)
        ).distinct()
        
        validation_results = {
            'symbols_with_indicators': symbols_with_indicators.count(),
            'indicators_validated': 0,
            'indicators_with_issues': 0,
            'validation_details': []
        }
        
        for symbol in symbols_with_indicators:
            try:
                # Get latest indicators
                latest_indicators = TechnicalIndicator.objects.filter(
                    symbol=symbol
                ).order_by('-timestamp').first()
                
                if latest_indicators:
                    # Validate indicator values
                    indicator_validation = validate_indicator_values(latest_indicators)
                    validation_results['validation_details'].append(indicator_validation)
                    
                    if indicator_validation['is_valid']:
                        validation_results['indicators_validated'] += 1
                    else:
                        validation_results['indicators_with_issues'] += 1
                
            except Exception as e:
                logger.error(f"Error validating indicators for {symbol.symbol}: {e}")
        
        logger.info(
            f"Technical indicators quality validation completed: "
            f"{validation_results['indicators_validated']} valid, "
            f"{validation_results['indicators_with_issues']} with issues"
        )
        
        return validation_results
        
    except Exception as e:
        logger.error(f"Error validating technical indicators quality: {e}")
        return {'error': str(e)}


def validate_indicator_values(indicators: TechnicalIndicator) -> Dict[str, any]:
    """Validate technical indicator values for reasonableness"""
    try:
        issues = []
        
        # Validate RSI (should be 0-100)
        if indicators.rsi is not None:
            rsi_value = float(indicators.rsi)
            if rsi_value < 0 or rsi_value > 100:
                issues.append(f"RSI out of range: {rsi_value}")
        
        # Validate MACD values
        if indicators.macd is not None and indicators.macd_signal is not None:
            macd_value = float(indicators.macd)
            signal_value = float(indicators.macd_signal)
            
            # Check for extreme values
            if abs(macd_value) > 1000 or abs(signal_value) > 1000:
                issues.append(f"MACD extreme values: {macd_value}, {signal_value}")
        
        # Validate Bollinger Bands
        if (indicators.bollinger_upper is not None and 
            indicators.bollinger_lower is not None):
            upper = float(indicators.bollinger_upper)
            lower = float(indicators.bollinger_lower)
            
            if upper <= lower:
                issues.append(f"Bollinger Bands inverted: upper={upper}, lower={lower}")
        
        # Validate moving averages
        if (indicators.sma_20 is not None and 
            indicators.sma_50 is not None):
            sma_20 = float(indicators.sma_20)
            sma_50 = float(indicators.sma_50)
            
            if sma_20 <= 0 or sma_50 <= 0:
                issues.append(f"Invalid SMA values: SMA20={sma_20}, SMA50={sma_50}")
        
        return {
            'symbol': indicators.symbol.symbol,
            'is_valid': len(issues) == 0,
            'issues': issues,
            'timestamp': indicators.timestamp
        }
        
    except Exception as e:
        logger.error(f"Error validating indicator values: {e}")
        return {
            'symbol': indicators.symbol.symbol,
            'is_valid': False,
            'issues': [f"Validation error: {e}"],
            'timestamp': indicators.timestamp
        }


@shared_task
def generate_data_quality_report():
    """Generate comprehensive data quality report"""
    try:
        logger.info("Starting data quality report generation...")
        
        # Get overall database health
        health_status = get_database_health_status()
        
        # Get symbols with recent data
        symbols_with_data = get_symbols_with_recent_data(hours_back=24, min_data_points=20)
        
        # Get data statistics
        total_symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True).count()
        
        # Calculate quality metrics
        data_availability = len(symbols_with_data) / total_symbols if total_symbols > 0 else 0
        data_freshness = 1.0 if health_status.get('latest_data_age_hours', 0) <= 2 else 0.5
        
        # Generate report
        report = {
            'timestamp': timezone.now(),
            'database_health': health_status,
            'total_symbols': total_symbols,
            'symbols_with_data': len(symbols_with_data),
            'data_availability': data_availability,
            'data_freshness': data_freshness,
            'overall_quality_score': (data_availability + data_freshness) / 2,
            'recommendations': generate_quality_recommendations(health_status, data_availability)
        }
        
        logger.info(f"Data quality report generated: {report['overall_quality_score']:.1%} quality")
        return report
        
    except Exception as e:
        logger.error(f"Error generating data quality report: {e}")
        return {'error': str(e)}


def generate_quality_recommendations(health_status: Dict, data_availability: float) -> List[str]:
    """Generate recommendations based on quality metrics"""
    recommendations = []
    
    # Data freshness recommendations
    data_age_hours = health_status.get('latest_data_age_hours', 0)
    if data_age_hours > 2:
        recommendations.append("Data is stale - check automated data collection")
    
    # Data availability recommendations
    if data_availability < 0.8:
        recommendations.append("Low data availability - check symbol coverage")
    
    # System health recommendations
    if health_status.get('status') == 'CRITICAL':
        recommendations.append("Database health critical - immediate attention required")
    elif health_status.get('status') == 'WARNING':
        recommendations.append("Database health warning - monitor closely")
    
    # General recommendations
    if not recommendations:
        recommendations.append("Data quality is good - continue monitoring")
    
    return recommendations














