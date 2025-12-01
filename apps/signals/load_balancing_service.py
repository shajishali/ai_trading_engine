"""
Load balancing and scaling service for database-driven signal generation
Phase 3: Advanced load balancing, auto-scaling, and performance optimization
"""

import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.trading.models import Symbol
from apps.signals.models import TradingSignal
from apps.signals.performance_optimization_service import performance_optimization_service
from apps.signals.monitoring_dashboard import monitoring_dashboard

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_RESPONSE_TIME = "least_response_time"
    RANDOM = "random"


class ScalingTrigger(Enum):
    """Scaling trigger conditions"""
    CPU_HIGH = "cpu_high"
    MEMORY_HIGH = "memory_high"
    QUEUE_LENGTH_HIGH = "queue_length_high"
    RESPONSE_TIME_HIGH = "response_time_high"
    ERROR_RATE_HIGH = "error_rate_high"


@dataclass
class WorkerNode:
    """Worker node configuration"""
    id: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 100
    current_connections: int = 0
    response_time: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    is_healthy: bool = True
    last_health_check: datetime = None


@dataclass
class ScalingMetrics:
    """Scaling metrics for auto-scaling decisions"""
    cpu_usage: float
    memory_usage: float
    queue_length: int
    response_time: float
    error_rate: float
    throughput: float
    timestamp: datetime


