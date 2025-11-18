#!/usr/bin/env python3
"""
Track API loading progress by monitoring memory usage.
"""

import time
import subprocess
import sys

def get_api_memory():
    """Get API process memory usage in MB."""
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )

    for line in result.stdout.split('\n'):
        if 'python3 -m src.scripts.run_api' in line and 'grep' not in line:
            parts = line.split()
            if len(parts) > 5:
                rss_kb = int(parts[5])
                return rss_kb / 1024  # Convert to MB
    return 0

def track_loading():
    """Track API loading progress."""

    print("=" * 60)
    print("API EMBEDDING LOADING TRACKER")
    print("=" * 60)
    print("\nMonitoring memory usage to track embedding loading...")
    print("(70,080 embeddings to load - estimated 3-5GB memory needed)\n")

    start_time = time.time()
    last_mem = 0
    stable_count = 0
    max_mem = 0

    while True:
        current_mem = get_api_memory()
        elapsed = time.time() - start_time
        elapsed_min = elapsed / 60

        if current_mem > max_mem:
            max_mem = current_mem

        # Estimate progress (rough: assume 50MB per 1000 embeddings)
        estimated_loaded = min(int(current_mem / 50) * 1000, 70080)
        progress = (estimated_loaded / 70080) * 100

        # Check if stable (loading complete)
        mem_change = abs(current_mem - last_mem)
        if mem_change < 10:  # Less than 10MB change
            stable_count += 1
        else:
            stable_count = 0

        # Display progress
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        status = "Loading" if stable_count < 5 else "Stabilizing"
        if stable_count >= 10:
            status = "Ready!"

        print(f"\r[{bar}] {progress:.1f}% | "
              f"Memory: {current_mem:.1f}MB | "
              f"Est. Embeddings: {estimated_loaded:,}/70,080 | "
              f"Time: {elapsed_min:.1f}min | "
              f"Status: {status}", end="")

        if stable_count >= 10 and current_mem > 100:
            print(f"\n\n✅ Loading Complete!")
            print(f"  Final memory usage: {current_mem:.1f}MB")
            print(f"  Peak memory usage: {max_mem:.1f}MB")
            print(f"  Total time: {elapsed_min:.1f} minutes")
            print(f"  Estimated embeddings loaded: {estimated_loaded:,}")
            break

        last_mem = current_mem
        time.sleep(5)

    # Test API
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            print(f"\n✅ API is responsive and ready for queries!")
    except:
        print(f"\n⚠️  API health check failed")

if __name__ == "__main__":
    try:
        track_loading()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")