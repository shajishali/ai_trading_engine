#!/usr/bin/env python
"""
S3 Deployment Script for AI Trading Engine

This script handles the migration from local file storage to AWS S3.
It collects static files, uploads them to S3, and migrates existing media files.

Usage:
    python deploy_to_s3.py [--settings=ai_trading_engine.settings_production]
"""

import os
import sys
import django
import argparse
import logging
from pathlib import Path
from django.core.management import execute_from_command_line
from django.core.files.storage import default_storage
from django.conf import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_django(settings_module='ai_trading_engine.settings_production'):
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    django.setup()


def check_s3_configuration():
    """Check if S3 is properly configured"""
    logger.info("Checking S3 configuration...")
    
    required_settings = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 
        'AWS_STORAGE_BUCKET_NAME',
        'AWS_S3_REGION_NAME'
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not hasattr(settings, setting) or not getattr(settings, setting):
            missing_settings.append(setting)
    
    if missing_settings:
        logger.error(f"Missing S3 configuration: {', '.join(missing_settings)}")
        logger.error("Please set these environment variables or add them to your .env file")
        return False
    
    logger.info("S3 configuration looks good!")
    return True


def collect_static_files():
    """Collect static files and upload to S3"""
    logger.info("Collecting static files...")
    
    try:
        # Run collectstatic command
        execute_from_command_line(['manage.py', 'collectstatic', '--noinput'])
        logger.info("Static files collected successfully!")
        return True
    except Exception as e:
        logger.error(f"Error collecting static files: {e}")
        return False


def migrate_media_files():
    """Migrate existing media files to S3"""
    logger.info("Migrating media files to S3...")
    
    try:
        from apps.data.tasks import migrate_local_files_to_s3_task
        
        # Run migration task
        result = migrate_local_files_to_s3_task()
        
        if result['status'] == 'success':
            logger.info(f"Migration completed successfully!")
            logger.info(f"Migrated {result['migrated_count']} files")
            if result['error_count'] > 0:
                logger.warning(f"Encountered {result['error_count']} errors during migration")
            return True
        else:
            logger.error(f"Migration failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error migrating media files: {e}")
        return False


def test_s3_connection():
    """Test S3 connection and permissions"""
    logger.info("Testing S3 connection...")
    
    try:
        # Test if we can access the bucket
        test_key = 'test/connection_test.txt'
        test_content = b'This is a test file for S3 connection'
        
        # Upload test file
        default_storage.save(test_key, test_content)
        logger.info("Successfully uploaded test file to S3")
        
        # Check if file exists
        if default_storage.exists(test_key):
            logger.info("Successfully verified file exists in S3")
            
            # Download and verify content
            with default_storage.open(test_key, 'rb') as f:
                downloaded_content = f.read()
                if downloaded_content == test_content:
                    logger.info("Successfully verified file content")
                else:
                    logger.error("File content verification failed")
                    return False
            
            # Clean up test file
            default_storage.delete(test_key)
            logger.info("Successfully deleted test file from S3")
            
        else:
            logger.error("Test file not found in S3")
            return False
            
        logger.info("S3 connection test passed!")
        return True
        
    except Exception as e:
        logger.error(f"S3 connection test failed: {e}")
        return False


def create_s3_directory_structure():
    """Create necessary directory structure in S3"""
    logger.info("Creating S3 directory structure...")
    
    directories = [
        'static/',
        'media/',
        'media/models/',
        'media/charts/',
        'media/reports/',
        'media/backups/',
        'logs/',
    ]
    
    try:
        for directory in directories:
            # Create empty file to establish directory structure
            placeholder_key = f"{directory}.gitkeep"
            default_storage.save(placeholder_key, b'')
            logger.info(f"Created directory: {directory}")
        
        logger.info("S3 directory structure created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error creating S3 directory structure: {e}")
        return False


def cleanup_local_files():
    """Clean up local static and media files after successful migration"""
    logger.info("Cleaning up local files...")
    
    try:
        # Only clean up if S3 is being used
        if not getattr(settings, 'USE_S3', False):
            logger.info("S3 not enabled, skipping local file cleanup")
            return True
        
        # Clean up staticfiles directory
        staticfiles_dir = getattr(settings, 'STATIC_ROOT', None)
        if staticfiles_dir and os.path.exists(staticfiles_dir):
            import shutil
            shutil.rmtree(staticfiles_dir)
            logger.info(f"Removed local staticfiles directory: {staticfiles_dir}")
        
        # Clean up media directory (be careful with this!)
        media_dir = getattr(settings, 'MEDIA_ROOT', None)
        if media_dir and os.path.exists(media_dir):
            logger.warning(f"Media directory exists: {media_dir}")
            logger.warning("Manual cleanup required for media files")
            logger.warning("Please verify S3 migration before deleting local media files")
        
        logger.info("Local file cleanup completed!")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up local files: {e}")
        return False


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(description='Deploy AI Trading Engine to S3')
    parser.add_argument(
        '--settings',
        default='ai_trading_engine.settings_production',
        help='Django settings module to use'
    )
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip S3 connection tests'
    )
    parser.add_argument(
        '--skip-cleanup',
        action='store_true',
        help='Skip local file cleanup'
    )
    
    args = parser.parse_args()
    
    logger.info("Starting S3 deployment for AI Trading Engine...")
    
    # Setup Django
    setup_django(args.settings)
    
    # Check S3 configuration
    if not check_s3_configuration():
        sys.exit(1)
    
    # Test S3 connection
    if not args.skip_tests:
        if not test_s3_connection():
            logger.error("S3 connection test failed. Aborting deployment.")
            sys.exit(1)
    
    # Create S3 directory structure
    if not create_s3_directory_structure():
        logger.error("Failed to create S3 directory structure. Aborting deployment.")
        sys.exit(1)
    
    # Collect static files
    if not collect_static_files():
        logger.error("Failed to collect static files. Aborting deployment.")
        sys.exit(1)
    
    # Migrate media files
    if not migrate_media_files():
        logger.error("Failed to migrate media files. Aborting deployment.")
        sys.exit(1)
    
    # Clean up local files
    if not args.skip_cleanup:
        if not cleanup_local_files():
            logger.warning("Local file cleanup failed, but deployment was successful")
    
    logger.info("S3 deployment completed successfully!")
    logger.info("Your AI Trading Engine is now using S3 for file storage.")
    
    # Print next steps
    print("\n" + "="*60)
    print("DEPLOYMENT COMPLETE!")
    print("="*60)
    print("Next steps:")
    print("1. Verify your S3 bucket contains the uploaded files")
    print("2. Test your application to ensure files are served correctly")
    print("3. Set up CloudFront CDN for better performance (optional)")
    print("4. Configure S3 lifecycle policies for cost optimization")
    print("5. Set up monitoring for S3 usage and costs")
    print("="*60)


if __name__ == '__main__':
    main()





