class LoadBalancingService:
    """Advanced load balancing and scaling service"""
    
    def __init__(self):
        self.worker_nodes: List[WorkerNode] = []
        self.load_balancing_strategy = LoadBalancingStrategy.ROUND_ROBIN
        self.auto_scaling_enabled = True
        self.scaling_metrics_history: List[ScalingMetrics] = []
        self.current_round_robin_index = 0
        
        # Scaling thresholds
        self.scaling_thresholds = {
            'scale_up_cpu': 80.0,      # Scale up when CPU > 80%
            'scale_up_memory': 85.0,    # Scale up when memory > 85%
            'scale_up_queue': 100,      # Scale up when queue > 100
            'scale_up_response_time': 5.0,  # Scale up when response time > 5s
            'scale_up_error_rate': 0.05,    # Scale up when error rate > 5%
            
            'scale_down_cpu': 30.0,     # Scale down when CPU < 30%
            'scale_down_memory': 40.0,  # Scale down when memory < 40%
            'scale_down_queue': 10,     # Scale down when queue < 10
            'scale_down_response_time': 1.0,  # Scale down when response time < 1s
            'scale_down_error_rate': 0.01,    # Scale down when error rate < 1%
        }
        
        # Initialize default worker nodes
        self._initialize_default_workers()
    
    def _initialize_default_workers(self):
        """Initialize default worker nodes"""
        try:
            # Add local worker node
            local_worker = WorkerNode(
                id="local_worker",
                host="localhost",
                port=8000,
                weight=1,
                max_connections=100
            )
            self.worker_nodes.append(local_worker)
            
            # Add additional worker nodes if configured
            additional_workers = getattr(settings, 'ADDITIONAL_WORKER_NODES', [])
            for worker_config in additional_workers:
                worker = WorkerNode(
                    id=worker_config['id'],
                    host=worker_config['host'],
                    port=worker_config['port'],
                    weight=worker_config.get('weight', 1),
                    max_connections=worker_config.get('max_connections', 100)
                )
                self.worker_nodes.append(worker)
            
            logger.info(f"Initialized {len(self.worker_nodes)} worker nodes")
            
        except Exception as e:
            logger.error(f"Error initializing worker nodes: {e}")
    
    def get_worker_node(self, task_type: str = None) -> Optional[WorkerNode]:
        """Get the best worker node for a task based on load balancing strategy"""
        try:
            if not self.worker_nodes:
                logger.warning("No worker nodes available")
                return None
            
            # Filter healthy nodes
            healthy_nodes = [node for node in self.worker_nodes if node.is_healthy]
            if not healthy_nodes:
                logger.warning("No healthy worker nodes available")
                return None
            
            # Select node based on strategy
            if self.load_balancing_strategy == LoadBalancingStrategy.ROUND_ROBIN:
                return self._round_robin_selection(healthy_nodes)
            elif self.load_balancing_strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                return self._least_connections_selection(healthy_nodes)
            elif self.load_balancing_strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin_selection(healthy_nodes)
            elif self.load_balancing_strategy == LoadBalancingStrategy.LEAST_RESPONSE_TIME:
                return self._least_response_time_selection(healthy_nodes)
            elif self.load_balancing_strategy == LoadBalancingStrategy.RANDOM:
                return self._random_selection(healthy_nodes)
            else:
                return self._round_robin_selection(healthy_nodes)
                
        except Exception as e:
            logger.error(f"Error selecting worker node: {e}")
            return None
    
    def _round_robin_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Round robin selection"""
        if not nodes:
            return None
        
        node = nodes[self.current_round_robin_index % len(nodes)]
        self.current_round_robin_index += 1
        return node
    
    def _least_connections_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Select node with least connections"""
        if not nodes:
            return None
        
        return min(nodes, key=lambda node: node.current_connections)
    
    def _weighted_round_robin_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Weighted round robin selection"""
        if not nodes:
            return None
        
        # Calculate total weight
        total_weight = sum(node.weight for node in nodes)
        
        # Select based on weight
        current_weight = 0
        for node in nodes:
            current_weight += node.weight
            if self.current_round_robin_index % total_weight < current_weight:
                self.current_round_robin_index += 1
                return node
        
        # Fallback to first node
        return nodes[0]
    
    def _least_response_time_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Select node with least response time"""
        if not nodes:
            return None
        
        return min(nodes, key=lambda node: node.response_time)
    
    def _random_selection(self, nodes: List[WorkerNode]) -> WorkerNode:
        """Random selection"""
        if not nodes:
            return None
        
        import random
        return random.choice(nodes)
    
    def update_worker_metrics(self, worker_id: str, metrics: Dict[str, Any]) -> bool:
        """Update worker node metrics"""
        try:
            worker = self._get_worker_by_id(worker_id)
            if not worker:
                logger.warning(f"Worker {worker_id} not found")
                return False
            
            # Update metrics
            worker.current_connections = metrics.get('current_connections', worker.current_connections)
            worker.response_time = metrics.get('response_time', worker.response_time)
            worker.cpu_usage = metrics.get('cpu_usage', worker.cpu_usage)
            worker.memory_usage = metrics.get('memory_usage', worker.memory_usage)
            worker.is_healthy = metrics.get('is_healthy', worker.is_healthy)
            worker.last_health_check = timezone.now()
            
            logger.debug(f"Updated metrics for worker {worker_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating worker metrics: {e}")
            return False
    
    def _get_worker_by_id(self, worker_id: str) -> Optional[WorkerNode]:
        """Get worker node by ID"""
        for worker in self.worker_nodes:
            if worker.id == worker_id:
                return worker
        return None
    
    def collect_scaling_metrics(self) -> ScalingMetrics:
        """Collect current scaling metrics"""
        try:
            # Get system metrics
            system_metrics = performance_optimization_service.get_performance_metrics()
            
            # Get database metrics
            db_metrics = system_metrics.get('database_performance', {})
            
            # Get signal generation metrics
            signal_metrics = system_metrics.get('signal_generation_performance', {})
            
            # Get memory usage
            memory_metrics = system_metrics.get('memory_usage', {})
            
            # Calculate metrics
            cpu_usage = self._get_cpu_usage()
            memory_usage = memory_metrics.get('memory_usage_percentage', 0.0)
            queue_length = self._get_queue_length()
            response_time = self._get_average_response_time()
            error_rate = self._get_error_rate()
            throughput = signal_metrics.get('signals_generated_last_hour', 0)
            
            metrics = ScalingMetrics(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                queue_length=queue_length,
                response_time=response_time,
                error_rate=error_rate,
                throughput=throughput,
                timestamp=timezone.now()
            )
            
            # Store metrics history
            self.scaling_metrics_history.append(metrics)
            
            # Keep only last 100 metrics
            if len(self.scaling_metrics_history) > 100:
                self.scaling_metrics_history = self.scaling_metrics_history[-100:]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting scaling metrics: {e}")
            return ScalingMetrics(
                cpu_usage=0.0,
                memory_usage=0.0,
                queue_length=0,
                response_time=0.0,
                error_rate=0.0,
                throughput=0.0,
                timestamp=timezone.now()
            )
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage"""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except ImportError:
            # Fallback if psutil not available
            return 50.0
        except Exception as e:
            logger.error(f"Error getting CPU usage: {e}")
            return 0.0
    
    def _get_queue_length(self) -> int:
        """Get current queue length"""
        try:
            # This would be implemented with actual queue monitoring
            # For now, return a simulated value
            return 10
        except Exception as e:
            logger.error(f"Error getting queue length: {e}")
            return 0
    
    def _get_average_response_time(self) -> float:
        """Get average response time"""
        try:
            # This would be implemented with actual response time monitoring
            # For now, return a simulated value
            return 1.5
        except Exception as e:
            logger.error(f"Error getting response time: {e}")
            return 0.0
    
    def _get_error_rate(self) -> float:
        """Get current error rate"""
        try:
            # This would be implemented with actual error rate monitoring
            # For now, return a simulated value
            return 0.02  # 2%
        except Exception as e:
            logger.error(f"Error getting error rate: {e}")
            return 0.0
    
    def evaluate_scaling_decision(self) -> Dict[str, Any]:
        """Evaluate if scaling is needed based on current metrics"""
        try:
            if not self.auto_scaling_enabled:
                return {'action': 'none', 'reason': 'Auto-scaling disabled'}
            
            # Get current metrics
            metrics = self.collect_scaling_metrics()
            
            # Check scale-up conditions
            scale_up_reasons = []
            if metrics.cpu_usage > self.scaling_thresholds['scale_up_cpu']:
                scale_up_reasons.append(f"CPU usage {metrics.cpu_usage:.1f}% > {self.scaling_thresholds['scale_up_cpu']}%")
            
            if metrics.memory_usage > self.scaling_thresholds['scale_up_memory']:
                scale_up_reasons.append(f"Memory usage {metrics.memory_usage:.1f}% > {self.scaling_thresholds['scale_up_memory']}%")
            
            if metrics.queue_length > self.scaling_thresholds['scale_up_queue']:
                scale_up_reasons.append(f"Queue length {metrics.queue_length} > {self.scaling_thresholds['scale_up_queue']}")
            
            if metrics.response_time > self.scaling_thresholds['scale_up_response_time']:
                scale_up_reasons.append(f"Response time {metrics.response_time:.1f}s > {self.scaling_thresholds['scale_up_response_time']}s")
            
            if metrics.error_rate > self.scaling_thresholds['scale_up_error_rate']:
                scale_up_reasons.append(f"Error rate {metrics.error_rate:.1%} > {self.scaling_thresholds['scale_up_error_rate']:.1%}")
            
            if scale_up_reasons:
                return {
                    'action': 'scale_up',
                    'reasons': scale_up_reasons,
                    'metrics': metrics
                }
            
            # Check scale-down conditions
            scale_down_reasons = []
            if (metrics.cpu_usage < self.scaling_thresholds['scale_down_cpu'] and
                metrics.memory_usage < self.scaling_thresholds['scale_down_memory'] and
                metrics.queue_length < self.scaling_thresholds['scale_down_queue'] and
                metrics.response_time < self.scaling_thresholds['scale_down_response_time'] and
                metrics.error_rate < self.scaling_thresholds['scale_down_error_rate']):
                
                scale_down_reasons.append("All metrics below scale-down thresholds")
                
                return {
                    'action': 'scale_down',
                    'reasons': scale_down_reasons,
                    'metrics': metrics
                }
            
            return {
                'action': 'none',
                'reason': 'Metrics within normal range',
                'metrics': metrics
            }
            
        except Exception as e:
            logger.error(f"Error evaluating scaling decision: {e}")
            return {'action': 'error', 'reason': str(e)}
    
    def execute_scaling_action(self, action: str, metrics: ScalingMetrics) -> bool:
        """Execute scaling action"""
        try:
            if action == 'scale_up':
                return self._scale_up(metrics)
            elif action == 'scale_down':
                return self._scale_down(metrics)
            else:
                logger.info("No scaling action needed")
                return True
                
        except Exception as e:
            logger.error(f"Error executing scaling action: {e}")
            return False
    
    def _scale_up(self, metrics: ScalingMetrics) -> bool:
        """Scale up the system"""
        try:
            logger.info(f"Scaling up system - CPU: {metrics.cpu_usage:.1f}%, Memory: {metrics.memory_usage:.1f}%")
            
            # Add new worker node
            new_worker_id = f"worker_{int(time.time())}"
            new_worker = WorkerNode(
                id=new_worker_id,
                host="localhost",  # In production, this would be a different host
                port=8000 + len(self.worker_nodes),
                weight=1,
                max_connections=100
            )
            
            self.worker_nodes.append(new_worker)
            
            # Start new worker (in production, this would start a new process/container)
            logger.info(f"Added new worker node: {new_worker_id}")
            
            # Update load balancing
            self._update_load_balancing_config()
            
            return True
            
        except Exception as e:
            logger.error(f"Error scaling up: {e}")
            return False
    
    def _scale_down(self, metrics: ScalingMetrics) -> bool:
        """Scale down the system"""
        try:
            if len(self.worker_nodes) <= 1:
                logger.info("Cannot scale down - minimum workers reached")
                return True
            
            logger.info(f"Scaling down system - CPU: {metrics.cpu_usage:.1f}%, Memory: {metrics.memory_usage:.1f}%")
            
            # Remove least used worker
            worker_to_remove = min(self.worker_nodes, key=lambda w: w.current_connections)
            self.worker_nodes.remove(worker_to_remove)
            
            logger.info(f"Removed worker node: {worker_to_remove.id}")
            
            # Update load balancing
            self._update_load_balancing_config()
            
            return True
            
        except Exception as e:
            logger.error(f"Error scaling down: {e}")
            return False
    
    def _update_load_balancing_config(self):
        """Update load balancing configuration"""
        try:
            # Update round robin index
            self.current_round_robin_index = 0
            
            # Update cache with new configuration
            cache.set('load_balancer_config', {
                'worker_nodes': len(self.worker_nodes),
                'strategy': self.load_balancing_strategy.value,
                'last_updated': timezone.now().isoformat()
            }, 300)
            
            logger.info(f"Updated load balancing config - {len(self.worker_nodes)} workers")
            
        except Exception as e:
            logger.error(f"Error updating load balancing config: {e}")
    
    def get_load_balancing_status(self) -> Dict[str, Any]:
        """Get current load balancing status"""
        try:
            # Get current metrics
            metrics = self.collect_scaling_metrics()
            
            # Get scaling decision
            scaling_decision = self.evaluate_scaling_decision()
            
            return {
                'worker_nodes': len(self.worker_nodes),
                'healthy_nodes': len([w for w in self.worker_nodes if w.is_healthy]),
                'load_balancing_strategy': self.load_balancing_strategy.value,
                'auto_scaling_enabled': self.auto_scaling_enabled,
                'current_metrics': {
                    'cpu_usage': metrics.cpu_usage,
                    'memory_usage': metrics.memory_usage,
                    'queue_length': metrics.queue_length,
                    'response_time': metrics.response_time,
                    'error_rate': metrics.error_rate,
                    'throughput': metrics.throughput
                },
                'scaling_decision': scaling_decision,
                'worker_details': [
                    {
                        'id': worker.id,
                        'host': worker.host,
                        'port': worker.port,
                        'weight': worker.weight,
                        'current_connections': worker.current_connections,
                        'response_time': worker.response_time,
                        'is_healthy': worker.is_healthy
                    }
                    for worker in self.worker_nodes
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting load balancing status: {e}")
            return {'error': str(e)}
    
    def set_load_balancing_strategy(self, strategy: LoadBalancingStrategy) -> bool:
        """Set load balancing strategy"""
        try:
            self.load_balancing_strategy = strategy
            self._update_load_balancing_config()
            
            logger.info(f"Load balancing strategy set to: {strategy.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting load balancing strategy: {e}")
            return False
    
    def enable_auto_scaling(self, enabled: bool = True) -> bool:
        """Enable or disable auto-scaling"""
        try:
            self.auto_scaling_enabled = enabled
            logger.info(f"Auto-scaling {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting auto-scaling: {e}")
            return False
    
    def get_scaling_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get scaling history for the specified hours"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            history = []
            for metrics in self.scaling_metrics_history:
                if metrics.timestamp >= cutoff_time:
                    history.append({
                        'timestamp': metrics.timestamp.isoformat(),
                        'cpu_usage': metrics.cpu_usage,
                        'memory_usage': metrics.memory_usage,
                        'queue_length': metrics.queue_length,
                        'response_time': metrics.response_time,
                        'error_rate': metrics.error_rate,
                        'throughput': metrics.throughput
                    })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting scaling history: {e}")
            return []


# Global instance
load_balancing_service = LoadBalancingService()














