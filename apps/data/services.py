import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
import logging
from django.utils import timezone
from django.db import transaction
from pycoingecko import CoinGeckoAPI
import ccxt
import websocket
import json
import threading
import time

from .models import (
    DataSource, MarketData, DataFeed, TechnicalIndicator, 
    DataSyncLog, EconomicIndicator, MacroSentiment, EconomicEvent,
    Sector, SectorPerformance, SectorRotation, SectorCorrelation
)
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class CoinGeckoService:
    """Service for CoinGecko API integration"""
    
    def __init__(self):
        self.api = CoinGeckoAPI()
        self.base_url = "https://api.coingecko.com/api/v3"
        
    def get_top_coins(self, limit: int = 200) -> List[Dict]:
        """Get top coins by market cap"""
        try:
            coins = self.api.get_coins_markets(
                vs_currency='usd',
                order='market_cap_desc',
                per_page=limit,
                page=1,
                sparkline=False
            )
            return coins
        except Exception as e:
            logger.error(f"Error fetching top coins: {e}")
            return []
    
    def get_all_coins(self, max_coins: int = 1000) -> List[Dict]:
        """
        Get all available coins from CoinGecko (paginated)
        
        Args:
            max_coins: Maximum number of coins to fetch (default: 1000)
        """
        try:
            all_coins = []
            page = 1
            per_page = 250  # Maximum per page for CoinGecko API
            
            while len(all_coins) < max_coins:
                try:
                    coins = self.api.get_coins_markets(
                        vs_currency='usd',
                        order='market_cap_desc',
                        per_page=per_page,
                        page=page,
                        sparkline=False
                    )
                    
                    if not coins or len(coins) == 0:
                        break
                    
                    all_coins.extend(coins)
                    logger.info(f"Fetched page {page}: {len(coins)} coins (Total: {len(all_coins)})")
                    
                    # If we got less than per_page, we've reached the end
                    if len(coins) < per_page:
                        break
                    
                    page += 1
                    # Add small delay to avoid rate limiting
                    import time
                    time.sleep(0.6)  # CoinGecko rate limit: 10-50 calls/minute
                    
                except Exception as e:
                    logger.warning(f"Error fetching page {page}: {e}")
                    break
            
            logger.info(f"Total coins fetched: {len(all_coins)}")
            return all_coins[:max_coins]  # Return up to max_coins
        except Exception as e:
            logger.error(f"Error fetching all coins: {e}")
            return []
    
    def get_coin_data(self, coin_id: str) -> Optional[Dict]:
        """Get detailed data for a specific coin"""
        try:
            data = self.api.get_coin_by_id(coin_id)
            return data
        except Exception as e:
            logger.error(f"Error fetching coin data for {coin_id}: {e}")
            return None
    
    def get_historical_data(self, coin_id: str, days: int = 30) -> Optional[List[Dict]]:
        """Get historical price data"""
        try:
            data = self.api.get_coin_market_chart_by_id(
                id=coin_id,
                vs_currency='usd',
                days=days
            )
            return data
        except Exception as e:
            logger.error(f"Error fetching historical data for {coin_id}: {e}")
            return None


class CryptoDataIngestionService:
    """Service for ingesting crypto market data"""
    
    def __init__(self):
        self.coingecko = CoinGeckoService()
        self.data_source, _ = DataSource.objects.get_or_create(
            name='CoinGecko',
            defaults={
                'source_type': 'API',
                'base_url': 'https://api.coingecko.com/api/v3',
                'is_active': True
            }
        )
    
    def sync_crypto_symbols(self, limit: Optional[int] = None, max_coins: int = 1000) -> bool:
        """
        Sync crypto symbols from CoinGecko
        
        Args:
            limit: Number of coins to sync (None = all available coins up to max_coins)
            max_coins: Maximum number of coins to fetch when limit is None (default: 1000)
        """
        try:
            if limit:
                coins = self.coingecko.get_top_coins(limit=min(limit, 250))  # API limit per call
                logger.info(f"Syncing top {limit} coins from CoinGecko")
            else:
                coins = self.coingecko.get_all_coins(max_coins=max_coins)
                logger.info(f"Syncing ALL available coins from CoinGecko (up to {max_coins})")
            
            created_count = 0
            updated_count = 0
            
            with transaction.atomic():
                for coin in coins:
                    symbol, created = Symbol.objects.get_or_create(
                        symbol=coin['symbol'].upper(),
                        defaults={
                            'name': coin['name'],
                            'symbol_type': 'CRYPTO',
                            'exchange': 'CoinGecko',
                            'is_active': True,
                            'is_crypto_symbol': True,
                            'market_cap_rank': coin.get('market_cap_rank')
                        }
                    )
                    
                    if created:
                        created_count += 1
                        logger.info(f"Created new symbol: {symbol.symbol} ({coin['name']})")
                    else:
                        # Update existing symbol to ensure it's active
                        if not symbol.is_active:
                            symbol.is_active = True
                            symbol.is_crypto_symbol = True
                            symbol.market_cap_rank = coin.get('market_cap_rank')
                            symbol.save()
                            updated_count += 1
            
            logger.info(f"Symbol sync completed: {created_count} created, {updated_count} updated, {len(coins)} total")
            return True
        except Exception as e:
            logger.error(f"Error syncing crypto symbols: {e}")
            return False
    
    def sync_market_data(self, symbol: Symbol, days: int = 30) -> bool:
        """Sync market data for a specific symbol from CoinGecko"""
        try:
            from apps.data.models import MarketData
            
            # Get CoinGecko coin ID (try symbol name or symbol itself)
            coin_id = symbol.symbol.lower()
            
            # Try to get coin ID from CoinGecko
            try:
                # Get coin list to find the correct ID
                coin_list = self.coingecko.api.get_coins_list()
                coin_info = next((c for c in coin_list if c['symbol'].upper() == symbol.symbol.upper()), None)
                if coin_info:
                    coin_id = coin_info['id']
            except:
                pass  # Fallback to symbol name
            
            historical_data = self.coingecko.get_historical_data(coin_id, days=days)
            
            if not historical_data or 'prices' not in historical_data:
                logger.warning(f"No historical data found for {symbol.symbol} (coin_id: {coin_id})")
                return False
            
            saved_count = 0
            with transaction.atomic():
                for price_data in historical_data['prices']:
                    from datetime import timezone as dt_timezone
                    timestamp = datetime.fromtimestamp(price_data[0] / 1000, tz=dt_timezone.utc)
                    price = Decimal(str(price_data[1]))
                    
                    # Get market data if available (for OHLCV)
                    market_caps = historical_data.get('market_caps', [])
                    total_volumes = historical_data.get('total_volumes', [])
                    
                    # Find matching volume and market cap
                    volume = Decimal('0')
                    for vol_data in total_volumes:
                        if abs(vol_data[0] - price_data[0]) < 1000:  # Within 1 second
                            volume = Decimal(str(vol_data[1]))
                            break
                    
                    # Create or update market data
                    market_data, created = MarketData.objects.update_or_create(
                        symbol=symbol,
                        timestamp=timestamp,
                        timeframe='1h',
                        defaults={
                            'open_price': price,
                            'high_price': price,
                            'low_price': price,
                            'close_price': price,
                            'volume': volume,
                            'source': self.data_source
                        }
                    )
                    
                    if created:
                        saved_count += 1
            
            logger.info(f"Synced {saved_count} market data records for {symbol.symbol}")
            return saved_count > 0
        except Exception as e:
            logger.error(f"Error syncing market data for {symbol.symbol}: {e}")
            return False


