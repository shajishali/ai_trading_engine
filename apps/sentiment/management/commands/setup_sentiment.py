from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.sentiment.models import (
    SocialMediaSource, NewsSource, SocialMediaPost, NewsArticle,
    CryptoMention, SentimentAggregate, Influencer
)
from apps.trading.models import Symbol


class Command(BaseCommand):
    help = 'Set up sentiment analysis system with sample data sources and influencers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample-data',
            action='store_true',
            help='Create sample sentiment data for testing',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up sentiment analysis system...')
        )

        # Create social media sources
        self.create_social_media_sources()
        
        # Create news sources
        self.create_news_sources()
        
        # Create influencers
        self.create_influencers()
        
        # Create sample data if requested
        if options['create_sample_data']:
            self.create_sample_data()
        
        self.stdout.write(
            self.style.SUCCESS('Sentiment analysis system setup completed!')
        )

    def create_social_media_sources(self):
        """Create social media data sources"""
        sources = [
            {
                'name': 'Twitter API',
                'platform': 'twitter',
                'is_active': True
            },
            {
                'name': 'Reddit r/cryptocurrency',
                'platform': 'reddit',
                'is_active': True
            },
            {
                'name': 'Reddit r/bitcoin',
                'platform': 'reddit',
                'is_active': True
            },
            {
                'name': 'Reddit r/ethereum',
                'platform': 'reddit',
                'is_active': True
            },
            {
                'name': 'Telegram Crypto Channels',
                'platform': 'telegram',
                'is_active': True
            }
        ]
        
        for source_data in sources:
            source, created = SocialMediaSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            )
            if created:
                self.stdout.write(f'Created social media source: {source.name}')
            else:
                self.stdout.write(f'Social media source already exists: {source.name}')

    def create_news_sources(self):
        """Create news data sources"""
        sources = [
            {
                'name': 'CoinDesk',
                'url': 'https://www.coindesk.com',
                'is_active': True
            },
            {
                'name': 'CoinTelegraph',
                'url': 'https://cointelegraph.com',
                'is_active': True
            },
            {
                'name': 'CryptoNews',
                'url': 'https://cryptonews.com',
                'is_active': True
            },
            {
                'name': 'Bitcoin.com News',
                'url': 'https://news.bitcoin.com',
                'is_active': True
            },
            {
                'name': 'Decrypt',
                'url': 'https://decrypt.co',
                'is_active': True
            }
        ]
        
        for source_data in sources:
            source, created = NewsSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            )
            if created:
                self.stdout.write(f'Created news source: {source.name}')
            else:
                self.stdout.write(f'News source already exists: {source.name}')

    def create_influencers(self):
        """Create sample crypto influencers"""
        influencers = [
            {
                'platform': 'twitter',
                'username': 'VitalikButerin',
                'display_name': 'Vitalik Buterin',
                'followers_count': 4500000,
                'impact_score': 0.95,
                'is_verified': True,
                'is_active': True
            },
            {
                'platform': 'twitter',
                'username': 'cz_binance',
                'display_name': 'CZ 🔶 Binance',
                'followers_count': 8900000,
                'impact_score': 0.92,
                'is_verified': True,
                'is_active': True
            },
            {
                'platform': 'twitter',
                'username': 'SBF_FTX',
                'display_name': 'SBF',
                'followers_count': 1200000,
                'impact_score': 0.85,
                'is_verified': True,
                'is_active': True
            },
            {
                'platform': 'twitter',
                'username': 'michael_saylor',
                'display_name': 'Michael Saylor',
                'followers_count': 3200000,
                'impact_score': 0.88,
                'is_verified': True,
                'is_active': True
            },
            {
                'platform': 'twitter',
                'username': 'elonmusk',
                'display_name': 'Elon Musk',
                'followers_count': 150000000,
                'impact_score': 0.90,
                'is_verified': True,
                'is_active': True
            }
        ]
        
        for influencer_data in influencers:
            influencer, created = Influencer.objects.get_or_create(
                platform=influencer_data['platform'],
                username=influencer_data['username'],
                defaults=influencer_data
            )
            if created:
                self.stdout.write(f'Created influencer: {influencer.display_name}')
            else:
                self.stdout.write(f'Influencer already exists: {influencer.display_name}')

    def create_sample_data(self):
        """Create sample sentiment data for testing"""
        self.stdout.write('Creating sample sentiment data...')
        
        # Get crypto assets
        crypto_assets = Symbol.objects.filter(is_active=True)[:10]
        if not crypto_assets.exists():
            self.stdout.write(
                self.style.WARNING('No crypto assets found. Please run sync_crypto_data first.')
            )
            return
        
        # Get sources
        twitter_source = SocialMediaSource.objects.filter(platform='twitter').first()
        reddit_source = SocialMediaSource.objects.filter(platform='reddit').first()
        news_source = NewsSource.objects.first()
        
        if not twitter_source or not reddit_source or not news_source:
            self.stdout.write(
                self.style.WARNING('Required sources not found. Please run setup first.')
            )
            return
        
        # Create sample social media posts
        sample_posts = [
            {
                'content': 'Bitcoin is looking bullish! The technical indicators are showing strong support at current levels. #BTC #crypto',
                'sentiment_label': 'bullish',
                'sentiment_score': 0.8,
                'confidence_score': 0.85
            },
            {
                'content': 'Ethereum is showing bearish signals. The market sentiment is turning negative. #ETH #crypto',
                'sentiment_label': 'bearish',
                'sentiment_score': -0.6,
                'confidence_score': 0.75
            },
            {
                'content': 'Just bought more Bitcoin. HODL strong! 💎🙌 #BTC #hodl',
                'sentiment_label': 'bullish',
                'sentiment_score': 0.9,
                'confidence_score': 0.90
            },
            {
                'content': 'Market is looking neutral today. No clear direction yet. #crypto #trading',
                'sentiment_label': 'neutral',
                'sentiment_score': 0.0,
                'confidence_score': 0.60
            },
            {
                'content': 'Selling my crypto. This bear market is too much. #dump #crypto',
                'sentiment_label': 'bearish',
                'sentiment_score': -0.7,
                'confidence_score': 0.80
            }
        ]
        
        # Create social media posts
        for i, post_data in enumerate(sample_posts):
            post = SocialMediaPost.objects.create(
                source=twitter_source if i % 2 == 0 else reddit_source,
                platform='twitter' if i % 2 == 0 else 'reddit',
                post_id=f'sample_post_{i}',
                author=f'sample_user_{i}',
                content=post_data['content'],
                sentiment_score=post_data['sentiment_score'],
                sentiment_label=post_data['sentiment_label'],
                confidence_score=post_data['confidence_score'],
                created_at=timezone.now() - timedelta(hours=random.randint(1, 24))
            )
            
            # Create crypto mentions
            for asset in crypto_assets[:3]:  # Mention first 3 assets
                CryptoMention.objects.create(
                    asset=asset,
                    social_post=post,
                    mention_type='social',
                    sentiment_score=post_data['sentiment_score'],
                    sentiment_label=post_data['sentiment_label'],
                    confidence_score=post_data['confidence_score']
                )
        
        # Create sample news articles
        sample_articles = [
            {
                'title': 'Bitcoin Surges to New Highs as Institutional Adoption Grows',
                'content': 'Bitcoin has reached new all-time highs as major institutions continue to adopt cryptocurrency...',
                'sentiment_label': 'bullish',
                'sentiment_score': 0.8,
                'confidence_score': 0.85
            },
            {
                'title': 'Crypto Market Faces Regulatory Uncertainty',
                'content': 'The cryptocurrency market is experiencing volatility due to regulatory concerns...',
                'sentiment_label': 'bearish',
                'sentiment_score': -0.6,
                'confidence_score': 0.75
            },
            {
                'title': 'Ethereum 2.0 Development Progresses Smoothly',
                'content': 'The Ethereum 2.0 upgrade is progressing according to schedule...',
                'sentiment_label': 'bullish',
                'sentiment_score': 0.7,
                'confidence_score': 0.80
            }
        ]
        
        for i, article_data in enumerate(sample_articles):
            article = NewsArticle.objects.create(
                source=news_source,
                title=article_data['title'],
                content=article_data['content'],
                url=f'https://example.com/article_{i}',
                published_at=timezone.now() - timedelta(hours=random.randint(1, 48)),
                sentiment_score=article_data['sentiment_score'],
                sentiment_label=article_data['sentiment_label'],
                confidence_score=article_data['confidence_score']
            )
            
            # Create crypto mentions
            for asset in crypto_assets[:2]:  # Mention first 2 assets
                CryptoMention.objects.create(
                    asset=asset,
                    news_article=article,
                    mention_type='news',
                    sentiment_score=article_data['sentiment_score'],
                    sentiment_label=article_data['sentiment_label'],
                    confidence_score=article_data['confidence_score']
                )
        
        # Create sentiment aggregates
        for asset in crypto_assets:
            for timeframe in ['1h', '4h', '1d']:
                SentimentAggregate.objects.create(
                    asset=asset,
                    timeframe=timeframe,
                    social_sentiment_score=random.uniform(-0.5, 0.8),
                    news_sentiment_score=random.uniform(-0.3, 0.6),
                    combined_sentiment_score=random.uniform(-0.4, 0.7),
                    bullish_mentions=random.randint(5, 50),
                    bearish_mentions=random.randint(3, 30),
                    neutral_mentions=random.randint(2, 20),
                    total_mentions=random.randint(10, 100),
                    confidence_score=random.uniform(0.6, 0.9)
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {len(sample_posts)} sample posts and {len(sample_articles)} sample articles')
        )
