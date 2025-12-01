"""
ML Signal Training Service
Trains models on strategy + sentiment + news data
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import joblib
import os
from pathlib import Path
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
import xgboost as xgb
import lightgbm as lgb
from django.utils import timezone

from apps.signals.models import TradingSignal
from apps.signals.ml_feature_engineering_service import MLFeatureEngineeringService
from apps.trading.models import Symbol

logger = logging.getLogger(__name__)


class MLSignalTrainingService:
    """Service to train ML models for signal generation"""
    
    def __init__(self):
        self.feature_service = MLFeatureEngineeringService()
        # Get absolute path for model storage
        backend_dir = Path(__file__).resolve().parent.parent.parent
        self.model_path = backend_dir / 'ml_models' / 'signals'
        self.model_path.mkdir(parents=True, exist_ok=True)
    
    def prepare_training_data(
        self,
        symbols: List[Symbol],
        start_date: datetime,
        end_date: datetime,
        prediction_horizon_hours: int = 24
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from historical signals
        
        X: Features (strategy + sentiment + news)
        y: Signal labels (BUY=1, SELL=-1, HOLD=0)
        """
        try:
            all_features = []
            all_labels = []
            
            logger.info(f"Preparing training data for {len(symbols)} symbols")
            
            for symbol in symbols:
                # Get historical signals - use all signals, not just executed ones
                # (since we may not have many executed signals)
                historical_signals = TradingSignal.objects.filter(
                    symbol=symbol,
                    created_at__gte=start_date,
                    created_at__lte=end_date
                ).order_by('created_at').select_related('signal_type')
                
                if not historical_signals.exists():
                    logger.debug(f"No signals found for {symbol.symbol}")
                    continue
                
                signal_count = 0
                # For each signal, get features at the time it was created
                for signal in historical_signals:
                    try:
                        # Get features at signal creation time
                        # Note: We use current time for feature extraction since we can't go back in time
                        # In production, you might want to store features with signals
                        features_df = self.feature_service.prepare_features_for_symbol(
                            symbol=symbol,
                            prediction_horizon_hours=prediction_horizon_hours
                        )
                        
                        if features_df.empty:
                            continue
                        
                        # Get label from signal type
                        signal_type_name = signal.signal_type.name if hasattr(signal, 'signal_type') and signal.signal_type else 'HOLD'
                        
                        # Map to 0, 1, 2 for multi-class classification (HOLD=0, BUY=1, SELL=2)
                        if signal_type_name in ['BUY', 'STRONG_BUY']:
                            label = 1
                        elif signal_type_name in ['SELL', 'STRONG_SELL']:
                            label = 2
                        else:
                            label = 0  # HOLD
                        
                        # Only use if signal was profitable (optional filter)
                        # Uncomment if you want to filter by profitability
                        # if signal.is_profitable is not None and not signal.is_profitable:
                        #     continue
                        
                        all_features.append(features_df.iloc[0].to_dict())
                        all_labels.append(label)
                        signal_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing signal {signal.id}: {e}", exc_info=True)
                        continue
                
                logger.info(f"Processed {signal_count} signals for {symbol.symbol}")
            
            if not all_features:
                logger.warning("No training data prepared")
                return pd.DataFrame(), pd.Series()
            
            X = pd.DataFrame(all_features)
            y = pd.Series(all_labels)
            
            logger.info(f"Prepared training data: {len(X)} samples, {len(X.columns)} features")
            logger.info(f"Label distribution: HOLD={sum(y==0)}, BUY={sum(y==1)}, SELL={sum(y==2)}")
            
            # Check if we have at least 2 classes and ensure label 0 exists
            unique_labels = set(y)
            
            # XGBoost requires labels to start from 0, so we need at least one HOLD sample
            if 0 not in unique_labels:
                logger.warning(f"Label 0 (HOLD) not found in training data. Adding synthetic HOLD samples...")
                # Add some HOLD samples by duplicating existing samples with label 0
                # This is a workaround - in production, you'd want more diverse data
                if len(X) > 0:
                    # Add at least 10% of samples as HOLD, minimum 5 samples
                    hold_samples = max(5, min(10, len(X) // 10))
                    for i in range(hold_samples):
                        idx = i % len(X)
                        all_features.append(X.iloc[idx].to_dict())
                        all_labels.append(0)  # HOLD
                    
                    X = pd.DataFrame(all_features)
                    y = pd.Series(all_labels)
                    logger.info(f"Added {hold_samples} HOLD samples. New distribution: HOLD={sum(y==0)}, BUY={sum(y==1)}, SELL={sum(y==2)}")
            
            # Also check if we have at least 2 classes
            unique_labels = set(y)
            if len(unique_labels) < 2:
                logger.warning(f"Only {len(unique_labels)} class(es) in training data. Adding more synthetic samples...")
                # Add samples from the minority class
                if len(X) > 0:
                    minority_class = min(unique_labels, key=lambda x: sum(y == x))
                    samples_to_add = max(5, len(X) // 10)
                    for i in range(samples_to_add):
                        idx = i % len(X)
                        all_features.append(X.iloc[idx].to_dict())
                        all_labels.append(minority_class)
                    
                    X = pd.DataFrame(all_features)
                    y = pd.Series(all_labels)
                    logger.info(f"Added {samples_to_add} samples for class {minority_class}. New distribution: HOLD={sum(y==0)}, BUY={sum(y==1)}, SELL={sum(y==2)}")
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preparing training data: {e}", exc_info=True)
            return pd.DataFrame(), pd.Series()
    
    def train_xgboost_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_name: str = 'signal_xgboost'
    ) -> Tuple[xgb.XGBClassifier, StandardScaler, Dict]:
        """Train XGBoost model for signal classification"""
        try:
            if X.empty or len(y) == 0:
                raise ValueError("Empty training data provided")
            
            # Handle missing values
            X = X.fillna(0)
            
            # Ensure training set has at least one sample from each class
            unique_labels_in_data = set(y)
            logger.info(f"Unique labels in full dataset: {sorted(unique_labels_in_data)}")
            
            # Check if we have enough data for time series split
            if len(X) < 10:
                logger.warning(f"Not enough data for time series split ({len(X)} samples). Using simple split.")
                # Simple train-test split, but ensure all classes are in training set
                split_idx = int(len(X) * 0.8)
                train_idx = list(range(split_idx))
                test_idx = list(range(split_idx, len(X)))
            else:
                # Split data (time series split to avoid data leakage)
                tscv = TimeSeriesSplit(n_splits=min(5, len(X) // 2))
                splits = list(tscv.split(X))
                train_idx, test_idx = splits[-1]  # Use last split
                # Convert to lists to allow modification
                train_idx = train_idx.tolist() if hasattr(train_idx, 'tolist') else list(train_idx)
                test_idx = test_idx.tolist() if hasattr(test_idx, 'tolist') else list(test_idx)
            
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Ensure training set has all classes
            unique_labels_in_train = set(y_train)
            if unique_labels_in_data != unique_labels_in_train:
                logger.warning(f"Training set missing classes. Full: {sorted(unique_labels_in_data)}, Train: {sorted(unique_labels_in_train)}")
                # Move at least one sample from each missing class from test to train
                for missing_label in unique_labels_in_data - unique_labels_in_train:
                    # Find indices in test set with this label
                    test_label_indices = [i for i, label in enumerate(y_test) if label == missing_label]
                    if test_label_indices:
                        # Move first sample to training set
                        move_idx = test_label_indices[0]
                        # Get the actual index in the original dataset
                        original_test_idx = test_idx[move_idx]
                        train_idx.append(original_test_idx)
                        test_idx.remove(original_test_idx)
                        logger.info(f"Moved sample with label {missing_label} from test to training set")
                
                # Recreate train/test sets
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            logger.info(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples")
            logger.info(f"Training set labels: {sorted(set(y_train))}, Distribution: HOLD={sum(y_train==0)}, BUY={sum(y_train==1)}, SELL={sum(y_train==2)}")
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train XGBoost model
            model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric='mlogloss',
                use_label_encoder=False
            )
            
            # Train model (try different early stopping approaches based on XGBoost version)
            try:
                # Try with early stopping using callbacks (XGBoost 2.1+)
                import xgboost as xgb_module
                if hasattr(xgb_module, 'callback') and hasattr(xgb_module.callback, 'EarlyStopping'):
                    model.fit(
                        X_train_scaled,
                        y_train,
                        eval_set=[(X_test_scaled, y_test)],
                        callbacks=[xgb_module.callback.EarlyStopping(rounds=20, save_best=True)],
                        verbose=False
                    )
                else:
                    # Try old API
                    model.fit(
                        X_train_scaled,
                        y_train,
                        eval_set=[(X_test_scaled, y_test)],
                        early_stopping_rounds=20,
                        verbose=False
                    )
            except (TypeError, AttributeError, ValueError) as e:
                # If early stopping not supported, train without it
                logger.warning(f"Early stopping not available, training without it: {e}")
                model.fit(
                    X_train_scaled,
                    y_train,
                    verbose=False
                )
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            
            metrics = {
                'accuracy': float(accuracy),
                'precision': float(precision),
                'recall': float(recall),
                'f1_score': float(f1),
                'classification_report': classification_report(y_test, y_pred, zero_division=0),
                'train_samples': len(X_train),
                'test_samples': len(X_test)
            }
            
            logger.info(f"XGBoost model trained - Accuracy: {accuracy:.3f}, F1: {f1:.3f}")
            
            # Save model
            model_path = self.model_path / f"{model_name}_model.pkl"
            scaler_path = self.model_path / f"{model_name}_scaler.pkl"
            
            joblib.dump(model, model_path)
            joblib.dump(scaler, scaler_path)
            
            logger.info(f"Model saved to {model_path}")
            logger.info(f"Scaler saved to {scaler_path}")
            
            return model, scaler, metrics
            
        except Exception as e:
            logger.error(f"Error training XGBoost model: {e}", exc_info=True)
            raise
    
    def train_lightgbm_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_name: str = 'signal_lightgbm'
    ) -> Tuple[lgb.LGBMClassifier, StandardScaler, Dict]:
        """Train LightGBM model for signal classification"""
        try:
            if X.empty or len(y) == 0:
                raise ValueError("Empty training data provided")
            
            # Handle missing values
            X = X.fillna(0)
            
            # Ensure training set has at least one sample from each class
            unique_labels_in_data = set(y)
            logger.info(f"Unique labels in full dataset: {sorted(unique_labels_in_data)}")
            
            # Check if we have enough data for time series split
            if len(X) < 10:
                logger.warning(f"Not enough data for time series split ({len(X)} samples). Using simple split.")
                # Simple train-test split, but ensure all classes are in training set
                split_idx = int(len(X) * 0.8)
                train_idx = list(range(split_idx))
                test_idx = list(range(split_idx, len(X)))
            else:
                # Split data
                tscv = TimeSeriesSplit(n_splits=min(5, len(X) // 2))
                splits = list(tscv.split(X))
                train_idx, test_idx = splits[-1]
                # Convert to lists to allow modification
                train_idx = train_idx.tolist() if hasattr(train_idx, 'tolist') else list(train_idx)
                test_idx = test_idx.tolist() if hasattr(test_idx, 'tolist') else list(test_idx)
            
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Ensure training set has all classes
            unique_labels_in_train = set(y_train)
            if unique_labels_in_data != unique_labels_in_train:
                logger.warning(f"Training set missing classes. Full: {sorted(unique_labels_in_data)}, Train: {sorted(unique_labels_in_train)}")
                # Move at least one sample from each missing class from test to train
                for missing_label in unique_labels_in_data - unique_labels_in_train:
                    # Find indices in test set with this label
                    test_label_indices = [i for i, label in enumerate(y_test) if label == missing_label]
                    if test_label_indices:
                        # Move first sample to training set
                        move_idx = test_label_indices[0]
                        # Get the actual index in the original dataset
                        original_test_idx = test_idx[move_idx]
                        train_idx.append(original_test_idx)
                        test_idx.remove(original_test_idx)
                        logger.info(f"Moved sample with label {missing_label} from test to training set")
                
                # Recreate train/test sets
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            logger.info(f"Training set: {len(X_train)} samples, Test set: {len(X_test)} samples")
            logger.info(f"Training set labels: {sorted(set(y_train))}, Distribution: HOLD={sum(y_train==0)}, BUY={sum(y_train==1)}, SELL={sum(y_train==2)}")
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train LightGBM model
            model = lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1
            )
            
            model.fit(
                X_train_scaled,
                y_train,
                eval_set=[(X_test_scaled, y_test)],
                callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False), lgb.log_evaluation(0)]
            )
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            
            metrics = {
                'accuracy': float(accuracy),
                'precision': float(precision),
                'recall': float(recall),
                'f1_score': float(f1),
                'classification_report': classification_report(y_test, y_pred, zero_division=0),
                'train_samples': len(X_train),
                'test_samples': len(X_test)
            }
            
            logger.info(f"LightGBM model trained - Accuracy: {accuracy:.3f}, F1: {f1:.3f}")
            
            # Save model
            model_path = self.model_path / f"{model_name}_model.pkl"
            scaler_path = self.model_path / f"{model_name}_scaler.pkl"
            
            joblib.dump(model, model_path)
            joblib.dump(scaler, scaler_path)
            
            logger.info(f"Model saved to {model_path}")
            logger.info(f"Scaler saved to {scaler_path}")
            
            return model, scaler, metrics
            
        except Exception as e:
            logger.error(f"Error training LightGBM model: {e}", exc_info=True)
            raise

