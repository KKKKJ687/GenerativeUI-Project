#!/bin/bash
# Start the GenerativeUI Project Web Application

# Navigate to project root
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check for API Key
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  Warning: GOOGLE_API_KEY not found in environment."
    echo "You may need to enter it in the Web UI sidebar."
fi

echo "🚀 Starting GenerativeUI Project..."
streamlit run app.py
