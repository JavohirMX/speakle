# Speakle Docker Deployment Guide

This guide provides comprehensive instructions for deploying the Speakle language exchange platform using Docker.

## 📋 Prerequisites

- Docker (v20.10+)
- Docker Compose (v2.0+)
- Git
- Domain name (for production)
- SSL certificates (for HTTPS)

## 🏗️ Architecture Overview

The Docker setup includes:
- **Django Application**: Main web server with WebSocket support
- **PostgreSQL**: Primary database
- **Redis**: Channel layer for real-time features
- **Nginx**: Reverse proxy and static file server

## 🚀 Quick Start

### Development Environment

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd speakle
   ```

2. **Start development environment**:
   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

3. **Access the application**:
   - Web app: http://localhost:8001
   - Database: localhost:5433
   - Redis: localhost:6380

### Production Environment

1. **Prepare environment variables**:
   ```bash
   cp env.example .env
   # Edit .env with your production values
   ```

2. **Build and start services**:
   ```bash
   docker-compose up --build -d
   ```

3. **Access the application**:
   - Web app: http://localhost (via Nginx)
   - Direct Django: http://localhost:8001
   - Database: localhost:5433
   - Redis: localhost:6380

## 📁 File Structure

```
speakle/
├── Dockerfile              # Production Django container
├── Dockerfile.dev          # Development Django container
├── docker-compose.yml      # Production stack
├── docker-compose.dev.yml  # Development stack
├── nginx.conf              # Nginx configuration
├── entrypoint.sh           # Container initialization script
├── .dockerignore           # Docker build context exclusions
├── env.example             # Environment variables template
└── config/
    └── settings_prod.py    # Production Django settings
```

## ⚙️ Configuration

### Environment Variables

Key variables in `.env`:

```bash
# Security
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgres://speakle_user:speakle_password@db:5432/speakle

# Redis
REDIS_URL=redis://redis:6379/0

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### SSL/HTTPS Setup

1. **Obtain SSL certificates** (Let's Encrypt recommended):
   ```bash
   mkdir ssl
   # Copy your certificates to ssl/cert.pem and ssl/key.pem
   ```

2. **Update nginx.conf**:
   - Uncomment HTTPS server block
   - Update domain names
   - Configure certificate paths

3. **Update environment variables**:
   ```bash
   SECURE_SSL_REDIRECT=True
   CSRF_COOKIE_SECURE=True
   SESSION_COOKIE_SECURE=True
   ```

## 🛠️ Management Commands

### Start Services

```bash
# Development
docker-compose -f docker-compose.dev.yml up

# Production
docker-compose up -d
```

### Database Operations

```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Database backup
docker-compose exec db pg_dump -U speakle_user speakle > backup.sql

# Database restore
docker-compose exec -T db psql -U speakle_user speakle < backup.sql
```

### Application Management

```bash
# View logs
docker-compose logs -f web

# Execute Django commands
docker-compose exec web python manage.py collectstatic
docker-compose exec web python manage.py shell

# Restart services
docker-compose restart web
```

### Scaling and Performance

```bash
# Scale Django workers
docker-compose up --scale web=3

# Monitor resource usage
docker stats

# Update containers
docker-compose pull
docker-compose up --build -d
```

## 🔧 Troubleshooting

### Common Issues

1. **Database connection errors**:
   ```bash
   # Check database status
   docker-compose exec db pg_isready -U speakle_user
   
   # View database logs
   docker-compose logs db
   ```

2. **WebSocket connection issues**:
   ```bash
   # Check Redis connectivity
   docker-compose exec redis redis-cli ping
   
   # View application logs
   docker-compose logs web
   ```

3. **Static files not loading**:
   ```bash
   # Rebuild with fresh static files
   docker-compose exec web python manage.py collectstatic --clear
   docker-compose restart nginx
   ```

4. **Permission issues**:
   ```bash
   # Fix volume permissions
   docker-compose exec web chown -R appuser:appuser /app/media
   ```

### Health Checks

```bash
# Check service health
docker-compose ps

# Test application endpoints
curl http://localhost/health/

# Test WebSocket connectivity
wscat -c ws://localhost/ws/notifications/
```

## 📊 Monitoring

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f nginx
docker-compose logs -f db
docker-compose logs -f redis
```

### Performance Metrics

```bash
# Container resource usage
docker stats

# Database performance
docker-compose exec db psql -U speakle_user -d speakle -c "SELECT * FROM pg_stat_activity;"

# Redis info
docker-compose exec redis redis-cli info
```

## 🔒 Security Considerations

1. **Change default passwords** in production
2. **Use environment variables** for sensitive data
3. **Enable SSL/HTTPS** for production
4. **Regular security updates**:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```
5. **Backup strategy** for data persistence
6. **Firewall configuration** for exposed ports

## 🚀 Production Deployment Checklist

- [ ] Update `env.example` with production values
- [ ] Configure SSL certificates
- [ ] Update domain names in nginx.conf
- [ ] Set up regular database backups
- [ ] Configure monitoring and alerting
- [ ] Test WebSocket functionality
- [ ] Verify email configuration
- [ ] Load test the application
- [ ] Set up log rotation
- [ ] Configure firewall rules

## 📞 Support

For deployment issues:
1. Check this guide first
2. Review Docker logs
3. Verify environment configuration
4. Test individual services
5. Check network connectivity

## 🔄 Updates and Maintenance

### Regular Updates

```bash
# Update containers
docker-compose pull
docker-compose up -d

# Update application code
git pull
docker-compose build web
docker-compose up -d web
```

### Database Maintenance

```bash
# Vacuum and analyze
docker-compose exec db psql -U speakle_user -d speakle -c "VACUUM ANALYZE;"

# Check database size
docker-compose exec db psql -U speakle_user -d speakle -c "SELECT pg_size_pretty(pg_database_size('speakle'));"
```

This deployment setup provides a robust, scalable foundation for the Speakle platform with proper separation of concerns and production-ready configurations. 