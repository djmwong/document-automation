#!/bin/bash
# Setup script for Document Automation System

set -e

echo "========================================="
echo "Document Automation System Setup"
echo "========================================="

OS="$(uname -s)"
case "${OS}" in
    Linux*)     OS_TYPE=Linux;;
    Darwin*)    OS_TYPE=Mac;;
    *)          OS_TYPE="Unknown"
esac

echo "Detected OS: ${OS_TYPE}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 required"
    exit 1
fi

# Install system dependencies
echo ""
echo "Installing system dependencies..."
if [ "${OS_TYPE}" = "Mac" ]; then
    brew install tesseract poppler 2>/dev/null || true
elif [ "${OS_TYPE}" = "Linux" ]; then
    sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
[ ! -d "venv" ] && python3 -m venv venv

# Activate and install
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Playwright
echo ""
echo "Installing Playwright..."
playwright install chromium

# Create directories
mkdir -p uploads screenshots

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "To run:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Optional: Add OpenAI key for better passport extraction:"
echo "  echo 'OPENAI_API_KEY=sk-your-key' > .env"
