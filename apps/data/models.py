from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.trading.models import Symbol


class DataSource(models.Model):
    """Data sources for market data"""
    SOURCE_TYPES = [
        ('API', 'API'),
        ('WEBSOCKET', 'WebSocket'),
        ('FILE', 'File'),
        ('DATABASE', 'Database'),
    ]
    
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=10, choices=SOURCE_TYPES)
    base_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class MarketData(models.Model):
    """Market data OHLCV records"""
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    open_price = models.DecimalField(max_digits=15, decimal_places=6)
    high_price = models.DecimalField(max_digits=15, decimal_places=6)
    low_price = models.DecimalField(max_digits=15, decimal_places=6)
    close_price = models.DecimalField(max_digits=15, decimal_places=6)
    volume = models.DecimalField(max_digits=20, decimal_places=2)
    timeframe = models.CharField(max_length=10, default='1h')  # e.g., 1m,5m,15m,1h,4h,1d
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['symbol', 'timestamp', 'timeframe']
        indexes = [
            models.Index(fields=['symbol', 'timestamp', 'timeframe']),
        ]
    
    def __str__(self):
        return f"{self.symbol.symbol} - {self.timestamp}"


class HistoricalDataRange(models.Model):
    """Track historical data coverage per symbol/timeframe."""
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    timeframe = models.CharField(max_length=10)
    earliest_date = models.DateTimeField()
    latest_date = models.DateTimeField()
    total_records = models.IntegerField(default=0)
    is_complete = models.BooleanField(default=False)
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['symbol', 'timeframe']
        indexes = [
            models.Index(fields=['symbol', 'timeframe']),
            models.Index(fields=['latest_date']),
        ]

    def __str__(self):
        return f"{self.symbol.symbol} {self.timeframe} {self.earliest_date.date()}→{self.latest_date.date()}"


class DataQuality(models.Model):
    """Quality metrics for stored historical data windows."""
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    timeframe = models.CharField(max_length=10)
    date_range_start = models.DateTimeField()
    date_range_end = models.DateTimeField()
    total_expected_records = models.IntegerField()
    total_actual_records = models.IntegerField()
    missing_records = models.IntegerField()
    completeness_percentage = models.FloatField()
    has_gaps = models.BooleanField(default=False)
    has_anomalies = models.BooleanField(default=False)
    checked_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'timeframe']),
            models.Index(fields=['date_range_start', 'date_range_end']),
        ]

    def __str__(self):
        return f"Quality {self.symbol.symbol} {self.timeframe}: {self.completeness_percentage:.2f}%"


class DataFeed(models.Model):
    """Real-time data feeds"""
    FEED_TYPES = [
        ('REALTIME', 'Real-time'),
        ('HISTORICAL', 'Historical'),
        ('STREAMING', 'Streaming'),
    ]
    
    name = models.CharField(max_length=100)
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE)
    feed_type = models.CharField(max_length=10, choices=FEED_TYPES)
    is_active = models.BooleanField(default=True)
    last_update = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.symbol.symbol}"


