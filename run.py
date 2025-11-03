#!/usr/bin/env python3
"""
OTrade - Unified Server Launcher
Runs both backend (FastAPI) and frontend (SvelteKit) servers
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_colored(message, color=Colors.OKGREEN):
    """Print colored message"""
    print(f"{color}{message}{Colors.ENDC}")


def check_python_packages():
    """Check if required Python packages are installed"""
    print_colored("\n📦 Checking Python dependencies...", Colors.OKCYAN)
    
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import pydantic
        print_colored("✅ All Python packages installed", Colors.OKGREEN)
        return True
    except ImportError as e:
        print_colored(f"❌ Missing Python package: {e}", Colors.FAIL)
        print_colored("\nInstalling Python dependencies...", Colors.WARNING)
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True


def check_node_packages():
    """Check if Node.js and npm are available"""
    print_colored("\n📦 Checking Node.js dependencies...", Colors.OKCYAN)
    
    try:
        subprocess.run(["node", "--version"], check=True, capture_output=True)
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
        print_colored("✅ Node.js and npm are available", Colors.OKGREEN)
        
        # Check if node_modules exists
        if not Path("frontend/node_modules").exists():
            print_colored("📥 Installing frontend dependencies...", Colors.WARNING)
            subprocess.run(["npm", "install"], cwd="frontend", check=True)
        
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_colored("❌ Node.js or npm not found", Colors.FAIL)
        print_colored("Please install Node.js from https://nodejs.org/", Colors.WARNING)
        return False


def setup_environment():
    """Setup environment variables"""
    if not Path(".env").exists():
        print_colored("\n⚙️  Creating .env file from template...", Colors.WARNING)
        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print_colored("✅ .env file created. Please update it with your credentials.", Colors.OKGREEN)
        else:
            print_colored("❌ .env.example not found", Colors.FAIL)


def start_backend():
    """Start FastAPI backend server"""
    print_colored("\n🚀 Starting Backend Server...", Colors.OKBLUE)
    
    # Get port from environment, default to 8000
    backend_port = os.getenv("BACKEND_PORT", "8000")
    # Use 0.0.0.0 to allow connections from both localhost and 127.0.0.1
    backend_host = os.getenv("BACKEND_HOST", "0.0.0.0")
    
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host", backend_host,
        "--port", backend_port,
        "--reload"
    ]
    
    return subprocess.Popen(
        backend_cmd,
        # Show output directly in terminal
        # stdout=subprocess.PIPE,
        # stderr=subprocess.STDOUT,
        # universal_newlines=True
    )


def start_frontend():
    """Start SvelteKit frontend server"""
    print_colored("\n🚀 Starting Frontend Server...", Colors.OKBLUE)
    
    # Get port from environment, default to 5173
    frontend_port = os.getenv("FRONTEND_PORT", "5173")
    frontend_host = os.getenv("HOST", "127.0.0.1")
    
    frontend_cmd = [
        "npm", "run", "dev", "--", 
        "--host", frontend_host, 
        "--port", frontend_port,
        "--strictPort"  # Exit if port is already in use instead of trying alternatives
    ]
    
    return subprocess.Popen(
        frontend_cmd,
        cwd="frontend",
        # Show output directly in terminal
        # stdout=subprocess.PIPE,
        # stderr=subprocess.STDOUT,
        # universal_newlines=True
    )


def print_startup_info():
    """Print startup information"""
    backend_port = os.getenv("BACKEND_PORT", "8000")
    frontend_port = os.getenv("FRONTEND_PORT", "5173")
    backend_host = os.getenv("BACKEND_HOST", "0.0.0.0")
    frontend_host = os.getenv("HOST", "127.0.0.1")
    
    # Display localhost for user-friendly URLs even when binding to 0.0.0.0
    display_host = "localhost" if backend_host == "0.0.0.0" else backend_host
    
    print_colored("\n" + "="*60, Colors.HEADER)
    print_colored("🎯 OTrade - Algorithmic Trading Platform", Colors.HEADER + Colors.BOLD)
    print_colored("="*60, Colors.HEADER)
    print_colored("\n📍 Server URLs:", Colors.OKCYAN)
    print_colored(f"   Backend:  http://{display_host}:{backend_port}", Colors.OKGREEN)
    print_colored(f"   Frontend: http://{frontend_host}:{frontend_port}", Colors.OKGREEN)
    print_colored(f"   API Docs: http://{display_host}:{backend_port}/docs", Colors.OKGREEN)
    print_colored("\n💡 Press Ctrl+C to stop both servers\n", Colors.WARNING)
    print_colored("="*60 + "\n", Colors.HEADER)


def main():
    """Main function to run both servers"""
    print_colored("\n" + "="*60, Colors.HEADER)
    print_colored("🚀 OTrade Server Launcher", Colors.HEADER + Colors.BOLD)
    print_colored("="*60 + "\n", Colors.HEADER)
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_python_packages():
        sys.exit(1)
    
    if not check_node_packages():
        sys.exit(1)
    
    # Start servers
    backend_process = None
    frontend_process = None
    
    try:
        backend_process = start_backend()
        time.sleep(3)  # Wait for backend to start
        
        frontend_process = start_frontend()
        time.sleep(3)  # Wait for frontend to start
        
        print_startup_info()
        
        # Monitor processes
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if backend_process.poll() is not None:
                print_colored("\n❌ Backend process died!", Colors.FAIL)
                break
            
            if frontend_process.poll() is not None:
                print_colored("\n❌ Frontend process died!", Colors.FAIL)
                break
    
    except KeyboardInterrupt:
        print_colored("\n\n⏹️  Shutting down servers...", Colors.WARNING)
    
    finally:
        # Cleanup
        if backend_process:
            print_colored("Stopping backend...", Colors.WARNING)
            backend_process.terminate()
            backend_process.wait(timeout=5)
        
        if frontend_process:
            print_colored("Stopping frontend...", Colors.WARNING)
            frontend_process.terminate()
            frontend_process.wait(timeout=5)
        
        print_colored("\n✅ Servers stopped successfully\n", Colors.OKGREEN)


if __name__ == "__main__":
    main()
