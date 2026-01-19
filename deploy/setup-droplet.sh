#!/bin/bash
# =============================================================================
# Biomedical Abstract Explorer - Droplet Setup Script
# Run this on your droplet as root to set up the application
# =============================================================================

set -e  # Exit on any error

# Configuration - CHANGE THESE
DOMAIN="YOUR_DOMAIN.com"  # Your domain pointing to this droplet
APP_DIR="/opt/openalex-digger"

echo "🚀 Setting up Biomedical Abstract Explorer on this droplet..."
echo "   Domain: $DOMAIN"
echo ""

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install dependencies
echo "📦 Installing Python 3.11 and Caddy..."
apt install -y python3.11 python3.11-venv python3.11-dev git curl

# Install Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy

# Create app directory
echo "📁 Creating application directory..."
mkdir -p $APP_DIR
mkdir -p /var/log/openalex-digger
mkdir -p /var/log/caddy

# Set permissions
chown -R www-data:www-data /var/log/openalex-digger

echo ""
echo "✅ Base setup complete!"
echo ""
echo "📋 Next steps (run these manually):"
echo ""
echo "1. Clone/copy your app to $APP_DIR:"
echo "   rsync -avz --exclude '.git' --exclude '__pycache__' --exclude 'venv' \\"
echo "     /path/to/openalex.author.abstract.digger/ root@YOUR_DROPLET_IP:$APP_DIR/"
echo ""
echo "2. Set up Python virtual environment:"
echo "   cd $APP_DIR"
echo "   python3.11 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "3. Configure Caddy (edit domain in Caddyfile):"
echo "   nano $APP_DIR/deploy/Caddyfile  # Change YOUR_DOMAIN.com"
echo "   cp $APP_DIR/deploy/Caddyfile /etc/caddy/Caddyfile"
echo "   systemctl restart caddy"
echo ""
echo "4. Create environment file with your API keys:"
echo "   nano $APP_DIR/.env"
echo "   # Add: GEMINI_API_KEY=your-api-key-here"
echo "   chmod 600 $APP_DIR/.env"
echo "   chown www-data:www-data $APP_DIR/.env"
echo ""
echo "5. Enable the systemd service:"
echo "   cp $APP_DIR/deploy/openalex-digger.service /etc/systemd/system/"
echo "   systemctl daemon-reload"
echo "   systemctl enable openalex-digger"
echo "   systemctl start openalex-digger"
echo ""
echo "6. Check status:"
echo "   systemctl status openalex-digger"
echo "   systemctl status caddy"
echo "   curl localhost:8000  # Should return HTML"
echo ""
echo "🎉 Your app will be live at https://$DOMAIN"

