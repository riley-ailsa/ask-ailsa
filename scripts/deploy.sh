#!/bin/bash
#
# Deployment script for Grant Discovery API
#
# Usage:
#   ./scripts/deploy.sh [environment]
#
# Environment: production (default) or staging
#

set -e  # Exit on error

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Grant Discovery API Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Project Dir: $PROJECT_DIR"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose first."
    exit 1
fi

echo "✓ Docker found: $(docker --version)"
echo "✓ docker-compose found: $(docker-compose --version)"
echo ""

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file from .env.example:"
    echo "  cp .env.example .env"
    echo "  # Edit .env and add your OPENAI_API_KEY"
    exit 1
fi

# Check for OPENAI_API_KEY
source "$PROJECT_DIR/.env"
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY not set in .env file"
    exit 1
fi

echo "✓ .env file found"
echo "✓ OPENAI_API_KEY configured"
echo ""

# Create data directory if it doesn't exist
mkdir -p "$PROJECT_DIR/data"
echo "✓ Data directory created/verified"
echo ""

# Pull latest code (if in git repo)
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "Pulling latest code..."
    cd "$PROJECT_DIR"
    git pull origin main || echo "⚠️  Git pull failed (continuing anyway)"
    echo ""
fi

# Stop existing containers
echo "Stopping existing containers..."
cd "$PROJECT_DIR"
docker-compose down || echo "⚠️  No containers to stop"
echo ""

# Build Docker image
echo "Building Docker image..."
docker-compose build --no-cache
echo "✓ Docker image built"
echo ""

# Start containers
echo "Starting containers..."
docker-compose up -d
echo "✓ Containers started"
echo ""

# Wait for health check
echo "Waiting for API to be healthy..."
sleep 5

MAX_RETRIES=12
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/health > /dev/null; then
        echo "✓ API is healthy!"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Attempt $RETRY_COUNT/$MAX_RETRIES - waiting..."
    sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ API health check failed after $MAX_RETRIES attempts"
    echo "Checking logs..."
    docker-compose logs --tail=50
    exit 1
fi

echo ""
echo "=========================================="
echo "Deployment Successful!"
echo "=========================================="
echo "API: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo ""
echo "Useful commands:"
echo "  View logs:       docker-compose logs -f"
echo "  Stop service:    docker-compose down"
echo "  Restart service: docker-compose restart"
echo "  Inspect DB:      python scripts/inspect_db.py --db data/grants.db"
echo "=========================================="
