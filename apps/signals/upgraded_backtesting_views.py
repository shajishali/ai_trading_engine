"""
Upgraded Backtesting Views
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

@login_required
def upgraded_backtesting_page(request):
    """Render the upgraded backtesting page"""
    return render(request, 'signals/upgraded_backtesting.html', {
        'page_title': 'Upgraded Backtesting - Enhanced Signal Management',
        'page_description': 'Advanced backtesting with 7-day signal expiration, 60% take profit, and 40% stop loss'
    })

@method_decorator(login_required, name='dispatch')
class UpgradedBacktestingDashboardView(View):
    """Dashboard view for upgraded backtesting"""
    
    def get(self, request):
        """Render the upgraded backtesting dashboard"""
        context = {
            'page_title': 'Upgraded Backtesting Dashboard',
            'page_description': 'Enhanced signal management with improved execution logic',
            'features': [
                {
                    'title': '7-Day Signal Expiration',
                    'description': 'Signals automatically expire after 7 days if not executed',
                    'icon': '⏰',
                    'color': 'primary'
                },
                {
                    'title': 'Fixed 60% Take Profit',
                    'description': 'Take profit set to 60% of capital when signal reaches target',
                    'icon': '💰',
                    'color': 'success'
                },
                {
                    'title': 'Maximum 40% Stop Loss',
                    'description': 'Stop loss limited to maximum 40% of capital loss',
                    'icon': '🛡️',
                    'color': 'warning'
                },
                {
                    'title': 'Enhanced Categorization',
                    'description': 'Signals categorized as executed, expired, or not opened',
                    'icon': '📊',
                    'color': 'info'
                }
            ]
        }
        return render(request, 'signals/upgraded_backtesting.html', context)



