class TechnicalIndicator(models.Model):
    """Technical indicators calculated from market data"""
    INDICATOR_TYPES = [
        ('SMA', 'Simple Moving Average'),
        ('EMA', 'Exponential Moving Average'),
        ('RSI', 'Relative Strength Index'),
        ('MACD', 'MACD'),
        ('BB', 'Bollinger Bands'),
        ('ATR', 'Average True Range'),
        ('STOCH', 'Stochastic'),
        ('CCI', 'Commodity Channel Index'),
    ]
    
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    indicator_type = models.CharField(max_length=10, choices=INDICATOR_TYPES)
    period = models.IntegerField()
    value = models.DecimalField(max_digits=15, decimal_places=6)
    timestamp = models.DateTimeField()
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['symbol', 'indicator_type', 'period', 'timestamp']
        indexes = [
            models.Index(fields=['symbol', 'indicator_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.symbol.symbol} {self.indicator_type}({self.period}) - {self.timestamp}"


class DataSyncLog(models.Model):
    """Log for data synchronization operations"""
    SYNC_TYPES = [
        ('MARKET_DATA', 'Market Data'),
        ('TECHNICAL_INDICATORS', 'Technical Indicators'),
        ('SIGNALS', 'Signals'),
    ]
    
    SYNC_STATUS = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=15, choices=SYNC_STATUS, default='PENDING')
    records_processed = models.IntegerField(default=0)
    records_added = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.sync_type} - {self.symbol.symbol if self.symbol else 'All'} - {self.status}"


class EconomicIndicator(models.Model):
    """Economic indicators that affect market sentiment"""
    INDICATOR_TYPES = [
        ('GDP', 'Gross Domestic Product'),
        ('INFLATION', 'Inflation Rate'),
        ('UNEMPLOYMENT', 'Unemployment Rate'),
        ('INTEREST_RATE', 'Interest Rate'),
        ('CPI', 'Consumer Price Index'),
        ('PPI', 'Producer Price Index'),
        ('RETAIL_SALES', 'Retail Sales'),
        ('HOUSING_STARTS', 'Housing Starts'),
        ('INDUSTRIAL_PRODUCTION', 'Industrial Production'),
        ('CONSUMER_CONFIDENCE', 'Consumer Confidence'),
    ]
    
    COUNTRIES = [
        ('US', 'United States'),
        ('EU', 'European Union'),
        ('CN', 'China'),
        ('JP', 'Japan'),
        ('GB', 'United Kingdom'),
        ('CA', 'Canada'),
        ('AU', 'Australia'),
        ('GLOBAL', 'Global'),
    ]
    
    indicator_type = models.CharField(max_length=25, choices=INDICATOR_TYPES)
    country = models.CharField(max_length=10, choices=COUNTRIES)
    value = models.DecimalField(max_digits=15, decimal_places=6)
    previous_value = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    expected_value = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=20, default='%')  # %, millions, index points
    timestamp = models.DateTimeField()
    release_date = models.DateTimeField()
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['indicator_type', 'country', 'timestamp']
        indexes = [
            models.Index(fields=['indicator_type', 'country', 'timestamp']),
            models.Index(fields=['release_date']),
        ]
    
    def __str__(self):
        return f"{self.country} {self.indicator_type}: {self.value}{self.unit}"
    
    @property
    def change_from_previous(self):
        """Calculate change from previous value"""
        if self.previous_value:
            return float(self.value) - float(self.previous_value)
        return None
    
    @property
    def surprise_factor(self):
        """Calculate surprise factor (actual vs expected)"""
        if self.expected_value:
            return float(self.value) - float(self.expected_value)
        return None


class MacroSentiment(models.Model):
    """Macro economic sentiment derived from economic indicators"""
    SENTIMENT_LEVELS = [
        ('VERY_BEARISH', 'Very Bearish'),
        ('BEARISH', 'Bearish'),
        ('NEUTRAL', 'Neutral'),
        ('BULLISH', 'Bullish'),
        ('VERY_BULLISH', 'Very Bullish'),
    ]
    
    country = models.CharField(max_length=10, choices=EconomicIndicator.COUNTRIES)
    sentiment_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Sentiment score from -1 (very bearish) to 1 (very bullish)"
    )
    sentiment_level = models.CharField(max_length=15, choices=SENTIMENT_LEVELS)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in sentiment analysis (0-1)"
    )
    
    # Contributing factors
    gdp_impact = models.FloatField(default=0.0)
    inflation_impact = models.FloatField(default=0.0)
    employment_impact = models.FloatField(default=0.0)
    monetary_policy_impact = models.FloatField(default=0.0)
    
    # Metadata
    calculation_timestamp = models.DateTimeField()
    data_period_start = models.DateTimeField()
    data_period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['country', 'calculation_timestamp']),
        ]
    
    def __str__(self):
        return f"{self.country} Macro Sentiment: {self.sentiment_level} ({self.sentiment_score:.2f})"


