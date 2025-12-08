"""
Price Validation Service - Validates that signal prices match real market history
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class PriceValidationService:
    """Service for validating signal prices against real market history"""
    
    def __init__(self):
        self.tolerance_percentage = 0.05  # 5% tolerance for price validation
        
    def validate_signal_prices(self, symbol: str, signal_date: datetime, 
                             entry_price: float, target_price: float, 
                             stop_loss: float) -> Dict:
        """
        Validate signal prices against real market history
        
        Args:
            symbol: Trading symbol
            signal_date: Date when signal was generated
            entry_price: Signal entry price
            target_price: Signal target price
            stop_loss: Signal stop loss price
        
        Returns:
            Validation result with status and details
        """
        try:
            from apps.data.historical_data_service import get_symbol_price_at_date
            
            # Get real historical price at signal date
            historical_price = get_symbol_price_at_date(symbol, signal_date)
            
            if not historical_price:
                return {
                    'is_valid': False,
                    'reason': 'No historical price data available',
                    'historical_price': None,
                    'entry_price': entry_price,
                    'deviation_percentage': None,
                    'recommendations': ['Historical data not available for validation']
                }
            
            # Calculate deviation from historical price
            deviation = abs(entry_price - historical_price) / historical_price
            
            # Check if entry price is within tolerance
            is_within_tolerance = deviation <= self.tolerance_percentage
            
            # Validate target and stop loss are reasonable
            target_reasonable = self._validate_target_stop_loss(
                entry_price, target_price, stop_loss, historical_price
            )
            
            validation_result = {
                'is_valid': is_within_tolerance and target_reasonable['is_valid'],
                'historical_price': historical_price,
                'entry_price': entry_price,
                'deviation_percentage': deviation * 100,
                'target_price': target_price,
                'stop_loss': stop_loss,
                'target_validation': target_reasonable,
                'recommendations': []
            }
            
            # Add recommendations
            if not is_within_tolerance:
                validation_result['recommendations'].append(
                    f"Entry price deviates {deviation*100:.2f}% from historical price "
                    f"(${historical_price:.2f}). Consider adjusting to match market conditions."
                )
            
            if not target_reasonable['is_valid']:
                validation_result['recommendations'].extend(target_reasonable['recommendations'])
            
            if validation_result['is_valid']:
                validation_result['reason'] = 'Prices match historical market conditions'
            else:
                validation_result['reason'] = 'Prices deviate significantly from historical market conditions'
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating prices for {symbol}: {e}")
            return {
                'is_valid': False,
                'reason': f'Validation error: {str(e)}',
                'historical_price': None,
                'entry_price': entry_price,
                'deviation_percentage': None,
                'recommendations': ['Unable to validate prices due to technical error']
            }
    
    def _validate_target_stop_loss(self, entry_price: float, target_price: float, 
                                  stop_loss: float, historical_price: float) -> Dict:
        """Validate target and stop loss prices are reasonable"""
        try:
            recommendations = []
            is_valid = True
            
            # Check if target price is reasonable for BUY signals
            if target_price > entry_price:  # BUY signal
                target_gain = (target_price - entry_price) / entry_price
                if target_gain > 0.5:  # More than 50% gain
                    recommendations.append(
                        f"Target price suggests {target_gain*100:.1f}% gain, which may be unrealistic"
                    )
                    is_valid = False
                
                # Check stop loss is below entry
                if stop_loss >= entry_price:
                    recommendations.append("Stop loss should be below entry price for BUY signals")
                    is_valid = False
                
                # Check stop loss is reasonable
                stop_loss_percentage = (entry_price - stop_loss) / entry_price
                if stop_loss_percentage > 0.3:  # More than 30% stop loss
                    recommendations.append(
                        f"Stop loss suggests {stop_loss_percentage*100:.1f}% loss, which may be too high"
                    )
                    is_valid = False
            
            # Check if target price is reasonable for SELL signals
            elif target_price < entry_price:  # SELL signal
                target_gain = (entry_price - target_price) / entry_price
                if target_gain > 0.5:  # More than 50% gain
                    recommendations.append(
                        f"Target price suggests {target_gain*100:.1f}% gain, which may be unrealistic"
                    )
                    is_valid = False
                
                # Check stop loss is above entry
                if stop_loss <= entry_price:
                    recommendations.append("Stop loss should be above entry price for SELL signals")
                    is_valid = False
                
                # Check stop loss is reasonable
                stop_loss_percentage = (stop_loss - entry_price) / entry_price
                if stop_loss_percentage > 0.3:  # More than 30% stop loss
                    recommendations.append(
                        f"Stop loss suggests {stop_loss_percentage*100:.1f}% loss, which may be too high"
                    )
                    is_valid = False
            
            else:
                recommendations.append("Target price should be different from entry price")
                is_valid = False
            
            return {
                'is_valid': is_valid,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error validating target/stop loss: {e}")
            return {
                'is_valid': False,
                'recommendations': [f'Validation error: {str(e)}']
            }
    
    def validate_signal_execution(self, symbol: str, signal_date: datetime, 
                                execution_date: datetime, execution_price: float) -> Dict:
        """
        Validate signal execution against real market history
        
        Args:
            symbol: Trading symbol
            signal_date: Date when signal was generated
            execution_date: Date when signal was executed
            execution_price: Price at which signal was executed
        
        Returns:
            Validation result with status and details
        """
        try:
            from apps.data.historical_data_service import get_symbol_price_at_date
            
            # Get real historical price at execution date
            historical_price = get_symbol_price_at_date(symbol, execution_date)
            
            if not historical_price:
                return {
                    'is_valid': False,
                    'reason': 'No historical price data available for execution date',
                    'historical_price': None,
                    'execution_price': execution_price,
                    'deviation_percentage': None
                }
            
            # Calculate deviation from historical price
            deviation = abs(execution_price - historical_price) / historical_price
            
            # Check if execution price is within tolerance
            is_within_tolerance = deviation <= self.tolerance_percentage
            
            return {
                'is_valid': is_within_tolerance,
                'reason': 'Execution price matches historical market conditions' if is_within_tolerance else 'Execution price deviates from historical market conditions',
                'historical_price': historical_price,
                'execution_price': execution_price,
                'deviation_percentage': deviation * 100,
                'signal_date': signal_date,
                'execution_date': execution_date
            }
            
        except Exception as e:
            logger.error(f"Error validating signal execution for {symbol}: {e}")
            return {
                'is_valid': False,
                'reason': f'Validation error: {str(e)}',
                'historical_price': None,
                'execution_price': execution_price,
                'deviation_percentage': None
            }
    
    def get_price_range_for_date(self, symbol: str, target_date: datetime) -> Optional[Dict]:
        """
        Get price range (high, low, open, close) for a specific date
        
        Args:
            symbol: Trading symbol
            target_date: Date to get price range for
        
        Returns:
            Price range data or None if not available
        """
        try:
            from apps.data.historical_data_service import get_historical_data
            
            # Get data for the target date
            start_date = target_date - timedelta(hours=1)
            end_date = target_date + timedelta(hours=1)
            
            historical_data = get_historical_data(symbol, start_date, end_date, '1h')
            
            if not historical_data:
                return None
            
            # Find the closest data point to target date
            # Handle timezone-aware and naive datetimes
            def time_diff(data_point):
                timestamp = data_point['timestamp']
                if timestamp.tzinfo is None and target_date.tzinfo is not None:
                    # Make timestamp timezone-aware
                    from django.utils import timezone
                    timestamp = timezone.make_aware(timestamp)
                elif timestamp.tzinfo is not None and target_date.tzinfo is None:
                    # Make target_date timezone-aware
                    from django.utils import timezone
                    target_date_tz = timezone.make_aware(target_date)
                else:
                    target_date_tz = target_date
                return abs((timestamp - target_date_tz).total_seconds())
            
            closest_data = min(historical_data, key=time_diff)
            
            return {
                'open': closest_data['open'],
                'high': closest_data['high'],
                'low': closest_data['low'],
                'close': closest_data['close'],
                'volume': closest_data['volume'],
                'timestamp': closest_data['timestamp']
            }
            
        except Exception as e:
            logger.error(f"Error getting price range for {symbol} at {target_date}: {e}")
            return None
    
    def validate_backtesting_results(self, symbol: str, start_date: datetime, 
                                   end_date: datetime, signals: List[Dict]) -> Dict:
        """
        Validate entire backtesting results against real market history
        
        Args:
            symbol: Trading symbol
            start_date: Backtesting start date
            end_date: Backtesting end date
            signals: List of signal data
        
        Returns:
            Comprehensive validation result
        """
        try:
            validation_results = {
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date,
                'total_signals': len(signals),
                'valid_signals': 0,
                'invalid_signals': 0,
                'signal_validations': [],
                'overall_valid': True,
                'recommendations': []
            }
            
            for signal in signals:
                signal_validation = self.validate_signal_prices(
                    symbol=symbol,
                    signal_date=signal.get('created_at', start_date),
                    entry_price=signal.get('entry_price', 0),
                    target_price=signal.get('target_price', 0),
                    stop_loss=signal.get('stop_loss', 0)
                )
                
                validation_results['signal_validations'].append(signal_validation)
                
                if signal_validation['is_valid']:
                    validation_results['valid_signals'] += 1
                else:
                    validation_results['invalid_signals'] += 1
                    validation_results['overall_valid'] = False
            
            # Calculate validation percentage
            if validation_results['total_signals'] > 0:
                validation_percentage = (validation_results['valid_signals'] / 
                                       validation_results['total_signals']) * 100
                validation_results['validation_percentage'] = validation_percentage
                
                if validation_percentage < 80:
                    validation_results['recommendations'].append(
                        f"Only {validation_percentage:.1f}% of signals are valid. "
                        "Consider reviewing signal generation logic."
                    )
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating backtesting results for {symbol}: {e}")
            return {
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date,
                'total_signals': len(signals),
                'valid_signals': 0,
                'invalid_signals': len(signals),
                'overall_valid': False,
                'error': str(e),
                'recommendations': ['Unable to validate backtesting results due to technical error']
            }


# Global instance
price_validation_service = PriceValidationService()


def validate_signal_prices(symbol: str, signal_date: datetime, entry_price: float, 
                          target_price: float, stop_loss: float) -> Dict:
    """Validate signal prices against real market history"""
    return price_validation_service.validate_signal_prices(
        symbol, signal_date, entry_price, target_price, stop_loss
    )


def validate_signal_execution(symbol: str, signal_date: datetime, execution_date: datetime, 
                            execution_price: float) -> Dict:
    """Validate signal execution against real market history"""
    return price_validation_service.validate_signal_execution(
        symbol, signal_date, execution_date, execution_price
    )


def validate_backtesting_results(symbol: str, start_date: datetime, end_date: datetime, 
                               signals: List[Dict]) -> Dict:
    """Validate entire backtesting results against real market history"""
    return price_validation_service.validate_backtesting_results(
        symbol, start_date, end_date, signals
    )
