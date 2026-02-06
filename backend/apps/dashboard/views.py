import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.db import OperationalError, transaction
import time
from apps.trading.models import Portfolio, Position, Trade
from apps.signals.models import TradingSignal, SignalType
from apps.data.models import MarketData, TechnicalIndicator
from django.utils import timezone

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def home(request):
    """Home page view. ensure_csrf_cookie sets CSRF cookie so header login modal works on mobile."""
    try:
        context = {
            'title': 'CryptAI',
            'description': 'Advanced trading platform powered by artificial intelligence',
        }
        # Fetch live crypto prices for the horizontal scroll section (under Quick Access)
        try:
            from apps.data.real_price_service import get_live_prices
            live_prices = get_live_prices()
            if live_prices:
                context['global_crypto_prices'] = live_prices
                context['has_live_prices'] = True
            else:
                context['global_crypto_prices'] = {}
                context['has_live_prices'] = False
        except Exception as e:
            logger.warning("Could not load live prices for home page: %s", e)
            context['global_crypto_prices'] = {}
            context['has_live_prices'] = False

        response = render(request, 'dashboard/home.html', context)
        # Ensure we always return a response
        if response is None:
            from django.http import HttpResponse
            return HttpResponse("Error loading page", status=500)
        return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in home view: {e}", exc_info=True)
        # Return a simple error response instead of 500
        from django.http import HttpResponse
        return HttpResponse(f"Error loading page: {str(e)}", status=500)


