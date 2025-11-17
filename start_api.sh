#!/bin/bash
# Load environment variables from .env
export $(cat .env | xargs)

# Start the API server
python3 -m src.scripts.run_api --reload
