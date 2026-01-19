#!/bin/bash
# =============================================================================
# Quick deploy script - run from your local machine
# Usage: ./deploy.sh user@your-droplet-ip
# =============================================================================

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh user@droplet-ip"
    echo "Example: ./deploy.sh root@164.92.123.45"
    exit 1
fi

REMOTE="$1"
APP_DIR="/opt/openalex-digger"

echo "🚀 Deploying Biomedical Abstract Explorer to $REMOTE..."

# Sync files (excluding unnecessary stuff)
echo "📦 Syncing files..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'venv' \
    --exclude '.env' \
    --exclude '*.egg-info' \
    ./ "$REMOTE:$APP_DIR/"

# Run remote commands
echo "🔧 Installing dependencies and restarting service..."
ssh "$REMOTE" << 'ENDSSH'
cd /opt/openalex-digger

# Create venv if doesn't exist
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi

# Install/update dependencies
source venv/bin/activate
pip install -q -r requirements.txt

# Restart the service
systemctl restart openalex-digger

echo "✅ Deployment complete!"
ENDSSH

echo ""
echo "🎉 Deployed! Check your site in a few seconds."

