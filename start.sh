#!/bin/bash
# Simple startup script for Grant Discovery

echo "Starting Grant Discovery..."
echo ""
echo "Backend API: http://localhost:8000"
echo "Frontend UI: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Load environment variables
export $(cat .env | xargs)

# Start Streamlit
streamlit run app.py
