from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from .models import DataSource, MarketData, TechnicalIndicator, DataFeed, DataSyncLog
from apps.trading.models import Symbol


class DataModelsTestCase(TestCase):
    def setUp(self):
        # Create test symbol
        self.symbol = Symbol.objects.create(
            symbol='BTC',
            name='Bitcoin',
            symbol_type='CRYPTO',
            exchange='CoinGecko'
        )
        
        # Create test data source
        self.data_source = DataSource.objects.create(
            name='CoinGecko',
            source_type='API',
            base_url='https://api.coingecko.com/api/v3',
            is_active=True
        )
        
        # Create test data feed
        self.data_feed = DataFeed.objects.create(
            name='BTC Price Feed',
            data_source=self.data_source,
            symbol=self.symbol,
            feed_type='REALTIME',
            is_active=True
        )

    def test_market_data_creation(self):
        """Test creating market data"""
        market_data = MarketData.objects.create(
            symbol=self.symbol,
            timestamp=timezone.now(),
            open_price=Decimal('50000.00'),
            high_price=Decimal('51000.00'),
            low_price=Decimal('49000.00'),
            close_price=Decimal('50500.00'),
            volume=Decimal('1000.00')
        )
        
        self.assertEqual(market_data.symbol.symbol, 'BTC')
        self.assertEqual(float(market_data.close_price), 50500.00)
        self.assertEqual(float(market_data.volume), 1000.00)

    def test_technical_indicator_creation(self):
        """Test creating technical indicators"""
        indicator = TechnicalIndicator.objects.create(
            symbol=self.symbol,
            indicator_type='RSI',
            period=14,
            value=Decimal('65.5'),
            timestamp=timezone.now()
        )
        
        self.assertEqual(indicator.indicator_type, 'RSI')
        self.assertEqual(indicator.period, 14)
        self.assertEqual(float(indicator.value), 65.5)

    def test_data_sync_log(self):
        """Test data sync logging"""
        sync_log = DataSyncLog.objects.create(
            sync_type='MARKET_DATA',
            symbol=self.symbol,
            status='COMPLETED',
            records_processed=100,
            records_added=50,
            records_updated=50
        )
        
        self.assertEqual(sync_log.sync_type, 'MARKET_DATA')
        self.assertEqual(sync_log.status, 'COMPLETED')
        self.assertEqual(sync_log.records_processed, 100)


class DataIntegrationTestCase(TestCase):
    def test_data_pipeline_integration(self):
        """Test the complete data pipeline integration"""
        # Create test data
        symbol = Symbol.objects.create(
            symbol='ETH',
            name='Ethereum',
            symbol_type='CRYPTO',
            exchange='CoinGecko'
        )
        
        source = DataSource.objects.create(
            name='Test API',
            source_type='API',
            is_active=True
        )
        
        # Test market data creation
        market_data = MarketData.objects.create(
            symbol=symbol,
            timestamp=timezone.now(),
            open_price=Decimal('3000.00'),
            high_price=Decimal('3100.00'),
            low_price=Decimal('2900.00'),
            close_price=Decimal('3050.00'),
            volume=Decimal('500.00')
        )
        
        # Test technical indicator creation
        indicator = TechnicalIndicator.objects.create(
            symbol=symbol,
            indicator_type='RSI',
            period=14,
            value=Decimal('70.5'),
            timestamp=timezone.now()
        )
        
        # Verify data relationships
        self.assertEqual(market_data.symbol, symbol)
        self.assertEqual(indicator.symbol, symbol)
        
        # Test data retrieval
        recent_data = MarketData.objects.filter(symbol=symbol).order_by('-timestamp')
        self.assertEqual(recent_data.count(), 1)
        
        recent_indicators = TechnicalIndicator.objects.filter(symbol=symbol).order_by('-timestamp')
        self.assertEqual(recent_indicators.count(), 1)
