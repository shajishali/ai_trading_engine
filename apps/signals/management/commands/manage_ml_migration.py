"""
Django management command to manage ML migration phases
"""

from django.core.management.base import BaseCommand, CommandError
from apps.signals.ml_migration_service import MLMigrationService, MigrationPhase


class Command(BaseCommand):
    help = 'Manage ML migration phases and configuration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--phase',
            type=str,
            choices=['parallel_running', 'ab_testing', 'full_migration', 'rollback'],
            help='Set migration phase'
        )
        parser.add_argument(
            '--ml-weight',
            type=float,
            help='ML signal weight for parallel running (0.0-1.0)'
        )
        parser.add_argument(
            '--ml-min-confidence',
            type=float,
            help='Minimum confidence threshold for ML signals (0.0-1.0)'
        )
        parser.add_argument(
            '--ab-split',
            type=float,
            help='A/B test split ratio (0.0-1.0, e.g., 0.5 = 50% ML, 50% rule-based)'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show migration statistics'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for statistics (default: 7)'
        )
    
    def handle(self, *args, **options):
        service = MLMigrationService()
        
        # Show current status
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ML MIGRATION MANAGEMENT'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write(f"Current Phase: {service.phase.value}")
        self.stdout.write(f"ML Model: {service.config['ml_model_name']}")
        self.stdout.write('')
        
        # Set phase
        if options['phase']:
            phase_map = {
                'parallel_running': MigrationPhase.PARALLEL_RUNNING,
                'ab_testing': MigrationPhase.AB_TESTING,
                'full_migration': MigrationPhase.FULL_MIGRATION,
                'rollback': MigrationPhase.ROLLBACK
            }
            service.set_phase(phase_map[options['phase']])
            self.stdout.write(self.style.SUCCESS(f"Phase set to: {options['phase']}"))
            self.stdout.write('')
        
        # Update configuration
        config_updates = {}
        if options['ml_weight'] is not None:
            if not 0.0 <= options['ml_weight'] <= 1.0:
                raise CommandError("ML weight must be between 0.0 and 1.0")
            config_updates['ml_weight'] = options['ml_weight']
        
        if options['ml_min_confidence'] is not None:
            if not 0.0 <= options['ml_min_confidence'] <= 1.0:
                raise CommandError("ML min confidence must be between 0.0 and 1.0")
            config_updates['ml_min_confidence'] = options['ml_min_confidence']
        
        if options['ab_split'] is not None:
            if not 0.0 <= options['ab_split'] <= 1.0:
                raise CommandError("A/B split must be between 0.0 and 1.0")
            config_updates['ab_test_split'] = options['ab_split']
        
        if config_updates:
            service.set_config(**config_updates)
            self.stdout.write(self.style.SUCCESS("Configuration updated:"))
            for key, value in config_updates.items():
                self.stdout.write(f"  {key}: {value}")
            self.stdout.write('')
        
        # Show statistics
        if options['stats']:
            stats = service.get_migration_stats(days=options['days'])
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('MIGRATION STATISTICS'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write('')
            self.stdout.write(f"Period: Last {stats['period_days']} days")
            self.stdout.write(f"Current Phase: {stats['phase']}")
            self.stdout.write('')
            
            self.stdout.write("ML Signals:")
            self.stdout.write(f"  Count: {stats['ml_signals']['count']}")
            self.stdout.write(f"  Avg Confidence: {stats['ml_signals']['avg_confidence']:.2%}")
            self.stdout.write(f"  Executed: {stats['ml_signals']['executed']}")
            self.stdout.write(f"  Profitable: {stats['ml_signals']['profitable']}")
            self.stdout.write(f"  Win Rate: {stats['ml_signals']['win_rate']:.2%}")
            self.stdout.write('')
            
            self.stdout.write("Rule-Based Signals:")
            self.stdout.write(f"  Count: {stats['rule_based_signals']['count']}")
            self.stdout.write(f"  Avg Confidence: {stats['rule_based_signals']['avg_confidence']:.2%}")
            self.stdout.write(f"  Executed: {stats['rule_based_signals']['executed']}")
            self.stdout.write(f"  Profitable: {stats['rule_based_signals']['profitable']}")
            self.stdout.write(f"  Win Rate: {stats['rule_based_signals']['win_rate']:.2%}")
            self.stdout.write('')
            
            self.stdout.write(f"Total Signals: {stats['total_signals']}")
            self.stdout.write(f"ML Percentage: {stats['ml_percentage']:.1f}%")
            self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))

