from django.urls import path
from apps.sentiment import views

app_name = 'sentiment'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.sentiment_dashboard, name='dashboard'),
    
    # API endpoints
    path('api/sentiment/<str:asset_symbol>/', views.get_sentiment_data, name='sentiment_data'),
    path('api/sentiment-summary/', views.get_sentiment_summary, name='sentiment_summary'),
    path('api/influencers/', views.get_influencer_data, name='influencer_data'),
    path('api/trends/<str:asset_symbol>/', views.get_sentiment_trends, name='sentiment_trends'),
    path('api/health/', views.get_sentiment_health, name='sentiment_health'),
    
    # Manual triggers
    path('api/trigger/collect/', views.trigger_sentiment_collection, name='trigger_collection'),
    path('api/trigger/aggregate/', views.trigger_sentiment_aggregation, name='trigger_aggregation'),
]
