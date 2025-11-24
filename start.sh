#!/bin/bash
# Startup script for Grant Discovery with PostgreSQL + Pinecone

set -e  # Exit on error

echo "================================================================================"
echo "🔬 Starting Grant Discovery (PostgreSQL + Pinecone Hybrid RAG)"
echo "================================================================================"
echo ""

# Check if PostgreSQL is running
echo "Checking PostgreSQL..."
if ! docker ps | grep -q ailsa-postgres; then
    echo "❌ PostgreSQL container is not running!"
    echo "Start it with: docker start ailsa-postgres"
    echo "Or create it with the docker run command from the migration docs"
    exit 1
fi
echo "✓ PostgreSQL container is running"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    exit 1
fi
echo "✓ Environment file found"

# Load environment variables (filter out comments)
export $(grep -v '^#' .env | xargs)
echo "✓ Environment variables loaded"
echo ""

# Start API server in background
echo "Starting API server..."
python3 -m src.scripts.run_api &
API_PID=$!

# Wait for API to be ready
echo "Waiting for API to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ API server is ready (PID: $API_PID)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ API server failed to start"
        kill $API_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo ""
echo "================================================================================"
echo "✓ Backend API: http://localhost:8000"
echo "  Docs:        http://localhost:8000/docs"
echo "================================================================================"
echo ""
echo "Starting Streamlit UI..."
echo ""

# Start Streamlit (this will block)
streamlit run ui/app.py

# Cleanup on exit
trap "echo 'Stopping services...'; kill $API_PID 2>/dev/null || true" EXIT
