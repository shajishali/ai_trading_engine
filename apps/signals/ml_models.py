"""
Phase 3 ML Models
Machine Learning models for trading signal enhancement
"""

from django.db import models
from django.utils import timezone
from decimal import Decimal
import json


class MLModel(models.Model):
    """Base model for storing ML model information"""
    
    MODEL_TYPES = [
        ('XGBOOST', 'XGBoost'),
        ('LIGHTGBM', 'LightGBM'),
        ('LSTM', 'LSTM'),
        ('GRU', 'GRU'),
        ('TRANSFORMER', 'Transformer'),
        ('ENSEMBLE', 'Ensemble'),
    ]
    
    MODEL_STATUS = [
        ('TRAINING', 'Training'),
        ('TRAINED', 'Trained'),
        ('DEPLOYED', 'Deployed'),
        ('ARCHIVED', 'Archived'),
        ('FAILED', 'Failed'),
    ]
    
    # Basic information
    name = models.CharField(max_length=200)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    version = models.CharField(max_length=20, default='1.0')
    status = models.CharField(max_length=20, choices=MODEL_STATUS, default='TRAINING')
    
    # Model configuration
    target_variable = models.CharField(max_length=50, help_text="Target variable (e.g., 'next_return', 'signal_direction')")
    prediction_horizon = models.IntegerField(help_text="Prediction horizon in hours")
    features_used = models.JSONField(default=list, help_text="List of features used in training")
    
    # Training parameters
    training_start_date = models.DateTimeField()
    training_end_date = models.DateTimeField()
    validation_start_date = models.DateTimeField()
    validation_end_date = models.DateTimeField()
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    auc_score = models.FloatField(null=True, blank=True)
    mse = models.FloatField(null=True, blank=True, help_text="Mean Squared Error")
    mae = models.FloatField(null=True, blank=True, help_text="Mean Absolute Error")
    
    # Model files and metadata
    model_file_path = models.CharField(max_length=500, null=True, blank=True)
    scaler_file_path = models.CharField(max_length=500, null=True, blank=True)
    feature_importance = models.JSONField(default=dict, blank=True)
    hyperparameters = models.JSONField(default=dict, blank=True)
    
    # Training metadata
    training_samples = models.IntegerField(null=True, blank=True)
    validation_samples = models.IntegerField(null=True, blank=True)
    training_time_seconds = models.IntegerField(null=True, blank=True)
    
    # Deployment information
    deployed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    confidence_threshold = models.FloatField(default=0.7, help_text="Minimum confidence for predictions")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'ML Model'
        verbose_name_plural = 'ML Models'
        indexes = [
            models.Index(fields=['model_type', 'status']),
            models.Index(fields=['is_active', 'deployed_at']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.model_type}) - v{self.version}"
    
    @property
    def is_deployed(self):
        """Check if model is currently deployed"""
        return self.status == 'DEPLOYED' and self.is_active
    
    @property
    def performance_score(self):
        """Calculate overall performance score"""
        if self.model_type in ['XGBOOST', 'LIGHTGBM']:
            # For classification models, use F1 score
            return self.f1_score or 0.0
        else:
            # For regression models, use negative MSE (higher is better)
            return -(self.mae or 0.0)


class MLPrediction(models.Model):
    """Store ML model predictions"""
    
    PREDICTION_TYPES = [
        ('SIGNAL_DIRECTION', 'Signal Direction (Buy/Sell/Hold)'),
        ('PRICE_CHANGE', 'Price Change Prediction'),
        ('VOLATILITY', 'Volatility Prediction'),
        ('SENTIMENT', 'Sentiment Prediction'),
        ('RISK_SCORE', 'Risk Score'),
    ]
    
    # Prediction information
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    symbol = models.ForeignKey('trading.Symbol', on_delete=models.CASCADE)
    prediction_type = models.CharField(max_length=20, choices=PREDICTION_TYPES)
    
    # Prediction data
    prediction_value = models.FloatField()
    confidence_score = models.FloatField()
    prediction_probabilities = models.JSONField(default=dict, blank=True)
    
    # Input features used
    input_features = models.JSONField(default=dict, blank=True)
    feature_values = models.JSONField(default=dict, blank=True)
    
    # Prediction context
    prediction_timestamp = models.DateTimeField()
    prediction_horizon_hours = models.IntegerField()
    actual_value = models.FloatField(null=True, blank=True, help_text="Actual value when available")
    
    # Performance tracking
    is_correct = models.BooleanField(null=True, blank=True)
    prediction_error = models.FloatField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'ML Prediction'
        verbose_name_plural = 'ML Predictions'
        indexes = [
            models.Index(fields=['model', 'symbol', 'prediction_timestamp']),
            models.Index(fields=['prediction_type', 'prediction_timestamp']),
            models.Index(fields=['confidence_score']),
        ]
        ordering = ['-prediction_timestamp']
    
    def __str__(self):
        return f"{self.model.name} - {self.symbol.symbol} - {self.prediction_value:.4f}"


