from django.db import models
from django.utils import timezone
from apps.trading.models import Symbol


class SocialMediaSource(models.Model):
    """Sources for social media data collection"""
    name = models.CharField(max_length=100, unique=True)
    platform = models.CharField(max_length=50)  # twitter, reddit, telegram, discord
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Social Media Source'
        verbose_name_plural = 'Social Media Sources'

    def __str__(self):
        return f"{self.name} ({self.platform})"


class NewsSource(models.Model):
    """Sources for news data collection"""
    name = models.CharField(max_length=100, unique=True)
    url = models.URLField()
    api_key = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'News Source'
        verbose_name_plural = 'News Sources'

    def __str__(self):
        return self.name


class SocialMediaPost(models.Model):
    """Stores social media posts for sentiment analysis"""
    source = models.ForeignKey(SocialMediaSource, on_delete=models.CASCADE)
    platform = models.CharField(max_length=50)
    post_id = models.CharField(max_length=255, unique=True)
    author = models.CharField(max_length=255)
    content = models.TextField()
    language = models.CharField(max_length=10, default='en')
    followers_count = models.IntegerField(default=0)
    engagement_score = models.FloatField(default=0.0)
    sentiment_score = models.FloatField(null=True, blank=True)
    sentiment_label = models.CharField(max_length=20, blank=True)  # bullish, bearish, neutral
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Social Media Post'
        verbose_name_plural = 'Social Media Posts'
        indexes = [
            models.Index(fields=['platform', 'created_at']),
            models.Index(fields=['sentiment_label', 'created_at']),
        ]

    def __str__(self):
        return f"{self.platform}: {self.author} - {self.content[:50]}..."


class NewsArticle(models.Model):
    """Stores news articles for sentiment analysis"""
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE)
    title = models.CharField(max_length=500)
    content = models.TextField()
    url = models.URLField()
    published_at = models.DateTimeField()
    language = models.CharField(max_length=10, default='en')
    sentiment_score = models.FloatField(null=True, blank=True)
    sentiment_label = models.CharField(max_length=20, blank=True)
    confidence_score = models.FloatField(default=0.0)
    impact_score = models.FloatField(default=0.0)  # Impact on crypto markets
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'News Article'
        verbose_name_plural = 'News Articles'
        indexes = [
            models.Index(fields=['published_at']),
            models.Index(fields=['sentiment_label', 'published_at']),
        ]

    def __str__(self):
        return f"{self.source.name}: {self.title[:50]}..."


class CryptoMention(models.Model):
    """Tracks mentions of crypto assets in social media and news"""
    asset = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    social_post = models.ForeignKey(SocialMediaPost, on_delete=models.CASCADE, null=True, blank=True)
    news_article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, null=True, blank=True)
    mention_type = models.CharField(max_length=20)  # social, news
    sentiment_score = models.FloatField()
    sentiment_label = models.CharField(max_length=20)
    confidence_score = models.FloatField(default=0.0)
    impact_weight = models.FloatField(default=1.0)  # Weight based on source credibility
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Crypto Mention'
        verbose_name_plural = 'Crypto Mentions'
        indexes = [
            models.Index(fields=['asset', 'mention_type', 'created_at']),
            models.Index(fields=['sentiment_label', 'created_at']),
        ]

    def __str__(self):
        return f"{self.asset.symbol}: {self.sentiment_label} ({self.confidence_score:.2f})"


class SentimentAggregate(models.Model):
    """Aggregated sentiment scores for crypto assets"""
    asset = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    timeframe = models.CharField(max_length=20)  # 1h, 4h, 1d, 1w
    social_sentiment_score = models.FloatField()
    news_sentiment_score = models.FloatField()
    combined_sentiment_score = models.FloatField()
    bullish_mentions = models.IntegerField(default=0)
    bearish_mentions = models.IntegerField(default=0)
    neutral_mentions = models.IntegerField(default=0)
    total_mentions = models.IntegerField(default=0)
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sentiment Aggregate'
        verbose_name_plural = 'Sentiment Aggregates'
        unique_together = ['asset', 'timeframe', 'created_at']
        indexes = [
            models.Index(fields=['asset', 'timeframe', 'created_at']),
        ]

    def __str__(self):
        return f"{self.asset.symbol} {self.timeframe}: {self.combined_sentiment_score:.3f}"


class Influencer(models.Model):
    """Tracks crypto influencers and their impact"""
    platform = models.CharField(max_length=50)
    username = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    followers_count = models.BigIntegerField(default=0)
    engagement_rate = models.FloatField(default=0.0)
    impact_score = models.FloatField(default=0.0)  # Impact on crypto markets
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Influencer'
        verbose_name_plural = 'Influencers'
        unique_together = ['platform', 'username']
        indexes = [
            models.Index(fields=['platform', 'impact_score']),
        ]

    def __str__(self):
        return f"{self.display_name} (@{self.username}) - {self.platform}"


class SentimentModel(models.Model):
    """Stores trained sentiment analysis models"""
    name = models.CharField(max_length=100, unique=True)
    model_type = models.CharField(max_length=50)  # bert, finbert, custom
    version = models.CharField(max_length=20)
    file_path = models.CharField(max_length=500)
    accuracy_score = models.FloatField()
    precision_score = models.FloatField()
    recall_score = models.FloatField()
    f1_score = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sentiment Model'
        verbose_name_plural = 'Sentiment Models'

    def __str__(self):
        return f"{self.name} v{self.version} ({self.model_type})"