class TechnicalAnalysisService:
    """Service for calculating technical indicators"""
    
    def __init__(self):
        self.data_source, _ = DataSource.objects.get_or_create(
            name='Technical Analysis',
            defaults={
                'source_type': 'CALCULATED',
                'is_active': True
            }
        )
    
    def get_market_data_df(self, symbol: Symbol, limit: int = 100) -> pd.DataFrame:
        """Get market data as pandas DataFrame"""
        market_data = MarketData.objects.filter(
            symbol=symbol
        ).order_by('-timestamp')[:limit]
        
        if not market_data:
            return pd.DataFrame()
        
        data = []
        for md in market_data:
            data.append({
                'timestamp': md.timestamp,
                'open': float(md.open_price),
                'high': float(md.high_price),
                'low': float(md.low_price),
                'close': float(md.close_price),
                'volume': float(md.volume)
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp')
        return df
    
    def calculate_rsi(self, symbol: Symbol, period: int = 14) -> Optional[float]:
        """Calculate RSI for a symbol"""
        try:
            df = self.get_market_data_df(symbol)
            if df.empty or len(df) < period:
                return None
            
            # Calculate RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            latest_rsi = rsi.iloc[-1]
            
            if not pd.isna(latest_rsi):
                # Save to database
                TechnicalIndicator.objects.create(
                    symbol=symbol,
                    indicator_type='RSI',
                    period=period,
                    value=Decimal(str(latest_rsi)),
                    timestamp=timezone.now(),
                    source=self.data_source
                )
                
                return float(latest_rsi)
            
            return None
        except Exception as e:
            logger.error(f"Error calculating RSI for {symbol.symbol}: {e}")
            return None
    
    def calculate_macd(self, symbol: Symbol, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[Dict]:
        """Calculate MACD for a symbol"""
        try:
            df = self.get_market_data_df(symbol)
            if df.empty or len(df) < slow:
                return None
            
            # Calculate MACD
            exp1 = df['close'].ewm(span=fast).mean()
            exp2 = df['close'].ewm(span=slow).mean()
            macd = exp1 - exp2
            signal_line = macd.ewm(span=signal).mean()
            histogram = macd - signal_line
            
            latest_macd = macd.iloc[-1]
            latest_signal = signal_line.iloc[-1]
            latest_histogram = histogram.iloc[-1]
            
            if not pd.isna(latest_macd):
                # Save to database
                TechnicalIndicator.objects.create(
                    symbol=symbol,
                    indicator_type='MACD',
                    period=fast,
                    value=Decimal(str(latest_macd)),
                    timestamp=timezone.now(),
                    source=self.data_source
                )
                
                return {
                    'macd': float(latest_macd),
                    'signal': float(latest_signal),
                    'histogram': float(latest_histogram)
                }
            
            return None
        except Exception as e:
            logger.error(f"Error calculating MACD for {symbol.symbol}: {e}")
            return None
    
    def calculate_bollinger_bands(self, symbol: Symbol, period: int = 20, std_dev: int = 2) -> Optional[Dict]:
        """Calculate Bollinger Bands for a symbol"""
        try:
            df = self.get_market_data_df(symbol)
            if df.empty or len(df) < period:
                return None
            
            # Calculate Bollinger Bands
            middle = df['close'].rolling(window=period).mean()
            std = df['close'].rolling(window=period).std()
            upper = middle + (std * std_dev)
            lower = middle - (std * std_dev)
            
            latest_middle = middle.iloc[-1]
            latest_upper = upper.iloc[-1]
            latest_lower = lower.iloc[-1]
            
            if not pd.isna(latest_middle):
                # Save to database
                TechnicalIndicator.objects.create(
                    symbol=symbol,
                    indicator_type='BB_MIDDLE',
                    period=period,
                    value=Decimal(str(latest_middle)),
                    timestamp=timezone.now(),
                    source=self.data_source
                )
                
                return {
                    'upper': float(latest_upper),
                    'middle': float(latest_middle),
                    'lower': float(latest_lower)
                }
            
            return None
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands for {symbol.symbol}: {e}")
            return None
    
    def calculate_all_indicators(self, symbol: Symbol) -> bool:
        """Calculate all technical indicators for a symbol"""
        try:
            success_count = 0
            
            # Calculate RSI
            if self.calculate_rsi(symbol):
                success_count += 1
            
            # Calculate MACD
            if self.calculate_macd(symbol):
                success_count += 1
            
            # Calculate Bollinger Bands
            if self.calculate_bollinger_bands(symbol):
                success_count += 1
            
            logger.info(f"Calculated {success_count}/3 indicators for {symbol.symbol}")
            return success_count > 0
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol.symbol}: {e}")
            return False


class RiskManagementService:
    """Service for risk management calculations"""
    
    def get_market_data_df(self, symbol: Symbol, limit: int = 100) -> pd.DataFrame:
        """Get market data as pandas DataFrame"""
        market_data = MarketData.objects.filter(
            symbol=symbol
        ).order_by('-timestamp')[:limit]
        
        if not market_data:
            return pd.DataFrame()
        
        data = []
        for md in market_data:
            data.append({
                'timestamp': md.timestamp,
                'open': float(md.open_price),
                'high': float(md.high_price),
                'low': float(md.low_price),
                'close': float(md.close_price),
                'volume': float(md.volume)
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('timestamp')
        return df
    
    def calculate_volatility(self, symbol: Symbol, period: int = 20) -> Optional[float]:
        """Calculate price volatility"""
        try:
            df = self.get_market_data_df(symbol, limit=period)
            if df.empty or len(df) < period:
                return None
            
            # Calculate daily returns
            returns = df['close'].pct_change().dropna()
            
            # Calculate volatility (standard deviation of returns)
            volatility = returns.std() * np.sqrt(252)  # Annualized
            
            return float(volatility)
        except Exception as e:
            logger.error(f"Error calculating volatility for {symbol.symbol}: {e}")
            return None
    
    def calculate_position_size(self, account_size: float, risk_per_trade: float, stop_loss_pct: float) -> float:
        """Calculate position size based on risk management rules"""
        try:
            risk_amount = account_size * risk_per_trade
            position_size = risk_amount / stop_loss_pct
            return min(position_size, account_size)  # Don't exceed account size
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def calculate_risk_reward_ratio(self, entry_price: float, stop_loss: float, take_profit: float) -> float:
        """Calculate risk-reward ratio"""
        try:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            
            if risk == 0:
                return 0.0
            
            return reward / risk
        except Exception as e:
            logger.error(f"Error calculating risk-reward ratio: {e}")
            return 0.0


class EconomicDataService:
    """Service for managing economic data and fundamental analysis"""
    
    def __init__(self):
        self.data_source, _ = DataSource.objects.get_or_create(
            name='Economic Data API',
            defaults={
                'source_type': 'API',
                'base_url': 'https://api.economicdata.com',
                'is_active': True
            }
        )
        
        # Economic indicator weights for sentiment calculation
        self.indicator_weights = {
            'GDP': 0.25,
            'INFLATION': 0.20,
            'UNEMPLOYMENT': 0.20,
            'INTEREST_RATE': 0.15,
            'CPI': 0.10,
            'CONSUMER_CONFIDENCE': 0.10
        }
    
    def calculate_macro_sentiment(self, country: str = 'US') -> Optional[MacroSentiment]:
        """Calculate macro economic sentiment for a country"""
        try:
            # Get latest economic indicators for the country
            latest_indicators = self._get_latest_indicators(country)
            
            if not latest_indicators:
                logger.warning(f"No economic indicators found for {country}")
                return None
            
            # Calculate individual impact scores
            gdp_impact = self._calculate_gdp_impact(latest_indicators.get('GDP'))
            inflation_impact = self._calculate_inflation_impact(latest_indicators.get('INFLATION'))
            employment_impact = self._calculate_employment_impact(latest_indicators.get('UNEMPLOYMENT'))
            monetary_impact = self._calculate_monetary_impact(latest_indicators.get('INTEREST_RATE'))
            
            # Calculate weighted sentiment score
            sentiment_score = (
                gdp_impact * self.indicator_weights.get('GDP', 0) +
                inflation_impact * self.indicator_weights.get('INFLATION', 0) +
                employment_impact * self.indicator_weights.get('UNEMPLOYMENT', 0) +
                monetary_impact * self.indicator_weights.get('INTEREST_RATE', 0)
            )
            
            # Normalize to -1 to 1 range
            sentiment_score = max(-1.0, min(1.0, sentiment_score))
            
            # Determine sentiment level
            sentiment_level = self._get_sentiment_level(sentiment_score)
            
            # Calculate confidence based on data availability
            confidence_score = self._calculate_confidence(latest_indicators)
            
            # Create or update macro sentiment
            macro_sentiment = MacroSentiment.objects.create(
                country=country,
                sentiment_score=sentiment_score,
                sentiment_level=sentiment_level,
                confidence_score=confidence_score,
                gdp_impact=gdp_impact,
                inflation_impact=inflation_impact,
                employment_impact=employment_impact,
                monetary_policy_impact=monetary_impact,
                calculation_timestamp=timezone.now(),
                data_period_start=timezone.now() - timedelta(days=90),
                data_period_end=timezone.now()
            )
            
            logger.info(f"Calculated macro sentiment for {country}: {sentiment_level} ({sentiment_score:.2f})")
            return macro_sentiment
            
        except Exception as e:
            logger.error(f"Error calculating macro sentiment for {country}: {e}")
            return None
    
    def get_market_impact_score(self, symbol_country: str = 'US') -> float:
        """Get market impact score based on economic sentiment"""
        try:
            # Get latest macro sentiment
            latest_sentiment = MacroSentiment.objects.filter(
                country=symbol_country
            ).order_by('-calculation_timestamp').first()
            
            if not latest_sentiment:
                return 0.0
            
            # Weight the sentiment score by confidence
            impact_score = latest_sentiment.sentiment_score * latest_sentiment.confidence_score
            
            return float(impact_score)
            
        except Exception as e:
            logger.error(f"Error getting market impact score: {e}")
            return 0.0
    
    def check_upcoming_events(self, days_ahead: int = 7) -> List[EconomicEvent]:
        """Get upcoming economic events that might impact markets"""
        try:
            future_date = timezone.now() + timedelta(days=days_ahead)
            
            upcoming_events = EconomicEvent.objects.filter(
                scheduled_date__gte=timezone.now(),
                scheduled_date__lte=future_date,
                is_completed=False
            ).order_by('scheduled_date')
            
            return list(upcoming_events)
            
        except Exception as e:
            logger.error(f"Error checking upcoming events: {e}")
            return []
    
    def analyze_event_impact(self, event: EconomicEvent) -> Dict:
        """Analyze the potential market impact of an economic event"""
        try:
            # Base impact score
            impact_multipliers = {
                'LOW': 0.25,
                'MEDIUM': 0.5,
                'HIGH': 0.75,
                'CRITICAL': 1.0
            }
            
            base_impact = impact_multipliers.get(event.impact_level, 0.5)
            
            # Adjust based on event type
            type_multipliers = {
                'POLICY_DECISION': 1.2,  # Fed decisions have higher impact
                'ANNOUNCEMENT': 1.0,
                'REPORT_RELEASE': 0.8,
                'SPEECH': 0.6,
                'MEETING': 0.4
            }
            
            type_impact = type_multipliers.get(event.event_type, 1.0)
            
            # Calculate final impact scores
            final_impact = base_impact * type_impact
            volatility_boost = event.volatility_impact * final_impact
            
            return {
                'market_impact': event.market_impact_score * final_impact,
                'volatility_impact': volatility_boost,
                'confidence': min(0.9, base_impact + 0.1),
                'time_to_event': (event.scheduled_date - timezone.now()).total_seconds() / 3600,  # hours
                'recommendation': self._get_event_recommendation(final_impact, event.market_impact_score)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing event impact: {e}")
            return {}
    
    def _get_latest_indicators(self, country: str) -> Dict:
        """Get latest economic indicators for a country"""
        try:
            indicators = {}
            
            for indicator_type, _ in EconomicIndicator.INDICATOR_TYPES:
                latest = EconomicIndicator.objects.filter(
                    country=country,
                    indicator_type=indicator_type
                ).order_by('-timestamp').first()
                
                if latest:
                    indicators[indicator_type] = latest
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting latest indicators for {country}: {e}")
            return {}
    
    def _calculate_gdp_impact(self, gdp_indicator: Optional[EconomicIndicator]) -> float:
        """Calculate GDP impact on market sentiment"""
        if not gdp_indicator:
            return 0.0
        
        try:
            # GDP growth above 2% is generally positive
            gdp_value = float(gdp_indicator.value)
            
            if gdp_value > 3.0:
                return 0.8  # Very positive
            elif gdp_value > 2.0:
                return 0.4  # Positive
            elif gdp_value > 0.0:
                return 0.0  # Neutral
            elif gdp_value > -2.0:
                return -0.4  # Negative
            else:
                return -0.8  # Very negative
                
        except Exception as e:
            logger.error(f"Error calculating GDP impact: {e}")
            return 0.0
    
    def _calculate_inflation_impact(self, inflation_indicator: Optional[EconomicIndicator]) -> float:
        """Calculate inflation impact on market sentiment"""
        if not inflation_indicator:
            return 0.0
        
        try:
            inflation_value = float(inflation_indicator.value)
            
            # Target inflation is usually around 2%
            if 1.5 <= inflation_value <= 2.5:
                return 0.3  # Ideal range
            elif 2.5 < inflation_value <= 4.0:
                return -0.2  # Slightly high
            elif inflation_value > 4.0:
                return -0.6  # Too high
            elif inflation_value < 1.0:
                return -0.3  # Too low (deflation risk)
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating inflation impact: {e}")
            return 0.0
    
    def _calculate_employment_impact(self, unemployment_indicator: Optional[EconomicIndicator]) -> float:
        """Calculate employment impact on market sentiment"""
        if not unemployment_indicator:
            return 0.0
        
        try:
            unemployment_value = float(unemployment_indicator.value)
            
            # Lower unemployment is better
            if unemployment_value < 4.0:
                return 0.6  # Very good
            elif unemployment_value < 5.0:
                return 0.3  # Good
            elif unemployment_value < 7.0:
                return 0.0  # Neutral
            elif unemployment_value < 10.0:
                return -0.4  # High
            else:
                return -0.8  # Very high
                
        except Exception as e:
            logger.error(f"Error calculating employment impact: {e}")
            return 0.0
    
    def _calculate_monetary_impact(self, interest_rate_indicator: Optional[EconomicIndicator]) -> float:
        """Calculate monetary policy impact on market sentiment"""
        if not interest_rate_indicator:
            return 0.0
        
        try:
            rate_value = float(interest_rate_indicator.value)
            
            # Consider rate changes more than absolute values
            change = interest_rate_indicator.change_from_previous
            
            if change is None:
                # Base assessment on absolute rate
                if rate_value < 2.0:
                    return 0.2  # Accommodative
                elif rate_value < 5.0:
                    return 0.0  # Neutral
                else:
                    return -0.3  # Restrictive
            else:
                # Rate increase is generally negative for markets in short term
                if change > 0.5:
                    return -0.6  # Big increase
                elif change > 0.25:
                    return -0.3  # Moderate increase
                elif change > 0:
                    return -0.1  # Small increase
                elif change < -0.25:
                    return 0.4  # Rate cut
                else:
                    return 0.0  # No change
                    
        except Exception as e:
            logger.error(f"Error calculating monetary impact: {e}")
            return 0.0
    
    def _get_sentiment_level(self, sentiment_score: float) -> str:
        """Convert sentiment score to level"""
        if sentiment_score >= 0.6:
            return 'VERY_BULLISH'
        elif sentiment_score >= 0.2:
            return 'BULLISH'
        elif sentiment_score >= -0.2:
            return 'NEUTRAL'
        elif sentiment_score >= -0.6:
            return 'BEARISH'
        else:
            return 'VERY_BEARISH'
    
    def _calculate_confidence(self, indicators: Dict) -> float:
        """Calculate confidence score based on data availability"""
        try:
            total_indicators = len(self.indicator_weights)
            available_indicators = len(indicators)
            
            base_confidence = available_indicators / total_indicators
            
            # Boost confidence if we have recent data
            recent_data_bonus = 0.0
            for indicator in indicators.values():
                if indicator and indicator.timestamp > timezone.now() - timedelta(days=30):
                    recent_data_bonus += 0.1
            
            return min(1.0, base_confidence + recent_data_bonus)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5
    
    def _get_event_recommendation(self, impact_score: float, market_impact: float) -> str:
        """Get trading recommendation based on event analysis"""
        try:
            if impact_score >= 0.8:
                if market_impact > 0.3:
                    return "STRONG_BUY_OPPORTUNITY"
                elif market_impact < -0.3:
                    return "STRONG_SELL_SIGNAL"
                else:
                    return "HIGH_VOLATILITY_EXPECTED"
            elif impact_score >= 0.5:
                if market_impact > 0.2:
                    return "MODERATE_BUY_SIGNAL"
                elif market_impact < -0.2:
                    return "MODERATE_SELL_SIGNAL"
                else:
                    return "MODERATE_VOLATILITY"
            else:
                return "LOW_IMPACT_EVENT"
                
        except Exception as e:
            logger.error(f"Error getting event recommendation: {e}")
            return "NEUTRAL"
    
    def create_sample_economic_data(self):
        """Create sample economic data for testing"""
        try:
            # Sample US economic indicators
            sample_data = [
                {
                    'indicator_type': 'GDP',
                    'country': 'US',
                    'value': 2.1,
                    'previous_value': 2.0,
                    'expected_value': 2.2,
                    'unit': '%'
                },
                {
                    'indicator_type': 'INFLATION',
                    'country': 'US',
                    'value': 3.2,
                    'previous_value': 3.0,
                    'expected_value': 3.1,
                    'unit': '%'
                },
                {
                    'indicator_type': 'UNEMPLOYMENT',
                    'country': 'US',
                    'value': 3.7,
                    'previous_value': 3.8,
                    'expected_value': 3.7,
                    'unit': '%'
                },
                {
                    'indicator_type': 'INTEREST_RATE',
                    'country': 'US',
                    'value': 5.25,
                    'previous_value': 5.0,
                    'expected_value': 5.25,
                    'unit': '%'
                }
            ]
            
            current_time = timezone.now()
            
            for data in sample_data:
                EconomicIndicator.objects.get_or_create(
                    indicator_type=data['indicator_type'],
                    country=data['country'],
                    timestamp=current_time,
                    defaults={
                        'value': data['value'],
                        'previous_value': data['previous_value'],
                        'expected_value': data['expected_value'],
                        'unit': data['unit'],
                        'release_date': current_time,
                        'source': self.data_source
                    }
                )
            
            # Sample economic events
            EconomicEvent.objects.get_or_create(
                name='Federal Reserve Meeting',
                country='US',
                scheduled_date=timezone.now() + timedelta(days=14),
                defaults={
                    'description': 'FOMC meeting to discuss monetary policy',
                    'event_type': 'POLICY_DECISION',
                    'impact_level': 'CRITICAL',
                    'market_impact_score': 0.0,
                    'volatility_impact': 0.8
                }
            )
            
            logger.info("Sample economic data created successfully")
            
        except Exception as e:
            logger.error(f"Error creating sample economic data: {e}")


class SectorAnalysisService:
    """Service for sector analysis and rotation detection"""
    
    def __init__(self):
        self.data_source, _ = DataSource.objects.get_or_create(
            name='Sector Analysis',
            defaults={
                'source_type': 'CALCULATED',
                'is_active': True
            }
        )
        
        # Sector categorization for analysis
        self.growth_sectors = ['TECHNOLOGY', 'CONSUMER_DISCRETIONARY', 'COMMUNICATION']
        self.value_sectors = ['FINANCIALS', 'ENERGY', 'MATERIALS']
        self.defensive_sectors = ['UTILITIES', 'CONSUMER_STAPLES', 'HEALTHCARE']
        self.cyclical_sectors = ['INDUSTRIALS', 'MATERIALS', 'ENERGY', 'FINANCIALS']
        
    def calculate_sector_performance(self, sector: Sector, timeframe_days: int = 30) -> Optional[SectorPerformance]:
        """Calculate performance metrics for a sector"""
        try:
            # Get symbols in this sector
            sector_symbols = Symbol.objects.filter(sector=sector, is_active=True)
            
            if not sector_symbols.exists():
                logger.warning(f"No symbols found for sector {sector.display_name}")
                return None
            
            # Calculate sector-wide performance
            total_daily_return = 0.0
            total_weekly_return = 0.0
            total_monthly_return = 0.0
            total_volatility = 0.0
            valid_symbols = 0
            
            for symbol in sector_symbols:
                perf_data = self._calculate_symbol_performance(symbol, timeframe_days)
                if perf_data:
                    total_daily_return += perf_data['daily_return']
                    total_weekly_return += perf_data['weekly_return']
                    total_monthly_return += perf_data['monthly_return']
                    total_volatility += perf_data['volatility']
                    valid_symbols += 1
            
            if valid_symbols == 0:
                return None
            
            # Average the performance metrics
            avg_daily_return = total_daily_return / valid_symbols
            avg_weekly_return = total_weekly_return / valid_symbols
            avg_monthly_return = total_monthly_return / valid_symbols
            avg_volatility = total_volatility / valid_symbols
            
            # Calculate momentum and relative strength
            momentum_score = self._calculate_sector_momentum(sector, timeframe_days)
            relative_strength = self._calculate_relative_strength(sector, avg_monthly_return)
            volume_trend = self._calculate_volume_trend(sector, timeframe_days)
            
            # Create sector performance record
            sector_performance = SectorPerformance.objects.create(
                sector=sector,
                timestamp=timezone.now(),
                daily_return=avg_daily_return,
                weekly_return=avg_weekly_return,
                monthly_return=avg_monthly_return,
                volatility=avg_volatility,
                momentum_score=momentum_score,
                relative_strength=relative_strength,
                volume_trend=volume_trend
            )
            
            logger.info(f"Calculated performance for {sector.display_name}: "
                       f"Monthly return: {avg_monthly_return:.2f}%, "
                       f"Relative strength: {relative_strength:.2f}")
            
            return sector_performance
            
        except Exception as e:
            logger.error(f"Error calculating sector performance for {sector.display_name}: {e}")
            return None
    
    def detect_sector_rotation(self, lookback_days: int = 30) -> List[SectorRotation]:
        """Detect sector rotation patterns"""
        try:
            rotations = []
            
            # Get recent sector performances
            recent_performances = {}
            for sector in Sector.objects.filter(is_active=True):
                latest_perf = SectorPerformance.objects.filter(
                    sector=sector,
                    timestamp__gte=timezone.now() - timedelta(days=lookback_days)
                ).order_by('-timestamp').first()
                
                if latest_perf:
                    recent_performances[sector] = latest_perf
            
            if len(recent_performances) < 2:
                return rotations
            
            # Sort sectors by relative strength
            sorted_sectors = sorted(
                recent_performances.items(),
                key=lambda x: x[1].relative_strength,
                reverse=True
            )
            
            # Identify rotation patterns
            strong_sectors = sorted_sectors[:3]  # Top 3 performers
            weak_sectors = sorted_sectors[-3:]   # Bottom 3 performers
            
            # Detect specific rotation types
            for weak_sector, weak_perf in weak_sectors:
                for strong_sector, strong_perf in strong_sectors:
                    rotation_type = self._classify_rotation_type(
                        weak_sector, strong_sector, weak_perf, strong_perf
                    )
                    
                    if rotation_type:
                        strength = abs(strong_perf.relative_strength - weak_perf.relative_strength)
                        confidence = min(0.9, strength * 2)  # Normalize confidence
                        
                        rotation = SectorRotation.objects.create(
                            rotation_type=rotation_type,
                            from_sector=weak_sector,
                            to_sector=strong_sector,
                            strength=min(1.0, strength),
                            confidence=confidence,
                            duration_days=lookback_days,
                            market_regime=self._get_current_market_regime(),
                            detected_at=timezone.now()
                        )
                        
                        rotations.append(rotation)
                        logger.info(f"Detected {rotation_type}: {weak_sector.display_name} → {strong_sector.display_name}")
            
            return rotations
            
        except Exception as e:
            logger.error(f"Error detecting sector rotation: {e}")
            return []
    
    def calculate_sector_correlations(self, timeframe: str = '1M') -> List[SectorCorrelation]:
        """Calculate correlations between sectors"""
        try:
            correlations = []
            sectors = list(Sector.objects.filter(is_active=True))
            
            for i, sector_a in enumerate(sectors):
                for sector_b in sectors[i+1:]:
                    correlation = self._calculate_pairwise_correlation(
                        sector_a, sector_b, timeframe
                    )
                    
                    if correlation is not None:
                        correlation_obj = SectorCorrelation.objects.create(
                            sector_a=sector_a,
                            sector_b=sector_b,
                            timeframe=timeframe,
                            correlation_coefficient=correlation['coefficient'],
                            p_value=correlation['p_value'],
                            sample_size=correlation['sample_size'],
                            calculated_at=timezone.now()
                        )
                        
                        correlations.append(correlation_obj)
            
            logger.info(f"Calculated {len(correlations)} sector correlations")
            return correlations
            
        except Exception as e:
            logger.error(f"Error calculating sector correlations: {e}")
            return []
    
    def get_sector_momentum_signals(self, sector: Sector) -> Dict:
        """Generate momentum-based signals for a sector"""
        try:
            # Get latest performance data
            latest_perf = SectorPerformance.objects.filter(
                sector=sector
            ).order_by('-timestamp').first()
            
            if not latest_perf:
                return {}
            
            signals = {
                'sector': sector.display_name,
                'momentum_signal': 'NEUTRAL',
                'strength': 0.0,
                'confidence': 0.0,
                'key_metrics': {}
            }
            
            # Momentum signal based on relative strength and momentum score
            if latest_perf.relative_strength > 0.3 and latest_perf.momentum_score > 0.2:
                signals['momentum_signal'] = 'STRONG_BUY'
                signals['strength'] = min(1.0, (latest_perf.relative_strength + latest_perf.momentum_score) / 2)
            elif latest_perf.relative_strength > 0.1 and latest_perf.momentum_score > 0.1:
                signals['momentum_signal'] = 'BUY'
                signals['strength'] = min(1.0, (latest_perf.relative_strength + latest_perf.momentum_score) / 2)
            elif latest_perf.relative_strength < -0.3 and latest_perf.momentum_score < -0.2:
                signals['momentum_signal'] = 'STRONG_SELL'
                signals['strength'] = min(1.0, abs((latest_perf.relative_strength + latest_perf.momentum_score) / 2))
            elif latest_perf.relative_strength < -0.1 and latest_perf.momentum_score < -0.1:
                signals['momentum_signal'] = 'SELL'
                signals['strength'] = min(1.0, abs((latest_perf.relative_strength + latest_perf.momentum_score) / 2))
            
            # Calculate confidence based on volatility and volume trend
            base_confidence = 0.5
            if latest_perf.volatility < 0.3:  # Low volatility increases confidence
                base_confidence += 0.2
            if abs(latest_perf.volume_trend) > 0.2:  # Strong volume trend increases confidence
                base_confidence += 0.2
            
            signals['confidence'] = min(1.0, base_confidence)
            signals['key_metrics'] = {
                'relative_strength': latest_perf.relative_strength,
                'momentum_score': latest_perf.momentum_score,
                'monthly_return': latest_perf.monthly_return,
                'volatility': latest_perf.volatility,
                'volume_trend': latest_perf.volume_trend
            }
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating sector momentum signals for {sector.display_name}: {e}")
            return {}
    
    def get_sector_impact_score(self, symbol: Symbol) -> float:
        """Get sector impact score for signal generation"""
        try:
            if not symbol.sector:
                return 0.0
            
            # Get sector momentum signals
            momentum_signals = self.get_sector_momentum_signals(symbol.sector)
            
            if not momentum_signals:
                return 0.0
            
            # Convert momentum signal to impact score
            signal_multipliers = {
                'STRONG_BUY': 0.8,
                'BUY': 0.4,
                'NEUTRAL': 0.0,
                'SELL': -0.4,
                'STRONG_SELL': -0.8
            }
            
            base_score = signal_multipliers.get(momentum_signals.get('momentum_signal', 'NEUTRAL'), 0.0)
            confidence = momentum_signals.get('confidence', 0.5)
            
            # Weight by confidence
            impact_score = base_score * confidence
            
            return float(impact_score)
            
        except Exception as e:
            logger.error(f"Error getting sector impact score for {symbol.symbol}: {e}")
            return 0.0
    
    def _calculate_symbol_performance(self, symbol: Symbol, timeframe_days: int) -> Optional[Dict]:
        """Calculate performance metrics for a single symbol"""
        try:
            # Get market data for the symbol
            end_date = timezone.now()
            start_date = end_date - timedelta(days=timeframe_days)
            
            market_data = MarketData.objects.filter(
                symbol=symbol,
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).order_by('timestamp')
            
            if market_data.count() < 2:
                return None
            
            prices = [float(md.close_price) for md in market_data]
            
            # Calculate returns
            daily_returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            
            if len(daily_returns) == 0:
                return None
            
            # Performance metrics
            latest_price = prices[-1]
            initial_price = prices[0]
            
            # Calculate different timeframe returns
            daily_return = daily_returns[-1] if daily_returns else 0.0
            weekly_return = (latest_price - prices[-min(7, len(prices))]) / prices[-min(7, len(prices))] if len(prices) >= 7 else daily_return
            monthly_return = (latest_price - initial_price) / initial_price
            
            # Volatility (annualized)
            volatility = np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 1 else 0.0
            
            return {
                'daily_return': daily_return * 100,  # Convert to percentage
                'weekly_return': weekly_return * 100,
                'monthly_return': monthly_return * 100,
                'volatility': volatility
            }
            
        except Exception as e:
            logger.error(f"Error calculating symbol performance for {symbol.symbol}: {e}")
            return None
    
    def _calculate_sector_momentum(self, sector: Sector, timeframe_days: int) -> float:
        """Calculate momentum score for a sector"""
        try:
            # Get historical sector performances
            historical_perfs = SectorPerformance.objects.filter(
                sector=sector,
                timestamp__gte=timezone.now() - timedelta(days=timeframe_days)
            ).order_by('-timestamp')[:10]
            
            if historical_perfs.count() < 3:
                return 0.0
            
            # Calculate momentum based on trend in relative strength
            recent_scores = [perf.relative_strength for perf in historical_perfs]
            
            if len(recent_scores) >= 3:
                # Simple momentum: recent vs older performance
                recent_avg = sum(recent_scores[:3]) / 3
                older_avg = sum(recent_scores[-3:]) / 3
                
                momentum = (recent_avg - older_avg) * 2  # Scale factor
                return max(-1.0, min(1.0, momentum))
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating sector momentum for {sector.display_name}: {e}")
            return 0.0
    
    def _calculate_relative_strength(self, sector: Sector, sector_return: float) -> float:
        """Calculate relative strength vs market"""
        try:
            # Calculate market average from all sectors
            all_sectors = Sector.objects.filter(is_active=True)
            market_returns = []
            
            for other_sector in all_sectors:
                if other_sector != sector:
                    symbols = Symbol.objects.filter(sector=other_sector, is_active=True)
                    if symbols.exists():
                        symbol = symbols.first()
                        perf_data = self._calculate_symbol_performance(symbol, 30)
                        if perf_data:
                            market_returns.append(perf_data['monthly_return'])
            
            if not market_returns:
                return 0.0
            
            market_avg = sum(market_returns) / len(market_returns)
            
            # Relative strength = (sector_return - market_return) / volatility
            relative_strength = (sector_return - market_avg) / 10.0  # Normalize
            
            return max(-1.0, min(1.0, relative_strength))
            
        except Exception as e:
            logger.error(f"Error calculating relative strength for {sector.display_name}: {e}")
            return 0.0
    
    def _calculate_volume_trend(self, sector: Sector, timeframe_days: int) -> float:
        """Calculate volume trend for a sector"""
        try:
            # Get symbols in sector
            sector_symbols = Symbol.objects.filter(sector=sector, is_active=True)[:5]  # Limit for performance
            
            if not sector_symbols:
                return 0.0
            
            total_volume_trend = 0.0
            valid_symbols = 0
            
            for symbol in sector_symbols:
                # Get recent volume data
                recent_data = MarketData.objects.filter(
                    symbol=symbol,
                    timestamp__gte=timezone.now() - timedelta(days=timeframe_days)
                ).order_by('-timestamp')[:10]
                
                if recent_data.count() >= 5:
                    volumes = [float(md.volume) for md in recent_data]
                    if len(volumes) >= 5:
                        recent_avg = sum(volumes[:3]) / 3
                        older_avg = sum(volumes[-3:]) / 3
                        
                        if older_avg > 0:
                            volume_change = (recent_avg - older_avg) / older_avg
                            total_volume_trend += volume_change
                            valid_symbols += 1
            
            if valid_symbols == 0:
                return 0.0
            
            avg_volume_trend = total_volume_trend / valid_symbols
            return max(-1.0, min(1.0, avg_volume_trend))
            
        except Exception as e:
            logger.error(f"Error calculating volume trend for {sector.display_name}: {e}")
            return 0.0
    
    def _classify_rotation_type(self, from_sector: Sector, to_sector: Sector, 
                               from_perf: SectorPerformance, to_perf: SectorPerformance) -> Optional[str]:
        """Classify the type of sector rotation"""
        try:
            from_name = from_sector.name
            to_name = to_sector.name
            
            # Growth to Value rotation
            if from_name in self.growth_sectors and to_name in self.value_sectors:
                return 'GROWTH_TO_VALUE'
            
            # Value to Growth rotation
            if from_name in self.value_sectors and to_name in self.growth_sectors:
                return 'VALUE_TO_GROWTH'
            
            # Defensive to Cyclical rotation
            if from_name in self.defensive_sectors and to_name in self.cyclical_sectors:
                return 'DEFENSIVE_TO_CYCLICAL'
            
            # Cyclical to Defensive rotation
            if from_name in self.cyclical_sectors and to_name in self.defensive_sectors:
                return 'CYCLICAL_TO_DEFENSIVE'
            
            # Risk On/Off based on relative strength difference
            strength_diff = to_perf.relative_strength - from_perf.relative_strength
            
            if strength_diff > 0.4:
                if to_name in self.growth_sectors or to_name in self.cyclical_sectors:
                    return 'RISK_ON'
                elif to_name in self.defensive_sectors:
                    return 'RISK_OFF'
            
            return None  # No clear rotation pattern
            
        except Exception as e:
            logger.error(f"Error classifying rotation type: {e}")
            return None
    
    def _calculate_pairwise_correlation(self, sector_a: Sector, sector_b: Sector, timeframe: str) -> Optional[Dict]:
        """Calculate correlation between two sectors"""
        try:
            # Map timeframe to days
            timeframe_days = {
                '1D': 1, '1W': 7, '1M': 30, '3M': 90, '6M': 180, '1Y': 365
            }.get(timeframe, 30)
            
            # Get performance data for both sectors
            perf_a = SectorPerformance.objects.filter(
                sector=sector_a,
                timestamp__gte=timezone.now() - timedelta(days=timeframe_days)
            ).order_by('timestamp')
            
            perf_b = SectorPerformance.objects.filter(
                sector=sector_b,
                timestamp__gte=timezone.now() - timedelta(days=timeframe_days)
            ).order_by('timestamp')
            
            if perf_a.count() < 5 or perf_b.count() < 5:
                return None
            
            # Extract returns for correlation calculation
            returns_a = [perf.daily_return for perf in perf_a]
            returns_b = [perf.daily_return for perf in perf_b]
            
            # Ensure same length
            min_len = min(len(returns_a), len(returns_b))
            returns_a = returns_a[:min_len]
            returns_b = returns_b[:min_len]
            
            if min_len < 5:
                return None
            
            # Calculate Pearson correlation
            correlation_matrix = np.corrcoef(returns_a, returns_b)
            correlation_coeff = correlation_matrix[0, 1]
            
            # Simple p-value approximation (for demonstration)
            # In production, you'd use scipy.stats for proper statistical tests
            p_value = 0.05 if abs(correlation_coeff) > 0.5 else 0.1
            
            return {
                'coefficient': float(correlation_coeff) if not np.isnan(correlation_coeff) else 0.0,
                'p_value': p_value,
                'sample_size': min_len
            }
            
        except Exception as e:
            logger.error(f"Error calculating correlation between {sector_a.display_name} and {sector_b.display_name}: {e}")
            return None
    
    def _get_current_market_regime(self) -> str:
        """Determine current market regime for context"""
        try:
            # Simple market regime detection based on sector performance
            growth_performance = 0.0
            value_performance = 0.0
            defensive_performance = 0.0
            
            for sector_name in self.growth_sectors:
                try:
                    sector = Sector.objects.get(name=sector_name, is_active=True)
                    latest_perf = SectorPerformance.objects.filter(
                        sector=sector
                    ).order_by('-timestamp').first()
                    
                    if latest_perf:
                        growth_performance += latest_perf.monthly_return
                except Sector.DoesNotExist:
                    continue
            
            for sector_name in self.value_sectors:
                try:
                    sector = Sector.objects.get(name=sector_name, is_active=True)
                    latest_perf = SectorPerformance.objects.filter(
                        sector=sector
                    ).order_by('-timestamp').first()
                    
                    if latest_perf:
                        value_performance += latest_perf.monthly_return
                except Sector.DoesNotExist:
                    continue
            
            for sector_name in self.defensive_sectors:
                try:
                    sector = Sector.objects.get(name=sector_name, is_active=True)
                    latest_perf = SectorPerformance.objects.filter(
                        sector=sector
                    ).order_by('-timestamp').first()
                    
                    if latest_perf:
                        defensive_performance += latest_perf.monthly_return
                except Sector.DoesNotExist:
                    continue
            
            # Determine regime
            if growth_performance > value_performance and growth_performance > defensive_performance:
                return "GROWTH_MOMENTUM"
            elif value_performance > growth_performance and value_performance > defensive_performance:
                return "VALUE_ROTATION"
            elif defensive_performance > growth_performance and defensive_performance > value_performance:
                return "DEFENSIVE_MODE"
            else:
                return "MIXED_SIGNALS"
                
        except Exception as e:
            logger.error(f"Error determining market regime: {e}")
            return "UNKNOWN"
    
    def create_sample_sectors(self):
        """Create sample sector data for testing"""
        try:
            sample_sectors = [
                {
                    'name': 'TECHNOLOGY',
                    'display_name': 'Technology',
                    'description': 'Technology companies including software, hardware, and internet services',
                    'market_cap_weight': 0.25
                },
                {
                    'name': 'HEALTHCARE',
                    'display_name': 'Healthcare',
                    'description': 'Healthcare and pharmaceutical companies',
                    'market_cap_weight': 0.15
                },
                {
                    'name': 'FINANCIALS',
                    'display_name': 'Financials',
                    'description': 'Banks, insurance, and financial services',
                    'market_cap_weight': 0.13
                },
                {
                    'name': 'CRYPTO_LAYER1',
                    'display_name': 'Layer 1 Cryptocurrencies',
                    'description': 'Base layer blockchain protocols',
                    'market_cap_weight': 0.08
                },
                {
                    'name': 'CRYPTO_DEFI',
                    'display_name': 'DeFi Tokens',
                    'description': 'Decentralized finance protocols and tokens',
                    'market_cap_weight': 0.05
                }
            ]
            
            for sector_data in sample_sectors:
                sector, created = Sector.objects.get_or_create(
                    name=sector_data['name'],
                    defaults={
                        'display_name': sector_data['display_name'],
                        'description': sector_data['description'],
                        'market_cap_weight': sector_data['market_cap_weight'],
                        'is_active': True
                    }
                )
                
                if created:
                    logger.info(f"Created sector: {sector.display_name}")
            
            logger.info("Sample sector data created successfully")
            
        except Exception as e:
            logger.error(f"Error creating sample sectors: {e}")


