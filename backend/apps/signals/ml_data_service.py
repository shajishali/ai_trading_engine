"""
Phase 3 ML Data Collection and Feature Engineering Service
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import talib
from django.utils import timezone
from django.db.models import Q

from apps.signals.models import MLFeature, MLModel, MLPrediction
from apps.data.models import MarketData, TechnicalIndicator
from apps.trading.models import Symbol
from apps.sentiment.models import SentimentAggregate
from apps.analytics.models import SentimentData as AnalyticsSentimentData

logger = logging.getLogger(__name__)


class MLDataCollectionService:
    """Service for collecting and preparing ML training data"""
    
    def __init__(self):
        self.logger = logger
        self.feature_cache = {}
    
    def collect_training_data(self, symbols: List[Symbol], start_date: datetime, 
                           end_date: datetime, prediction_horizon_hours: int = 24) -> pd.DataFrame:
        """
        Collect comprehensive training data for ML models
        
        Args:
            symbols: List of symbols to collect data for
            start_date: Start date for data collection
            end_date: End date for data collection
            prediction_horizon_hours: Hours ahead to predict
            
        Returns:
            DataFrame with features and labels
        """
        try:
            self.logger.info(f"Collecting ML training data for {len(symbols)} symbols")
            
            all_data = []
            
            for symbol in symbols:
                self.logger.info(f"Processing {symbol.symbol}")
                
                # Get market data
                market_data = self._get_market_data(symbol, start_date, end_date)
                if market_data.empty:
                    self.logger.warning(f"No market data for {symbol.symbol}")
                    continue
                
                # Get technical indicators
                technical_data = self._get_technical_indicators(symbol, start_date, end_date)
                
                # Get sentiment data
                sentiment_data = self._get_sentiment_data(symbol, start_date, end_date)
                
                # Combine all data
                symbol_data = self._combine_data_sources(market_data, technical_data, sentiment_data)
                
                # Add symbol identifier
                symbol_data['symbol'] = symbol.symbol
                symbol_data['symbol_id'] = symbol.id
                
                # Generate features
                symbol_data = self._generate_features(symbol_data)
                
                # Generate labels
                symbol_data = self._generate_labels(symbol_data, prediction_horizon_hours)
                
                all_data.append(symbol_data)
            
            if not all_data:
                self.logger.error("No data collected for any symbols")
                return pd.DataFrame()
            
            # Combine all symbol data
            combined_data = pd.concat(all_data, ignore_index=True)
            
            # Clean and validate data
            combined_data = self._clean_data(combined_data)
            
            self.logger.info(f"Collected {len(combined_data)} training samples")
            return combined_data
            
        except Exception as e:
            self.logger.error(f"Error collecting training data: {e}")
            return pd.DataFrame()
    
    def _get_market_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get market data for a symbol"""
        try:
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not market_data.exists():
                return pd.DataFrame()
            
            data = []
            for record in market_data:
                data.append({
                    'timestamp': record.timestamp,
                    'open': float(record.open_price),
                    'high': float(record.high_price),
                    'low': float(record.low_price),
                    'close': float(record.close_price),
                    'volume': float(record.volume)
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol.symbol}: {e}")
            return pd.DataFrame()
    
    def _get_technical_indicators(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get technical indicators for a symbol"""
        try:
            indicators = TechnicalIndicator.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if not indicators.exists():
                return pd.DataFrame()
            
            data = []
            for indicator in indicators:
                data.append({
                    'timestamp': indicator.timestamp,
                    'indicator_name': indicator.name,
                    'indicator_value': float(indicator.value)
                })
            
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame()
            
            # Pivot to get indicators as columns
            df_pivot = df.pivot(index='timestamp', columns='indicator_name', values='indicator_value')
            return df_pivot
            
        except Exception as e:
            self.logger.error(f"Error getting technical indicators for {symbol.symbol}: {e}")
            return pd.DataFrame()
    
    def _get_sentiment_data(self, symbol: Symbol, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get sentiment data for a symbol"""
        try:
            # Try both sentiment models
            sentiment_data = []
            
            # From sentiment app
            try:
                sentiments = SentimentAggregate.objects.filter(
                    symbol=symbol,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date
                ).order_by('timestamp')
                
                for sentiment in sentiments:
                    sentiment_data.append({
                        'timestamp': sentiment.timestamp,
                        'compound_score': sentiment.compound_score,
                        'positive_score': sentiment.positive_score,
                        'negative_score': sentiment.negative_score,
                        'neutral_score': sentiment.neutral_score
                    })
            except Exception:
                pass
            
            # From analytics app
            try:
                analytics_sentiments = AnalyticsSentimentData.objects.filter(
                    symbol=symbol.symbol,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date
                ).order_by('timestamp')
                
                for sentiment in analytics_sentiments:
                    sentiment_data.append({
                        'timestamp': sentiment.timestamp,
                        'compound_score': sentiment.compound_score,
                        'positive_score': sentiment.positive_score,
                        'negative_score': sentiment.negative_score,
                        'neutral_score': sentiment.neutral_score
                    })
            except Exception:
                pass
            
            if not sentiment_data:
                return pd.DataFrame()
            
            df = pd.DataFrame(sentiment_data)
            df.set_index('timestamp', inplace=True)
            
            # Resample to daily and forward fill
            df = df.resample('D').mean().fillna(method='ffill')
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment data for {symbol.symbol}: {e}")
            return pd.DataFrame()
    
    def _combine_data_sources(self, market_data: pd.DataFrame, technical_data: pd.DataFrame, 
                            sentiment_data: pd.DataFrame) -> pd.DataFrame:
        """Combine all data sources"""
        try:
            # Start with market data
            combined = market_data.copy()
            
            # Add technical indicators
            if not technical_data.empty:
                combined = combined.join(technical_data, how='left')
            
            # Add sentiment data
            if not sentiment_data.empty:
                combined = combined.join(sentiment_data, how='left')
            
            # Forward fill missing values
            combined = combined.fillna(method='ffill')
            
            return combined
            
        except Exception as e:
            self.logger.error(f"Error combining data sources: {e}")
            return market_data
    
    def _generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate ML features from raw data"""
        try:
            df = data.copy()
            
            # Price-based features
            df = self._add_price_features(df)
            
            # Technical indicator features
            df = self._add_technical_features(df)
            
            # Volume features
            df = self._add_volume_features(df)
            
            # Time-based features
            df = self._add_time_features(df)
            
            # Sentiment features
            df = self._add_sentiment_features(df)
            
            # Lagged features
            df = self._add_lagged_features(df)
            
            # Rolling window features
            df = self._add_rolling_features(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error generating features: {e}")
            return data
    
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price-based features"""
        try:
            # Price changes
            df['price_change'] = df['close'].pct_change()
            df['price_change_abs'] = df['price_change'].abs()
            
            # High-Low features
            df['hl_ratio'] = df['high'] / df['low']
            df['oc_ratio'] = df['open'] / df['close']
            
            # Price position within day range
            df['price_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
            
            # Price momentum
            df['momentum_5'] = df['close'].pct_change(5)
            df['momentum_10'] = df['close'].pct_change(10)
            df['momentum_20'] = df['close'].pct_change(20)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding price features: {e}")
            return df
    
    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicator features"""
        try:
            # Moving averages
            df['sma_5'] = df['close'].rolling(5).mean()
            df['sma_10'] = df['close'].rolling(10).mean()
            df['sma_20'] = df['close'].rolling(20).mean()
            df['sma_50'] = df['close'].rolling(50).mean()
            
            # Exponential moving averages
            df['ema_5'] = df['close'].ewm(span=5).mean()
            df['ema_10'] = df['close'].ewm(span=10).mean()
            df['ema_20'] = df['close'].ewm(span=20).mean()
            
            # Bollinger Bands
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(df['close'], timeperiod=20)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            
            # Stochastic
            df['stoch_k'], df['stoch_d'] = talib.STOCH(df['high'], df['low'], df['close'])
            
            # Williams %R
            df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'])
            
            # ATR
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding technical features: {e}")
            return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features"""
        try:
            # Volume changes
            df['volume_change'] = df['volume'].pct_change()
            df['volume_sma_10'] = df['volume'].rolling(10).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma_10']
            
            # Price-Volume features
            df['price_volume'] = df['close'] * df['volume']
            df['vwap'] = df['price_volume'].rolling(20).sum() / df['volume'].rolling(20).sum()
            
            # Volume momentum
            df['volume_momentum'] = df['volume'].pct_change(5)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding volume features: {e}")
            return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features"""
        try:
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['day_of_month'] = df.index.day
            df['month'] = df.index.month
            df['quarter'] = df.index.quarter
            
            # Cyclical encoding
            df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
            df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
            df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
            df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding time features: {e}")
            return df
    
    def _add_sentiment_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add sentiment-based features"""
        try:
            if 'compound_score' in df.columns:
                # Sentiment momentum
                df['sentiment_momentum'] = df['compound_score'].pct_change(5)
                
                # Sentiment volatility
                df['sentiment_volatility'] = df['compound_score'].rolling(10).std()
                
                # Sentiment extremes
                df['sentiment_extreme'] = (df['compound_score'].abs() > 0.5).astype(int)
                
                # Sentiment trend
                df['sentiment_trend'] = df['compound_score'].rolling(5).mean()
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding sentiment features: {e}")
            return df
    
    def _add_lagged_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lagged features"""
        try:
            # Lagged price features
            for lag in [1, 2, 3, 5, 10]:
                df[f'close_lag_{lag}'] = df['close'].shift(lag)
                df[f'volume_lag_{lag}'] = df['volume'].shift(lag)
                if 'compound_score' in df.columns:
                    df[f'sentiment_lag_{lag}'] = df['compound_score'].shift(lag)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding lagged features: {e}")
            return df
    
    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add rolling window features"""
        try:
            # Rolling statistics
            for window in [5, 10, 20]:
                df[f'close_std_{window}'] = df['close'].rolling(window).std()
                df[f'close_skew_{window}'] = df['close'].rolling(window).skew()
                df[f'close_kurt_{window}'] = df['close'].rolling(window).kurt()
                
                df[f'volume_std_{window}'] = df['volume'].rolling(window).std()
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding rolling features: {e}")
            return df
    
    def _generate_labels(self, data: pd.DataFrame, prediction_horizon_hours: int) -> pd.DataFrame:
        """Generate labels for ML training"""
        try:
            df = data.copy()
            
            # Future price change
            df['future_price'] = df['close'].shift(-prediction_horizon_hours)
            df['future_return'] = (df['future_price'] - df['close']) / df['close']
            
            # Classification labels
            df['signal_direction'] = 0  # Hold
            df.loc[df['future_return'] > 0.02, 'signal_direction'] = 1  # Buy
            df.loc[df['future_return'] < -0.02, 'signal_direction'] = -1  # Sell
            
            # Binary classification
            df['is_profitable'] = (df['future_return'] > 0).astype(int)
            
            # Regression targets
            df['target_return'] = df['future_return']
            df['target_volatility'] = df['future_return'].rolling(5).std().shift(-prediction_horizon_hours)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error generating labels: {e}")
            return data
    
    def _clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the data"""
        try:
            df = data.copy()
            
            # Remove rows with missing target values
            df = df.dropna(subset=['future_return', 'signal_direction'])
            
            # Remove infinite values
            df = df.replace([np.inf, -np.inf], np.nan)
            
            # Fill remaining NaN values
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].mean())
            
            # Remove outliers (optional)
            # df = self._remove_outliers(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error cleaning data: {e}")
            return data
    
    def get_feature_list(self) -> List[str]:
        """Get list of all available features"""
        try:
            features = MLFeature.objects.filter(is_active=True)
            return [feature.name for feature in features]
        except Exception as e:
            self.logger.error(f"Error getting feature list: {e}")
            return []
    
    def create_feature_definitions(self):
        """Create feature definitions in the database"""
        try:
            feature_definitions = [
                {
                    'name': 'price_change',
                    'feature_type': 'PRICE',
                    'description': 'Percentage change in closing price',
                    'calculation_method': 'pct_change()',
                    'is_lagging': False
                },
                {
                    'name': 'rsi',
                    'feature_type': 'TECHNICAL',
                    'description': 'Relative Strength Index (14-period)',
                    'calculation_method': 'talib.RSI(close, 14)',
                    'is_lagging': False
                },
                {
                    'name': 'macd',
                    'feature_type': 'TECHNICAL',
                    'description': 'MACD line',
                    'calculation_method': 'talib.MACD(close)',
                    'is_lagging': False
                },
                {
                    'name': 'bb_position',
                    'feature_type': 'TECHNICAL',
                    'description': 'Position within Bollinger Bands',
                    'calculation_method': '(close - bb_lower) / (bb_upper - bb_lower)',
                    'is_lagging': False
                },
                {
                    'name': 'volume_ratio',
                    'feature_type': 'VOLUME',
                    'description': 'Volume relative to 10-period SMA',
                    'calculation_method': 'volume / volume_sma_10',
                    'is_lagging': False
                },
                {
                    'name': 'compound_score',
                    'feature_type': 'SENTIMENT',
                    'description': 'Sentiment compound score',
                    'calculation_method': 'VADER sentiment analysis',
                    'is_lagging': False
                }
            ]
            
            for feature_def in feature_definitions:
                MLFeature.objects.get_or_create(
                    name=feature_def['name'],
                    defaults=feature_def
                )
            
            self.logger.info(f"Created {len(feature_definitions)} feature definitions")
            
        except Exception as e:
            self.logger.error(f"Error creating feature definitions: {e}")
