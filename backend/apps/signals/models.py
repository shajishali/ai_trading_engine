from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.trading.models import Symbol
from apps.data.models import TechnicalIndicator
from apps.sentiment.models import SentimentAggregate


class SignalType(models.Model):
    """Types of trading signals"""
    SIGNAL_TYPES = [
        ('BUY', 'Buy Signal'),
        ('SELL', 'Sell Signal'),
        ('HOLD', 'Hold Signal'),
        ('STRONG_BUY', 'Strong Buy'),
        ('STRONG_SELL', 'Strong Sell'),
    ]
    
    name = models.CharField(max_length=20, choices=SIGNAL_TYPES, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#000000')  # Hex color
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class SignalFactor(models.Model):
    """Individual factors that contribute to signal generation"""
    FACTOR_TYPES = [
        ('TECHNICAL', 'Technical Indicator'),
        ('SENTIMENT', 'Sentiment Analysis'),
        ('NEWS', 'News Event'),
        ('VOLUME', 'Volume Analysis'),
        ('PATTERN', 'Chart Pattern'),
        ('CORRELATION', 'Correlation Analysis'),
        ('ECONOMIC', 'Economic/Fundamental Analysis'),
        ('SECTOR', 'Sector Analysis'),
    ]
    
    name = models.CharField(max_length=100)
    factor_type = models.CharField(max_length=20, choices=FACTOR_TYPES)
    weight = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        default=0.1,
        help_text="Weight of this factor in signal calculation (0-1)"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Signal Factor'
        verbose_name_plural = 'Signal Factors'
    
    def __str__(self):
        return f"{self.name} ({self.factor_type})"


class TradingSignal(models.Model):
    """Generated trading signals with quality metrics"""
    SIGNAL_STRENGTHS = [
        ('WEAK', 'Weak'),
        ('MODERATE', 'Moderate'),
        ('STRONG', 'Strong'),
        ('VERY_STRONG', 'Very Strong'),
    ]
    
    CONFIDENCE_LEVELS = [
        ('LOW', 'Low (<50%)'),
        ('MEDIUM', 'Medium (50-70%)'),
        ('HIGH', 'High (70-85%)'),
        ('VERY_HIGH', 'Very High (>85%)'),
    ]
    
    # Basic signal information
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    signal_type = models.ForeignKey(SignalType, on_delete=models.CASCADE)
    strength = models.CharField(max_length=20, choices=SIGNAL_STRENGTHS)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score (0-1)"
    )
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_LEVELS)
    
    # Signal details
    entry_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    target_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    stop_loss = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    risk_reward_ratio = models.FloatField(null=True, blank=True)
    
    # Timeframe and Entry Point Analysis
    TIMEFRAME_CHOICES = [
        ('1M', '1 Minute'),
        ('5M', '5 Minutes'),
        ('15M', '15 Minutes'),
        ('30M', '30 Minutes'),
        ('1H', '1 Hour'),
        ('4H', '4 Hours'),
        ('1D', '1 Day'),
        ('1W', '1 Week'),
        ('1M', '1 Month'),
    ]
    
    timeframe = models.CharField(
        max_length=10, 
        choices=TIMEFRAME_CHOICES, 
        null=True,
        blank=True,
        default='1H',
        help_text="Timeframe used for signal analysis"
    )
    
    entry_point_type = models.CharField(
        max_length=50,
        choices=[
            ('SUPPORT_BREAK', 'Support Break'),
            ('RESISTANCE_BREAK', 'Resistance Break'),
            ('SUPPORT_BOUNCE', 'Support Bounce'),
            ('RESISTANCE_REJECTION', 'Resistance Rejection'),
            ('BREAKOUT', 'Breakout'),
            ('BREAKDOWN', 'Breakdown'),
            ('MEAN_REVERSION', 'Mean Reversion'),
            ('TREND_FOLLOWING', 'Trend Following'),
            ('CONSOLIDATION_BREAK', 'Consolidation Break'),
            ('VOLUME_SPIKE', 'Volume Spike'),
            ('PATTERN_COMPLETION', 'Pattern Completion'),
            ('INDICATOR_CROSSOVER', 'Indicator Crossover'),
        ],
        null=True,
        blank=True,
        default='TREND_FOLLOWING',
        help_text="Type of entry point identified"
    )
    
    entry_point_details = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Detailed entry point analysis (levels, patterns, indicators)"
    )
    
    entry_zone_low = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Lower bound of entry zone"
    )
    
    entry_zone_high = models.DecimalField(
        max_digits=15, 
        decimal_places=6, 
        null=True, 
        blank=True,
        help_text="Upper bound of entry zone"
    )
    
    entry_confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        default=0.8,
        help_text="Confidence in entry point accuracy (0-1)"
    )
    
    # Quality metrics
    quality_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Overall signal quality score"
    )
    is_valid = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Contributing factors
    technical_score = models.FloatField(default=0.0)
    sentiment_score = models.FloatField(default=0.0)
    news_score = models.FloatField(default=0.0)
    volume_score = models.FloatField(default=0.0)
    pattern_score = models.FloatField(default=0.0)
    economic_score = models.FloatField(default=0.0)  # Economic/fundamental analysis score
    sector_score = models.FloatField(default=0.0)  # Sector analysis score
    
    # Performance tracking
    is_executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    is_profitable = models.BooleanField(null=True, blank=True)
    profit_loss = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    
    # Metadata
    is_hybrid = models.BooleanField(default=False, help_text="Is this a hybrid signal (spot + futures)?")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata")
    analyzed_at = models.DateTimeField(default=timezone.now, help_text='Time when signal was analyzed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    # Daily Best Signals Tracking
    is_best_of_day = models.BooleanField(
        default=False,
        help_text="Marked as one of the best signals of the day"
    )
    best_of_day_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when this signal was marked as best of day"
    )
    best_of_day_rank = models.IntegerField(
        null=True,
        blank=True,
        help_text="Rank of this signal among best signals of the day (1 = best)"
    )
    
    # Hourly slot: which calendar date and hour (0-23) this signal belongs to (UTC).
    # Enables "exactly 5 per hour" and "one coin per day" with DB enforcement.
    signal_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Calendar date (UTC) this signal was generated for"
    )
    signal_hour = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Hour of day (0-23 UTC) this signal was generated for"
    )
    
    class Meta:
        verbose_name = 'Trading Signal'
        verbose_name_plural = 'Trading Signals'
        indexes = [
            models.Index(fields=['symbol', 'created_at']),
            models.Index(fields=['signal_type', 'confidence_score']),
            models.Index(fields=['is_valid', 'expires_at']),
            models.Index(fields=['is_best_of_day', 'best_of_day_date']),
            models.Index(fields=['signal_date', 'signal_hour']),
        ]
        # One coin per day enforced in app logic (tasks.py); MySQL does not support partial unique constraints.
    
    def __str__(self):
        return f"{self.symbol.symbol} {self.signal_type.name} - {self.confidence_score:.2f}"
    
    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def time_to_expiry(self):
        if not self.expires_at:
            return None
        return self.expires_at - timezone.now()


