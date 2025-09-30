#!/bin/bash

# Start Main API Gateway
echo "Starting main service..."
python3 /path/to/main/app.py &

# Start File Service
echo "Starting file service..."
python3 /path/to/file_service/app.py &

# Start Extraction Service
echo "Starting extraction service..."
python3 /path/to/extraction_service/app.py &

# Wait for all background jobs
wait
