#!/bin/bash
# Start the Streamlit UI for Ask Ailsa

# Make sure backend is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  Backend API is not running!"
    echo "Please start it first with: ./start_api.sh"
    exit 1
fi

echo "✓ Backend API is running"
echo "Starting Ask Ailsa UI..."
echo ""

# Start Streamlit
streamlit run ui/app.py
