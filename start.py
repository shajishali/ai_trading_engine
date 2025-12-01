#!/usr/bin/env python3
"""
AI Trading Engine - Single Startup Script
=========================================

This is the ONLY script you need to run the entire AI Trading Engine project.
It automatically starts all required services.

Usage: python start.py
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TradingEngine:
    def __init__(self):
        self.processes = []
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Ensure we're in the project directory
        self.project_dir = Path(__file__).parent.absolute()
        os.chdir(self.project_dir)
        
        print(f"{Colors.CYAN}{Colors.BOLD}")
        print("=" * 50)
        print("    AI TRADING ENGINE")
        print("=" * 50)
        print(f"{Colors.END}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n{Colors.YELLOW}Stopping all services...{Colors.END}")
        self.running = False
        self.stop_all_services()

    def print_status(self, message, status="INFO"):
        """Print colored status messages"""
        timestamp = time.strftime("%H:%M:%S")
        color = Colors.GREEN if status == "SUCCESS" else Colors.RED if status == "ERROR" else Colors.BLUE
        print(f"{Colors.WHITE}[{timestamp}]{Colors.END} {color}[{status}]{Colors.END} {message}")

    def start_service(self, name, command, wait_time=2):
        """Start a service and track the process"""
        self.print_status(f"Starting {name}...")
        try:
            if isinstance(command, str):
                # For Windows batch commands
                if os.name == 'nt':
                    process = subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    process = subprocess.Popen(command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # For Python command lists
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            self.processes.append(process)
            time.sleep(wait_time)
            self.print_status(f"{name}: Started", "SUCCESS")
            return True
        except Exception as e:
            self.print_status(f"Failed to start {name}: {e}", "ERROR")
            return False

    def check_redis(self):
        """Check if Redis is running"""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            r.ping()
            return True
        except:
            return False

    def start_redis(self):
        """Start Redis server"""
        if self.check_redis():
            self.print_status("Redis: Already running", "SUCCESS")
            return True
        
        # Try different Redis startup methods
        redis_commands = [
            # Local executable
            "redis-server.exe redis.conf",
            # Windows service
            "net start redis",
            # System PATH
            "redis-server redis.conf"
        ]
        
        for cmd in redis_commands:
            if self.start_service("Redis", cmd, 3):
                if self.check_redis():
                    return True
        
        self.print_status("Redis startup failed - continuing without Redis", "ERROR")
        return False

    def run_migrations(self):
        """Run Django migrations"""
        self.print_status("Running database migrations...")
        try:
            result = subprocess.run([sys.executable, "manage.py", "migrate"], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.print_status("Migrations: Completed", "SUCCESS")
                return True
            else:
                self.print_status("Migrations failed - continuing anyway", "ERROR")
                return False
        except:
            self.print_status("Migration error - continuing anyway", "ERROR")
            return False

    def stop_all_services(self):
        """Stop all running services"""
        for process in self.processes:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
            except:
                pass
        self.processes.clear()

    def print_success_message(self):
        """Print success message with access info"""
        print(f"\n{Colors.GREEN}{Colors.BOLD}")
        print("=" * 50)
        print("    🚀 ALL SERVICES STARTED!")
        print("=" * 50)
        print(f"{Colors.END}")
        print(f"{Colors.CYAN}🌐 Main Application:{Colors.END}")
        print(f"   http://localhost:8000")
        print()
        print(f"{Colors.CYAN}📊 Key Features:{Colors.END}")
        print(f"   • Trading Signals: http://localhost:8000/signals/")
        print(f"   • Analytics: http://localhost:8000/analytics/")
        print(f"   • Portfolio: http://localhost:8000/dashboard/portfolio/")
        print(f"   • Backtesting: http://localhost:8000/backtesting/")
        print()
        print(f"{Colors.CYAN}⚙️  Running Services:{Colors.END}")
        print(f"   • Django Server (main web interface)")
        print(f"   • Celery Worker (executes tasks)")
        print(f"   • Celery Beat (schedules update coin task only)")
        print(f"   • Active Task: fetch-and-store-coins (every hour)")
        print()
        print(f"{Colors.YELLOW}⚠️  Press Ctrl+C to stop all services{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}=" * 50)
        print(f"{Colors.END}")

    def run(self):
        """Main execution method"""
        try:
            # Step 1: Run migrations
            self.run_migrations()
            
            # Step 2: Start Redis
            self.start_redis()
            
            # Step 3: Start Celery Worker (required for executing scheduled tasks)
            # Only the update coin task is scheduled - other tasks are disabled
            self.start_service("Celery Worker", [
                sys.executable, "-m", "celery", 
                "-A", "ai_trading_engine", 
                "worker", "-l", "info", "--pool=solo"
            ])
            
            # Step 4: Start Celery Beat (schedules the update coin task only)
            # Only 'fetch-and-store-coins' task is active - all others are disabled
            self.start_service("Celery Beat", [
                sys.executable, "-m", "celery", 
                "-A", "ai_trading_engine", 
                "beat", "-l", "info"
            ])
            
            # Step 5: Start Django Server
            self.start_service("Django Server", [
                sys.executable, "manage.py", "runserver", "0.0.0.0:8000"
            ])
            
            # Step 6: Open browser
            import webbrowser
            time.sleep(2)  # Wait 2 seconds for server to start
            self.print_status("Opening web browser...")
            webbrowser.open('http://localhost:8000')
            self.print_status("Browser opened", "SUCCESS")
            
            # Step 7: Print success message
            self.print_success_message()
            
            # Step 8: Keep running until interrupted
            try:
                while self.running:
                    time.sleep(1)
                    # Check if Django process is still running
                    if not any(p.poll() is None for p in self.processes):
                        self.print_status("Django server stopped", "ERROR")
                        break
            except KeyboardInterrupt:
                pass
                
        except Exception as e:
            self.print_status(f"Error: {e}", "ERROR")
            return False
        finally:
            self.stop_all_services()
        
        return True

def main():
    """Main entry point"""
    print(f"{Colors.WHITE}Starting AI Trading Engine...{Colors.END}")
    
    engine = TradingEngine()
    success = engine.run()
    
    if success:
        print(f"\n{Colors.GREEN}AI Trading Engine stopped successfully.{Colors.END}")
    else:
        print(f"\n{Colors.RED}AI Trading Engine stopped with errors.{Colors.END}")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()




























































