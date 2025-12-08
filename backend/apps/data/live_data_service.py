"""
Live Data Service for Real-Time Market Data
Connects to crypto APIs and provides live price updates
"""

import asyncio
import aiohttp
import logging
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from apps.core.services import RealTimeBroadcaster
from apps.data.models import MarketData, DataSource
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class LiveDataService:
    """Service for fetching live market data from external APIs"""
    
    def __init__(self):
        self.broadcaster = RealTimeBroadcaster()
        self.session = None
        self.is_running = False
        
        # API endpoints
        self.binance_api = "https://api.binance.com/api/v3"
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        
        # Supported symbols for live data
        self.live_symbols = [
            'BTC', 'ETH', 'XRP', 'USDT', 'BNB', 'SOL', 'USDC', 
            'STETH', 'DOGE', 'TRX', 'ADA', 'WBTC', 'LINK', 'XLM'
        ]
    
    async def start(self):
        """Start the live data service"""
        if self.is_running:
            logger.warning("Live data service is already running")
            return
        
        self.is_running = True
        self.session = aiohttp.ClientSession()
        
        logger.info("Starting live data service...")
        
        try:
            # Start live data collection
            await self.collect_live_data()
        except Exception as e:
            logger.error(f"Error in live data service: {e}")
            self.is_running = False
        finally:
            if self.session:
                await self.session.close()
    
    async def stop(self):
        """Stop the live data service"""
        self.is_running = False
        if self.session:
            await self.session.close()
        logger.info("Live data service stopped")
    
    async def collect_live_data(self):
        """Collect live market data from APIs"""
        while self.is_running:
            try:
                # Fetch data from multiple sources
                await self.fetch_binance_data()
                await self.fetch_coingecko_data()
                
                # Wait before next update (5 seconds)
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error collecting live data: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def fetch_binance_data(self):
        """Fetch live data from Binance API"""
        try:
            # Get 24hr ticker for all symbols
            url = f"{self.binance_api}/ticker/24hr"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for ticker in data:
                        symbol = ticker['symbol']
                        
                        # Filter for supported symbols
                        if any(s in symbol for s in self.live_symbols):
                            # Extract base symbol (remove USDT, BTC, etc.)
                            base_symbol = self.extract_base_symbol(symbol)
                            
                            if base_symbol in self.live_symbols:
                                await self.process_binance_ticker(base_symbol, ticker)
                
        except Exception as e:
            logger.error(f"Error fetching Binance data: {e}")
    
    async def fetch_coingecko_data(self):
        """Fetch live data from CoinGecko API"""
        try:
            # Get current prices for supported coins
            coin_ids = self.get_coingecko_ids()
            url = f"{self.coingecko_api}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for coin_id, coin_data in data.items():
                        symbol = self.coingecko_id_to_symbol(coin_id)
                        if symbol in self.live_symbols:
                            await self.process_coingecko_data(symbol, coin_data)
                
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data: {e}")
    
    async def process_binance_ticker(self, symbol, ticker):
        """Process Binance ticker data and broadcast updates"""
        try:
            # Extract data
            price = Decimal(ticker['lastPrice'])
            change_24h = Decimal(ticker['priceChangePercent'])
            volume_24h = Decimal(ticker['volume'])
            
            # Calculate price change
            prev_price = price - (price * change_24h / 100)
            change = price - prev_price
            
            # Broadcast real-time update
            self.broadcaster.broadcast_market_update(
                symbol=symbol,
                price=float(price),
                change=float(change),
                volume=float(volume_24h),
                timestamp=timezone.now()
            )
            
            # Save to database
            await self.save_market_data(symbol, price, change, volume_24h)
            
        except Exception as e:
            logger.error(f"Error processing Binance ticker for {symbol}: {e}")
    
    async def process_coingecko_data(self, symbol, coin_data):
        """Process CoinGecko data and broadcast updates"""
        try:
            # Extract data
            price = Decimal(str(coin_data.get('usd', 0)))
            change_24h = Decimal(str(coin_data.get('usd_24h_change', 0)))
            volume_24h = Decimal(str(coin_data.get('usd_24h_vol', 0)))
            
            # Calculate price change
            change = price * (change_24h / 100)
            
            # Broadcast real-time update
            self.broadcaster.broadcast_market_update(
                symbol=symbol,
                price=float(price),
                change=float(change),
                volume=float(volume_24h),
                timestamp=timezone.now()
            )
            
            # Save to database
            await self.save_market_data(symbol, price, change, volume_24h)
            
        except Exception as e:
            logger.error(f"Error processing CoinGecko data for {symbol}: {e}")
    
    async def save_market_data(self, symbol, price, change, volume):
        """Save market data to database"""
        try:
            # Get or create symbol
            symbol_obj, created = await self.get_symbol(symbol)
            
            if symbol_obj:
                # Create market data record
                market_data = MarketData(
                    symbol=symbol_obj,
                    timestamp=timezone.now(),
                    open_price=price,
                    high_price=price,
                    low_price=price,
                    close_price=price,
                    volume=volume
                )
                market_data.save()
                
                logger.debug(f"Saved market data for {symbol}: ${price}")
                
        except Exception as e:
            logger.error(f"Error saving market data for {symbol}: {e}")
    
    @staticmethod
    def extract_base_symbol(symbol):
        """Extract base symbol from trading pair (e.g., BTCUSDT -> BTC)"""
        # Common quote currencies
        quote_currencies = ['USDT', 'BTC', 'ETH', 'BNB', 'USD']
        
        for quote in quote_currencies:
            if symbol.endswith(quote):
                return symbol[:-len(quote)]
        
        return symbol
    
    @staticmethod
    def get_coingecko_ids():
        """Get CoinGecko coin IDs for supported symbols"""
        # Map of symbols to CoinGecko IDs
        symbol_to_id = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'XRP': 'ripple',
            'USDT': 'tether',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'USDC': 'usd-coin',
            'DOGE': 'dogecoin',
            'TRX': 'tron',
            'ADA': 'cardano',
            'LINK': 'chainlink',
            'XLM': 'stellar'
        }
        
        return list(symbol_to_id.values())
    
    @staticmethod
    def coingecko_id_to_symbol(coin_id):
        """Convert CoinGecko coin ID to symbol"""
        id_to_symbol = {
            'bitcoin': 'BTC',
            'ethereum': 'ETH',
            'ripple': 'XRP',
            'tether': 'USDT',
            'binancecoin': 'BNB',
            'solana': 'SOL',
            'usd-coin': 'USDC',
            'dogecoin': 'DOGE',
            'tron': 'TRX',
            'cardano': 'ADA',
            'chainlink': 'LINK',
            'stellar': 'XLM'
        }
        
        return id_to_symbol.get(coin_id, coin_id.upper())
    
    @staticmethod
    async def get_symbol(symbol_name):
        """Get or create symbol object"""
        try:
            symbol_obj = Symbol.objects.get(symbol=symbol_name)
            return symbol_obj, False
        except Symbol.DoesNotExist:
            # Create new symbol
            symbol_obj = Symbol.objects.create(
                symbol=symbol_name,
                name=symbol_name,
                symbol_type='CRYPTO',
                exchange='Binance/CoinGecko',
                is_active=True
            )
            return symbol_obj, True
        except Exception as e:
            logger.error(f"Error getting symbol {symbol_name}: {e}")
            return None, False


# Global instance
live_data_service = LiveDataService()


def start_live_data_service():
    """Start the live data service (for management commands)"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(live_data_service.start())
    except Exception as e:
        logger.error(f"Error starting live data service: {e}")


def stop_live_data_service():
    """Stop the live data service"""
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(live_data_service.stop())
    except Exception as e:
        logger.error(f"Error stopping live data service: {e}")






