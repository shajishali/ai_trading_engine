from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Symbol

# Create your views here.

@csrf_exempt
@require_http_methods(["GET"])
def get_symbols(request):
    """Get all available symbols"""
    try:
        symbols = Symbol.objects.filter(is_active=True).values('symbol', 'name', 'symbol_type', 'exchange')
        symbols_list = list(symbols)
        
        return JsonResponse({
            'success': True,
            'symbols': symbols_list,
            'count': len(symbols_list)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
