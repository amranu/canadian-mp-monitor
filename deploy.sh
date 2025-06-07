#!/bin/bash

# Canadian MP Monitor Deployment Script
# Usage: ./deploy.sh [environment]

set -e

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$SCRIPT_DIR/ansible"

echo "🚀 Deploying Canadian MP Monitor to $ENVIRONMENT environment..."

# Check if ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Ansible is not installed. Please install it first:"
    echo "   pip install ansible"
    exit 1
fi

# Check if inventory file exists
if [ ! -f "$ANSIBLE_DIR/inventory.yml" ]; then
    echo "❌ Inventory file not found: $ANSIBLE_DIR/inventory.yml"
    exit 1
fi

# Check if variables file exists
if [ ! -f "$ANSIBLE_DIR/group_vars/all.yml" ]; then
    echo "❌ Variables file not found: $ANSIBLE_DIR/group_vars/all.yml"
    echo "Please configure your deployment variables."
    exit 1
fi

# Check for required variables
echo "🔍 Checking configuration..."
if ! grep -q "git_repo:" "$ANSIBLE_DIR/group_vars/all.yml" || grep -q "yourusername" "$ANSIBLE_DIR/group_vars/all.yml"; then
    echo "❌ Please update git_repo in ansible/group_vars/all.yml with your actual repository URL"
    exit 1
fi

if grep -q "your-email@example.com" "$ANSIBLE_DIR/group_vars/all.yml"; then
    echo "❌ Please update letsencrypt_email in ansible/group_vars/all.yml with your actual email"
    exit 1
fi

# Run ansible playbook
echo "📦 Running Ansible playbook..."
cd "$ANSIBLE_DIR"

ansible-playbook \
    -i inventory.yml \
    deploy.yml \
    --extra-vars "environment=$ENVIRONMENT" \
    -v

echo "✅ Deployment completed successfully!"
echo "🌐 Your application should be available at: https://mptracker.ca"
echo "🔍 Health check: https://mptracker.ca/health"