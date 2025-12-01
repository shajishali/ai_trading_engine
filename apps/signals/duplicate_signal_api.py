"""
Duplicate Signal Removal API

REST API endpoints for identifying and removing duplicate trading signals.
Provides web interface for duplicate signal management.
"""

import json
import logging
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.signals.duplicate_signal_removal_service import duplicate_removal_service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class DuplicateSignalAPIView(View):
    """API view for duplicate signal operations"""
    
    def get(self, request):
        """Get duplicate signal statistics or identify duplicates"""
        try:
            action = request.GET.get('action', 'statistics')
            
            if action == 'statistics':
                return self._get_statistics(request)
            elif action == 'identify':
                return self._identify_duplicates(request)
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action. Use "statistics" or "identify"'
                })
                
        except Exception as e:
            logger.error(f"Error in DuplicateSignalAPIView GET: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def post(self, request):
        """Remove duplicate signals"""
        try:
            data = json.loads(request.body)
            action = data.get('action', 'remove')
            
            if action == 'remove':
                return self._remove_duplicates(request, data)
            elif action == 'cleanup_old':
                return self._cleanup_old_duplicates(request, data)
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action. Use "remove" or "cleanup_old"'
                })
                
        except Exception as e:
            logger.error(f"Error in DuplicateSignalAPIView POST: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _get_statistics(self, request):
        """Get duplicate signal statistics"""
        try:
            symbol = request.GET.get('symbol')
            
            result = duplicate_removal_service.get_duplicate_statistics(symbol=symbol)
            
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _identify_duplicates(self, request):
        """Identify duplicate signals without removing them"""
        try:
            # Get parameters
            symbol = request.GET.get('symbol')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            tolerance = float(request.GET.get('tolerance', 0.01))
            
            # Parse dates
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                try:
                    parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid start_date format. Use ISO format.'
                    })
            
            if end_date:
                try:
                    parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid end_date format. Use ISO format.'
                    })
            
            result = duplicate_removal_service.identify_duplicates(
                symbol=symbol,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                tolerance_percentage=tolerance
            )
            
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Error identifying duplicates: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _remove_duplicates(self, request, data):
        """Remove duplicate signals"""
        try:
            # Get parameters
            symbol = data.get('symbol')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            tolerance = float(data.get('tolerance', 0.01))
            dry_run = data.get('dry_run', True)  # Default to dry run for safety
            
            # Parse dates
            parsed_start_date = None
            parsed_end_date = None
            
            if start_date:
                try:
                    parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid start_date format. Use ISO format.'
                    })
            
            if end_date:
                try:
                    parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid end_date format. Use ISO format.'
                    })
            
            result = duplicate_removal_service.remove_duplicates(
                symbol=symbol,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                dry_run=dry_run,
                tolerance_percentage=tolerance
            )
            
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Error removing duplicates: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def _cleanup_old_duplicates(self, request, data):
        """Clean up old duplicate signals"""
        try:
            days_old = int(data.get('days_old', 30))
            dry_run = data.get('dry_run', True)  # Default to dry run for safety
            
            result = duplicate_removal_service.cleanup_old_duplicates(
                days_old=days_old,
                dry_run=dry_run
            )
            
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Error cleaning up old duplicates: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class DuplicateSignalDashboardAPIView(View):
    """API view for duplicate signal dashboard data"""
    
    def get(self, request):
        """Get dashboard data for duplicate signals"""
        try:
            # Get overall statistics
            overall_stats = duplicate_removal_service.get_duplicate_statistics()
            
            # Get recent duplicate groups (last 7 days)
            recent_cutoff = timezone.now() - timedelta(days=7)
            recent_duplicates = duplicate_removal_service.identify_duplicates(
                start_date=recent_cutoff,
                tolerance_percentage=0.01
            )
            
            # Get symbols with most duplicates
            symbols_stats = {}
            if recent_duplicates.get('success'):
                for group in recent_duplicates.get('duplicate_groups', []):
                    symbol = group['signals'][0].symbol.symbol
                    if symbol not in symbols_stats:
                        symbols_stats[symbol] = 0
                    symbols_stats[symbol] += len(group['duplicate_signals'])
            
            # Sort symbols by duplicate count
            top_duplicate_symbols = sorted(
                symbols_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return JsonResponse({
                'success': True,
                'overall_statistics': overall_stats,
                'recent_duplicates': {
                    'groups_found': recent_duplicates.get('duplicate_groups_found', 0),
                    'total_duplicates': recent_duplicates.get('total_duplicate_signals', 0)
                },
                'top_duplicate_symbols': top_duplicate_symbols,
                'last_updated': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
