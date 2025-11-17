#!/bin/bash
#
# Database backup script for Grant Discovery
#
# Usage:
#   ./scripts/backup_db.sh [db_path] [backup_dir]
#
# Defaults:
#   db_path: data/grants.db
#   backup_dir: backups/
#

set -e  # Exit on error

DB_PATH=${1:-"data/grants.db"}
BACKUP_DIR=${2:-"backups"}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="grants_backup_${TIMESTAMP}.db"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Grant Discovery Database Backup"
echo "=========================================="
echo "Database: $DB_PATH"
echo "Backup Dir: $BACKUP_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""

# Check if database exists
if [ ! -f "$PROJECT_DIR/$DB_PATH" ]; then
    echo "❌ Database not found: $PROJECT_DIR/$DB_PATH"
    exit 1
fi

# Create backup directory
mkdir -p "$PROJECT_DIR/$BACKUP_DIR"
echo "✓ Backup directory created/verified"

# Get database size
DB_SIZE=$(du -h "$PROJECT_DIR/$DB_PATH" | cut -f1)
echo "✓ Database size: $DB_SIZE"
echo ""

# Perform backup (using SQLite's backup command for consistency)
echo "Creating backup..."

if command -v sqlite3 &> /dev/null; then
    # Use SQLite's VACUUM INTO for consistent backup
    sqlite3 "$PROJECT_DIR/$DB_PATH" "VACUUM INTO '$PROJECT_DIR/$BACKUP_DIR/$BACKUP_NAME';"
    echo "✓ Backup created using SQLite VACUUM INTO"
else
    # Fallback to cp (less safe but works)
    cp "$PROJECT_DIR/$DB_PATH" "$PROJECT_DIR/$BACKUP_DIR/$BACKUP_NAME"
    echo "✓ Backup created using cp (install sqlite3 for safer backups)"
fi

# Verify backup exists
if [ ! -f "$PROJECT_DIR/$BACKUP_DIR/$BACKUP_NAME" ]; then
    echo "❌ Backup failed - file not created"
    exit 1
fi

BACKUP_SIZE=$(du -h "$PROJECT_DIR/$BACKUP_DIR/$BACKUP_NAME" | cut -f1)
echo "✓ Backup verified: $BACKUP_SIZE"
echo ""

# Compress backup
echo "Compressing backup..."
gzip "$PROJECT_DIR/$BACKUP_DIR/$BACKUP_NAME"
COMPRESSED_NAME="${BACKUP_NAME}.gz"
COMPRESSED_SIZE=$(du -h "$PROJECT_DIR/$BACKUP_DIR/$COMPRESSED_NAME" | cut -f1)
echo "✓ Compressed: $COMPRESSED_SIZE"
echo ""

# Clean up old backups (keep last 7 days)
echo "Cleaning up old backups (keeping last 7 days)..."
find "$PROJECT_DIR/$BACKUP_DIR" -name "grants_backup_*.db.gz" -type f -mtime +7 -delete
REMAINING=$(find "$PROJECT_DIR/$BACKUP_DIR" -name "grants_backup_*.db.gz" -type f | wc -l | tr -d ' ')
echo "✓ Cleanup complete ($REMAINING backups remaining)"
echo ""

echo "=========================================="
echo "Backup Successful!"
echo "=========================================="
echo "Backup file: $BACKUP_DIR/$COMPRESSED_NAME"
echo "Original size: $DB_SIZE"
echo "Compressed size: $COMPRESSED_SIZE"
echo ""
echo "Restore command:"
echo "  gunzip -c $BACKUP_DIR/$COMPRESSED_NAME > $DB_PATH"
echo "=========================================="