@never_cache
@ensure_csrf_cookie
def login_view(request):
    """Login view with email verification check. ensure_csrf_cookie sets CSRF cookie on GET so mobile login works."""
    # If user is already authenticated, redirect immediately (before processing POST)
    if request.user.is_authenticated:
        next_url = request.GET.get('next', '/dashboard/')
        return redirect(next_url)
    
    if request.method == 'POST':
        try:
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
            
            # Validate input
            if not username:
                return render(request, 'dashboard/login.html', {
                    'error': 'Please enter a username.'
                })
            
            if not password:
                return render(request, 'dashboard/login.html', {
                    'error': 'Please enter a password.'
                })
            
            # Authenticate user with retry logic for database locks
            user = None
            max_retries = 3
            retry_delay = 0.5  # seconds
            
            for attempt in range(max_retries):
                try:
                    user = authenticate(request, username=username, password=password)
                    break  # Success, exit retry loop
                except OperationalError as e:
                    if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        # Re-raise if it's not a lock error or we've exhausted retries
                        raise
            
            if user is not None:
                # Superusers and staff can always log in (bypass email verification)
                if user.is_superuser or user.is_staff:
                    if user.is_active:
                        try:
                            login(request, user)
                            next_url = request.GET.get('next', '/dashboard/')
                            print(f"User {username} (superuser/staff) logged in successfully, redirecting to {next_url}")
                            return redirect(next_url)
                        except OperationalError as e:
                            if "database is locked" in str(e).lower():
                                return render(request, 'dashboard/login.html', {
                                    'error': 'Database is temporarily locked. Please wait a moment and try again.'
                                })
                            raise
                    else:
                        return render(request, 'dashboard/login.html', {
                            'error': 'Your account is inactive. Please contact support for assistance.'
                        })
                
                # Check if user account is active
                if not user.is_active:
                    # Check if email is verified
                    from apps.subscription.models import UserProfile
                    try:
                        profile = UserProfile.objects.get(user=user)
                        if not profile.email_verified:
                            # User exists but email not verified
                            return render(request, 'dashboard/login.html', {
                                'error': 'Your email address has not been verified. Please check your email for the verification link.',
                                'email_not_verified': True,
                                'user_email': user.email,
                            })
                    except UserProfile.DoesNotExist:
                        # Profile doesn't exist - for regular users, require email verification
                        # But allow login if account is active (might be a new account setup)
                        # Create profile with email_verified=False to track verification status
                        from apps.subscription.models import UserProfile
                        try:
                            profile = UserProfile.objects.create(
                                user=user,
                                email_verified=False,
                                subscription_status='inactive'
                            )
                        except OperationalError as e:
                            if "database is locked" in str(e).lower():
                                return render(request, 'dashboard/login.html', {
                                    'error': 'Database is temporarily locked. Please wait a moment and try again.'
                                })
                            raise
                        return render(request, 'dashboard/login.html', {
                            'error': 'Your email address has not been verified. Please check your email for the verification link.',
                            'email_not_verified': True,
                            'user_email': user.email,
                        })
                    except OperationalError as e:
                        if "database is locked" in str(e).lower():
                            return render(request, 'dashboard/login.html', {
                                'error': 'Database is temporarily locked. Please wait a moment and try again.'
                            })
                        raise
                    else:
                        # Account is inactive for other reasons
                        return render(request, 'dashboard/login.html', {
                            'error': 'Your account is inactive. Please contact support for assistance.'
                        })
                
                # User is active - check email verification for regular users
                from apps.subscription.models import UserProfile
                try:
                    profile = UserProfile.objects.get(user=user)
                    # For active users, allow login even if email not verified (can be made stricter later)
                    # But show a warning if email is not verified
                    if not profile.email_verified:
                        # Still allow login but could show a warning
                        try:
                            login(request, user)
                            next_url = request.GET.get('next', '/dashboard/')
                            print(f"User {username} logged in (email not verified), redirecting to {next_url}")
                            return redirect(next_url)
                        except OperationalError as e:
                            if "database is locked" in str(e).lower():
                                return render(request, 'dashboard/login.html', {
                                    'error': 'Database is temporarily locked. Please wait a moment and try again.'
                                })
                            raise
                    # Email is verified, proceed with login
                    try:
                        login(request, user)
                        next_url = request.GET.get('next', '/dashboard/')
                        print(f"User {username} logged in successfully, redirecting to {next_url}")
                        return redirect(next_url)
                    except OperationalError as e:
                        if "database is locked" in str(e).lower():
                            return render(request, 'dashboard/login.html', {
                                'error': 'Database is temporarily locked. Please wait a moment and try again.'
                            })
                        raise
                except UserProfile.DoesNotExist:
                    # No profile exists - create one and allow login
                    from apps.subscription.models import UserProfile
                    try:
                        UserProfile.objects.create(
                            user=user,
                            email_verified=True,  # Allow login for existing active users without profile
                            subscription_status='inactive'
                        )
                    except OperationalError as e:
                        if "database is locked" in str(e).lower():
                            return render(request, 'dashboard/login.html', {
                                'error': 'Database is temporarily locked. Please wait a moment and try again.'
                            })
                        raise
                    # Log in the user after creating profile
                    try:
                        login(request, user)
                        next_url = request.GET.get('next', '/dashboard/')
                        print(f"User {username} logged in (profile created), redirecting to {next_url}")
                        return redirect(next_url)
                    except OperationalError as e:
                        if "database is locked" in str(e).lower():
                            return render(request, 'dashboard/login.html', {
                                'error': 'Database is temporarily locked. Please wait a moment and try again.'
                            })
                        raise
                except OperationalError as e:
                    if "database is locked" in str(e).lower():
                        return render(request, 'dashboard/login.html', {
                            'error': 'Database is temporarily locked. Please wait a moment and try again.'
                        })
                    raise
            else:
                print(f"Failed login attempt for username: {username}")
                return render(request, 'dashboard/login.html', {
                    'error': 'Invalid username or password. Please check your credentials and try again.'
                })
        except OperationalError as e:
            error_msg = str(e).lower()
            if "database is locked" in error_msg:
                return render(request, 'dashboard/login.html', {
                    'error': 'Database is temporarily locked. This usually happens when multiple processes are accessing the database. Please wait a few seconds and try again. If the problem persists, restart the development server.'
                })
            else:
                import traceback
                print(f"Database error during login: {e}")
                print(traceback.format_exc())
                return render(request, 'dashboard/login.html', {
                    'error': f'Database error: {str(e)}. Please try again or contact support.'
                })
        except Exception as e:
            import traceback
            print(f"Login error: {e}")
            print(traceback.format_exc())
            # Don't expose full error details to users, but log them
            error_message = 'An error occurred during login. Please try again.'
            if "database is locked" in str(e).lower():
                error_message = 'Database is temporarily locked. Please wait a few seconds and try again.'
            return render(request, 'dashboard/login.html', {
                'error': error_message
            })
    
    return render(request, 'dashboard/login.html')


