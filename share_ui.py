#!/usr/bin/env python3
"""
Quick script to create shareable links for Ask Ailsa using pyngrok.
This script sets up tunnels for both the backend API and frontend UI.
"""

import subprocess
import time
import sys
import os

def main():
    print("🚀 Setting up shareable links for Ask Ailsa...")
    print()

    # Check if pyngrok is installed
    try:
        from pyngrok import ngrok
    except ImportError:
        print("❌ pyngrok not installed. Installing now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
        from pyngrok import ngrok
        print("✅ pyngrok installed successfully")
        print()

    # Start backend in background
    print("📡 Starting backend API...")
    api_process = subprocess.Popen(
        ["python3", "-m", "src.scripts.run_api", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, **dict(line.strip().split('=', 1) for line in open('.env') if '=' in line)}
    )

    # Wait for backend to start
    print("⏳ Waiting for backend to be ready...")
    time.sleep(5)

    # Create tunnel for backend
    print("🌐 Creating public tunnel for backend API...")
    api_tunnel = ngrok.connect(8000, bind_tls=True)
    api_url = api_tunnel.public_url
    print(f"✅ Backend API available at: {api_url}")
    print()

    # Update ui/app.py with the new backend URL
    print("🔧 Updating frontend to use public backend URL...")
    with open('ui/app.py', 'r') as f:
        ui_code = f.read()

    # Replace localhost backend with ngrok URL
    ui_code = ui_code.replace(
        'BACKEND_URL = "http://localhost:8000"',
        f'BACKEND_URL = "{api_url}"  # Auto-updated by share_ui.py'
    )

    with open('ui/app.py', 'w') as f:
        f.write(ui_code)

    print("✅ Frontend updated")
    print()

    # Start Streamlit
    print("🎨 Starting Streamlit UI...")
    ui_process = subprocess.Popen(
        ["streamlit", "run", "ui/app.py", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for Streamlit to start
    print("⏳ Waiting for Streamlit to be ready...")
    time.sleep(5)

    # Create tunnel for Streamlit
    print("🌐 Creating public tunnel for frontend UI...")
    ui_tunnel = ngrok.connect(8501, bind_tls=True)
    ui_url = ui_tunnel.public_url

    print()
    print("=" * 60)
    print("✨ Ask Ailsa is now publicly accessible!")
    print("=" * 60)
    print()
    print(f"🔗 Share this link with testers:")
    print(f"   {ui_url}")
    print()
    print(f"📊 Backend API: {api_url}")
    print(f"🎨 Frontend UI: {ui_url}")
    print()
    print("⚠️  These links are public - anyone with the URL can access your app")
    print("⏱️  Links remain active as long as this script is running")
    print()
    print("Press Ctrl+C to stop and clean up...")
    print("=" * 60)

    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("🛑 Shutting down...")

        # Restore original ui/app.py
        print("🔧 Restoring original frontend configuration...")
        ui_code = ui_code.replace(
            f'BACKEND_URL = "{api_url}"  # Auto-updated by share_ui.py',
            'BACKEND_URL = "http://localhost:8000"'
        )
        with open('ui/app.py', 'w') as f:
            f.write(ui_code)

        # Cleanup
        print("🧹 Cleaning up processes...")
        api_process.terminate()
        ui_process.terminate()
        ngrok.disconnect(api_tunnel.public_url)
        ngrok.disconnect(ui_tunnel.public_url)

        print("✅ Cleanup complete. Goodbye!")

if __name__ == "__main__":
    main()
