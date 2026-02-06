"""
Phase 3 ML Inference Service
Live prediction service for deployed ML models
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import joblib
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from django.utils import timezone
from django.db import transaction

from apps.signals.models import MLModel, MLPrediction, MLFeature
from apps.signals.ml_data_service import MLDataCollectionService
from apps.trading.models import Symbol
from apps.data.models import MarketData

logger = logging.getLogger(__name__)


class MLInferenceService:
    """Service for making live predictions with trained ML models"""
    
    def __init__(self):
        self.logger = logger
        self.data_service = MLDataCollectionService()
        self.model_cache = {}
        self.scaler_cache = {}
    
    def predict_signal_direction(self, symbol: Symbol, model_name: Optional[str] = None,
                                prediction_horizon_hours: int = 24) -> Dict[str, Any]:
        """
        Predict signal direction for a symbol using deployed ML models
        
        Args:
            symbol: Symbol to predict for
            model_name: Specific model to use (if None, uses best active model)
            prediction_horizon_hours: Hours ahead to predict
            
        Returns:
            Dictionary with prediction results
        """
        try:
            # Get the best active model
            if model_name:
                model = MLModel.objects.get(name=model_name, is_active=True)
            else:
                model = self._get_best_active_model('signal_direction')
            
            if not model:
                raise ValueError("No active ML model found for signal direction prediction")
            
            # Get recent data
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)  # Get last 30 days of data
            
            recent_data = self.data_service.collect_training_data(
                [symbol], start_date, end_date, prediction_horizon_hours
            )
            
            if recent_data.empty:
                raise ValueError(f"No recent data available for {symbol.symbol}")
            
            # Prepare features
            X, feature_names = self._prepare_prediction_features(recent_data, model)
            
            # Load model and scaler
            ml_model, scaler = self._load_model_and_scaler(model)
            
            # Make prediction
            prediction_result = self._make_prediction(ml_model, scaler, X, model)
            
            # Store prediction
            prediction = MLPrediction.objects.create(
                model=model,
                symbol=symbol,
                prediction_type='SIGNAL_DIRECTION',
                prediction_value=prediction_result['prediction'],
                confidence_score=prediction_result['confidence'],
                prediction_probabilities=prediction_result.get('probabilities', {}),
                input_features=dict(zip(feature_names, X.flatten())),
                prediction_timestamp=timezone.now(),
                prediction_horizon_hours=prediction_horizon_hours
            )
            
            return {
                'prediction_id': prediction.id,
                'symbol': symbol.symbol,
                'model_name': model.name,
                'prediction': prediction_result['prediction'],
                'confidence': prediction_result['confidence'],
                'probabilities': prediction_result.get('probabilities', {}),
                'prediction_horizon_hours': prediction_horizon_hours,
                'timestamp': prediction.prediction_timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error predicting signal direction for {symbol.symbol}: {e}")
            raise e
    
    def predict_signal_direction_as_of_date(
        self,
        symbol: Symbol,
        as_of_date: datetime,
        model_name: Optional[str] = None,
        prediction_horizon_hours: int = 24,
        store_prediction: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Predict signal direction for a symbol as of a historical date (for backtesting / Search Signals).
        Uses data up to as_of_date only. Returns None if no model or no data.
        """
        try:
            if as_of_date.tzinfo is None:
                as_of_date = timezone.make_aware(as_of_date)
            if model_name:
                model = MLModel.objects.get(name=model_name, is_active=True)
            else:
                model = self._get_best_active_model('signal_direction')
            if not model:
                return None
            end_date = as_of_date
            start_date = end_date - timedelta(days=30)
            recent_data = self.data_service.collect_training_data(
                [symbol], start_date, end_date, prediction_horizon_hours
            )
            if recent_data.empty or len(recent_data) < 2:
                return None
            X, feature_names = self._prepare_prediction_features(recent_data, model)
            ml_model, scaler = self._load_model_and_scaler(model)
            prediction_result = self._make_prediction(ml_model, scaler, X, model)
            pred_value = prediction_result['prediction']
            direction = 'BUY' if (pred_value == 1 or (isinstance(pred_value, (int, float)) and pred_value > 0.5)) else 'SELL'
            if store_prediction:
                MLPrediction.objects.create(
                    model=model,
                    symbol=symbol,
                    prediction_type='SIGNAL_DIRECTION',
                    prediction_value=pred_value,
                    confidence_score=prediction_result['confidence'],
                    prediction_probabilities=prediction_result.get('probabilities', {}),
                    input_features=dict(zip(feature_names, X.flatten().tolist())),
                    prediction_timestamp=as_of_date,
                    prediction_horizon_hours=prediction_horizon_hours
                )
            return {
                'symbol': symbol.symbol,
                'model_name': model.name,
                'prediction': pred_value,
                'direction': direction,
                'confidence': prediction_result['confidence'],
                'probabilities': prediction_result.get('probabilities', {}),
            }
        except Exception as e:
            self.logger.debug(f"ML prediction as of date for {symbol.symbol} skipped: {e}")
            return None

    def predict_price_change(self, symbol: Symbol, model_name: Optional[str] = None,
                           prediction_horizon_hours: int = 24) -> Dict[str, Any]:
        """Predict price change for a symbol"""
        try:
            # Get the best active model for price prediction
            if model_name:
                model = MLModel.objects.get(name=model_name, is_active=True)
            else:
                model = self._get_best_active_model('target_return')
            
            if not model:
                raise ValueError("No active ML model found for price change prediction")
            
            # Get recent data
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)
            
            recent_data = self.data_service.collect_training_data(
                [symbol], start_date, end_date, prediction_horizon_hours
            )
            
            if recent_data.empty:
                raise ValueError(f"No recent data available for {symbol.symbol}")
            
            # Prepare features
            X, feature_names = self._prepare_prediction_features(recent_data, model)
            
            # Load model and scaler
            ml_model, scaler = self._load_model_and_scaler(model)
            
            # Make prediction
            prediction_result = self._make_prediction(ml_model, scaler, X, model)
            
            # Store prediction
            prediction = MLPrediction.objects.create(
                model=model,
                symbol=symbol,
                prediction_type='PRICE_CHANGE',
                prediction_value=prediction_result['prediction'],
                confidence_score=prediction_result['confidence'],
                input_features=dict(zip(feature_names, X.flatten())),
                prediction_timestamp=timezone.now(),
                prediction_horizon_hours=prediction_horizon_hours
            )
            
            return {
                'prediction_id': prediction.id,
                'symbol': symbol.symbol,
                'model_name': model.name,
                'predicted_return': prediction_result['prediction'],
                'confidence': prediction_result['confidence'],
                'prediction_horizon_hours': prediction_horizon_hours,
                'timestamp': prediction.prediction_timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error predicting price change for {symbol.symbol}: {e}")
            raise e
    
    def predict_volatility(self, symbol: Symbol, model_name: Optional[str] = None,
                          prediction_horizon_hours: int = 24) -> Dict[str, Any]:
        """Predict volatility for a symbol"""
        try:
            # Get the best active model for volatility prediction
            if model_name:
                model = MLModel.objects.get(name=model_name, is_active=True)
            else:
                model = self._get_best_active_model('target_volatility')
            
            if not model:
                raise ValueError("No active ML model found for volatility prediction")
            
            # Similar implementation to price change prediction
            end_date = timezone.now()
            start_date = end_date - timedelta(days=30)
            
            recent_data = self.data_service.collect_training_data(
                [symbol], start_date, end_date, prediction_horizon_hours
            )
            
            if recent_data.empty:
                raise ValueError(f"No recent data available for {symbol.symbol}")
            
            X, feature_names = self._prepare_prediction_features(recent_data, model)
            ml_model, scaler = self._load_model_and_scaler(model)
            prediction_result = self._make_prediction(ml_model, scaler, X, model)
            
            prediction = MLPrediction.objects.create(
                model=model,
                symbol=symbol,
                prediction_type='VOLATILITY',
                prediction_value=prediction_result['prediction'],
                confidence_score=prediction_result['confidence'],
                input_features=dict(zip(feature_names, X.flatten())),
                prediction_timestamp=timezone.now(),
                prediction_horizon_hours=prediction_horizon_hours
            )
            
            return {
                'prediction_id': prediction.id,
                'symbol': symbol.symbol,
                'model_name': model.name,
                'predicted_volatility': prediction_result['prediction'],
                'confidence': prediction_result['confidence'],
                'prediction_horizon_hours': prediction_horizon_hours,
                'timestamp': prediction.prediction_timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error predicting volatility for {symbol.symbol}: {e}")
            raise e
    
    def get_ensemble_prediction(self, symbol: Symbol, prediction_horizon_hours: int = 24) -> Dict[str, Any]:
        """
        Get ensemble prediction combining multiple models
        
        Args:
            symbol: Symbol to predict for
            prediction_horizon_hours: Hours ahead to predict
            
        Returns:
            Dictionary with ensemble prediction results
        """
        try:
            # Get all active models
            active_models = MLModel.objects.filter(
                is_active=True,
                status='DEPLOYED'
            ).order_by('-performance_score')
            
            if not active_models.exists():
                raise ValueError("No active models available for ensemble prediction")
            
            predictions = []
            model_weights = []
            
            # Get predictions from each model
            for model in active_models:
                try:
                    if model.target_variable == 'signal_direction':
                        pred_result = self.predict_signal_direction(symbol, model.name, prediction_horizon_hours)
                        predictions.append(pred_result['prediction'])
                        model_weights.append(model.performance_score or 0.5)
                    elif model.target_variable == 'target_return':
                        pred_result = self.predict_price_change(symbol, model.name, prediction_horizon_hours)
                        predictions.append(pred_result['predicted_return'])
                        model_weights.append(model.performance_score or 0.5)
                except Exception as e:
                    self.logger.warning(f"Failed to get prediction from model {model.name}: {e}")
                    continue
            
            if not predictions:
                raise ValueError("No valid predictions obtained from any model")
            
            # Calculate weighted ensemble prediction
            weights = np.array(model_weights)
            weights = weights / weights.sum()  # Normalize weights
            
            if len(set(predictions)) == 1:
                # All models agree
                ensemble_prediction = predictions[0]
                ensemble_confidence = 1.0
            else:
                # Weighted average
                ensemble_prediction = np.average(predictions, weights=weights)
                ensemble_confidence = 1.0 - np.std(predictions) / (np.mean(np.abs(predictions)) + 1e-8)
            
            return {
                'symbol': symbol.symbol,
                'ensemble_prediction': ensemble_prediction,
                'ensemble_confidence': ensemble_confidence,
                'individual_predictions': predictions,
                'model_weights': weights.tolist(),
                'models_used': len(predictions),
                'prediction_horizon_hours': prediction_horizon_hours,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting ensemble prediction for {symbol.symbol}: {e}")
            raise e
    
    def _get_best_active_model(self, target_variable: str) -> Optional[MLModel]:
        """Get the best active model for a specific target variable"""
        try:
            models = MLModel.objects.filter(
                target_variable=target_variable,
                is_active=True,
                status='DEPLOYED'
            ).order_by('-performance_score')
            
            return models.first()
            
        except Exception as e:
            self.logger.error(f"Error getting best active model: {e}")
            return None
    
    def _prepare_prediction_features(self, data: pd.DataFrame, model: MLModel) -> Tuple[np.ndarray, List[str]]:
        """Prepare features for prediction"""
        try:
            # Use the same features as training
            feature_names = model.features_used
            
            if not feature_names:
                raise ValueError(f"No features defined for model {model.name}")
            
            # Select only the features used in training
            available_features = [f for f in feature_names if f in data.columns]
            
            if len(available_features) != len(feature_names):
                missing_features = set(feature_names) - set(available_features)
                self.logger.warning(f"Missing features for {model.name}: {missing_features}")
            
            # Get the latest data point
            latest_data = data[available_features].iloc[-1:].values
            
            # Handle missing values
            latest_data = np.nan_to_num(latest_data, nan=0.0)
            
            return latest_data, available_features
            
        except Exception as e:
            self.logger.error(f"Error preparing prediction features: {e}")
            raise e
    
    def _load_model_and_scaler(self, model: MLModel) -> Tuple[Any, Any]:
        """Load model and scaler from cache or disk"""
        try:
            model_key = f"{model.name}_{model.version}"
            
            # Check cache first
            if model_key in self.model_cache:
                return self.model_cache[model_key], self.scaler_cache[model_key]
            
            # Load model
            if model.model_type in ['LSTM', 'GRU']:
                # Keras model
                ml_model = tf.keras.models.load_model(model.model_file_path.replace('.pkl', '.h5'))
            else:
                # Sklearn/XGBoost/LightGBM model
                ml_model = joblib.load(model.model_file_path)
            
            # Load scaler
            scaler = joblib.load(model.scaler_file_path)
            
            # Cache for future use
            self.model_cache[model_key] = ml_model
            self.scaler_cache[model_key] = scaler
            
            return ml_model, scaler
            
        except Exception as e:
            self.logger.error(f"Error loading model and scaler: {e}")
            raise e
    
    def _make_prediction(self, ml_model: Any, scaler: StandardScaler, X: np.ndarray, model: MLModel) -> Dict[str, Any]:
        """Make prediction using loaded model"""
        try:
            # Scale features
            X_scaled = scaler.transform(X)
            
            # Make prediction
            if hasattr(ml_model, 'predict_proba'):
                # Classification model with probabilities
                probabilities = ml_model.predict_proba(X_scaled)[0]
                prediction = ml_model.predict(X_scaled)[0]
                confidence = np.max(probabilities)
                
                # Convert probabilities to dictionary
                if len(probabilities) == 2:
                    prob_dict = {'class_0': probabilities[0], 'class_1': probabilities[1]}
                else:
                    prob_dict = {f'class_{i}': prob for i, prob in enumerate(probabilities)}
                
                return {
                    'prediction': prediction,
                    'confidence': confidence,
                    'probabilities': prob_dict
                }
            else:
                # Regression model
                prediction = ml_model.predict(X_scaled)[0]
                
                # Estimate confidence based on model type
                if hasattr(ml_model, 'predict'):
                    # For regression, confidence is based on prediction magnitude
                    confidence = min(1.0, abs(prediction) / 0.1)  # Normalize to 0-1
                else:
                    confidence = 0.5  # Default confidence
                
                return {
                    'prediction': prediction,
                    'confidence': confidence
                }
                
        except Exception as e:
            self.logger.error(f"Error making prediction: {e}")
            raise e
    
    def update_prediction_accuracy(self, prediction_id: int, actual_value: float):
        """Update prediction with actual value and calculate accuracy"""
        try:
            prediction = MLPrediction.objects.get(id=prediction_id)
            
            # Update actual value
            prediction.actual_value = actual_value
            
            # Calculate accuracy
            if prediction.prediction_type == 'SIGNAL_DIRECTION':
                # For classification
                predicted_direction = 1 if prediction.prediction_value > 0 else -1
                actual_direction = 1 if actual_value > 0 else -1
                prediction.is_correct = (predicted_direction == actual_direction)
            else:
                # For regression
                prediction.prediction_error = abs(prediction.prediction_value - actual_value)
                prediction.is_correct = prediction.prediction_error < 0.05  # 5% threshold
            
            prediction.save()
            
            self.logger.info(f"Updated prediction {prediction_id} with actual value {actual_value}")
            
        except Exception as e:
            self.logger.error(f"Error updating prediction accuracy: {e}")
    
    def get_model_performance_summary(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get performance summary for models"""
        try:
            if model_name:
                models = MLModel.objects.filter(name=model_name)
            else:
                models = MLModel.objects.filter(is_active=True)
            
            summary = {
                'total_models': models.count(),
                'active_models': models.filter(is_active=True).count(),
                'deployed_models': models.filter(status='DEPLOYED').count(),
                'model_performance': []
            }
            
            for model in models:
                # Get recent predictions
                recent_predictions = MLPrediction.objects.filter(
                    model=model,
                    prediction_timestamp__gte=timezone.now() - timedelta(days=30)
                )
                
                if recent_predictions.exists():
                    correct_predictions = recent_predictions.filter(is_correct=True).count()
                    total_predictions = recent_predictions.count()
                    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
                    
                    avg_confidence = recent_predictions.aggregate(
                        avg_conf=models.Avg('confidence_score')
                    )['avg_conf'] or 0
                else:
                    accuracy = 0
                    avg_confidence = 0
                
                summary['model_performance'].append({
                    'model_name': model.name,
                    'model_type': model.model_type,
                    'target_variable': model.target_variable,
                    'status': model.status,
                    'is_active': model.is_active,
                    'performance_score': model.performance_score,
                    'recent_accuracy': accuracy,
                    'avg_confidence': avg_confidence,
                    'total_predictions': recent_predictions.count()
                })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting model performance summary: {e}")
            return {}
