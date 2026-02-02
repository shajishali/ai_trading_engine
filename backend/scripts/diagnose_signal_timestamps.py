"""
Diagnostic script to check signal timestamp issues
This script will help identify why old signals show with updated created dates
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.signals.models import TradingSignal
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q

def diagnose_signal_timestamps():
    """Diagnose signal timestamp issues"""
    print("=" * 80)
    print("SIGNAL TIMESTAMP DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # Get all signals ordered by created_at using values() to avoid field issues
    all_signals_data = TradingSignal.objects.values(
        'id', 'symbol__symbol', 'signal_type__name', 'created_at', 'analyzed_at', 'updated_at', 'is_valid'
    ).order_by('-created_at')[:20]
    
    print(f"Total signals in database: {TradingSignal.objects.count()}")
    print(f"Valid signals: {TradingSignal.objects.filter(is_valid=True).count()}")
    print(f"Invalid signals: {TradingSignal.objects.filter(is_valid=False).count()}")
    print()
    
    print("=" * 80)
    print("RECENT 20 SIGNALS (by created_at):")
    print("=" * 80)
    print(f"{'ID':<8} {'Symbol':<12} {'Type':<10} {'Created At':<25} {'Analyzed At':<25} {'Updated At':<25} {'Is Valid':<10}")
    print("-" * 80)
    
    for signal in all_signals_data:
        created_str = signal['created_at'].strftime('%Y-%m-%d %H:%M:%S') if signal['created_at'] else 'N/A'
        analyzed_str = signal['analyzed_at'].strftime('%Y-%m-%d %H:%M:%S') if signal.get('analyzed_at') else 'N/A'
        updated_str = signal['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if signal.get('updated_at') else 'N/A'
        
        print(f"{signal['id']:<8} {signal['symbol__symbol']:<12} {signal['signal_type__name']:<10} {created_str:<25} {analyzed_str:<25} {updated_str:<25} {str(signal['is_valid']):<10}")
    
    print()
    print("=" * 80)
    print("CHECKING FOR DUPLICATE SIGNALS (same symbol + type):")
    print("=" * 80)
    
    # Check for duplicate signals (same symbol and type)
    duplicates = TradingSignal.objects.values('symbol', 'signal_type').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')[:10]
    
    if duplicates:
        print(f"Found {len(duplicates)} symbol+type combinations with multiple signals:")
        for dup in duplicates:
            symbol_id = dup['symbol']
            signal_type_id = dup['signal_type']
            count = dup['count']
            
            # Get symbol and type names using values()
            first_signal = TradingSignal.objects.filter(
                symbol_id=symbol_id, 
                signal_type_id=signal_type_id
            ).values('symbol__symbol', 'signal_type__name').first()
            
            if first_signal:
                print(f"  - {first_signal['symbol__symbol']} + {first_signal['signal_type__name']}: {count} signals")
                
                # Show the signals using values()
                signals = TradingSignal.objects.filter(
                    symbol_id=symbol_id, 
                    signal_type_id=signal_type_id
                ).values('id', 'created_at', 'analyzed_at', 'is_valid').order_by('-created_at')[:5]
                
                for sig in signals:
                    created_str = sig['created_at'].strftime('%Y-%m-%d %H:%M:%S') if sig['created_at'] else 'N/A'
                    analyzed_str = sig['analyzed_at'].strftime('%Y-%m-%d %H:%M:%S') if sig.get('analyzed_at') else 'N/A'
                    print(f"    ID {sig['id']}: created={created_str}, analyzed={analyzed_str}, valid={sig['is_valid']}")
    else:
        print("No duplicate signals found (same symbol + type)")
    
    print()
    print("=" * 80)
    print("CHECKING FOR SIGNALS WITH MISMATCHED TIMESTAMPS:")
    print("=" * 80)
    
    # Check for signals where analyzed_at is newer than created_at (shouldn't happen for new signals)
    try:
        mismatched = TradingSignal.objects.filter(
            analyzed_at__gt=timezone.now() - timedelta(hours=1)
        ).exclude(
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).values('id', 'symbol__symbol', 'created_at', 'analyzed_at')[:10]
        
        if mismatched:
            print(f"Found {len(mismatched)} signals with analyzed_at in last hour but created_at older:")
            for sig in mismatched:
                created_str = sig['created_at'].strftime('%Y-%m-%d %H:%M:%S') if sig['created_at'] else 'N/A'
                analyzed_str = sig['analyzed_at'].strftime('%Y-%m-%d %H:%M:%S') if sig.get('analyzed_at') else 'N/A'
                print(f"  ID {sig['id']} ({sig['symbol__symbol']}): created={created_str}, analyzed={analyzed_str}")
        else:
            print("No mismatched timestamps found")
    except Exception as e:
        print(f"Error checking mismatched timestamps: {e}")
    
    print()
    print("=" * 80)
    print("CHECKING RECENT SIGNAL UPDATES:")
    print("=" * 80)
    
    # Check for signals updated recently
    try:
        recent_updates = TradingSignal.objects.filter(
            updated_at__gte=timezone.now() - timedelta(hours=1)
        ).values('id', 'symbol__symbol', 'created_at', 'updated_at').order_by('-updated_at')[:10]
        
        if recent_updates:
            print(f"Found {len(recent_updates)} signals updated in last hour:")
            for sig in recent_updates:
                created_str = sig['created_at'].strftime('%Y-%m-%d %H:%M:%S') if sig['created_at'] else 'N/A'
                updated_str = sig['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if sig.get('updated_at') else 'N/A'
                if sig['created_at'] and sig.get('updated_at'):
                    time_diff = (sig['updated_at'] - sig['created_at']).total_seconds() / 60
                    print(f"  ID {sig['id']} ({sig['symbol__symbol']}): created={created_str}, updated={updated_str}, diff={time_diff:.1f} min")
                else:
                    print(f"  ID {sig['id']} ({sig['symbol__symbol']}): created={created_str}, updated={updated_str}")
        else:
            print("No recent signal updates found")
    except Exception as e:
        print(f"Error checking recent updates: {e}")
    
    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    diagnose_signal_timestamps()