@ensure_csrf_cookie
def get_csrf_token(request):
    """API endpoint to get CSRF token for AJAX requests"""
    from django.middleware.csrf import get_token
    token = get_token(request)
    return JsonResponse({'csrfToken': token})


def logout_view(request):
    """Logout view"""
    logout(request)
    return redirect('/')


@login_required
def dashboard(request):
    """Main dashboard view"""
    try:
        return _dashboard_impl(request)
    except Exception as e:
        logger.exception("Dashboard view error: %s", e)
        raise


def _dashboard_impl(request):
    """Dashboard implementation (wrapped for error logging)."""
    try:
        portfolio = Portfolio.objects.get(user=request.user)
    except Portfolio.DoesNotExist:
        portfolio = None

    # Get recent *active* signals (failsafe: exclude already-expired even if is_valid wasn't updated)
    recent_signals = (
        TradingSignal.objects.select_related('symbol', 'signal_type')
        .filter(
            is_valid=True,
        )
        .filter(
            Q(expires_at__gte=timezone.now()) |
            # Legacy/sample signals might have NULL expires_at; treat them as active
            # only within the default expiry window (48h).
            Q(expires_at__isnull=True, created_at__gte=timezone.now() - timezone.timedelta(hours=48))
        )
        .order_by('-created_at')[:10]
    )

    # Evaluate and keep only signals with valid symbol/signal_type (avoid template AttributeError)
    recent_list = list(recent_signals)
    recent_list = [s for s in recent_list if getattr(s, 'symbol', None) and getattr(s, 'signal_type', None)]

    # Calculate confidence percentages for display (guard against None)
    for signal in recent_list:
        signal.confidence_percentage = int((signal.confidence_score or 0) * 100)
        signal.quality_percentage = int((signal.quality_score or 0) * 100)

    # If no signals exist, create some sample signals for demonstration
    if not recent_list:
        try:
            from apps.trading.models import Symbol
            from apps.signals.models import SignalType
            
            # Get or create sample symbols
            btc_symbol, _ = Symbol.objects.get_or_create(
                symbol='BTC',
                defaults={'symbol_type': 'CRYPTO', 'is_active': True, 'name': 'Bitcoin'}
            )
            eth_symbol, _ = Symbol.objects.get_or_create(
                symbol='ETH',
                defaults={'symbol_type': 'CRYPTO', 'is_active': True, 'name': 'Ethereum'}
            )
            sol_symbol, _ = Symbol.objects.get_or_create(
                symbol='SOL',
                defaults={'symbol_type': 'CRYPTO', 'is_active': True, 'name': 'Solana'}
            )
            
            # Get or create signal types
            buy_signal, _ = SignalType.objects.get_or_create(
                name='BUY',
                defaults={'description': 'Buy Signal', 'color': '#28a745'}
            )
            sell_signal, _ = SignalType.objects.get_or_create(
                name='SELL',
                defaults={'description': 'Sell Signal', 'color': '#dc3545'}
            )
            hold_signal, _ = SignalType.objects.get_or_create(
                name='HOLD',
                defaults={'description': 'Hold Signal', 'color': '#ffc107'}
            )
            
            # Create sample signals (timezone already imported at top of file)
            from decimal import Decimal
            from datetime import timedelta
            
            sample_signals = [
                {
                    'symbol': btc_symbol,
                    'signal_type': buy_signal,
                    'strength': 'STRONG',
                    'confidence_score': 0.85,
                    'confidence_level': 'HIGH',
                    'entry_price': Decimal('45000.00'),
                    'target_price': Decimal('50000.00'),
                    'stop_loss': Decimal('42000.00'),
                    'quality_score': 0.82,
                    'is_valid': True,
                    'created_at': timezone.now() - timedelta(hours=2)
                },
                {
                    'symbol': eth_symbol,
                    'signal_type': buy_signal,
                    'strength': 'MODERATE',
                    'confidence_score': 0.72,
                    'confidence_level': 'HIGH',
                    'entry_price': Decimal('3200.00'),
                    'target_price': Decimal('3500.00'),
                    'stop_loss': Decimal('3000.00'),
                    'quality_score': 0.75,
                    'is_valid': True,
                    'created_at': timezone.now() - timedelta(hours=4)
                },
                {
                    'symbol': sol_symbol,
                    'signal_type': sell_signal,
                    'strength': 'WEAK',
                    'confidence_score': 0.45,
                    'confidence_level': 'MEDIUM',
                    'entry_price': Decimal('180.00'),
                    'target_price': Decimal('160.00'),
                    'stop_loss': Decimal('200.00'),
                    'quality_score': 0.48,
                    'is_valid': True,
                    'created_at': timezone.now() - timedelta(hours=6)
                },
                {
                    'symbol': btc_symbol,
                    'signal_type': hold_signal,
                    'strength': 'MODERATE',
                    'confidence_score': 0.65,
                    'confidence_level': 'MEDIUM',
                    'entry_price': Decimal('45000.00'),
                    'target_price': Decimal('45000.00'),
                    'stop_loss': Decimal('44000.00'),
                    'quality_score': 0.60,
                    'is_valid': True,
                    'created_at': timezone.now() - timedelta(hours=8)
                },
                {
                    'symbol': eth_symbol,
                    'signal_type': sell_signal,
                    'strength': 'STRONG',
                    'confidence_score': 0.78,
                    'confidence_level': 'HIGH',
                    'entry_price': Decimal('3200.00'),
                    'target_price': Decimal('3000.00'),
                    'stop_loss': Decimal('3400.00'),
                    'quality_score': 0.75,
                    'is_valid': True,
                    'created_at': timezone.now() - timedelta(hours=10)
                },
                {
                    'symbol': sol_symbol,
                    'signal_type': buy_signal,
                    'strength': 'VERY_STRONG',
                    'confidence_score': 0.92,
                    'confidence_level': 'VERY_HIGH',
                    'entry_price': Decimal('180.00'),
                    'target_price': Decimal('220.00'),
                    'stop_loss': Decimal('170.00'),
                    'quality_score': 0.88,
                    'is_valid': True,
                    'created_at': timezone.now() - timedelta(hours=12)
                }
            ]
            
            for signal_data in sample_signals:
                TradingSignal.objects.get_or_create(
                    symbol=signal_data['symbol'],
                    signal_type=signal_data['signal_type'],
                    created_at=signal_data['created_at'],
                    defaults=signal_data
                )
            
            # Refresh the signals query and build safe list
            recent_signals = TradingSignal.objects.select_related('symbol', 'signal_type').filter(is_valid=True).order_by('-created_at')[:10]
            recent_list = [s for s in list(recent_signals) if getattr(s, 'symbol', None) and getattr(s, 'signal_type', None)]
            for s in recent_list:
                s.confidence_percentage = int((s.confidence_score or 0) * 100)
                s.quality_percentage = int((s.quality_score or 0) * 100)
        except Exception as e:
            logger.warning("Error creating sample signals: %s", e)
            recent_list = []

    # Get portfolio statistics
    if portfolio:
        open_positions = Position.objects.filter(portfolio=portfolio, is_open=True)
        total_positions = open_positions.count()
        total_pnl = sum([(pos.unrealized_pnl or 0) for pos in open_positions])
        
        # Recent trades
        recent_trades = Trade.objects.filter(portfolio=portfolio).order_by('-executed_at')[:5]
    else:
        total_positions = 0
        total_pnl = 0
        recent_trades = []
    
    # Signal type statistics
    try:
        active_signal_types = SignalType.objects.filter(is_active=True).count()
    except:
        active_signal_types = 0
    
    # Calculate metrics for enhanced dashboard
    total_signals = TradingSignal.objects.count()
    active_signals = TradingSignal.objects.filter(is_valid=True).count()
    
    # Calculate win rate (simplified)
    executed_signals = TradingSignal.objects.filter(is_executed=True)
    if executed_signals.count() > 0:
        win_rate = round((executed_signals.filter(profit_loss__gt=0).count() / executed_signals.count()) * 100)
    else:
        win_rate = 73  # Default

    # recent_list already set above (filtered for valid symbol/signal_type)
    if recent_list:
        avg_quality = round(sum([(s.quality_score or 0) for s in recent_list]) / len(recent_list) * 100)
        avg_confidence = round(sum([(s.confidence_score or 0) for s in recent_list]) / len(recent_list) * 100)
    else:
        avg_quality = 75  # Default
        avg_confidence = 70  # Default
    

    
    # Calculate signal distribution for charts
    signal_distribution = {}
    if recent_list:
        for signal in recent_list:
            signal_type = signal.signal_type.name
            if signal_type in signal_distribution:
                signal_distribution[signal_type] += 1
            else:
                signal_distribution[signal_type] = 1
    
    # If no signals, provide default distribution
    if not signal_distribution:
        signal_distribution = {'BUY': 2, 'SELL': 1}
    
    context = {
        'portfolio': portfolio,
        'recent_signals': recent_list,
        'total_positions': total_positions,
        'total_pnl': total_pnl,
        'recent_trades': recent_trades,
        'active_signal_types': active_signal_types,
        'total_signals': total_signals,
        'active_signals': active_signals,
        'win_rate': win_rate,
        'profit_factor': 2.8,  # Default
        'signal_distribution': signal_distribution,
        'avg_quality': avg_quality,
        'avg_confidence': avg_confidence,
    }
    
    return render(request, 'dashboard/enhanced_dashboard.html', context)