class EconomicEvent(models.Model):
    """Scheduled economic events and their market impact"""
    IMPACT_LEVELS = [
        ('LOW', 'Low Impact'),
        ('MEDIUM', 'Medium Impact'),
        ('HIGH', 'High Impact'),
        ('CRITICAL', 'Critical Impact'),
    ]
    
    EVENT_TYPES = [
        ('ANNOUNCEMENT', 'Economic Announcement'),
        ('POLICY_DECISION', 'Policy Decision'),
        ('REPORT_RELEASE', 'Report Release'),
        ('SPEECH', 'Central Bank Speech'),
        ('MEETING', 'Economic Meeting'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    country = models.CharField(max_length=10, choices=EconomicIndicator.COUNTRIES)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    impact_level = models.CharField(max_length=10, choices=IMPACT_LEVELS)
    
    # Event timing
    scheduled_date = models.DateTimeField()
    actual_date = models.DateTimeField(null=True, blank=True)
    
    # Market impact
    market_impact_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Expected market impact (-1 negative, 1 positive)"
    )
    volatility_impact = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Expected volatility increase (0-1)"
    )
    
    # Related data
    related_indicators = models.ManyToManyField(EconomicIndicator, blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['scheduled_date', 'impact_level']),
            models.Index(fields=['country', 'scheduled_date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.country}) - {self.impact_level}"


class Sector(models.Model):
    """Market sectors for classification and analysis"""
    SECTOR_TYPES = [
        ('TECHNOLOGY', 'Technology'),
        ('HEALTHCARE', 'Healthcare'),
        ('FINANCIALS', 'Financials'),
        ('ENERGY', 'Energy'),
        ('CONSUMER_DISCRETIONARY', 'Consumer Discretionary'),
        ('CONSUMER_STAPLES', 'Consumer Staples'),
        ('INDUSTRIALS', 'Industrials'),
        ('MATERIALS', 'Materials'),
        ('UTILITIES', 'Utilities'),
        ('REAL_ESTATE', 'Real Estate'),
        ('COMMUNICATION', 'Communication Services'),
        ('CRYPTO_DEFI', 'DeFi'),
        ('CRYPTO_LAYER1', 'Layer 1'),
        ('CRYPTO_LAYER2', 'Layer 2'),
        ('CRYPTO_GAMING', 'Gaming'),
        ('CRYPTO_MEME', 'Meme Coins'),
        ('CRYPTO_STABLECOIN', 'Stablecoins'),
    ]
    
    name = models.CharField(max_length=30, choices=SECTOR_TYPES, unique=True)
    display_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    market_cap_weight = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Sector weight in overall market (0-1)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.display_name


class SectorPerformance(models.Model):
    """Track sector performance metrics over time"""
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    
    # Performance metrics
    daily_return = models.FloatField(default=0.0)
    weekly_return = models.FloatField(default=0.0)
    monthly_return = models.FloatField(default=0.0)
    ytd_return = models.FloatField(default=0.0)
    
    # Volatility and momentum
    volatility = models.FloatField(
        validators=[MinValueValidator(0.0)],
        default=0.0,
        help_text="Annualized volatility"
    )
    momentum_score = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Momentum score (-1 to 1)"
    )
    
    # Relative performance
    relative_strength = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Relative strength vs market (-1 to 1)"
    )
    
    # Volume and activity
    volume_trend = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        default=0.0,
        help_text="Volume trend indicator (-1 to 1)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['sector', 'timestamp']
        indexes = [
            models.Index(fields=['sector', 'timestamp']),
            models.Index(fields=['timestamp', 'relative_strength']),
        ]
    
    def __str__(self):
        return f"{self.sector.display_name} - {self.timestamp.strftime('%Y-%m-%d')}"


class SectorRotation(models.Model):
    """Track sector rotation patterns and signals"""
    ROTATION_TYPES = [
        ('GROWTH_TO_VALUE', 'Growth to Value'),
        ('VALUE_TO_GROWTH', 'Value to Growth'),
        ('DEFENSIVE_TO_CYCLICAL', 'Defensive to Cyclical'),
        ('CYCLICAL_TO_DEFENSIVE', 'Cyclical to Defensive'),
        ('RISK_ON', 'Risk On'),
        ('RISK_OFF', 'Risk Off'),
    ]
    
    rotation_type = models.CharField(max_length=25, choices=ROTATION_TYPES)
    from_sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='rotations_out')
    to_sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='rotations_in')
    
    # Rotation metrics
    strength = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Rotation strength (0-1)"
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in rotation signal (0-1)"
    )
    duration_days = models.IntegerField(default=0)
    
    # Market context
    market_regime = models.CharField(max_length=20, blank=True)
    economic_driver = models.CharField(max_length=100, blank=True)
    
    detected_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['rotation_type', 'detected_at']),
            models.Index(fields=['from_sector', 'to_sector', 'detected_at']),
        ]
    
    def __str__(self):
        return f"{self.rotation_type}: {self.from_sector.display_name} → {self.to_sector.display_name}"


class SectorCorrelation(models.Model):
    """Track correlations between sectors"""
    TIMEFRAMES = [
        ('1D', '1 Day'),
        ('1W', '1 Week'),
        ('1M', '1 Month'),
        ('3M', '3 Months'),
        ('6M', '6 Months'),
        ('1Y', '1 Year'),
    ]
    
    sector_a = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='correlations_a')
    sector_b = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='correlations_b')
    timeframe = models.CharField(max_length=2, choices=TIMEFRAMES)
    
    correlation_coefficient = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Pearson correlation coefficient (-1 to 1)"
    )
    
    # Statistical significance
    p_value = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=1.0
    )
    sample_size = models.IntegerField(default=0)
    
    calculated_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['sector_a', 'sector_b', 'timeframe', 'calculated_at']
        indexes = [
            models.Index(fields=['sector_a', 'sector_b', 'timeframe']),
            models.Index(fields=['correlation_coefficient', 'calculated_at']),
        ]
    
    def __str__(self):
        return f"{self.sector_a.display_name} ↔ {self.sector_b.display_name} ({self.timeframe}): {self.correlation_coefficient:.3f}"
