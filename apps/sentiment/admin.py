from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from apps.sentiment.models import (
    SocialMediaSource, NewsSource, SocialMediaPost, NewsArticle,
    CryptoMention, SentimentAggregate, Influencer, SentimentModel
)


@admin.register(SocialMediaSource)
class SocialMediaSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SocialMediaPost)
class SocialMediaPostAdmin(admin.ModelAdmin):
    list_display = [
        'platform', 'author', 'sentiment_label', 'confidence_score',
        'created_at', 'processed_at'
    ]
    list_filter = ['platform', 'sentiment_label', 'created_at']
    search_fields = ['author', 'content']
    readonly_fields = ['processed_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('source')
    
    def sentiment_color(self, obj):
        colors = {
            'bullish': 'green',
            'bearish': 'red',
            'neutral': 'gray'
        }
        color = colors.get(obj.sentiment_label, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.sentiment_label
        )
    sentiment_color.short_description = 'Sentiment'


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'source', 'sentiment_label', 'confidence_score',
        'published_at', 'processed_at'
    ]
    list_filter = ['sentiment_label', 'published_at', 'source']
    search_fields = ['title', 'content']
    readonly_fields = ['processed_at']
    date_hierarchy = 'published_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('source')


@admin.register(CryptoMention)
class CryptoMentionAdmin(admin.ModelAdmin):
    list_display = [
        'asset', 'mention_type', 'sentiment_label', 'confidence_score',
        'impact_weight', 'created_at'
    ]
    list_filter = ['mention_type', 'sentiment_label', 'created_at', 'asset']
    search_fields = ['asset__symbol', 'asset__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('asset', 'social_post', 'news_article')


@admin.register(SentimentAggregate)
class SentimentAggregateAdmin(admin.ModelAdmin):
    list_display = [
        'asset', 'timeframe', 'combined_sentiment_score',
        'total_mentions', 'confidence_score', 'created_at'
    ]
    list_filter = ['timeframe', 'created_at', 'asset']
    search_fields = ['asset__symbol', 'asset__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('asset')
    
    def sentiment_score_color(self, obj):
        if obj.combined_sentiment_score > 0.1:
            color = 'green'
        elif obj.combined_sentiment_score < -0.1:
            color = 'red'
        else:
            color = 'gray'
        
        return format_html(
            '<span style="color: {};">{:.3f}</span>',
            color,
            obj.combined_sentiment_score
        )
    sentiment_score_color.short_description = 'Sentiment Score'


@admin.register(Influencer)
class InfluencerAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'username', 'platform', 'followers_count',
        'impact_score', 'is_verified', 'is_active'
    ]
    list_filter = ['platform', 'is_verified', 'is_active']
    search_fields = ['display_name', 'username']
    readonly_fields = ['created_at', 'updated_at']
    
    def impact_score_color(self, obj):
        if obj.impact_score > 0.7:
            color = 'green'
        elif obj.impact_score > 0.3:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.3f}</span>',
            color,
            obj.impact_score
        )
    impact_score_color.short_description = 'Impact Score'


@admin.register(SentimentModel)
class SentimentModelAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'model_type', 'version', 'accuracy_score',
        'f1_score', 'is_active', 'created_at'
    ]
    list_filter = ['model_type', 'is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    def accuracy_color(self, obj):
        if obj.accuracy_score > 0.8:
            color = 'green'
        elif obj.accuracy_score > 0.6:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.3f}</span>',
            color,
            obj.accuracy_score
        )
    accuracy_color.short_description = 'Accuracy'


# Custom admin site configuration
admin.site.site_header = "AI Trading Signal Engine - Sentiment Analysis"
admin.site.site_title = "Sentiment Analysis Admin"
admin.site.index_title = "Sentiment Analysis Dashboard"