@login_required
def signals_view(request):
    """Redirect to main signals page (table-only dashboard)."""
    return redirect('signals:signal_dashboard')


def api_dashboard_stats(request):
    """API endpoint for dashboard statistics"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        portfolio = Portfolio.objects.get(user=request.user)
        open_positions = Position.objects.filter(portfolio=portfolio, is_open=True)
        total_pnl = sum([pos.unrealized_pnl for pos in open_positions])
        
        stats = {
            'total_positions': open_positions.count(),
            'total_pnl': float(total_pnl),
            'portfolio_balance': float(portfolio.balance),
            'active_signals': TradingSignal.objects.filter(is_valid=True).count(),
        }
        
        return JsonResponse(stats)
    except Portfolio.DoesNotExist:
        return JsonResponse({'error': 'Portfolio not found'}, status=404)


@login_required
def settings_view(request):
    """Settings view for user preferences"""
    if request.method == 'POST':
        # Handle form submission
        action = request.POST.get('action')
        
        if action == 'update_profile':
            # Update user profile
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()
            
        elif action == 'change_password':
            # Change password
            user = request.user
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            if not current_password:
                messages.error(request, 'Please enter your current password.')
            elif new_password != confirm_password:
                messages.error(request, 'New password and confirmation do not match.')
            elif len(new_password) < 8:
                messages.error(request, 'New password must be at least 8 characters.')
            elif user.check_password(current_password):
                try:
                    user.set_password(new_password)
                    user.save()
                    # Re-login user after password change (session is invalidated)
                    login(request, user)
                    messages.success(request, 'Password changed successfully.')
                except Exception as e:
                    messages.error(request, 'Password could not be set. Try a stronger password (e.g. 8+ characters, mixed letters and numbers).')
                    logger.warning('Password change validation failed: %s', e)
            else:
                messages.error(request, 'Current password is incorrect.')
            return redirect('dashboard:settings')
        
        elif action == 'update_preferences':
            # Update trading preferences
            try:
                portfolio = Portfolio.objects.get(user=request.user)
                portfolio.risk_tolerance = request.POST.get('risk_tolerance', 'medium')
                portfolio.max_position_size = float(request.POST.get('max_position_size', 5.0))
                portfolio.daily_loss_limit = float(request.POST.get('daily_loss_limit', 2.0))
                portfolio.save()
            except Portfolio.DoesNotExist:
                pass
        
        messages.success(request, 'Settings updated successfully!')
        return redirect('dashboard:settings')
    
    # Get current user data
    try:
        portfolio = Portfolio.objects.get(user=request.user)
    except Portfolio.DoesNotExist:
        portfolio = None
    
    context = {
        'portfolio': portfolio,
    }
    
    return render(request, 'dashboard/settings.html', context)
