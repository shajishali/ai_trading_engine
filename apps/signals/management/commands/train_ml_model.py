"""
Management command to train ML models for Phase 3
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
from apps.signals.models import MLModel, MLFeature
from apps.signals.ml_signal_training_service import MLSignalTrainingService
from apps.signals.ml_data_service import MLDataCollectionService
from apps.trading.models import Symbol


class Command(BaseCommand):
    help = 'Train ML models for trading signal enhancement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            type=str,
            choices=['XGBOOST', 'LIGHTGBM', 'LSTM'],
            help='Type of model to train',
            default='XGBOOST'
        )
        parser.add_argument(
            '--target',
            type=str,
            help='Target variable to predict',
            default='signal_direction'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            nargs='+',
            help='Symbols to train on (e.g., BTCUSDT ETHUSDT)',
            default=['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
        )
        parser.add_argument(
            '--training-days',
            type=int,
            help='Days of training data',
            default=180
        )
        parser.add_argument(
            '--prediction-horizon',
            type=int,
            help='Prediction horizon in hours',
            default=24
        )
        parser.add_argument(
            '--walk-forward',
            action='store_true',
            help='Perform walk-forward validation'
        )
        parser.add_argument(
            '--model-name',
            type=str,
            help='Custom model name',
            default=None
        )

    def handle(self, *args, **options):
        try:
            # Get symbols
            symbols = []
            for symbol_name in options['symbols']:
                try:
                    symbol = Symbol.objects.get(symbol=symbol_name)
                    symbols.append(symbol)
                except Symbol.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"Symbol {symbol_name} not found, skipping...")
                    )
            
            if not symbols:
                raise CommandError("No valid symbols found")
            
            self.stdout.write(f"Training {options['model_type']} model on {len(symbols)} symbols")
            
            # Initialize services
            training_service = MLTrainingService()
            data_service = MLDataCollectionService()
            
            # Create feature definitions
            self.stdout.write("Creating feature definitions...")
            data_service.create_feature_definitions()
            
            # Generate model name if not provided
            model_name = options['model_name'] or f"{options['model_type']}_{options['target']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if options['walk_forward']:
                # Perform walk-forward validation
                self.stdout.write("Starting walk-forward validation...")
                results = training_service.walk_forward_validation(
                    symbols=symbols,
                    model_type=options['model_type'],
                    target_variable=options['target'],
                    prediction_horizon_hours=options['prediction_horizon'],
                    training_window_days=options['training_days'],
                    validation_window_days=30
                )
                
                self.stdout.write(f"Walk-forward validation completed:")
                self.stdout.write(f"  Total folds: {results['overall_metrics']['total_folds']}")
                self.stdout.write(f"  Average accuracy: {results['overall_metrics']['avg_accuracy']:.3f}")
                self.stdout.write(f"  Average F1 score: {results['overall_metrics']['avg_f1_score']:.3f}")
                
            else:
                # Train single model
                self.stdout.write(f"Training {options['model_type']} model...")
                
                if options['model_type'] == 'XGBOOST':
                    model = training_service.train_xgboost_model(
                        symbols=symbols,
                        model_name=model_name,
                        target_variable=options['target'],
                        prediction_horizon_hours=options['prediction_horizon'],
                        training_days=options['training_days']
                    )
                elif options['model_type'] == 'LIGHTGBM':
                    model = training_service.train_lightgbm_model(
                        symbols=symbols,
                        model_name=model_name,
                        target_variable=options['target'],
                        prediction_horizon_hours=options['prediction_horizon'],
                        training_days=options['training_days']
                    )
                elif options['model_type'] == 'LSTM':
                    model = training_service.train_lstm_model(
                        symbols=symbols,
                        model_name=model_name,
                        target_variable=options['target'],
                        prediction_horizon_hours=options['prediction_horizon'],
                        training_days=options['training_days']
                    )
                
            # Display results
            self.stdout.write(
                self.style.SUCCESS(f"✓ Model {model.name} trained successfully!")
            )
            self.stdout.write(f"  Model ID: {model.id}")
            self.stdout.write(f"  Status: {model.status}")
            self.stdout.write(f"  Training samples: {model.training_samples}")
            self.stdout.write(f"  Validation samples: {model.validation_samples}")
            
            if model.accuracy:
                self.stdout.write(f"  Accuracy: {model.accuracy:.3f}")
            if model.f1_score:
                self.stdout.write(f"  F1 Score: {model.f1_score:.3f}")
            
            # Deploy model if performance is good
            if model.accuracy and model.accuracy > 0.6:
                model.status = 'DEPLOYED'
                model.deployed_at = timezone.now()
                model.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Model deployed automatically (accuracy > 0.6)")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠ Model not deployed (accuracy <= 0.6)")
                )
            
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ ML model training completed successfully!")
            )
            
        except Exception as e:
            raise CommandError(f"ML training failed: {e}")

