import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
import asyncio

logger = logging.getLogger(__name__)


class MarketDataConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time market data"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return
        
        # Join market data room
        await self.channel_layer.group_add(
            "market_data",
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Market data WebSocket connected for user: {self.user.username}")
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to real-time market data',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave market data room
        await self.channel_layer.group_discard(
            "market_data",
            self.channel_name
        )
        logger.info(f"Market data WebSocket disconnected for user: {self.user.username}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_symbol':
                # Subscribe to specific symbol updates
                symbol = data.get('symbol')
                await self.channel_layer.group_add(
                    f"market_data_{symbol}",
                    self.channel_name
                )
                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'symbol': symbol,
                    'message': f'Subscribed to {symbol} updates'
                }))
            
            elif message_type == 'unsubscribe_symbol':
                # Unsubscribe from specific symbol updates
                symbol = data.get('symbol')
                await self.channel_layer.group_discard(
                    f"market_data_{symbol}",
                    self.channel_name
                )
                await self.send(text_data=json.dumps({
                    'type': 'unsubscription_confirmed',
                    'symbol': symbol,
                    'message': f'Unsubscribed from {symbol} updates'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in market data consumer: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def market_update(self, event):
        """Send market data updates to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'market_update',
            'symbol': event['symbol'],
            'price': event['price'],
            'change': event['change'],
            'volume': event['volume'],
            'timestamp': event['timestamp']
        }))
    
    async def price_alert(self, event):
        """Send price alerts to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'price_alert',
            'symbol': event['symbol'],
            'alert_type': event['alert_type'],
            'price': event['price'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))


class TradingSignalsConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time trading signals"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return
        
        # Join trading signals room
        await self.channel_layer.group_add(
            "trading_signals",
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Trading signals WebSocket connected for user: {self.user.username}")
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to real-time trading signals',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave trading signals room
        await self.channel_layer.group_discard(
            "trading_signals",
            self.channel_name
        )
        logger.info(f"Trading signals WebSocket disconnected for user: {self.user.username}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'subscribe_signals':
                # Subscribe to all signal updates
                await self.send(text_data=json.dumps({
                    'type': 'subscription_confirmed',
                    'message': 'Subscribed to trading signals'
                }))
            
            elif message_type == 'filter_signals':
                # Filter signals by criteria
                symbol = data.get('symbol')
                signal_type = data.get('signal_type')
                
                if symbol:
                    await self.channel_layer.group_add(
                        f"signals_{symbol}",
                        self.channel_name
                    )
                
                await self.send(text_data=json.dumps({
                    'type': 'filter_applied',
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'message': 'Signal filter applied'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in trading signals consumer: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def new_signal(self, event):
        """Send new trading signal to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_signal',
            'signal_id': event['signal_id'],
            'symbol': event['symbol'],
            'signal_type': event['signal_type'],
            'strength': event['strength'],
            'confidence_score': event['confidence_score'],
            'entry_price': event['entry_price'],
            'target_price': event['target_price'],
            'stop_loss': event['stop_loss'],
            'timestamp': event['timestamp']
        }))
    
    async def signal_update(self, event):
        """Send signal updates to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'signal_update',
            'signal_id': event['signal_id'],
            'update_type': event['update_type'],
            'new_value': event['new_value'],
            'timestamp': event['timestamp']
        }))


class NotificationsConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return
        
        # Join user-specific notifications room
        await self.channel_layer.group_add(
            f"notifications_{self.user.id}",
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Notifications WebSocket connected for user: {self.user.username}")
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to real-time notifications',
            'timestamp': timezone.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave notifications room
        await self.channel_layer.group_discard(
            f"notifications_{self.user.id}",
            self.channel_name
        )
        logger.info(f"Notifications WebSocket disconnected for user: {self.user.username}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                # Mark notification as read
                notification_id = data.get('notification_id')
                # Here you would update the database
                await self.send(text_data=json.dumps({
                    'type': 'notification_marked_read',
                    'notification_id': notification_id,
                    'message': 'Notification marked as read'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error in notifications consumer: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))
    
    async def new_notification(self, event):
        """Send new notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification_id': event['notification_id'],
            'title': event['title'],
            'message': event['message'],
            'notification_type': event['notification_type'],
            'priority': event['priority'],
            'timestamp': event['timestamp']
        }))
    
    async def portfolio_update(self, event):
        """Send portfolio updates to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'portfolio_update',
            'total_value': event['total_value'],
            'daily_change': event['daily_change'],
            'daily_change_percent': event['daily_change_percent'],
            'timestamp': event['timestamp']
        }))











