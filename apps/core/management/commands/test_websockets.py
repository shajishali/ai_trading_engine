"""
Management command to test WebSocket connections and broadcasting
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.services import market_broadcaster, signals_broadcaster, notification_broadcaster
import time
import random


class Command(BaseCommand):
    help = 'Test WebSocket connections and broadcasting functionality'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['market', 'signals', 'notifications', 'all'],
            default='all',
            help='Type of test to run'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of test messages to send'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='Delay between messages in seconds'
        )
    
    def handle(self, *args, **options):
        test_type = options['type']
        count = options['count']
        delay = options['delay']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting WebSocket test: {test_type} messages')
        )
        
        if test_type in ['market', 'all']:
            self.test_market_broadcasting(count, delay)
        
        if test_type in ['signals', 'all']:
            self.test_signals_broadcasting(count, delay)
        
        if test_type in ['notifications', 'all']:
            self.test_notifications_broadcasting(count, delay)
        
        self.stdout.write(
            self.style.SUCCESS('WebSocket test completed successfully!')
        )
    
    def test_market_broadcasting(self, count, delay):
        """Test market data broadcasting"""
        self.stdout.write('Testing market data broadcasting...')
        
        symbols = ['BTC-USD', 'ETH-USD', 'AAPL', 'GOOGL', 'TSLA']
        
        for i in range(count):
            symbol = random.choice(symbols)
            price = round(random.uniform(100, 50000), 2)
            change = round(random.uniform(-10, 10), 2)
            volume = random.randint(1000, 1000000)
            
            try:
                market_broadcaster.broadcast_market_update(
                    symbol=symbol,
                    price=price,
                    change=change,
                    volume=volume
                )
                
                self.stdout.write(
                    f'  ✓ Market update sent: {symbol} @ ${price} ({change:+.2f}%)'
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Market update failed: {e}')
                )
            
            time.sleep(delay)
    
    def test_signals_broadcasting(self, count, delay):
        """Test trading signals broadcasting"""
        self.stdout.write('Testing trading signals broadcasting...')
        
        signal_types = ['BUY', 'SELL', 'HOLD']
        symbols = ['BTC-USD', 'ETH-USD', 'AAPL', 'GOOGL']
        
        for i in range(count):
            signal_type = random.choice(signal_types)
            symbol = random.choice(symbols)
            signal_id = f"test_signal_{int(timezone.now().timestamp())}_{i}"
            
            try:
                if signal_type == 'HOLD':
                    signals_broadcaster.broadcast_hold_signal(
                        signal_id=signal_id,
                        symbol=symbol,
                        reason="Market conditions unfavorable",
                        confidence_score=random.randint(60, 90)
                    )
                    
                    self.stdout.write(
                        f'  ✓ Hold signal sent: {symbol} - Market conditions unfavorable'
                    )
                    
                else:
                    entry_price = round(random.uniform(100, 50000), 2)
                    target_price = entry_price * (1 + random.uniform(0.05, 0.20))
                    stop_loss = entry_price * (1 - random.uniform(0.05, 0.15))
                    
                    signals_broadcaster.broadcast_trading_signal(
                        signal_id=signal_id,
                        symbol=symbol,
                        signal_type=signal_type,
                        strength='STRONG',
                        confidence_score=random.randint(70, 95),
                        entry_price=entry_price,
                        target_price=round(target_price, 2),
                        stop_loss=round(stop_loss, 2)
                    )
                    
                    self.stdout.write(
                        f'  ✓ {signal_type} signal sent: {symbol} @ ${entry_price}'
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Signal broadcast failed: {e}')
                )
            
            time.sleep(delay)
    
    def test_notifications_broadcasting(self, count, delay):
        """Test notifications broadcasting"""
        self.stdout.write('Testing notifications broadcasting...')
        
        notification_types = ['system', 'trade', 'risk', 'market']
        priorities = ['low', 'medium', 'high']
        
        for i in range(count):
            notification_type = random.choice(notification_types)
            priority = random.choice(priorities)
            user_id = random.randint(1, 10)  # Test with user IDs 1-10
            
            if notification_type == 'system':
                title = "System Maintenance"
                message = "Scheduled maintenance in 30 minutes"
                
            elif notification_type == 'trade':
                title = "Trade Executed"
                message = f"BUY 100 BTC-USD @ ${random.randint(40000, 50000)}"
                
            elif notification_type == 'risk':
                title = "Risk Alert"
                message = "Portfolio risk level increased to HIGH"
                
            else:  # market
                title = "Market Update"
                message = "Major market movement detected"
            
            try:
                notification_broadcaster.broadcast_notification(
                    user_id=user_id,
                    notification_id=f"test_notif_{int(timezone.now().timestamp())}_{i}",
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority
                )
                
                self.stdout.write(
                    f'  ✓ Notification sent to user {user_id}: {title}'
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Notification failed: {e}')
                )
            
            time.sleep(delay)









