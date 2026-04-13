#!/bin/bash
# Toll Navigator - Hetzner Deploy Script
# Usage: ./deploy/hetzner-setup.sh

set -e

echo "🚛 Toll Navigator - Deploy Setup"

# Update system
apt-get update -y

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install PM2
npm install -g pm2

# Clone/pull project (adjust to your git remote)
if [ -d "/opt/toll-navigator" ]; then
  cd /opt/toll-navigator && git pull
else
  git clone YOUR_GIT_URL /opt/toll-navigator
  cd /opt/toll-navigator
fi

# Install dependencies
cd backend && npm ci --only=production

# Setup data directory
mkdir -p /opt/toll-navigator/data

# Start with PM2
cd /opt/toll-navigator/backend
pm2 start ecosystem.config.js
pm2 save
pm2 startup

echo "✅ Toll Navigator deployed on port 3001"
