"""
Capital-Based Risk Management Service

Implements take profit and stop loss logic based on capital percentages:
- 60% profit take profit point (target)
- 40% capital loss stop loss point

This service provides utilities for calculating position sizes and price levels
based on these capital-based criteria.
"""

from decimal import Decimal, ROUND_DOWN
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class CapitalBasedRiskManager:
    """
    Risk management service that calculates position sizes and exit points
    based on capital percentage allocations for profit and loss.
    """
    
    def __init__(self, capital_per_trade: float = 1000.0):
        """
        Initialize with the capital amount to risk per trade.
        
        Args:
            capital_per_trade: Amount of capital to risk per trade in USD
        """
        self.capital_per_trade = Decimal(str(capital_per_trade))
        self.profit_target_percentage = Decimal('0.60')  # 60% profit target
        self.loss_limit_percentage = Decimal('0.40')     # 40% loss limit
    
    def calculate_capital_based_targets(self, 
                                      symbol: str,
                                      entry_price: float, 
                                      signal_type: str = 'BUY',
                                      symbol_quantity: Optional[float] = None) -> Dict[str, Optional[float]]:
        """
        Calculate take profit and stop loss levels based on capital percentages.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            entry_price: Entry price for the trade
            signal_type: Type of signal ('BUY', 'SELL', 'STRONG_BUY', etc.)
            symbol_quantity: Specific quantity to trade (if None, calculates optimal)
            
        Returns:
            Dict containing calculated values:
            - position_size: Number of units to trade
            - take_profit_price: Price level for taking profit (60% of capital gain)
            - stop_loss_price: Price level for stopping loss (40% of capital loss)
            - take_profit_amount: Dollar amount of profit target
            - stop_loss_amount: Dollar amount of loss limit
            - position_value: Total value of the position
            - risk_reward_ratio: Risk to reward ratio
        """
        try:
            entry_decimal = Decimal(str(entry_price))
            signal_type = signal_type.upper()
            
            # Validate signal type
            valid_signals = ['BUY', 'SELL', 'STRONG_BUY', 'STRONG_SELL']
            if signal_type not in valid_signals:
                raise ValueError(f"Invalid signal type: {signal_type}. Must be one of {valid_signals}")
            
            # Determine if this is a long (buy) or short (sell) position
            is_long_position = signal_type in ['BUY', 'STRONG_BUY']
            
            # Calculate position size (units to trade)
            if symbol_quantity is None:
                # Use entire capital allocation
                position_size = self.capital_per_trade / entry_decimal
            else:
                position_size = Decimal(str(symbol_quantity))
                # Verify we don't exceed capital allocation
                position_value = position_size * entry_decimal
                if position_value > self.capital_per_trade:
                    logger.warning(f"Position value {position_value} exceeds capital allocation {self.capital_per_trade}")
                    position_size = self.capital_per_trade / entry_decimal
            
            # Calculate dollar amounts for profit and loss targets
            profit_target_amount = self.capital_per_trade * self.profit_target_percentage
            loss_limit_amount = self.capital_per_trade * self.loss_limit_percentage
            
            # Calculate price levels based on position type
            if is_long_position:
                # Long position: profit upward, loss downward
                take_profit_price = entry_decimal + (profit_target_amount / position_size)
                stop_loss_price = entry_decimal - (loss_limit_amount / position_size)
            else:
                # Short position: profit downward, loss upward
                take_profit_price = entry_decimal - (profit_target_amount / position_size)
                stop_loss_price = entry_decimal + (loss_limit_amount / position_size)
            
            # Calculate risk-reward ratio
            price_distance_to_profit = abs(take_profit_price - entry_decimal)
            price_distance_to_loss = abs(entry_decimal - stop_loss_price)
            
            if price_distance_to_loss != Decimal('0'):
                risk_reward_ratio = float(price_distance_to_profit / price_distance_to_loss)
            else:
                risk_reward_ratio = 0.0
            
            # Calculate position value
            position_value = position_size * entry_decimal
            
            result = {
                'symbol': symbol,
                'signal_type': signal_type,
                'position_size': float(position_size),
                'position_value': float(position_value),
                'take_profit_price': float(take_profit_price),
                'stop_loss_price': float(stop_loss_price),
                'take_profit_amount': float(profit_target_amount),
                'stop_loss_amount': float(loss_limit_amount),
                'risk_reward_ratio': risk_reward_ratio,
                'capital_per_trade': float(self.capital_per_trade),
                'entry_price': float(entry_decimal),
                'is_long_position': is_long_position
            }
            
            logger.info(f"Calculated capital-based targets for {symbol}: "
                       f"TP={result['take_profit_price']:.6f}, "
                       f"SL={result['stop_loss_price']:.6f}, "
                       f"RR={risk_reward_ratio:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating capital-based targets: {e}")
            return {}
    
    def calculate_position_size_for_fixed_capital(self, 
                                               entry_price: float, 
                                               available_capital: float) -> float:
        """
        Calculate position size using available capital.
        
        Args:
            entry_price: Entry price for the trade
            available_capital: Available capital to use
            
        Returns:
            Number of units that can be purchased
        """
        try:
            entry_decimal = Decimal(str(entry_price))
            capital_decimal = Decimal(str(available_capital))
            
            position_size = capital_decimal / entry_decimal
            
            logger.info(f"Position size calculated: {float(position_size):.6f} units "
                       f"for ${float(capital_decimal):.2f} capital at price ${float(entry_decimal):.6f}")
            
            return float(position_size)
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def validate_price_levels(self, 
                            entry_price: float, 
                            take_profit_price: float, 
                            stop_loss_price: float,
                            signal_type: str = 'BUY') -> Dict[str, any]:
        """
        Validate that calculated price levels make sense.
        
        Args:
            entry_price: Entry price
            take_profit_price: Calculated take profit price
            stop_loss_price: Calculated stop loss price
            signal_type: Type of signal
            
        Returns:
            Dict with validation results and warnings
        """
        validation = {
            'is_valid': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            signal_type = signal_type.upper()
            is_long = signal_type in ['BUY', 'STRONG_BUY']
            
            if is_long:
                # For long positions
                if take_profit_price <= entry_price:
                    validation['errors'].append(
                        f"Take profit price {take_profit_price} should be above entry price {entry_price} for long positions"
                    )
                    validation['is_valid'] = False
                
                if stop_loss_price >= entry_price:
                    validation['errors'].append(
                        f"Stop loss price {stop_loss_price} should be below entry price {entry_price} for long positions"
                    )
                    validation['is_valid'] = False
                    
                # Check for reasonable spread
                profit_distance = take_profit_price - entry_price
                loss_distance = entry_price - stop_loss_price
                
                if loss_distance <= 0:
                    validation['errors'].append("Stop loss price is invalid (above entry price for long)")
                    validation['is_valid'] = False
                    
            else:
                # For short positions
                if take_profit_price >= entry_price:
                    validation['errors'].append(
                        f"Take profit price {take_profit_price} should be below entry price {entry_price} for short positions"
                    )
                    validation['is_valid'] = False
                
                if stop_loss_price <= entry_price:
                    validation['errors'].append(
                        f"Stop loss price {stop_loss_price} should be above entry price {entry_price} for short positions"
                    )
                    validation['is_valid'] = False
            
            # Check for reasonable risk-reward ratio
            if validation['is_valid']:
                profit_distance = abs(take_profit_price - entry_price)
                loss_distance = abs(entry_price - stop_loss_price)
                
                if loss_distance > 0:
                    risk_reward_ratio = profit_distance / loss_distance
                    if risk_reward_ratio < 1.5:
                        validation['warnings'].append(
                            f"Risk-reward ratio is low: {risk_reward_ratio:.2f} "
                            f"(recommend at least 1.5)"
                        )
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating price levels: {e}")
            validation['is_valid'] = False
            validation['errors'].append(f"Validation error: {str(e)}")
            return validation
    
    def calculate_profit_loss_at_price(self,
                                     entry_price: float,
                                     current_price: float,
                                     position_size: float,
                                     signal_type: str = 'BUY') -> Dict[str, float]:
        """
        Calculate profit/loss at current market price.
        
        Args:
            entry_price: Original entry price
            current_price: Current market price
            position_size: Position size in units
            signal_type: Type of original signal
            
        Returns:
            Dict with profit/loss information
        """
        try:
            entry_decimal = Decimal(str(entry_price))
            current_decimal = Decimal(str(current_price))
            size_decimal = Decimal(str(position_size))
            signal_type = signal_type.upper()
            
            is_long = signal_type in ['BUY', 'STRONG_BUY']
            
            if is_long:
                pnl = (current_decimal - entry_decimal) * size_decimal
                pnl_percentage = ((current_decimal - entry_decimal) / entry_decimal) * 100
            else:
                pnl = (entry_decimal - current_decimal) * size_decimal
                pnl_percentage = ((entry_decimal - current_decimal) / entry_decimal) * 100
            
            # Calculate what percentage of our capital this represents
            capital_percentage = (abs(pnl) / self.capital_per_trade) * 100
            
            result = {
                'pnl': float(pnl),
                'pnl_percentage': float(pnl_percentage),
                'capital_percentage': float(capital_percentage),
                'position_value': float(position_size * current_decimal),
                'cost_basis': float(position_size * entry_decimal),
                'is_profitable': pnl > 0,
                'is_at_take_profit': False,
                'is_at_stop_loss': False,
                'distance_to_tp': 0.0,
                'distance_to_sl': 0.0
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}")
            return {'pnl': 0.0, 'pnl_percentage': 0.0, 'capital_percentage': 0.0}


# Utility function for easy integration with existing code
def create_capital_based_position(symbol: str, 
                                entry_price: float, 
                                signal_type: str,
                                capital_amount: float = 1000.0) -> Dict[str, any]:
    """
    Quick utility function to create capital-based position with TP/SL levels.
    
    Args:
        symbol: Trading symbol
        entry_price: Entry price
        signal_type: Signal type ('BUY', 'SELL', etc.)
        capital_amount: Capital to allocate for this trade
        
    Returns:
        Complete position information including TP/SL levels
    """
    risk_manager = CapitalBasedRiskManager(capital_amount)
    return risk_manager.calculate_capital_based_targets(symbol, entry_price, signal_type)



























































