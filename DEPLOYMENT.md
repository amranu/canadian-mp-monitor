# Deployment Guide for Canadian MP Monitor

This guide covers deploying the Canadian MP Monitor application to your VPS using Ansible, Docker, and nginx.

## Prerequisites

### Local Machine
- Ansible installed (`pip install ansible`)
- SSH access to your VPS
- Git repository hosted (GitHub, GitLab, etc.)

### VPS Requirements
- Ubuntu 20.04+ or Debian 10+
- Root access or sudo privileges
- Domain name pointing to the server (mptracker.ca)
- Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)

## Setup Instructions

### 1. Configure Variables

Edit `ansible/group_vars/all.yml`:

```yaml
# Update these required fields:
git_repo: "https://github.com/yourusername/canadian-mp-monitor.git"
letsencrypt_email: "your-email@example.com"
```

### 2. Configure Inventory

Edit `ansible/inventory.yml` if needed:

```yaml
all:
  children:
    production:
      hosts:
        mptracker:
          ansible_host: mptracker.ca  # Your server IP or domain
          ansible_user: root          # Your SSH user
          ansible_ssh_private_key_file: ~/.ssh/id_rsa  # Your SSH key
```

### 3. Deploy

Run the deployment script:

```bash
./deploy.sh
```

Or run Ansible directly:

```bash
cd ansible
ansible-playbook -i inventory.yml deploy.yml -v
```

## Architecture Overview

### Services
- **Backend**: Flask API (port 5000) - Serves /api/* endpoints
- **Frontend**: React app with serve (port 3000) - Serves static files
- **Nginx**: Reverse proxy (ports 80/443) - SSL termination and routing
- **Certbot**: SSL certificate management

### File Structure
```
/home/user/mp-monitor/
├── backend/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
├── nginx/
│   ├── nginx.conf
│   └── conf.d/default.conf
├── docker-compose.yml
└── ansible/
    ├── deploy.yml
    ├── inventory.yml
    └── group_vars/all.yml
```

### Docker Volumes
- `backend_cache`: Persistent storage for MP and vote caches
- `certbot_conf`: SSL certificates
- `certbot_www`: Certbot challenge files

## Deployment Process

1. **System Setup**: Install Docker, docker-compose, configure firewall
2. **Repository Clone**: Pull latest code from your Git repository
3. **SSL Certificate**: Obtain Let's Encrypt certificate for domain
4. **Container Build**: Build Docker images for backend and frontend
5. **Service Start**: Launch all services with docker-compose
6. **Health Check**: Verify all services are running correctly

## Post-Deployment

### Monitoring
- Health check endpoint: `https://mptracker.ca/health`
- Backend status: `https://mptracker.ca/api/`
- Docker logs: `docker-compose logs -f [service]`

### SSL Certificate Renewal
- Automatic renewal via cron job (daily at 2 AM)
- Manual renewal: `docker-compose exec certbot certbot renew`

### Updates
To deploy updates:
```bash
./deploy.sh
```

The script will:
1. Pull latest code from repository
2. Rebuild containers if needed
3. Restart services with zero downtime

### Backup
Backend cache data is stored in Docker volume `backend_cache`. To backup:
```bash
docker run --rm -v mp-monitor_backend_cache:/data -v $(pwd):/backup alpine tar czf /backup/cache-backup.tar.gz /data
```

## Troubleshooting

### Common Issues

**SSL Certificate Fails**
- Ensure domain points to server IP
- Check firewall allows ports 80/443
- Verify nginx is serving challenge files

**Backend API Not Responding**
- Check backend container logs: `docker-compose logs backend`
- Verify cache directory permissions
- Check if Open Parliament API is accessible

**Frontend Not Loading**
- Check frontend container logs: `docker-compose logs frontend`
- Verify build completed successfully
- Check nginx proxy configuration

### Log Locations
- Nginx: `docker-compose logs nginx`
- Backend: `docker-compose logs backend`
- Frontend: `docker-compose logs frontend`
- System: `/var/log/nginx/` (on host)

### Useful Commands
```bash
# View all service status
docker-compose ps

# Restart specific service
docker-compose restart [service]

# Rebuild and restart all services
docker-compose up --build -d

# View logs for all services
docker-compose logs -f

# Access backend shell
docker-compose exec backend bash

# Check SSL certificate
openssl s_client -connect mptracker.ca:443 -servername mptracker.ca
```

## Security Features

- Non-root containers
- UFW firewall configuration
- SSL/TLS encryption
- Security headers in nginx
- Container isolation
- Log rotation

## Performance Optimizations

- Gzip compression
- Container health checks
- Persistent cache storage
- Nginx caching headers
- Log rotation
- Resource limits (configurable)

## Environment Variables

Configure in `docker-compose.yml` if needed:

```yaml
environment:
  - FLASK_ENV=production
  - FLASK_DEBUG=false
  - CACHE_DURATION=10800  # 3 hours
```