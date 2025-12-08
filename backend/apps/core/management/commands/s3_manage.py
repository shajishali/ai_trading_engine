"""
Django management command for S3 operations
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.files.storage import default_storage
from django.conf import settings
from apps.data.tasks import (
    upload_file_to_s3_task,
    download_file_from_s3_task,
    migrate_local_files_to_s3_task,
    cleanup_s3_files_task
)
import os


class Command(BaseCommand):
    help = 'Manage S3 operations for AI Trading Engine'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['test', 'migrate', 'cleanup', 'upload', 'download', 'list'],
            help='Action to perform'
        )
        parser.add_argument(
            '--file-path',
            help='Local file path for upload/download operations'
        )
        parser.add_argument(
            '--s3-key',
            help='S3 key for upload/download operations'
        )
        parser.add_argument(
            '--prefix',
            default='',
            help='S3 prefix for list operation'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'test':
            self.test_s3_connection()
        elif action == 'migrate':
            self.migrate_files()
        elif action == 'cleanup':
            self.cleanup_files()
        elif action == 'upload':
            self.upload_file(options['file_path'], options['s3_key'])
        elif action == 'download':
            self.download_file(options['s3_key'], options['file_path'])
        elif action == 'list':
            self.list_files(options['prefix'])

    def test_s3_connection(self):
        """Test S3 connection"""
        self.stdout.write("Testing S3 connection...")
        
        try:
            # Test upload
            test_key = 'test/connection_test.txt'
            test_content = b'This is a test file'
            
            from django.core.files.base import ContentFile
            default_storage.save(test_key, ContentFile(test_content))
            self.stdout.write(
                self.style.SUCCESS("✓ Successfully uploaded test file")
            )
            
            # Test download
            if default_storage.exists(test_key):
                with default_storage.open(test_key, 'rb') as f:
                    content = f.read()
                    if content == test_content:
                        self.stdout.write(
                            self.style.SUCCESS("✓ Successfully downloaded and verified file")
                        )
                    else:
                        raise CommandError("File content verification failed")
            
            # Clean up
            default_storage.delete(test_key)
            self.stdout.write(
                self.style.SUCCESS("✓ Successfully deleted test file")
            )
            
            self.stdout.write(
                self.style.SUCCESS("S3 connection test passed!")
            )
            
        except Exception as e:
            raise CommandError(f"S3 connection test failed: {e}")

    def migrate_files(self):
        """Migrate local files to S3"""
        self.stdout.write("Starting file migration to S3...")
        
        try:
            result = migrate_local_files_to_s3_task()
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Migration completed! Migrated {result['migrated_count']} files"
                    )
                )
                if result['error_count'] > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Encountered {result['error_count']} errors during migration"
                        )
                    )
            else:
                raise CommandError(f"Migration failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            raise CommandError(f"Migration failed: {e}")

    def cleanup_files(self):
        """Clean up old files from S3"""
        self.stdout.write("Starting S3 cleanup...")
        
        try:
            result = cleanup_s3_files_task()
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS("S3 cleanup completed!")
                )
            else:
                raise CommandError(f"Cleanup failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            raise CommandError(f"Cleanup failed: {e}")

    def upload_file(self, file_path, s3_key):
        """Upload a file to S3"""
        if not file_path or not s3_key:
            raise CommandError("Both --file-path and --s3-key are required for upload")
        
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")
        
        self.stdout.write(f"Uploading {file_path} to S3 as {s3_key}...")
        
        try:
            result = upload_file_to_s3_task(file_path, s3_key)
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully uploaded to S3: {result['s3_key']}")
                )
            else:
                raise CommandError(f"Upload failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            raise CommandError(f"Upload failed: {e}")

    def download_file(self, s3_key, file_path):
        """Download a file from S3"""
        if not s3_key or not file_path:
            raise CommandError("Both --s3-key and --file-path are required for download")
        
        self.stdout.write(f"Downloading {s3_key} from S3 to {file_path}...")
        
        try:
            result = download_file_from_s3_task(s3_key, file_path)
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully downloaded to: {result['local_path']}")
                )
            else:
                raise CommandError(f"Download failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            raise CommandError(f"Download failed: {e}")

    def list_files(self, prefix):
        """List files in S3"""
        self.stdout.write(f"Listing files in S3 with prefix: {prefix or '(root)'}")
        
        try:
            files, dirs = default_storage.listdir(prefix)
            
            if files:
                self.stdout.write("\nFiles:")
                for file in files:
                    self.stdout.write(f"  📄 {file}")
            
            if dirs:
                self.stdout.write("\nDirectories:")
                for dir in dirs:
                    self.stdout.write(f"  📁 {dir}/")
            
            if not files and not dirs:
                self.stdout.write("No files found.")
                
        except Exception as e:
            raise CommandError(f"List operation failed: {e}")
