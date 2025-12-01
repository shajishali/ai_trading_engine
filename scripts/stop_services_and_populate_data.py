"""
Helper script to stop all services and populate historical data for all coins
"""
import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

def stop_processes_by_name(process_names):
    """Stop processes by name (works on Windows and Unix)"""
    import platform
    stopped = []
    
    if platform.system() == 'Windows':
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                for name in process_names:
                    if name.lower() in cmdline.lower() or name.lower() in proc.info['name'].lower():
                        try:
                            proc.terminate()
                            stopped.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
                        except:
                            pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    else:
        # Unix/Linux/Mac
        try:
            for name in process_names:
                result = subprocess.run(
                    ['pkill', '-f', name],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    stopped.append(name)
        except:
            pass
    
    return stopped

def stop_celery_processes():
    """Stop Celery worker and beat processes"""
    print("Stopping Celery processes...")
    stopped = stop_processes_by_name(['celery', 'celerybeat'])
    if stopped:
        print(f"  ✓ Stopped: {', '.join(stopped)}")
    else:
        print("  ℹ No Celery processes found")
    time.sleep(1)

def stop_redis():
    """Stop Redis server"""
    print("Stopping Redis server...")
    import platform
    if platform.system() == 'Windows':
        # Try to stop Redis on Windows
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if 'redis' in proc.info['name'].lower():
                    try:
                        proc.terminate()
                        print(f"  ✓ Stopped Redis (PID: {proc.info['pid']})")
                        time.sleep(1)
                        return
                    except:
                        pass
        except ImportError:
            print("  ℹ psutil not available - please stop Redis manually")
        print("  ℹ Please stop Redis manually if running")
    else:
        stopped = stop_processes_by_name(['redis-server'])
        if stopped:
            print(f"  ✓ Stopped Redis")
        else:
            print("  ℹ Redis not running or couldn't stop")

def stop_django_server():
    """Stop Django development server"""
    print("Stopping Django server...")
    stopped = stop_processes_by_name(['runserver', 'manage.py'])
    if stopped:
        print(f"  ✓ Stopped Django server")
        time.sleep(1)
    else:
        print("  ℹ Django server not running")

def run_population_command():
    """Run the population command"""
    print("\n" + "="*60)
    print("Starting Historical Data Population")
    print("="*60 + "\n")
    
    try:
        # Run the Django management command
        result = subprocess.run(
            [sys.executable, 'manage.py', 'populate_all_coins_historical_data'],
            cwd=backend_dir
        )
        
        if result.returncode == 0:
            print("\n" + "="*60)
            print("✓ Historical data population completed successfully!")
            print("="*60)
            return True
        else:
            print("\n" + "="*60)
            print("✗ Historical data population failed!")
            print("="*60)
            return False
            
    except KeyboardInterrupt:
        print("\n\n⚠ Population interrupted by user")
        return False
    except Exception as e:
        print(f"\n✗ Error running population command: {e}")
        return False

def main():
    """Main function"""
    print("="*60)
    print("Stop Services & Populate Historical Data")
    print("="*60)
    print()
    
    # Step 1: Stop all services
    print("Step 1: Stopping all services...")
    print("-" * 60)
    stop_celery_processes()
    stop_django_server()
    stop_redis()
    print()
    
    # Wait a bit for processes to fully stop
    print("Waiting 3 seconds for processes to stop...")
    time.sleep(3)
    print()
    
    # Step 2: Run population command
    success = run_population_command()
    
    if success:
        print("\n" + "="*60)
        print("Next Steps:")
        print("  1. Start services again: python start.py")
        print("  2. Verify data: Check admin panel or run signals generation")
        print("="*60)
    
    return 0 if success else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)










