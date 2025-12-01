"""
Django management command to train ML models for signal generation
"""

from django.core.management.base import BaseCommand
from apps.signals.ml_signal_training_service import MLSignalTrainingService
from apps.trading.models import Symbol
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train ML models for signal generation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model-type',
            type=str,
            default='xgboost',
            choices=['xgboost', 'lightgbm', 'both'],
            help='Type of model to train (default: xgboost)'
        )
        parser.add_argument(
            '--lookback-days',
            type=int,
            default=90,
            help='Number of days of historical data to use for training (default: 90)'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            nargs='+',
            help='Specific symbols to use for training (default: all active crypto symbols)'
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=50,
            help='Minimum number of training samples required (default: 50)'
        )
    
    def handle(self, *args, **options):
        model_type = options['model_type']
        lookback_days = options['lookback_days']
        symbol_names = options.get('symbols')
        min_samples = options['min_samples']
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ML MODEL TRAINING FOR SIGNAL GENERATION'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        
        # Get symbols
        if symbol_names:
            symbols = Symbol.objects.filter(
                symbol__in=symbol_names,
                is_active=True,
                is_crypto_symbol=True
            )
            self.stdout.write(f'Training on specified symbols: {", ".join(symbol_names)}')
        else:
            symbols = Symbol.objects.filter(is_active=True, is_crypto_symbol=True)
            self.stdout.write(f'Training on all active crypto symbols: {symbols.count()} symbols')
        
        if not symbols.exists():
            self.stdout.write(self.style.ERROR('No active crypto symbols found!'))
            return
        
        self.stdout.write('')
        self.stdout.write(f'Model type: {model_type}')
        self.stdout.write(f'Lookback period: {lookback_days} days')
        self.stdout.write('')
        
        # Prepare training data
        self.stdout.write('Preparing training data...')
        end_date = timezone.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        training_service = MLSignalTrainingService()
        
        try:
            X, y = training_service.prepare_training_data(
                symbols=list(symbols),
                start_date=start_date,
                end_date=end_date
            )
            
            if X.empty:
                self.stdout.write(self.style.ERROR('No training data available!'))
                self.stdout.write('')
                self.stdout.write('Possible reasons:')
                self.stdout.write('  - No historical signals in the specified date range')
                self.stdout.write('  - Signals don\'t have required market data')
                self.stdout.write('  - Feature extraction failed')
                return
            
            self.stdout.write(self.style.SUCCESS(f'Training data prepared: {len(X)} samples, {len(X.columns)} features'))
            self.stdout.write(f'Label distribution: HOLD={sum(y==0)}, BUY={sum(y==1)}, SELL={sum(y==2)}')
            self.stdout.write('')
            
            if len(X) < min_samples:
                self.stdout.write(self.style.WARNING(
                    f'Warning: Only {len(X)} samples available (minimum recommended: {min_samples})'
                ))
                self.stdout.write('Model may not perform well with limited data.')
                response = input('Continue anyway? (y/n): ')
                if response.lower() != 'y':
                    self.stdout.write('Training cancelled.')
                    return
                self.stdout.write('')
            
            # Train model(s)
            if model_type == 'both':
                models_to_train = ['xgboost', 'lightgbm']
            else:
                models_to_train = [model_type]
            
            for mt in models_to_train:
                self.stdout.write('-' * 60)
                self.stdout.write(f'Training {mt.upper()} model...')
                self.stdout.write('-' * 60)
                
                try:
                    if mt == 'xgboost':
                        model, scaler, metrics = training_service.train_xgboost_model(
                            X, y, model_name='signal_xgboost'
                        )
                    else:
                        model, scaler, metrics = training_service.train_lightgbm_model(
                            X, y, model_name='signal_lightgbm'
                        )
                    
                    self.stdout.write('')
                    self.stdout.write(self.style.SUCCESS(f'{mt.upper()} Model Training Results:'))
                    self.stdout.write(f'  Accuracy:  {metrics["accuracy"]:.3f}')
                    self.stdout.write(f'  Precision: {metrics["precision"]:.3f}')
                    self.stdout.write(f'  Recall:    {metrics["recall"]:.3f}')
                    self.stdout.write(f'  F1 Score:  {metrics["f1_score"]:.3f}')
                    self.stdout.write('')
                    self.stdout.write('Classification Report:')
                    self.stdout.write(metrics['classification_report'])
                    self.stdout.write('')
                    self.stdout.write(self.style.SUCCESS(f'{mt.upper()} model saved successfully!'))
                    self.stdout.write('')
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error training {mt} model: {e}'))
                    logger.error(f'Error training {mt} model', exc_info=True)
                    continue
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('TRAINING COMPLETED'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
            self.stdout.write('Next Steps:')
            self.stdout.write('1. Proceed to Phase 5: ML Signal Generation Service')
            self.stdout.write('2. Test signal generation with trained models')
            self.stdout.write('3. Integrate ML models into signal generation pipeline')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during training: {e}'))
            logger.error('Error during training', exc_info=True)
            raise

