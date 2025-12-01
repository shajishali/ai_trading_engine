from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.signals.models import SignalType, SignalFactor
from apps.trading.models import Symbol


class Command(BaseCommand):
    help = 'Set up signal generation system with initial data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample-signals',
            action='store_true',
            help='Create sample signals for testing',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up Signal Generation System...')
        )

        # Create signal types
        self.create_signal_types()
        
        # Create signal factors
        self.create_signal_factors()
        
        # Create sample signals if requested
        if options['create_sample_signals']:
            self.create_sample_signals()

        self.stdout.write(
            self.style.SUCCESS('Signal Generation System setup completed!')
        )

    def create_signal_types(self):
        """Create signal types"""
        self.stdout.write('Creating signal types...')
        
        signal_types = [
            {
                'name': 'BUY',
                'description': 'Buy signal - indicates bullish sentiment',
                'color': '#28a745'
            },
            {
                'name': 'SELL',
                'description': 'Sell signal - indicates bearish sentiment',
                'color': '#dc3545'
            },
            {
                'name': 'HOLD',
                'description': 'Hold signal - indicates neutral sentiment',
                'color': '#ffc107'
            },
            {
                'name': 'STRONG_BUY',
                'description': 'Strong buy signal - high confidence bullish signal',
                'color': '#20c997'
            },
            {
                'name': 'STRONG_SELL',
                'description': 'Strong sell signal - high confidence bearish signal',
                'color': '#e83e8c'
            }
        ]
        
        for signal_type_data in signal_types:
            signal_type, created = SignalType.objects.get_or_create(
                name=signal_type_data['name'],
                defaults={
                    'description': signal_type_data['description'],
                    'color': signal_type_data['color'],
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created signal type: {signal_type.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Signal type already exists: {signal_type.name}')
                )

    def create_signal_factors(self):
        """Create signal factors"""
        self.stdout.write('Creating signal factors...')
        
        signal_factors = [
            {
                'name': 'Technical Analysis',
                'factor_type': 'TECHNICAL',
                'weight': 0.35,
                'description': 'Technical indicators analysis (RSI, MACD, Moving Averages)'
            },
            {
                'name': 'Sentiment Analysis',
                'factor_type': 'SENTIMENT',
                'weight': 0.25,
                'description': 'Social media and news sentiment analysis'
            },
            {
                'name': 'News Impact',
                'factor_type': 'NEWS',
                'weight': 0.15,
                'description': 'News event impact analysis'
            },
            {
                'name': 'Volume Analysis',
                'factor_type': 'VOLUME',
                'weight': 0.15,
                'description': 'Volume pattern analysis'
            },
            {
                'name': 'Pattern Recognition',
                'factor_type': 'PATTERN',
                'weight': 0.10,
                'description': 'Chart pattern analysis'
            }
        ]
        
        for factor_data in signal_factors:
            factor, created = SignalFactor.objects.get_or_create(
                name=factor_data['name'],
                defaults={
                    'factor_type': factor_data['factor_type'],
                    'weight': factor_data['weight'],
                    'description': factor_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created signal factor: {factor.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Signal factor already exists: {factor.name}')
                )

    def create_sample_signals(self):
        """Create sample signals for testing"""
        self.stdout.write('Creating sample signals...')
        
        try:
            from apps.signals.services import SignalGenerationService
            from apps.signals.models import TradingSignal
            
            # Get active symbols
            active_symbols = Symbol.objects.filter(is_active=True)[:5]
            
            if not active_symbols.exists():
                self.stdout.write(
                    self.style.WARNING('No active symbols found. Skipping sample signal creation.')
                )
                return
            
            signal_service = SignalGenerationService()
            total_signals = 0
            
            for symbol in active_symbols:
                try:
                    # Generate signals for symbol
                    signals = signal_service.generate_signals_for_symbol(symbol)
                    total_signals += len(signals)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Generated {len(signals)} signals for {symbol.symbol}')
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error generating signals for {symbol.symbol}: {e}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Created {total_signals} sample signals')
            )
            
        except ImportError:
            self.stdout.write(
                self.style.WARNING('Signal generation service not available. Skipping sample signal creation.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating sample signals: {e}')
            )
