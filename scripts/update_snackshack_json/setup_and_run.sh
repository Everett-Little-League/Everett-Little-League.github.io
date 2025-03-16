#!/bin/bash
# Script to set up the virtual environment and run the snackshack updater

# Exit on error
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install or update dependencies
echo "Installing dependencies..."
pip install -r requirements.pip

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating sample .env file..."
    echo "SIGNUP_ID=your_signup_id" > .env
    echo "API_KEY=your_user_key" >> .env
    echo "Please edit the .env file with your actual SignUpGenius credentials."
    exit 1
fi

# Run the updater
echo "Running snackshack updater..."
python update.py

# Deactivate virtual environment
deactivate

echo "Done!" 