class SignalFactorContribution(models.Model):
    """Individual factor contributions to a signal"""
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE, related_name='factor_contributions')
    factor = models.ForeignKey(SignalFactor, on_delete=models.CASCADE)
    score = models.FloatField(help_text="Factor score (-1 to 1)")
    weight = models.FloatField(help_text="Weight applied to this factor")
    contribution = models.FloatField(help_text="Weighted contribution to final signal")
    details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Signal Factor Contribution'
        verbose_name_plural = 'Signal Factor Contributions'
    
    def __str__(self):
        return f"{self.signal.symbol.symbol} - {self.factor.name}: {self.contribution:.3f}"


class MarketRegime(models.Model):
    """Market regime classification for adaptive strategies"""
    REGIME_TYPES = [
        ('BULL', 'Bull Market'),
        ('BEAR', 'Bear Market'),
        ('SIDEWAYS', 'Sideways Market'),
        ('VOLATILE', 'High Volatility'),
        ('LOW_VOL', 'Low Volatility'),
    ]
    
    name = models.CharField(max_length=20, choices=REGIME_TYPES)
    description = models.TextField(blank=True)
    volatility_level = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Market volatility level (0-1)"
    )
    trend_strength = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Trend strength (-1 to 1)"
    )
    confidence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Regime classification confidence"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Market Regime'
        verbose_name_plural = 'Market Regimes'
        indexes = [
            models.Index(fields=['name', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class SignalPerformance(models.Model):
    """Performance tracking for signal generation system"""
    PERIOD_TYPES = [
        ('1H', '1 Hour'),
        ('4H', '4 Hours'),
        ('1D', '1 Day'),
        ('1W', '1 Week'),
        ('1M', '1 Month'),
    ]
    
    period_type = models.CharField(max_length=3, choices=PERIOD_TYPES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Performance metrics
    total_signals = models.IntegerField(default=0)
    profitable_signals = models.IntegerField(default=0)
    win_rate = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Win rate (0-1)"
    )
    average_profit = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    average_loss = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    profit_factor = models.FloatField(default=0.0)
    max_drawdown = models.FloatField(default=0.0)
    
    # Signal quality metrics
    average_confidence = models.FloatField(default=0.0)
    average_quality_score = models.FloatField(default=0.0)
    signal_accuracy = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Signal Performance'
        verbose_name_plural = 'Signal Performances'
        indexes = [
            models.Index(fields=['period_type', 'start_date']),
        ]
    
    def __str__(self):
        return f"{self.period_type} Performance - {self.start_date.strftime('%Y-%m-%d')}"


class SignalAlert(models.Model):
    """Alerts and notifications for signal events"""
    ALERT_TYPES = [
        ('SIGNAL_GENERATED', 'Signal Generated'),
        ('SIGNAL_EXPIRED', 'Signal Expired'),
        ('SIGNAL_EXECUTED', 'Signal Executed'),
        ('PERFORMANCE_ALERT', 'Performance Alert'),
        ('SYSTEM_ALERT', 'System Alert'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    title = models.CharField(max_length=200)
    message = models.TextField()
    signal = models.ForeignKey(TradingSignal, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Signal Alert'
        verbose_name_plural = 'Signal Alerts'
        indexes = [
            models.Index(fields=['alert_type', 'created_at']),
            models.Index(fields=['priority', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.alert_type} - {self.title}"


class SpotPortfolio(models.Model):
    """Spot trading portfolio for long-term investment strategies"""
    PORTFOLIO_TYPES = [
        ('ACCUMULATION', 'Accumulation Portfolio'),
        ('DCA', 'Dollar Cost Average Portfolio'),
        ('BALANCED', 'Balanced Portfolio'),
        ('GROWTH', 'Growth Portfolio'),
        ('CONSERVATIVE', 'Conservative Portfolio'),
    ]
    
    REBALANCE_FREQUENCIES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('SEMI_ANNUALLY', 'Semi-Annually'),
        ('ANNUALLY', 'Annually'),
    ]
    
    name = models.CharField(max_length=100)
    portfolio_type = models.CharField(max_length=20, choices=PORTFOLIO_TYPES)
    description = models.TextField(blank=True)
    total_value_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    target_allocation = models.JSONField(default=dict, help_text="Target allocation per symbol")
    rebalance_frequency = models.CharField(max_length=20, choices=REBALANCE_FREQUENCIES, default='QUARTERLY')
    
    # Performance metrics
    total_return_percentage = models.FloatField(default=0)
    annualized_return = models.FloatField(default=0)
    max_drawdown = models.FloatField(default=0)
    sharpe_ratio = models.FloatField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Spot Portfolio'
        verbose_name_plural = 'Spot Portfolios'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.portfolio_type})"


class TradingType(models.Model):
    """Types of trading strategies"""
    TRADING_TYPES = [
        ('FUTURES', 'Futures Trading'),
        ('SPOT', 'Spot Trading'),
        ('MARGIN', 'Margin Trading'),
        ('STAKING', 'Staking'),
    ]
    
    name = models.CharField(max_length=20, choices=TRADING_TYPES, unique=True)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    
    class Meta:
        verbose_name = 'Trading Type'
        verbose_name_plural = 'Trading Types'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class SpotTradingSignal(models.Model):
    """Spot trading signals for long-term investment strategies"""
    SIGNAL_CATEGORIES = [
        ('ACCUMULATION', 'Accumulation Phase'),
        ('DISTRIBUTION', 'Distribution Phase'),
        ('HOLD', 'Hold Position'),
        ('DCA', 'Dollar Cost Average'),
        ('REBALANCE', 'Portfolio Rebalance'),
    ]
    
    INVESTMENT_HORIZONS = [
        ('SHORT_TERM', '6-12 months'),
        ('MEDIUM_TERM', '1-2 years'),
        ('LONG_TERM', '2-5 years'),
        ('VERY_LONG_TERM', '5+ years'),
    ]
    
    DCA_FREQUENCIES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
    ]
    
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    signal_category = models.CharField(max_length=20, choices=SIGNAL_CATEGORIES)
    investment_horizon = models.CharField(max_length=20, choices=INVESTMENT_HORIZONS)
    
    # Analysis scores (0-1)
    fundamental_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Fundamental analysis score (0-1)"
    )
    technical_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Technical analysis score (0-1)"
    )
    sentiment_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Market sentiment score (0-1)"
    )
    
    # Portfolio allocation
    recommended_allocation = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Recommended portfolio allocation (0-1)"
    )
    
    # DCA settings
    dca_frequency = models.CharField(max_length=20, choices=DCA_FREQUENCIES, default='MONTHLY')
    dca_amount_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Target prices
    target_price_6m = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    target_price_1y = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    target_price_2y = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    
    # Risk management
    max_position_size = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Maximum position size as % of portfolio"
    )
    stop_loss_percentage = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Stop loss as % of entry price"
    )
    
    # Additional data
    analysis_metadata = models.JSONField(default=dict, blank=True)
    fundamental_factors = models.JSONField(default=list, blank=True)
    technical_factors = models.JSONField(default=list, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    analyzed_at = models.DateTimeField(default=timezone.now, help_text='Time when signal was analyzed')
    
    class Meta:
        verbose_name = 'Spot Trading Signal'
        verbose_name_plural = 'Spot Trading Signals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['symbol', 'is_active']),
            models.Index(fields=['signal_category', 'investment_horizon']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.symbol.symbol} - {self.signal_category} ({self.investment_horizon})"


class SpotSignalHistory(models.Model):
    """Historical record of spot trading signals for performance tracking"""
    original_signal = models.ForeignKey(SpotTradingSignal, on_delete=models.CASCADE)
    symbol_name = models.CharField(max_length=20)
    signal_category = models.CharField(max_length=20)
    investment_horizon = models.CharField(max_length=20)
    
    # Scores
    fundamental_score = models.FloatField()
    technical_score = models.FloatField()
    sentiment_score = models.FloatField()
    recommended_allocation = models.FloatField()
    dca_frequency = models.CharField(max_length=20)
    
    # Target prices
    target_price_6m = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    target_price_1y = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    target_price_2y = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    
    # Performance tracking
    entry_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    exit_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    performance_percentage = models.FloatField(null=True, blank=True)
    is_profitable = models.BooleanField(null=True, blank=True)
    
    created_at = models.DateTimeField()
    archived_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Spot Signal History'
        verbose_name_plural = 'Spot Signal Histories'
        ordering = ['-archived_at']
    
    def __str__(self):
        return f"{self.symbol_name} - {self.signal_category} (Archived)"


class SpotPosition(models.Model):
    """Spot trading positions within portfolios"""
    portfolio = models.ForeignKey(SpotPortfolio, on_delete=models.CASCADE, related_name='positions')
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    
    # Position details
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    average_price = models.DecimalField(max_digits=15, decimal_places=6)
    current_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    
    # Value calculations
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)
    current_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    unrealized_pnl = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    unrealized_pnl_percentage = models.FloatField(null=True, blank=True)
    
    # Portfolio allocation
    portfolio_allocation = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Position allocation as % of portfolio"
    )
    
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Spot Position'
        verbose_name_plural = 'Spot Positions'
        ordering = ['-portfolio_allocation']
        unique_together = [['portfolio', 'symbol']]
    
    def __str__(self):
        return f"{self.portfolio.name} - {self.symbol.symbol}"