class MLFeature(models.Model):
    """Store feature engineering information"""
    
    FEATURE_TYPES = [
        ('TECHNICAL', 'Technical Indicator'),
        ('PRICE', 'Price-based Feature'),
        ('VOLUME', 'Volume-based Feature'),
        ('SENTIMENT', 'Sentiment Feature'),
        ('FUNDAMENTAL', 'Fundamental Feature'),
        ('TIME', 'Time-based Feature'),
        ('DERIVED', 'Derived Feature'),
    ]
    
    # Feature information
    name = models.CharField(max_length=100, unique=True)
    feature_type = models.CharField(max_length=20, choices=FEATURE_TYPES)
    description = models.TextField()
    
    # Feature calculation
    calculation_method = models.CharField(max_length=200, help_text="How the feature is calculated")
    parameters = models.JSONField(default=dict, blank=True)
    dependencies = models.JSONField(default=list, blank=True, help_text="Other features this depends on")
    
    # Feature properties
    is_lagging = models.BooleanField(default=False, help_text="Does this feature use future data?")
    lag_periods = models.IntegerField(default=0, help_text="Number of periods to lag")
    window_size = models.IntegerField(null=True, blank=True, help_text="Window size for calculations")
    
    # Usage tracking
    models_using = models.JSONField(default=list, blank=True, help_text="Models that use this feature")
    importance_score = models.FloatField(null=True, blank=True, help_text="Average feature importance")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'ML Feature'
        verbose_name_plural = 'ML Features'
        indexes = [
            models.Index(fields=['feature_type', 'is_active']),
            models.Index(fields=['name']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.feature_type})"


class MLTrainingSession(models.Model):
    """Track ML model training sessions"""
    
    SESSION_STATUS = [
        ('STARTED', 'Started'),
        ('DATA_PREPARATION', 'Data Preparation'),
        ('FEATURE_ENGINEERING', 'Feature Engineering'),
        ('TRAINING', 'Training'),
        ('VALIDATION', 'Validation'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    # Session information
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    session_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='STARTED')
    
    # Training configuration
    training_config = models.JSONField(default=dict, blank=True)
    hyperparameters = models.JSONField(default=dict, blank=True)
    
    # Progress tracking
    current_step = models.CharField(max_length=50, default='Started')
    progress_percentage = models.FloatField(default=0.0)
    
    # Performance tracking
    training_loss = models.JSONField(default=list, blank=True)
    validation_loss = models.JSONField(default=list, blank=True)
    training_metrics = models.JSONField(default=dict, blank=True)
    validation_metrics = models.JSONField(default=dict, blank=True)
    
    # Timing information
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_traceback = models.TextField(blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'ML Training Session'
        verbose_name_plural = 'ML Training Sessions'
        indexes = [
            models.Index(fields=['model', 'status']),
            models.Index(fields=['started_at']),
        ]
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.session_name} - {self.model.name} ({self.status})"
    
    @property
    def is_completed(self):
        """Check if training session is completed"""
        return self.status == 'COMPLETED'
    
    @property
    def is_failed(self):
        """Check if training session failed"""
        return self.status == 'FAILED'


class MLModelPerformance(models.Model):
    """Track ML model performance over time"""
    
    # Performance information
    model = models.ForeignKey(MLModel, on_delete=models.CASCADE)
    evaluation_date = models.DateTimeField()
    
    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    auc_score = models.FloatField(null=True, blank=True)
    mse = models.FloatField(null=True, blank=True)
    mae = models.FloatField(null=True, blank=True)
    
    # Prediction statistics
    total_predictions = models.IntegerField(default=0)
    correct_predictions = models.IntegerField(default=0)
    avg_confidence = models.FloatField(null=True, blank=True)
    
    # Performance context
    evaluation_period_days = models.IntegerField(default=30)
    symbols_evaluated = models.JSONField(default=list, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'ML Model Performance'
        verbose_name_plural = 'ML Model Performances'
        indexes = [
            models.Index(fields=['model', 'evaluation_date']),
            models.Index(fields=['evaluation_date']),
        ]
        ordering = ['-evaluation_date']
    
    def __str__(self):
        return f"{self.model.name} - {self.evaluation_date.date()} - Acc: {self.accuracy:.3f}"
    
    @property
    def win_rate(self):
        """Calculate win rate"""
        if self.total_predictions > 0:
            return self.correct_predictions / self.total_predictions
        return 0.0

