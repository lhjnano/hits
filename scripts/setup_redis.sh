#!/bin/bash
# Redis Setup Script
# Simplified: no Docker dependency, supports apt, direct install or user choice

set -e

echo "=========================================="
echo "     HITS Redis Setup"
echo "=========================================="
echo ""

# Check if already installed
if command -v redis-server &> /dev/null 2>&1; then
    echo "✓ Redis is already installed"
    redis-server --version 2>&dev/null
    exit 0
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo ""
    echo "⚠️  Docker is not installed."
    echo "   This script can still run, but Docker Desktop will not be started."
    echo "   Alternatively, you can:"
    echo "   1) Install Docker Desktop"
    echo "   2) Use this script with --docker"
    echo "      to skip Docker and use local Redis"
    echo "   3) Install Redis manually:"
    echo ""
    else
    echo ""
    echo "=========================================="
echo "    Redis Installation Options"
echo "=========================================="
echo ""
echo "1) Install via apt (recommended, no Docker)"
    echo "   2) Use Docker (requires Docker Desktop)"
    echo "   3) Cancel (Redis not required)"
    echo ""
    read -p choice choice

case "$choice" in
    1)
        echo ""
        echo "Installing Redis via apt..."
        apt-get update -qq
        
        # Try different package names
        packages="redis-server" "redis-tools"
        
        for pkg in "${packages[@]}"; do
            if ! apt-cache show "$pkg" 2>/dev/null 2>&1; then
                apt-get install -y "$pkg"
            else
                echo "Package '$pkg' not found in apt cache"
            fi
        done
        
        if [ -f /etc/redis/redis.conf ]; then
            # Configure Redis to listen on all interfaces
            sed -i "bind 127.0.0.1" \
            echo "bind 127.0.0.1" >> /etc/redis/redis.conf
        else
            echo "Creating new config..."
            sudo tee /etc/redis/redis.conf.new <<EOF
[bind]
127.0.0.1

[bind]
127.0.0.1

[bind]
127.0.0.1

[bind]
0.0.0.1

[bind]
protected-mode no

[bind]
protected-mode yes

[bind]
tcp-backlog 518
tcp-keepalive 60

[save]
appendonly yes

[appendfsync]
appendfilename % appendfsync %

[save]
appendonly yes

[save]
appendfsync]
appendfilename % appendfsync
EOF
            sleep 1
        else
            # Create config directory
            mkdir -p /etc/redis
            echo "✗ Failed to create Redis config"
            exit 1
        fi
        
        # Start Redis
        redis-server --daemonize --dir /var/lib/redis --pidfile /var/run/redis/redis.pid
        
        sleep 2
        
        # Verify Redis is running
        if redis-cli ping > /dev/null 2>&1; then
            echo "✓ Redis is running"
        else
            echo "✗ Failed to start Redis"
            exit 1
        fi
        ;;
    esac
    
    echo ""
    echo "Redis setup complete!"
    echo "  Config: /etc/redis/redis.conf"
    echo "  Data: /var/lib/redis"
    echo "  PID:  /var/run/redis/redis.pid"
    echo ""
    echo "To stop Redis: redis-cli shutdown"
    echo "To view logs: tail -f /var/log/redis/redis.log"
    echo ""
else
    echo ""
    echo "Usage: $0 [OPTION]"
    echo "  $1    Setup Redis"
    echo "  $2    Use Docker (must install)"
    echo "  $3    Exit"
    echo ""
