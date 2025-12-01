from django.core.management.base import BaseCommand
from apps.signals.smc_pattern_analysis_service import SMCPatternAnalysisService
from apps.trading.models import Symbol
import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Analyze SMC pattern statistics and performance (Phase 5.2)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            help='Comma-separated list of symbol codes to analyze',
        )
        parser.add_argument(
            '--timeframes',
            type=str,
            default='1H,4H,1D',
            help='Comma-separated list of timeframes (default: 1H,4H,1D)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Number of days back to analyze (default: 30)',
        )
        parser.add_argument(
            '--export-csv',
            action='store_true',
            help='Export analysis to CSV file',
        )
        parser.add_argument(
            '--export-json',
            action='store_true',
            help='Export analysis to JSON file',
        )
        parser.add_argument(
            '--top-patterns',
            type=int,
            default=10,
            help='Number of top performing patterns to show (default: 10)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting SMC pattern analysis (Phase 5.2)...')
        
        # Initialize SMC pattern analysis service
        analysis_service = SMCPatternAnalysisService()
        
        # Get symbols to analyze
        if options['symbols']:
            symbol_codes = [s.strip().upper() for s in options['symbols'].split(',')]
            symbols = Symbol.objects.filter(symbol__in=symbol_codes, is_active=True)
        else:
            symbols = Symbol.objects.filter(is_active=True)[:5]  # Default to first 5
        
        timeframes = options['timeframes'].split(',')
        
        self.stdout.write(f'Analyzing patterns for {symbols.count()} symbols...')
        self.stdout.write(f'Timeframes: {", ".join(timeframes)}')
        self.stdout.write(f'Analysis period: {options["days_back"]} days')
        
        # Analyze each symbol
        for symbol in symbols:
            try:
                self.stdout.write(f'\n=== Analyzing {symbol.symbol} ===')
                
                # Get pattern statistics
                stats = analysis_service.get_pattern_statistics(
                    symbol=symbol,
                    days_back=options['days_back']
                )
                
                if stats and stats['overview']['total_patterns'] > 0:
                    self._display_symbol_statistics(symbol, stats)
                    
                    # Analyze each timeframe
                    for timeframe in timeframes:
                        timeframe = timeframe.strip()
                        self.stdout.write(f'\n--- {timeframe} Analysis ---')
                        
                        timeframe_stats = analysis_service.get_pattern_statistics(
                            symbol=symbol,
                            timeframe=timeframe,
                            days_back=options['days_back']
                        )
                        
                        if timeframe_stats and timeframe_stats['overview']['total_patterns'] > 0:
                            self._display_timeframe_statistics(timeframe, timeframe_stats)
                        else:
                            self.stdout.write(f'  No patterns found for {timeframe}')
                
                else:
                    self.stdout.write(f'  No patterns found for {symbol.symbol}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error analyzing {symbol.symbol}: {e}')
                )
        
        # Overall analysis
        self.stdout.write(f'\n=== Overall Analysis ===')
        
        try:
            # Get overall statistics
            overall_stats = analysis_service.get_pattern_statistics(
                days_back=options['days_back']
            )
            
            if overall_stats and overall_stats['overview']['total_patterns'] > 0:
                self._display_overall_statistics(overall_stats)
                
                # Get performance metrics
                performance_metrics = analysis_service.get_pattern_performance_metrics()
                self._display_performance_metrics(performance_metrics)
                
                # Get top performing patterns
                top_patterns = analysis_service.get_top_performing_patterns(
                    limit=options['top_patterns']
                )
                self._display_top_patterns(top_patterns)
                
                # Export data if requested
                if options['export_csv'] or options['export_json']:
                    self._export_analysis_data(analysis_service, options)
            
            else:
                self.stdout.write('No patterns found for analysis')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error in overall analysis: {e}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('\nSMC pattern analysis completed!')
        )
    
    def _display_symbol_statistics(self, symbol, stats):
        """Display symbol statistics"""
        overview = stats['overview']
        pattern_breakdown = stats['pattern_breakdown']
        confidence_stats = stats['confidence_stats']
        
        self.stdout.write(
            f'Total Patterns: {overview["total_patterns"]} '
            f'(Validated: {overview["validated_patterns"]}, '
            f'Rate: {overview["validation_rate"]}%)'
        )
        
        self.stdout.write(f'Avg Confidence: {confidence_stats["avg_confidence"]}')
        
        self.stdout.write('Pattern Breakdown:')
        for pattern_type, data in pattern_breakdown.items():
            if data['count'] > 0:
                self.stdout.write(
                    f'  {pattern_type}: {data["count"]} '
                    f'({data["percentage"]:.1f}%, '
                    f'Avg Conf: {data["avg_confidence"]})'
                )
    
    def _display_timeframe_statistics(self, timeframe, stats):
        """Display timeframe statistics"""
        overview = stats['overview']
        pattern_breakdown = stats['pattern_breakdown']
        
        self.stdout.write(
            f'  Patterns: {overview["total_patterns"]} '
            f'(Validated: {overview["validated_patterns"]})'
        )
        
        for pattern_type, data in pattern_breakdown.items():
            if data['count'] > 0:
                self.stdout.write(
                    f'    {pattern_type}: {data["count"]} '
                    f'(Conf: {data["avg_confidence"]})'
                )
    
    def _display_overall_statistics(self, stats):
        """Display overall statistics"""
        overview = stats['overview']
        pattern_breakdown = stats['pattern_breakdown']
        confidence_stats = stats['confidence_stats']
        
        self.stdout.write(
            f'Total Patterns: {overview["total_patterns"]} '
            f'(Validated: {overview["validated_patterns"]}, '
            f'Rate: {overview["validation_rate"]}%)'
        )
        
        self.stdout.write(
            f'Confidence: Avg {confidence_stats["avg_confidence"]}, '
            f'Max {confidence_stats["max_confidence"]}, '
            f'Min {confidence_stats["min_confidence"]}'
        )
        
        self.stdout.write('Pattern Distribution:')
        for pattern_type, data in pattern_breakdown.items():
            if data['count'] > 0:
                self.stdout.write(
                    f'  {pattern_type}: {data["count"]} '
                    f'({data["percentage"]:.1f}%, '
                    f'Avg Conf: {data["avg_confidence"]})'
                )
    
    def _display_performance_metrics(self, performance_metrics):
        """Display performance metrics"""
        self.stdout.write('\nPerformance Metrics by Pattern Type:')
        
        for pattern_type, metrics in performance_metrics.items():
            if metrics['total_count'] > 0:
                self.stdout.write(
                    f'  {pattern_type}:'
                )
                self.stdout.write(
                    f'    Total: {metrics["total_count"]}, '
                    f'Validation Rate: {metrics["validation_rate"]}%, '
                    f'Avg Confidence: {metrics["avg_confidence"]}'
                )
                
                conf_dist = metrics['confidence_distribution']
                self.stdout.write(
                    f'    Confidence: High {conf_dist["high"]}, '
                    f'Medium {conf_dist["medium"]}, '
                    f'Low {conf_dist["low"]}'
                )
    
    def _display_top_patterns(self, top_patterns):
        """Display top performing patterns"""
        self.stdout.write(f'\nTop {len(top_patterns)} Performing Patterns:')
        
        for i, pattern in enumerate(top_patterns, 1):
            self.stdout.write(
                f'  {i}. {pattern["symbol"]} - {pattern["timeframe"]} - '
                f'{pattern["pattern_type"]} (Conf: {pattern["confidence_score"]:.3f})'
            )
    
    def _export_analysis_data(self, analysis_service, options):
        """Export analysis data"""
        try:
            if options['export_csv']:
                csv_data = analysis_service.export_pattern_analysis()
                filename = f'smc_pattern_analysis_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
                
                with open(filename, 'w') as f:
                    f.write(csv_data)
                
                self.stdout.write(f'CSV export saved to: {filename}')
            
            if options['export_json']:
                stats = analysis_service.get_pattern_statistics()
                performance = analysis_service.get_pattern_performance_metrics()
                trends = analysis_service.get_pattern_trends()
                top_patterns = analysis_service.get_top_performing_patterns()
                
                export_data = {
                    'statistics': stats,
                    'performance_metrics': performance,
                    'trends': trends,
                    'top_patterns': top_patterns,
                    'export_timestamp': timezone.now().isoformat()
                }
                
                filename = f'smc_pattern_analysis_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
                
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                self.stdout.write(f'JSON export saved to: {filename}')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error exporting data: {e}')
            )

