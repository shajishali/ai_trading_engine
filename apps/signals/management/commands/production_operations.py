from django.core.management.base import BaseCommand
from apps.signals.performance_optimization_service import (
    PerformanceOptimizationService, PerformanceMonitoringService, 
    ABTestingService, AutomatedRetrainingService
)
from apps.signals.caching_performance_service import (
    CachingService, PerformanceOptimizationService as PerfOptService, AsyncProcessingService
)
from apps.signals.production_deployment_config import PRODUCTION_CONFIGS
# Chart-based ML models removed - using signal generation ML only
# from apps.signals.models import ChartMLModel, ABTest, RetrainingTask, ModelPerformanceMetrics
from apps.signals.models import MLModel  # Use MLModel for signal generation instead
from apps.trading.models import Symbol
import logging
import json
import os

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Production operations for ML trading signals system (Phase 5.5)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=[
                'optimize', 'monitor', 'ab-test', 'retrain', 'cache', 'performance', 
                'deploy', 'status', 'health-check', 'backup', 'restore'
            ],
            default='status',
            help='Action to perform (default: status)',
        )
        parser.add_argument(
            '--model-id',
            type=int,
            help='Model ID for optimization, monitoring, or retraining',
        )
        parser.add_argument(
            '--optimization-type',
            type=str,
            choices=['quantization', 'pruning', 'full'],
            default='full',
            help='Type of model optimization (default: full)',
        )
        parser.add_argument(
            '--test-name',
            type=str,
            help='Name for A/B test',
        )
        parser.add_argument(
            '--model-b-id',
            type=int,
            help='Model B ID for A/B testing',
        )
        parser.add_argument(
            '--deployment-type',
            type=str,
            choices=['docker', 'kubernetes', 'local'],
            default='docker',
            help='Deployment type (default: docker)',
        )
        parser.add_argument(
            '--config-file',
            type=str,
            help='Configuration file path',
        )
        parser.add_argument(
            '--backup-path',
            type=str,
            help='Backup file path',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting Production Operations (Phase 5.5)...')
        
        action = options['action']
        
        if action == 'optimize':
            self._optimize_model(options)
        elif action == 'monitor':
            self._monitor_model(options)
        elif action == 'ab-test':
            self._ab_test_models(options)
        elif action == 'retrain':
            self._retrain_model(options)
        elif action == 'cache':
            self._manage_cache(options)
        elif action == 'performance':
            self._check_performance(options)
        elif action == 'deploy':
            self._deploy_system(options)
        elif action == 'status':
            self._show_status(options)
        elif action == 'health-check':
            self._health_check(options)
        elif action == 'backup':
            self._backup_system(options)
        elif action == 'restore':
            self._restore_system(options)
        else:
            self.stdout.write(self.style.ERROR(f'Unknown action: {action}'))
    
    def _optimize_model(self, options):
        """Optimize ML model for production"""
        try:
            model_id = options['model_id']
            if not model_id:
                self.stdout.write(self.style.ERROR('Model ID is required for optimization'))
                return
            
            optimization_type = options['optimization_type']
            
            self.stdout.write(f'Optimizing model {model_id} with type: {optimization_type}')
            
            # Initialize optimization service
            optimization_service = PerformanceOptimizationService()
            
            # Optimize model
            result = optimization_service.optimize_model(model_id, optimization_type)
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Model {model_id} optimized successfully!\n'
                        f'Optimized model ID: {result["optimized_model_id"]}\n'
                        f'Optimization results: {json.dumps(result["optimization_results"], indent=2)}'
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f'Error optimizing model: {result["message"]}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in model optimization: {e}'))
    
    def _monitor_model(self, options):
        """Monitor ML model performance"""
        try:
            model_id = options['model_id']
            if not model_id:
                self.stdout.write(self.style.ERROR('Model ID is required for monitoring'))
                return
            
            self.stdout.write(f'Starting monitoring for model {model_id}')
            
            # Initialize monitoring service
            monitoring_service = PerformanceMonitoringService()
            
            # Start monitoring
            result = monitoring_service.start_monitoring(model_id)
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Monitoring started for model {model_id}\n'
                        f'Monitoring key: {result["monitoring_key"]}'
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f'Error starting monitoring: {result["message"]}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in model monitoring: {e}'))
    
    def _ab_test_models(self, options):
        """Start A/B test between models"""
        try:
            model_a_id = options['model_id']
            model_b_id = options['model_b_id']
            test_name = options['test_name']
            
            if not all([model_a_id, model_b_id, test_name]):
                self.stdout.write(self.style.ERROR('Model A ID, Model B ID, and test name are required for A/B testing'))
                return
            
            self.stdout.write(f'Starting A/B test: {test_name} (Model A: {model_a_id}, Model B: {model_b_id})')
            
            # Initialize A/B testing service
            ab_testing_service = ABTestingService()
            
            # Start A/B test
            result = ab_testing_service.start_ab_test(model_a_id, model_b_id, test_name)
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f'A/B test started successfully!\n'
                        f'Test ID: {result["test_id"]}\n'
                        f'Test Name: {result["test_name"]}\n'
                        f'Traffic Split: {result["traffic_split"]}\n'
                        f'Test Duration: {result["test_duration_days"]} days'
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f'Error starting A/B test: {result["message"]}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in A/B testing: {e}'))
    
    def _retrain_model(self, options):
        """Schedule model retraining"""
        try:
            model_id = options['model_id']
            if not model_id:
                self.stdout.write(self.style.ERROR('Model ID is required for retraining'))
                return
            
            self.stdout.write(f'Scheduling retraining for model {model_id}')
            
            # Initialize retraining service
            retraining_service = AutomatedRetrainingService()
            
            # Schedule retraining
            result = retraining_service.schedule_retraining(model_id)
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Retraining scheduled successfully!\n'
                        f'Task ID: {result["task_id"]}\n'
                        f'Estimated completion: {result["estimated_completion"]}'
                    )
                )
            elif result['status'] == 'skipped':
                self.stdout.write(
                    self.style.WARNING(
                        f'Retraining skipped: {result["message"]}\n'
                        f'Next check: {result["next_check"]}'
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f'Error scheduling retraining: {result["message"]}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in model retraining: {e}'))
    
    def _manage_cache(self, options):
        """Manage cache operations"""
        try:
            self.stdout.write('Managing cache operations...')
            
            # Initialize caching service
            caching_service = CachingService()
            
            # Get cache stats
            stats = caching_service.get_cache_stats()
            
            self.stdout.write('Cache Statistics:')
            self.stdout.write(f'  Backend: {stats.get("cache_backend", "N/A")}')
            self.stdout.write(f'  Location: {stats.get("cache_location", "N/A")}')
            self.stdout.write(f'  Config: {json.dumps(stats.get("cache_config", {}), indent=2)}')
            
            # Clear cache if requested
            if options.get('clear_cache'):
                self.stdout.write('Clearing cache...')
                result = caching_service.clear_all_cache()
                if result:
                    self.stdout.write(self.style.SUCCESS('Cache cleared successfully'))
                else:
                    self.stdout.write(self.style.ERROR('Error clearing cache'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in cache management: {e}'))
    
    def _check_performance(self, options):
        """Check system performance"""
        try:
            self.stdout.write('Checking system performance...')
            
            # Initialize performance service
            performance_service = PerfOptService()
            
            # Get performance metrics
            metrics = performance_service.get_performance_metrics()
            
            self.stdout.write('Performance Metrics:')
            self.stdout.write(f'  Query Count: {metrics.get("query_count", 0)}')
            self.stdout.write(f'  Cache Hit Ratio: {metrics.get("cache_hit_ratio", 0):.2%}')
            self.stdout.write(f'  Average Response Time: {metrics.get("average_response_time", 0):.2f}ms')
            self.stdout.write(f'  Average Memory Usage: {metrics.get("average_memory_usage", 0):.2f}MB')
            self.stdout.write(f'  Average CPU Usage: {metrics.get("average_cpu_usage", 0):.2f}%')
            
            # Optimize memory and CPU
            self.stdout.write('\nOptimizing memory usage...')
            memory_result = performance_service.optimize_memory_usage()
            if memory_result['status'] == 'success':
                self.stdout.write(f'  Memory optimized: {memory_result["memory_usage_mb"]:.2f}MB')
            
            self.stdout.write('Optimizing CPU usage...')
            cpu_result = performance_service.optimize_cpu_usage()
            if cpu_result['status'] == 'success':
                self.stdout.write(f'  CPU usage: {cpu_result["cpu_percent"]:.2f}%')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in performance check: {e}'))
    
    def _deploy_system(self, options):
        """Deploy system to production"""
        try:
            deployment_type = options['deployment_type']
            config_file = options['config_file']
            
            self.stdout.write(f'Deploying system using {deployment_type}...')
            
            if deployment_type == 'docker':
                self._deploy_docker(config_file)
            elif deployment_type == 'kubernetes':
                self._deploy_kubernetes(config_file)
            elif deployment_type == 'local':
                self._deploy_local(config_file)
            else:
                self.stdout.write(self.style.ERROR(f'Unknown deployment type: {deployment_type}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in system deployment: {e}'))
    
    def _deploy_docker(self, config_file):
        """Deploy using Docker"""
        try:
            self.stdout.write('Deploying with Docker...')
            
            # Create Docker files
            dockerfile_content = PRODUCTION_CONFIGS['dockerfile']
            docker_compose_content = PRODUCTION_CONFIGS['docker_compose']
            
            # Write files
            with open('Dockerfile', 'w') as f:
                f.write(dockerfile_content)
            
            with open('docker-compose.yml', 'w') as f:
                f.write(docker_compose_content)
            
            self.stdout.write(self.style.SUCCESS('Docker files created successfully'))
            self.stdout.write('Run: docker-compose up -d')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in Docker deployment: {e}'))
    
    def _deploy_kubernetes(self, config_file):
        """Deploy using Kubernetes"""
        try:
            self.stdout.write('Deploying with Kubernetes...')
            
            # Create Kubernetes manifests
            k8s_content = PRODUCTION_CONFIGS['kubernetes_manifests']
            
            # Write files
            os.makedirs('k8s', exist_ok=True)
            with open('k8s/deployment.yaml', 'w') as f:
                f.write(k8s_content)
            
            self.stdout.write(self.style.SUCCESS('Kubernetes manifests created successfully'))
            self.stdout.write('Run: kubectl apply -f k8s/')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in Kubernetes deployment: {e}'))
    
    def _deploy_local(self, config_file):
        """Deploy locally"""
        try:
            self.stdout.write('Deploying locally...')
            
            # Create local deployment files
            nginx_content = PRODUCTION_CONFIGS['nginx_config']
            supervisor_content = PRODUCTION_CONFIGS['supervisor_config']
            
            # Write files
            with open('nginx.conf', 'w') as f:
                f.write(nginx_content)
            
            with open('supervisor.conf', 'w') as f:
                f.write(supervisor_content)
            
            self.stdout.write(self.style.SUCCESS('Local deployment files created successfully'))
            self.stdout.write('Run: supervisord -c supervisor.conf')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in local deployment: {e}'))
    
    def _show_status(self, options):
        """Show system status"""
        try:
            self.stdout.write('System Status Report')
            self.stdout.write('=' * 50)
            
            # ML Models Status (Signal Generation Models)
            from apps.signals.models import MLModel, MLTrainingSession
            models = MLModel.objects.all()
            active_models = models.filter(status='DEPLOYED')
            trained_models = models.filter(status='TRAINED')
            
            self.stdout.write(f'\nML Models (Signal Generation):')
            self.stdout.write(f'  Total Models: {models.count()}')
            self.stdout.write(f'  Deployed Models: {active_models.count()}')
            self.stdout.write(f'  Trained Models: {trained_models.count()}')
            
            if trained_models.exists():
                avg_accuracy = sum(m.accuracy for m in trained_models if m.accuracy) / trained_models.count()
                self.stdout.write(f'  Average Accuracy: {avg_accuracy:.4f}')
            
            # Training Sessions Status
            training_sessions = MLTrainingSession.objects.all()
            active_sessions = training_sessions.filter(status='RUNNING')
            completed_sessions = training_sessions.filter(status='COMPLETED')
            
            self.stdout.write(f'\nTraining Sessions:')
            self.stdout.write(f'  Total Sessions: {training_sessions.count()}')
            self.stdout.write(f'  Active Sessions: {active_sessions.count()}')
            self.stdout.write(f'  Completed Sessions: {completed_sessions.count()}')
                self.stdout.write(f'  Error Count: {latest_metrics.error_count}')
            
            # Cache Status
            caching_service = CachingService()
            cache_stats = caching_service.get_cache_stats()
            
            self.stdout.write(f'\nCache Status:')
            self.stdout.write(f'  Backend: {cache_stats.get("cache_backend", "N/A")}')
            self.stdout.write(f'  Location: {cache_stats.get("cache_location", "N/A")}')
            
            # Async Processing Status
            async_service = AsyncProcessingService()
            queue_status = async_service.get_queue_status()
            
            self.stdout.write(f'\nAsync Processing:')
            self.stdout.write(f'  Enabled: {queue_status.get("enabled", False)}')
            self.stdout.write(f'  Queue Size: {queue_status.get("queue_size", 0)}')
            self.stdout.write(f'  Workers: {queue_status.get("worker_count", 0)}')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error showing status: {e}'))
    
    def _health_check(self, options):
        """Perform health check"""
        try:
            self.stdout.write('Performing health check...')
            
            health_status = {
                'database': False,
                'cache': False,
                'models': False,
                'async_processing': False
            }
            
            # Check database
            try:
                Symbol.objects.count()
                health_status['database'] = True
                self.stdout.write('✓ Database connection: OK')
            except Exception as e:
                self.stdout.write(f'✗ Database connection: FAILED ({e})')
            
            # Check cache
            try:
                from django.core.cache import cache
                cache.set('health_check', 'ok', 10)
                if cache.get('health_check') == 'ok':
                    health_status['cache'] = True
                    self.stdout.write('✓ Cache: OK')
                else:
                    self.stdout.write('✗ Cache: FAILED')
            except Exception as e:
                self.stdout.write(f'✗ Cache: FAILED ({e})')
            
            # Check models (Signal Generation ML Models)
            try:
                from apps.signals.models import MLModel
                active_models = MLModel.objects.filter(status='DEPLOYED')
                if active_models.exists():
                    health_status['models'] = True
                    self.stdout.write(f'✓ ML Models: OK ({active_models.count()} deployed)')
                else:
                    self.stdout.write('✗ ML Models: NO DEPLOYED MODELS')
            except Exception as e:
                self.stdout.write(f'✗ ML Models: FAILED ({e})')
            
            # Check async processing
            try:
                async_service = AsyncProcessingService()
                queue_status = async_service.get_queue_status()
                if queue_status.get('enabled', False):
                    health_status['async_processing'] = True
                    self.stdout.write('✓ Async Processing: OK')
                else:
                    self.stdout.write('✗ Async Processing: DISABLED')
            except Exception as e:
                self.stdout.write(f'✗ Async Processing: FAILED ({e})')
            
            # Overall health
            overall_health = all(health_status.values())
            
            if overall_health:
                self.stdout.write(self.style.SUCCESS('\n✓ Overall Health: HEALTHY'))
            else:
                self.stdout.write(self.style.ERROR('\n✗ Overall Health: UNHEALTHY'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in health check: {e}'))
    
    def _backup_system(self, options):
        """Backup system data"""
        try:
            backup_path = options['backup_path'] or 'backup.json'
            
            self.stdout.write(f'Creating system backup: {backup_path}')
            
            from apps.signals.models import MLModel, MLTrainingSession
            backup_data = {
                'timestamp': timezone.now().isoformat(),
                'models': [],
                'training_sessions': []
            }
            
            # Backup signal generation ML models
            for model in MLModel.objects.all():
                backup_data['models'].append({
                    'id': model.id,
                    'name': model.name,
                    'model_type': model.model_type,
                    'version': model.version,
                    'status': model.status,
                    'accuracy': float(model.accuracy) if model.accuracy else None,
                    'target_variable': model.target_variable,
                    'features_used': model.features_used,
                    'created_at': model.training_start_date.isoformat() if model.training_start_date else None
                })
            
            # Backup training sessions
            for session in MLTrainingSession.objects.all():
                backup_data['training_sessions'].append({
                    'id': session.id,
                    'model_name': session.model_name if hasattr(session, 'model_name') else None,
                    'status': session.status,
                    'created_at': session.created_at.isoformat() if hasattr(session, 'created_at') else None
                })
            
            # Write backup file
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            self.stdout.write(self.style.SUCCESS(f'Backup created successfully: {backup_path}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating backup: {e}'))
    
    def _restore_system(self, options):
        """Restore system from backup"""
        try:
            backup_path = options['backup_path']
            if not backup_path:
                self.stdout.write(self.style.ERROR('Backup path is required for restore'))
                return
            
            if not os.path.exists(backup_path):
                self.stdout.write(self.style.ERROR(f'Backup file not found: {backup_path}'))
                return
            
            self.stdout.write(f'Restoring system from: {backup_path}')
            
            # Load backup data
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            # Restore models (basic info only) - Signal Generation ML Models
            from apps.signals.models import MLModel
            restored_models = 0
            for model_data in backup_data.get('models', []):
                try:
                    MLModel.objects.get_or_create(
                        id=model_data['id'],
                        defaults={
                            'name': model_data['name'],
                            'model_type': model_data['model_type'],
                            'version': model_data['version'],
                            'status': model_data['status'],
                            'accuracy_score': model_data['accuracy_score'],
                            'is_active': model_data['is_active']
                        }
                    )
                    restored_models += 1
                except Exception as e:
                    logger.error(f"Error restoring model {model_data['id']}: {e}")
            
            self.stdout.write(self.style.SUCCESS(f'Restored {restored_models} models'))
            self.stdout.write(self.style.SUCCESS('System restore completed'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error restoring system: {e}'))























