from django.core.management.base import BaseCommand
from apps.signals.smc_pattern_recognition_service import SMCPatternRecognitionService
from apps.signals.models import ChartImage, ChartPattern
from apps.trading.models import Symbol
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Detect and label SMC patterns for chart images (Phase 5.2)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of symbol codes to detect patterns for',
        )
        parser.add_argument(
            '--timeframes',
            type=str,
            default='1H,4H,1D',
            help='Comma-separated list of timeframes (default: 1H,4H,1D)',
        )
        parser.add_argument(
            '--pattern-types',
            type=str,
            default='bos,choch,order_blocks,fvg,liquidity_sweeps',
            help='Comma-separated list of pattern types to detect',
        )
        parser.add_argument(
            '--charts-limit',
            type=int,
            default=100,
            help='Maximum number of charts to process per symbol (default: 100)',
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.6,
            help='Minimum confidence score for patterns (default: 0.6)',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing patterns before detection',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting SMC pattern detection (Phase 5.2)...')
        
        # Initialize SMC pattern recognition service
        smc_service = SMCPatternRecognitionService()
        
        # Get symbols to process
        if options['symbols']:
            symbol_codes = [s.strip().upper() for s in options['symbols'].split(',')]
            symbols = Symbol.objects.filter(symbol__in=symbol_codes, is_active=True)
        else:
            symbols = Symbol.objects.filter(is_active=True)[:5]  # Default to first 5
        
        timeframes = options['timeframes'].split(',')
        pattern_types = options['pattern_types'].split(',')
        
        self.stdout.write(f'Processing {symbols.count()} symbols...')
        self.stdout.write(f'Timeframes: {", ".join(timeframes)}')
        self.stdout.write(f'Pattern types: {", ".join(pattern_types)}')
        
        # Clear existing patterns if requested
        if options['clear_existing']:
            self.stdout.write('Clearing existing patterns...')
            ChartPattern.objects.all().delete()
            self.stdout.write('Existing patterns cleared.')
        
        total_stats = {
            'symbols_processed': 0,
            'charts_processed': 0,
            'patterns_detected': 0,
            'patterns_saved': 0,
            'bos_count': 0,
            'choch_count': 0,
            'order_blocks_count': 0,
            'fvg_count': 0,
            'liquidity_sweeps_count': 0
        }
        
        for symbol in symbols:
            try:
                total_stats['symbols_processed'] += 1
                self.stdout.write(f'\nProcessing {symbol.symbol}...')
                
                symbol_stats = {
                    'charts_processed': 0,
                    'patterns_detected': 0,
                    'patterns_saved': 0,
                    'bos_count': 0,
                    'choch_count': 0,
                    'order_blocks_count': 0,
                    'fvg_count': 0,
                    'liquidity_sweeps_count': 0
                }
                
                for timeframe in timeframes:
                    timeframe = timeframe.strip()
                    
                    # Get chart images for this symbol and timeframe
                    chart_images = ChartImage.objects.filter(
                        symbol=symbol,
                        timeframe=timeframe,
                        is_training_data=True
                    ).order_by('-created_at')[:options['charts_limit']]
                    
                    if not chart_images.exists():
                        self.stdout.write(f'  No charts found for {symbol.symbol} - {timeframe}')
                        continue
                    
                    self.stdout.write(f'  Processing {chart_images.count()} charts for {timeframe}...')
                    
                    for chart_image in chart_images:
                        try:
                            # Detect patterns for this chart
                            patterns = smc_service.detect_patterns_for_chart(chart_image)
                            
                            if patterns:
                                symbol_stats['charts_processed'] += 1
                                
                                # Filter patterns by type and confidence
                                filtered_patterns = {}
                                for pattern_type, pattern_list in patterns.items():
                                    if pattern_type in pattern_types:
                                        filtered_list = [
                                            p for p in pattern_list 
                                            if p.confidence_score >= options['min_confidence']
                                        ]
                                        if filtered_list:
                                            filtered_patterns[pattern_type] = filtered_list
                                
                                # Count patterns by type
                                for pattern_type, pattern_list in filtered_patterns.items():
                                    count = len(pattern_list)
                                    symbol_stats['patterns_detected'] += count
                                    
                                    if pattern_type == 'bos':
                                        symbol_stats['bos_count'] += count
                                    elif pattern_type == 'choch':
                                        symbol_stats['choch_count'] += count
                                    elif pattern_type == 'order_blocks':
                                        symbol_stats['order_blocks_count'] += count
                                    elif pattern_type == 'fvg':
                                        symbol_stats['fvg_count'] += count
                                    elif pattern_type == 'liquidity_sweeps':
                                        symbol_stats['liquidity_sweeps_count'] += count
                                
                                # Save patterns to database
                                saved_count = smc_service.save_patterns_to_database(filtered_patterns)
                                symbol_stats['patterns_saved'] += saved_count
                                
                                if saved_count > 0:
                                    self.stdout.write(
                                        f'    ✓ Chart {chart_image.id}: {saved_count} patterns saved'
                                    )
                            
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'    ✗ Error processing chart {chart_image.id}: {e}'
                                )
                            )
                    
                    # Display timeframe summary
                    if symbol_stats['charts_processed'] > 0:
                        self.stdout.write(
                            f'  {timeframe} Summary: {symbol_stats["charts_processed"]} charts, '
                            f'{symbol_stats["patterns_detected"]} patterns detected, '
                            f'{symbol_stats["patterns_saved"]} patterns saved'
                        )
                
                # Display symbol summary
                if symbol_stats['charts_processed'] > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ {symbol.symbol} completed: '
                            f'{symbol_stats["charts_processed"]} charts, '
                            f'{symbol_stats["patterns_detected"]} patterns detected, '
                            f'{symbol_stats["patterns_saved"]} patterns saved'
                        )
                    )
                    
                    # Display pattern breakdown
                    if symbol_stats['bos_count'] > 0:
                        self.stdout.write(f'    BOS: {symbol_stats["bos_count"]}')
                    if symbol_stats['choch_count'] > 0:
                        self.stdout.write(f'    CHoCH: {symbol_stats["choch_count"]}')
                    if symbol_stats['order_blocks_count'] > 0:
                        self.stdout.write(f'    Order Blocks: {symbol_stats["order_blocks_count"]}')
                    if symbol_stats['fvg_count'] > 0:
                        self.stdout.write(f'    FVG: {symbol_stats["fvg_count"]}')
                    if symbol_stats['liquidity_sweeps_count'] > 0:
                        self.stdout.write(f'    Liquidity Sweeps: {symbol_stats["liquidity_sweeps_count"]}')
                
                # Update total stats
                for key in symbol_stats:
                    total_stats[key] += symbol_stats[key]
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing symbol {symbol.symbol}: {e}')
                )
        
        # Display final summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSMC Pattern Detection Completed!\n'
                f'Symbols processed: {total_stats["symbols_processed"]}\n'
                f'Charts processed: {total_stats["charts_processed"]}\n'
                f'Patterns detected: {total_stats["patterns_detected"]}\n'
                f'Patterns saved: {total_stats["patterns_saved"]}\n'
                f'\nPattern Breakdown:\n'
                f'  BOS: {total_stats["bos_count"]}\n'
                f'  CHoCH: {total_stats["choch_count"]}\n'
                f'  Order Blocks: {total_stats["order_blocks_count"]}\n'
                f'  FVG: {total_stats["fvg_count"]}\n'
                f'  Liquidity Sweeps: {total_stats["liquidity_sweeps_count"]}'
            )
        )

