"""
Management command to run backtests for Phase 2
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
from apps.signals.models import Symbol
from apps.signals.backtesting_service import Phase2BacktestingService
from apps.signals.strategy_engine import StrategyEngine


class Command(BaseCommand):
    help = 'Run backtests for trading strategies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='Symbol to backtest (e.g., BTCUSDT)',
            default='BTCUSDT'
        )
        parser.add_argument(
            '--strategy',
            type=str,
            help='Strategy name to test',
            default='SMA_Crossover'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD)',
            default=(timezone.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD)',
            default=timezone.now().strftime('%Y-%m-%d')
        )
        parser.add_argument(
            '--initial-capital',
            type=float,
            help='Initial capital for backtest',
            default=10000.0
        )
        parser.add_argument(
            '--commission-rate',
            type=float,
            help='Commission rate (e.g., 0.001 for 0.1%)',
            default=0.001
        )
        parser.add_argument(
            '--slippage-rate',
            type=float,
            help='Slippage rate (e.g., 0.0005 for 0.05%)',
            default=0.0005
        )
        parser.add_argument(
            '--all-symbols',
            action='store_true',
            help='Run backtest for all active symbols'
        )

    def handle(self, *args, **options):
        try:
            # Parse dates and make them timezone-aware
            from django.utils import timezone
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
            
            # Make timezone-aware
            start_date = timezone.make_aware(start_date)
            end_date = timezone.make_aware(end_date)
            
            if start_date >= end_date:
                raise CommandError('Start date must be before end date')
            
            # Get symbols to backtest
            if options['all_symbols']:
                symbols = Symbol.objects.filter(is_active=True)
                self.stdout.write(f"Running backtests for {symbols.count()} symbols")
            else:
                try:
                    symbols = [Symbol.objects.get(symbol=options['symbol'])]
                except Symbol.DoesNotExist:
                    raise CommandError(f"Symbol '{options['symbol']}' not found")
            
            # Initialize backtesting service
            backtest_service = Phase2BacktestingService(
                initial_capital=options['initial_capital'],
                commission_rate=options['commission_rate'],
                slippage_rate=options['slippage_rate']
            )
            
            # Run backtests
            results = []
            for symbol in symbols:
                self.stdout.write(f"Running backtest for {symbol.symbol}...")
                
                try:
                    # Initialize strategy engine
                    strategy_engine = StrategyEngine()
                    
                    # Run backtest
                    result = backtest_service.run_backtest(
                        symbol=symbol,
                        strategy_name=options['strategy'],
                        start_date=start_date,
                        end_date=end_date,
                        strategy_engine=strategy_engine
                    )
                    
                    results.append(result)
                    
                    # Display results
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {symbol.symbol}: {result.total_return_percentage:.2f}% return, "
                            f"{result.win_rate:.1%} win rate, {result.total_trades} trades"
                        )
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ {symbol.symbol}: Error - {e}")
                    )
            
            # Summary
            if results:
                self.stdout.write("\n" + "="*50)
                self.stdout.write("BACKTEST SUMMARY")
                self.stdout.write("="*50)
                
                total_return = sum(r.total_return_percentage for r in results) / len(results)
                avg_win_rate = sum(r.win_rate for r in results) / len(results)
                total_trades = sum(r.total_trades for r in results)
                
                self.stdout.write(f"Average Return: {total_return:.2f}%")
                self.stdout.write(f"Average Win Rate: {avg_win_rate:.1%}")
                self.stdout.write(f"Total Trades: {total_trades}")
                
                # Best and worst performers
                best_result = max(results, key=lambda r: r.total_return_percentage)
                worst_result = min(results, key=lambda r: r.total_return_percentage)
                
                self.stdout.write(f"\nBest Performer: {best_result.symbol.symbol} ({best_result.total_return_percentage:.2f}%)")
                self.stdout.write(f"Worst Performer: {worst_result.symbol.symbol} ({worst_result.total_return_percentage:.2f}%)")
                
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Backtest completed successfully! {len(results)} results saved.")
                )
            else:
                self.stdout.write(
                    self.style.WARNING("No backtest results generated.")
                )
                
        except Exception as e:
            raise CommandError(f"Backtest failed: {e}")
