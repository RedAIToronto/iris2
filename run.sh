#!/bin/bash

# Create necessary directories if they don't exist
mkdir -p static/gallery
mkdir -p data

# Install dependencies
pip install -r requirements.txt

# Start the application
python main.py 