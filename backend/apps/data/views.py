from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import MarketData, DataSource
from apps.trading.models import Symbol
from apps.core.services import RealTimeBroadcaster
import json


@login_required
def dashboard(request):
    """Data dashboard view"""
    # Get latest market data
    latest_data = MarketData.objects.select_related('symbol').order_by('-timestamp')[:20]
    
    # Get data sources
    data_sources = DataSource.objects.filter(is_active=True)
    
    # Get symbol statistics
    total_symbols = Symbol.objects.count()
    crypto_symbols = Symbol.objects.filter(symbol_type='CRYPTO').count()
    stock_symbols = Symbol.objects.filter(symbol_type='STOCK').count()
    
    context = {
        'latest_data': latest_data,
        'data_sources': data_sources,
        'total_symbols': total_symbols,
        'crypto_symbols': crypto_symbols,
        'stock_symbols': stock_symbols,
    }
    
    return render(request, 'data/dashboard.html', context)


@login_required
def realtime_dashboard(request):
    """Real-time market data dashboard"""
    # Get supported live symbols
    live_symbols = ['BTC', 'ETH', 'XRP', 'USDT', 'BNB', 'SOL', 'USDC', 'STETH', 'DOGE', 'TRX', 'ADA', 'WBTC', 'LINK', 'XLM']
    
    try:
        # Try to get real-time prices from external APIs
        from .real_price_service import get_live_prices
        live_prices = get_live_prices()
        
        # Convert to the format expected by the template
        live_data = {}
        for symbol in live_symbols:
            if symbol in live_prices:
                price_data = live_prices[symbol]
                live_data[symbol] = {
                    'price': price_data['price'],
                    'change': price_data['change_24h'],
                    'volume': price_data['volume_24h'],
                    'timestamp': price_data['last_updated'],
                    'change_percent': price_data['change_24h'],
                    'source': price_data.get('source', 'API')
                }
            else:
                # Fallback to database data
                try:
                    latest = MarketData.objects.filter(symbol__symbol=symbol).order_by('-timestamp').first()
                    if latest:
                        live_data[symbol] = {
                            'price': float(latest.close_price),
                            'change': float(latest.close_price - latest.open_price),
                            'volume': float(latest.volume),
                            'timestamp': latest.timestamp.isoformat(),
                            'change_percent': float(((latest.close_price - latest.open_price) / latest.open_price) * 100),
                            'source': 'Database'
                        }
                except:
                    pass
        
    except Exception as e:
        # Fallback to database data if API fails
        live_data = {}
        for symbol in live_symbols:
            try:
                latest = MarketData.objects.filter(symbol__symbol=symbol).order_by('-timestamp').first()
                if latest:
                    live_data[symbol] = {
                        'price': float(latest.close_price),
                        'change': float(latest.close_price - latest.open_price),
                        'volume': float(latest.volume),
                        'timestamp': latest.timestamp.isoformat(),
                        'change_percent': float(((latest.close_price - latest.open_price) / latest.open_price) * 100),
                        'source': 'Database'
                    }
            except:
                pass
    
    context = {
        'live_symbols': live_symbols,
        'live_data': live_data,
    }
    
    return render(request, 'data/realtime_dashboard.html', context)


@login_required
def api_market_data(request):
    """API endpoint for market data"""
    symbol = request.GET.get('symbol', '')
    
    if symbol:
        # Get data for specific symbol
        data = MarketData.objects.filter(symbol__symbol=symbol).order_by('-timestamp')[:100]
        market_data = []
        
        for record in data:
            market_data.append({
                'timestamp': record.timestamp.isoformat(),
                'open': float(record.open_price),
                'high': float(record.high_price),
                'low': float(record.low_price),
                'close': float(record.close_price),
                'volume': float(record.volume)
            })
        
        return JsonResponse({
            'symbol': symbol,
            'data': market_data
        })
    else:
        # Get latest data for all symbols
        latest_data = MarketData.objects.select_related('symbol').order_by('-timestamp')[:50]
        market_data = []
        
        for record in latest_data:
            market_data.append({
                'symbol': record.symbol.symbol,
                'name': record.symbol.name,
                'price': float(record.close_price),
                'change': float(record.close_price - record.open_price),
                'volume': float(record.volume),
                'timestamp': record.timestamp.isoformat()
            })
        
        return JsonResponse({
            'data': market_data
        })


@login_required
def api_symbols(request):
    """API endpoint for symbols"""
    symbol_type = request.GET.get('type', '')
    
    if symbol_type:
        symbols = Symbol.objects.filter(symbol_type=symbol_type.upper(), is_active=True)
    else:
        symbols = Symbol.objects.filter(is_active=True)
    
    symbols_data = []
    for symbol in symbols:
        symbols_data.append({
            'symbol': symbol.symbol,
            'name': symbol.name,
            'type': symbol.symbol_type,
            'exchange': symbol.exchange,
            'is_active': symbol.is_active
        })
    
    return JsonResponse({
        'symbols': symbols_data,
        'total': len(symbols_data)
    })


def api_live_prices(request):
    """API endpoint for live prices (public GET so home page can load prices without login)"""
    try:
        from .real_price_service import get_live_prices
        
        # Get real-time prices from external APIs
        live_prices = get_live_prices()
        
        return JsonResponse({
            'live_prices': live_prices,
            'timestamp': timezone.now().isoformat(),
            'source': 'Real-time APIs (Binance + CoinGecko)'
        })
        
    except Exception as e:
        # Fallback to database data if API fails
        live_symbols = ['BTC', 'ETH', 'XRP', 'USDT', 'BNB', 'SOL', 'USDC', 'STETH', 'DOGE', 'TRX', 'ADA', 'WBTC', 'LINK', 'XLM']
        
        live_prices = {}
        for symbol in live_symbols:
            try:
                latest = MarketData.objects.filter(symbol__symbol=symbol).order_by('-timestamp').first()
                if latest:
                    live_prices[symbol] = {
                        'price': float(latest.close_price),
                        'change_24h': float(((latest.close_price - latest.open_price) / latest.open_price) * 100),
                        'volume_24h': float(latest.volume),
                        'last_updated': latest.timestamp.isoformat()
                    }
            except:
                pass
        
        return JsonResponse({
            'live_prices': live_prices,
            'timestamp': timezone.now().isoformat(),
            'source': 'Database (fallback)',
            'error': str(e)
        })
