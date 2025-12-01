"""
ML Signal Generation Service
Uses trained ML models to generate trading signals
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import joblib
import os
from pathlib import Path
from decimal import Decimal
from django.utils import timezone

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal, SignalType
from apps.signals.ml_feature_engineering_service import MLFeatureEngineeringService
from apps.data.models import MarketData

logger = logging.getLogger(__name__)


class MLSignalGenerationService:
    """Service to generate trading signals using trained ML models"""
    
    def __init__(self, model_name: str = 'signal_xgboost'):
        """
        Initialize ML signal generation service
        
        Args:
            model_name: Name of the model to use ('signal_xgboost' or 'signal_lightgbm')
        """
        self.model_name = model_name
        self.model_path = Path(__file__).parent.parent.parent / 'ml_models' / 'signals'
        self.model = None
        self.scaler = None
        self.feature_service = MLFeatureEngineeringService()
        
        # Load model and scaler
        self._load_model()
    
    def _load_model(self):
        """Load trained model and scaler from disk"""
        try:
            model_file = self.model_path / f"{self.model_name}_model.pkl"
            scaler_file = self.model_path / f"{self.model_name}_scaler.pkl"
            
            if not model_file.exists():
                raise FileNotFoundError(f"Model file not found: {model_file}")
            if not scaler_file.exists():
                raise FileNotFoundError(f"Scaler file not found: {scaler_file}")
            
            self.model = joblib.load(model_file)
            self.scaler = joblib.load(scaler_file)
            
            logger.info(f"Loaded {self.model_name} model and scaler successfully")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}", exc_info=True)
            raise
    
    def generate_signals_for_symbol(
        self,
        symbol: Symbol,
        prediction_horizon_hours: int = 24,
        min_confidence: float = 0.5
    ) -> List[TradingSignal]:
        """
        Generate trading signals for a symbol using ML model
        
        Args:
            symbol: Symbol to generate signals for
            prediction_horizon_hours: Prediction horizon in hours
            min_confidence: Minimum confidence score to create a signal (0-1)
        
        Returns:
            List of TradingSignal objects
        """
        try:
            # Prepare features
            features_df = self.feature_service.prepare_features_for_symbol(
                symbol=symbol,
                prediction_horizon_hours=prediction_horizon_hours
            )
            
            if features_df.empty:
                logger.warning(f"No features available for {symbol.symbol}")
                return []
            
            # Scale features
            features_scaled = self.scaler.transform(features_df)
            
            # Get prediction
            prediction = self.model.predict(features_scaled)[0]
            
            # Get prediction probabilities (confidence scores)
            try:
                probabilities = self.model.predict_proba(features_scaled)[0]
                # Map class indices to probabilities
                confidence_scores = {
                    0: probabilities[0] if len(probabilities) > 0 else 0.0,  # HOLD
                    1: probabilities[1] if len(probabilities) > 1 else 0.0,  # BUY
                    2: probabilities[2] if len(probabilities) > 2 else 0.0,  # SELL
                }
            except Exception as e:
                logger.warning(f"Could not get prediction probabilities: {e}")
                # Fallback: use prediction as confidence
                confidence_scores = {
                    0: 1.0 if prediction == 0 else 0.0,
                    1: 1.0 if prediction == 1 else 0.0,
                    2: 1.0 if prediction == 2 else 0.0,
                }
            
            signals = []
            
            # Map prediction to signal type
            # 0 = HOLD, 1 = BUY, 2 = SELL
            if prediction == 0:
                # HOLD - don't create a signal unless confidence is very high
                if confidence_scores[0] >= 0.9:
                    signal_type_name = 'HOLD'
                    confidence = confidence_scores[0]
                else:
                    # If HOLD confidence is not high, don't create signal
                    logger.info(f"HOLD prediction for {symbol.symbol} with confidence {confidence_scores[0]:.2f} - skipping")
                    return []
            elif prediction == 1:
                signal_type_name = 'BUY'
                confidence = confidence_scores[1]
            elif prediction == 2:
                signal_type_name = 'SELL'
                confidence = confidence_scores[2]
            else:
                logger.warning(f"Unknown prediction value: {prediction}")
                return []
            
            # Check minimum confidence threshold
            # For SELL signals, use slightly lower threshold to ensure we get SELL signals
            threshold = min_confidence if signal_type_name != 'SELL' else min_confidence * 0.9
            
            if confidence < threshold:
                logger.debug(f"Prediction confidence {confidence:.2f} below threshold {threshold} for {symbol.symbol} ({signal_type_name})")
                return []
            
            # Get or create signal type
            signal_type, _ = SignalType.objects.get_or_create(
                name=signal_type_name,
                defaults={'description': f'ML-generated {signal_type_name} signal'}
            )
            
            # Get current market price
            latest_market_data = MarketData.objects.filter(
                symbol=symbol
            ).order_by('-timestamp').first()
            
            entry_price = None
            if latest_market_data:
                entry_price = latest_market_data.close_price
            
            # Calculate signal strength based on confidence
            if confidence >= 0.85:
                strength = 'VERY_STRONG'
            elif confidence >= 0.70:
                strength = 'STRONG'
            elif confidence >= 0.55:
                strength = 'MODERATE'
            else:
                strength = 'WEAK'
            
            # Calculate confidence level
            if confidence >= 0.85:
                confidence_level = 'VERY_HIGH'
            elif confidence >= 0.70:
                confidence_level = 'HIGH'
            elif confidence >= 0.50:
                confidence_level = 'MEDIUM'
            else:
                confidence_level = 'LOW'
            
            # Calculate quality score (combination of confidence and other factors)
            quality_score = confidence
            
            # Create trading signal
            signal = TradingSignal.objects.create(
                symbol=symbol,
                signal_type=signal_type,
                strength=strength,
                confidence_score=confidence,
                confidence_level=confidence_level,
                entry_price=entry_price,
                timeframe='1H',
                entry_point_type='TREND_FOLLOWING',
                quality_score=quality_score,
                is_valid=True,
                metadata={
                    'model_name': self.model_name,
                    'prediction_horizon_hours': prediction_horizon_hours,
                    'prediction': int(prediction),
                    'all_probabilities': {
                        'HOLD': float(confidence_scores[0]),
                        'BUY': float(confidence_scores[1]),
                        'SELL': float(confidence_scores[2]),
                    }
                },
                notes=f"Generated by ML model ({self.model_name})"
            )
            
            signals.append(signal)
            logger.info(f"Generated {signal_type_name} signal for {symbol.symbol} with confidence {confidence:.2f}")
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals for {symbol.symbol}: {e}", exc_info=True)
            return []
    
    def generate_signals_for_all_symbols(
        self,
        symbols: Optional[List[Symbol]] = None,
        prediction_horizon_hours: int = 24,
        min_confidence: float = 0.5
    ) -> Dict[str, List[TradingSignal]]:
        """
        Generate signals for multiple symbols
        
        Args:
            symbols: List of symbols to generate signals for (None = all active crypto symbols)
            prediction_horizon_hours: Prediction horizon in hours
            min_confidence: Minimum confidence score to create a signal
        
        Returns:
            Dictionary mapping symbol names to lists of signals
        """
        if symbols is None:
            symbols = list(Symbol.objects.filter(is_active=True, is_crypto_symbol=True))
        
        results = {}
        for symbol in symbols:
            try:
                signals = self.generate_signals_for_symbol(
                    symbol=symbol,
                    prediction_horizon_hours=prediction_horizon_hours,
                    min_confidence=min_confidence
                )
                if signals:
                    results[symbol.symbol] = signals
            except Exception as e:
                logger.error(f"Error generating signals for {symbol.symbol}: {e}")
                continue
        
        logger.info(f"Generated signals for {len(results)} symbols")
        return results

