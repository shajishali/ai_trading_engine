from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Main analytics views
    path('', views.backtesting_view, name='dashboard'),  # Redirect root to backtesting
    path('backtesting/', views.backtesting_view, name='backtesting'),
    path('news/', views.news_analysis, name='news_analysis'),
    path('sentiment/', views.market_sentiment_view, name='market_sentiment'),
    
    # API endpoints
    path('api/market-data/', views.market_data_api, name='market_data_api'),
    path('api/sentiment/update/', views.update_sentiment_data, name='update_sentiment_data'),
    path('api/news/fetch/', views.fetch_news_now, name='fetch_news_now'),
]
