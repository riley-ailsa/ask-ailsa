#!/usr/bin/env python3
"""
Monitor enhancement progress in real-time.
"""

import time
import subprocess
import sys

def monitor_enhancement():
    """Monitor the enhancement progress."""

    print("=" * 60)
    print("ENHANCEMENT PROGRESS MONITOR")
    print("=" * 60)

    while True:
        try:
            # Count processed grants
            result = subprocess.run(
                ["grep", "-c", "Processing", "enhancement_full_450.log"],
                capture_output=True,
                text=True
            )
            processed = int(result.stdout.strip()) if result.stdout.strip() else 0

            # Check if complete
            result = subprocess.run(
                ["grep", "ENHANCEMENT COMPLETE", "enhancement_full_450.log"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"\n✅ ENHANCEMENT COMPLETE!")
                # Show final stats
                subprocess.run(["tail", "-15", "enhancement_full_450.log"])
                break

            # Calculate progress
            total = 450
            percent = (processed / total) * 100
            remaining = total - processed

            # Estimate time
            if processed > 10:
                avg_time = processed * 1.5  # Rough estimate of 1.5 seconds per grant
                eta = remaining * 1.5 / 60  # Minutes
                print(f"\r[{processed}/{total}] {percent:.1f}% complete - ETA: {eta:.1f} minutes", end="")
            else:
                print(f"\r[{processed}/{total}] {percent:.1f}% complete - Calculating ETA...", end="")

            time.sleep(5)  # Check every 5 seconds

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break

if __name__ == "__main__":
    monitor_enhancement()