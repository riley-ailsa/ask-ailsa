#!/usr/bin/env python3
"""
Monitor the API's embedding indexing progress.
"""

import sys
import os
import time
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def monitor_indexing():
    """Monitor embedding indexing progress."""

    print("=" * 80)
    print("EMBEDDING INDEXING MONITOR")
    print("=" * 80)

    # Get total counts from database
    conn = sqlite3.connect("grants.db")
    cursor = conn.cursor()

    # Total embeddings in database
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    total_embeddings = cursor.fetchone()[0]

    # Embeddings for enhanced content (linked pages, PDFs)
    cursor.execute("""
        SELECT COUNT(*) FROM embeddings
        WHERE doc_type IN ('linked_page', 'pdf', 'partner_page')
    """)
    enhanced_embeddings = cursor.fetchone()[0]

    # Get unique documents
    cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM embeddings")
    unique_docs = cursor.fetchone()[0]

    print(f"\n📊 Database Statistics:")
    print(f"  Total embeddings: {total_embeddings:,}")
    print(f"  Enhanced content embeddings: {enhanced_embeddings:,}")
    print(f"  Unique documents with embeddings: {unique_docs:,}")

    # Check API server status
    import subprocess
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True,
        text=True
    )

    api_running = False
    for line in result.stdout.split('\n'):
        if 'python3 -m src.scripts.run_api' in line and 'grep' not in line:
            api_running = True
            # Extract memory usage
            parts = line.split()
            if len(parts) > 5:
                pid = parts[1]
                cpu = parts[2]
                mem = parts[3]
                vsz = int(parts[4]) / 1024  # Convert to MB
                rss = int(parts[5]) / 1024  # Convert to MB

                print(f"\n🚀 API Server Status:")
                print(f"  PID: {pid}")
                print(f"  CPU Usage: {cpu}%")
                print(f"  Memory Usage: {mem}%")
                print(f"  Virtual Memory: {vsz:.1f} MB")
                print(f"  Resident Memory: {rss:.1f} MB")
                break

    if not api_running:
        print(f"\n⚠️  API Server not running")

    # Try to check if API is responsive
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            print(f"\n✅ API is responsive")

            # Try to get index stats if available
            try:
                response = requests.get("http://localhost:8000/api/stats", timeout=2)
                if response.status_code == 200:
                    stats = response.json()
                    print(f"\n📈 Index Statistics:")
                    for key, value in stats.items():
                        print(f"  {key}: {value}")
            except:
                pass
    except:
        print(f"\n⏳ API is starting up (not yet responsive)")

    # Estimate loading progress based on memory usage
    if api_running:
        # Rough estimate: ~20K embeddings = ~1GB memory
        estimated_loaded = min(int(rss / 50), total_embeddings)  # 50MB per 1000 embeddings
        progress = (estimated_loaded / total_embeddings * 100) if total_embeddings > 0 else 0

        print(f"\n📊 Estimated Loading Progress:")
        print(f"  Estimated embeddings loaded: ~{estimated_loaded:,}/{total_embeddings:,}")
        print(f"  Progress: {progress:.1f}%")

        # Progress bar
        bar_length = 50
        filled_length = int(bar_length * progress // 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        print(f"  [{bar}] {progress:.1f}%")

        if progress < 100:
            # Estimate time remaining (very rough)
            remaining = total_embeddings - estimated_loaded
            eta_seconds = remaining / 100  # Assume 100 embeddings per second
            eta_minutes = eta_seconds / 60
            print(f"  Estimated time to complete: ~{eta_minutes:.1f} minutes")

    conn.close()
    print("\n" + "=" * 80)

    # Monitor tips
    print("\n💡 Tips:")
    print("  - The API loads embeddings into memory on startup")
    print("  - With 20K embeddings, this can take 2-5 minutes")
    print("  - Memory usage will stabilize once loading is complete")
    print("  - You can test search while it's loading (partial results)")

if __name__ == "__main__":
    monitor_indexing()