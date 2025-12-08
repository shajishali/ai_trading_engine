"""
Position Utility Service

Provides utilities for managing positions with capital-based take profit and stop loss.
Integrates with the CapitalBasedRiskManager for consistent position management.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from apps.trading.models import Position, Trade, Portfolio, Symbol
from apps.data.services import RiskManagementService
import logging

logger = logging.getLogger(__name__)


class PositionManager:
    """Service for managing positions with capital-based TP/SL"""
    
    def __init__(self):
        self.risk_service = RiskManagementService()
    
    def create_capital_based_position(self, 
                                    portfolio: Portfolio,
                                    symbol: Symbol,
                                    entry_price: float,
                                    signal_type: str,
                                    capital_amount: float = 1000.0,
                                    quantity: Optional[float] = None) -> Optional[Position]:
        """
        Create a new position with capital-based targets.
        
        Args:
            portfolio: User portfolio
            symbol: Trading symbol
            entry_price: Entry price
            signal_type: Signal type ('BUY', 'SELL', etc.)
            capital_amount: Capital to allocate for this trade
            quantity: Specific quantity (if None, calculates based on capital)
            
        Returns:
            Created Position object or None if failed
        """
        try:
            # Calculate capital-based position data
            position_data = self.risk_service.calculate_capital_based_position(
                symbol=symbol.symbol,
                entry_price=entry_price,
                signal_type=signal_type,
                capital_amount=capital_amount
            )
            
            if not position_data:
                logger.error(f"Failed to calculate position data for {symbol.symbol}")
                return None
            
            # Determine position type
            position_type = 'LONG' if position_data.get('is_long_position', True) else 'SHORT'
            
            # Use calculated position size if quantity not provided
            if quantity is None:
                quantity = position_data.get('position_size', capital_amount / entry_price)
            
            # Create position
            with transaction.atomic():
                position = Position.objects.create(
                    portfolio=portfolio,
                    symbol=symbol,
                    position_type=position_type,
                    quantity=Decimal(str(quantity)),
                    entry_price=Decimal(str(entry_price)),
                    take_profit=Decimal(str(position_data.get('take_profit_price', entry_price))),
                    stop_loss=Decimal(str(position_data.get('stop_loss_price', entry_price))),
                )
                
                # Set capital-based targets
                position.set_capital_based_targets(
                    capital_amount=capital_amount,
                    profit_target_pct=60.0,  # 60% profit target
                    loss_limit_pct=40.0      # 40% loss limit
                )
                
                position.save()
                
                logger.info(f"Created capital-based position for {symbol.symbol}: "
                           f"Capital=${capital_amount}, TP=${position.take_profit:.6f}, "
                           f"SL=${position.stop_loss:.6f}")
                
                return position
                
        except Exception as e:
            logger.error(f"Error creating capital-based position: {e}")
            return None
    
    def update_position_metrics(self, position: Position, current_price: float) -> bool:
        """Update position metrics with current price"""
        try:
            success = position.update_capital_based_metrics(current_price)
            if success:
                position.save()
                
                # Check if exit conditions met
                if position.is_profit_target_hit or position.is_loss_limit_hit:
                    logger.info(f"Exit condition met for position {position.id}: "
                               f"{position.capital_based_status}")
                
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating position metrics: {e}")
            return False
    
    def close_position(self, 
                      position: Position, 
                      exit_price: float, 
                      reason: str = "Manual close") -> bool:
        """Close a position and record the trade"""
        try:
            if not position.is_open:
                logger.warning(f"Position {position.id} is already closed")
                return False
            
            # Update final metrics
            self.update_position_metrics(position, exit_price)
            
            with transaction.atomic():
                # Create closing trade
                Trade.objects.create(
                    portfolio=position.portfolio,
                    symbol=position.symbol,
                    trade_type='SELL' if position.position_type == 'LONG' else 'BUY',
                    quantity=position.quantity,
                    price=Decimal(str(exit_price)),
                    notes=f"Position closed: {reason}"
                )
                
                # Close the position
                position.is_open = False
                position.current_price = Decimal(str(exit_price))
                position.closed_at = timezone.now()
                position.save()
                
                logger.info(f"Closed position {position.id} at {exit_price}: "
                           f"{position.capital_based_status}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    def check_exit_conditions(self, position: Position, current_price: float) -> Optional[Dict]:
        """Check if position should be closed due to TP/SL conditions"""
        try:
            # Update metrics first
            self.update_position_metrics(position, current_price)
            
            exit_reason = None
            
            if position.is_profit_target_hit:
                exit_reason = "Take profit target reached"
            elif position.is_loss_limit_hit:
                exit_reason = "Stop loss limit reached"
            
            if exit_reason:
                pnl_amount = float(position.current_profit_loss_amount or 0)
                pnl_pct = (pnl_amount / float(position.capital_allocation)) * 100
                
                return {
                    'should_exit': True,
                    'reason': exit_reason,
                    'pnl_amount': pnl_amount,
                    'pnl_percentage': pnl_pct,
                    'exit_price': current_price,
                    'capital_allocation': float(position.capital_allocation),
                    'profit_target': float(position.profit_target_amount),
                    'loss_limit': float(position.loss_limit_amount)
                }
            
            return {'should_exit': False}
            
        except Exception as e:
            logger.error(f"Error checking exit conditions: {e}")
            return {'should_exit': False, 'error': str(e)}
    
    def get_positions_needing_monitoring(self, portfolio: Portfolio) -> List[Position]:
        """Get all open positions that need capital-based monitoring"""
        try:
            return Position.objects.filter(
                portfolio=portfolio,
                is_open=True,
                capital_allocation__isnull=False
            ).select_related('symbol')
            
        except Exception as e:
            logger.error(f"Error getting positions for monitoring: {e}")
            return []
    
    def calculate_portfolio_capital_metrics(self, portfolio: Portfolio) -> Dict:
        """Calculate portfolio-wide capital-based metrics"""
        try:
            positions = self.get_positions_needing_monitoring(portfolio)
            
            total_capital = sum(float(p.capital_allocation) for p in positions if p.capital_allocation)
            total_current_pnl = sum(float(p.current_profit_loss_amount or 0) for p in positions)
            
            metrics = {
                'total_positions': len(positions),
                'total_capital_allocated': total_capital,
                'total_current_pnl': total_current_pnl,
                'portfolio_pnl_percentage': (total_current_pnl / total_capital * 100) if total_capital > 0 else 0,
                'profit_target_hit_count': sum(1 for p in positions if p.is_profit_target_hit),
                'loss_limit_hit_count': sum(1 for p in positions if p.is_loss_limit_hit),
                'positions': []
            }
            
            # Add individual position details
            for position in positions:
                metrics['positions'].append({
                    'symbol': position.symbol.symbol,
                    'position_type': position.position_type,
                    'capital_allocation': float(position.capital_allocation),
                    'current_pnl': float(position.current_profit_loss_amount or 0),
                    'pnl_percentage': float(position.current_profit_loss_percentage or 0),
                    'status': position.capital_based_status,
                    'is_profit_target_hit': position.is_profit_target_hit,
                    'is_loss_limit_hit': position.is_loss_limit_hit
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating portfolio metrics: {e}")
            return {}
    
    def auto_close_positions(self, portfolio: Portfolio, current_prices: Dict[str, float]) -> Dict:
        """Automatically close positions that meet exit conditions"""
        try:
            positions = self.get_positions_needing_monitoring(portfolio)
            results = {
                'checked': len(positions),
                'closed': 0,
                'errors': 0,
                'details': []
            }
            
            for position in positions:
                symbol_key = position.symbol.symbol
                
                if symbol_key not in current_prices:
                    results['errors'] += 1
                    results['details'].append({
                        'position': position.symbol.symbol,
                        'action': 'skipped',
                        'reason': 'No current price available'
                    })
                    continue
                
                current_price = current_prices[symbol_key]
                
                # Check exit conditions
                exit_check = self.check_exit_conditions(position, current_price)
                
                if exit_check.get('should_exit'):
                    closed = self.close_position(position, current_price, exit_check['reason'])
                    
                    if closed:
                        results['closed'] += 1
                        results['details'].append({
                            'position': position.symbol.symbol,
                            'action': 'closed',
                            'reason': exit_check['reason'],
                            'pnl': exit_check.get('pnl_amount', 0),
                            'exit_price': current_price
                        })
                    else:
                        results['errors'] += 1
                        results['details'].append({
                            'position': position.symbol.symbol,
                            'action': 'failed_to_close',
                            'reason': 'Close operation failed'
                        })
                else:
                    results['details'].append({
                        'position': position.symbol.symbol,
                        'action': 'monitored',
                        'reason': 'No exit conditions met'
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in auto_close_positions: {e}")
            return {'error': str(e)}


# Utility functions for easy integration
def create_capital_based_position(portfolio_id: int, 
                                symbol_name: str, 
                                entry_price: float, 
                                signal_type: str,
                                capital_amount: float = 1000.0) -> Optional[int]:
    """Quick utility function to create a capital-based position"""
    try:
        from django.contrib.auth.models import User
        
        portfolio = Portfolio.objects.get(id=portfolio_id)
        symbol = Symbol.objects.get(symbol=symbol_name)
        
        manager = PositionManager()
        position = manager.create_capital_based_position(
            portfolio=portfolio,
            symbol=symbol,
            entry_price=entry_price,
            signal_type=signal_type,
            capital_amount=capital_amount
        )
        
        return position.id if position else None
        
    except Exception as e:
        logger.error(f"Error in create_capital_based_position utility: {e}")
        return None


def update_position_price(position_id: int, current_price: float) -> bool:
    """Update a position's metrics with current price"""
    try:
        position = Position.objects.get(id=position_id)
        manager = PositionManager()
        return manager.update_position_metrics(position, current_price)
        
    except Position.DoesNotExist:
        logger.error(f"Position {position_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error updating position {position_id}: {e}")
        return False
