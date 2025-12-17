#!/usr/bin/env python
"""
Signal Generation Runner
Continuously generates trading signals for all active symbols
"""

import os
import sys
import io
import django
import time
import logging
from datetime import datetime
from django.utils import timezone

# Setup Django environment
# Get the backend directory (parent of scripts directory)
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.core.management import call_command
from apps.signals.models import TradingSignal

# Configure logging with UTF-8 encoding support
# Ensure stdout uses UTF-8 encoding on Windows
if sys.platform == 'win32':
    # Reconfigure stdout to use UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    elif hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def generate_signals():
    """
    Generate trading signals using Django management command
    """
    try:
        logger.info("=" * 60)
        logger.info("Starting signal generation cycle...")
        logger.info("=" * 60)
        
        # Call the Django management command
        call_command('generate_signals', verbosity=2)
        
        # Get count of active signals
        active_signals = TradingSignal.objects.filter(is_valid=True).count()
        logger.info(f"Total active signals in database: {active_signals}")
        
        logger.info("=" * 60)
        logger.info("Signal generation cycle completed successfully!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Error during signal generation: {e}", exc_info=True)
        return False


def main():
    """
    Main function to run signal generation continuously
    """
    logger.info("=" * 60)
    logger.info("TRADING SIGNAL GENERATION RUNNER")
    logger.info("=" * 60)
    logger.info("This script will continuously generate trading signals")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    logger.info("")
    
    # Configuration
    UPDATE_INTERVAL = 60 * 60  # 1 hour in seconds (3600 seconds)
    INITIAL_DELAY = 30  # Wait 30 seconds before first generation
    
    try:
        logger.info(f"Waiting {INITIAL_DELAY} seconds before first signal generation...")
        time.sleep(INITIAL_DELAY)
        
        cycle_count = 0
        
        while True:
            cycle_count += 1
            logger.info("")
            logger.info(f"[*] Signal Generation Cycle #{cycle_count}")
            logger.info(f"[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("")
            
            # Generate signals
            success = generate_signals()
            
            if success:
                logger.info(f"[OK] Cycle #{cycle_count} completed successfully")
            else:
                logger.warning(f"[WARNING] Cycle #{cycle_count} completed with errors")
            
            # Wait for next cycle
            logger.info("")
            logger.info(f"[WAIT] Next signal generation in {UPDATE_INTERVAL // 60} minutes...")
            logger.info("=" * 60)
            
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("Signal generation stopped by user")
        logger.info("=" * 60)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in signal generation runner: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

