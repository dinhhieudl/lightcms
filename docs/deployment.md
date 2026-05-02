# Z-Core Deployment Guide

## Deployment Options

| Method | Complexity | Best For |
|--------|-----------|----------|
| Direct (systemd) | Low | VPS with FastPanel |
| Docker | Medium | Any Docker-capable host |
| Docker Compose | Medium | Production with volumes |

## Prerequisites

- Python 3.11+ (or Docker)
- 512MB+ RAM
- 1GB+ disk space
- Nginx (for production reverse proxy)

## Option 1: Direct Deployment (FastPanel)

### Step 1: Server Setup

```bash
# SSH into server
ssh root@your-server-ip

# Install Python 3.11+ if needed
apt update && apt install -y python3 python3-pip python3-venv git

# Clone repository
cd /var/www
git clone https://github.com/dinhhieudl/lightcms.git zcore
cd zcore
```

### Step 2: Application Setup

```bash
# Run automated setup
chmod +x scripts/*.sh
./scripts/setup.sh
```

The setup script:
1. Creates Python virtual environment (`venv/`)
2. Installs dependencies from `requirements.txt`
3. Copies `.env.example` → `.env` with generated secret key
4. Creates `data/` directory for SQLite
5. Initializes database (creates all tables)
6. Prompts for admin username/password

### Step 3: Configure Environment

```bash
nano .env
```

**Required changes:**
```bash
ZCORE_SITE_URL=https://your-domain.com
ZCORE_SITE_TITLE=Your Store Name
ZCORE_SECRET_KEY=<already-generated-by-setup.sh>
```

**Optional (enable notifications):**
```bash
ZCORE_TELEGRAM_BOT_TOKEN=your-token
ZCORE_TELEGRAM_CHAT_ID=your-chat-id
ZCORE_SMTP_HOST=smtp.gmail.com
ZCORE_SMTP_USER=you@gmail.com
ZCORE_SMTP_PASS=your-app-password
```

### Step 4: Systemd Service

Create service file:
```bash
sudo nano /etc/systemd/system/zcore.service
```

```ini
[Unit]
Description=Z-Core CMS
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/zcore
Environment=PATH=/var/www/zcore/venv/bin
ExecStart=/var/www/zcore/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
# Set permissions
sudo chown -R www-data:www-data /var/www/zcore/data
sudo chown -R www-data:www-data /var/www/zcore/app/static/uploads

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable zcore
sudo systemctl start zcore

# Check status
sudo systemctl status zcore
sudo journalctl -u zcore -f
```

### Step 5: Nginx Configuration

**Via FastPanel:**
1. FastPanel → Sites → Select domain
2. Nginx Settings → Custom config
3. Paste content from `config/nginx.conf`
4. Update `server_name` and `alias` paths
5. Save → Restart Nginx

**Manual:**
```bash
# Copy config
sudo cp config/nginx.conf /etc/nginx/sites-available/zcore.conf

# Edit paths
sudo nano /etc/nginx/sites-available/zcore.conf
# Change:
#   server_name your-domain.com;
#   alias /var/www/zcore/app/static/;

# Enable site
sudo ln -sf /etc/nginx/sites-available/zcore.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6: SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Certbot automatically modifies Nginx config for HTTPS.

### Step 7: Verify

```bash
# Check app responds
curl -I https://your-domain.com

# Check admin accessible
curl -I https://your-domain.com/admin/login

# Check static files
curl -I https://your-domain.com/static/css/style.css

# Check sitemap
curl https://your-domain.com/sitemap.xml
```

## Option 2: Docker Deployment

### Build Image

```bash
cd /path/to/lightcms
docker build -t zcore -f docker/Dockerfile .
```

### Run Container

```bash
docker run -d \
    --name zcore \
    --restart unless-stopped \
    -p 8000:8000 \
    -v zcore-data:/app/data \
    -v ./uploads:/app/app/static/uploads \
    --env-file .env \
    zcore
```

### Docker Compose

```bash
cd docker
# Edit ../.env first
docker compose up -d
```

`docker-compose.yml`:
```yaml
version: "3.8"
services:
  zcore:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: zcore
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - zcore-data:/app/data
      - ./uploads:/app/app/static/uploads
    env_file:
      - ../.env
volumes:
  zcore-data:
```

## Option 3: Docker + Nginx (Production)

Same as Option 2, but add Nginx as reverse proxy:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /var/www/zcore/app/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Updating (Zero-Downtime Deploy)

### Automated

```bash
cd /var/www/zcore
./scripts/deploy.sh
```

The deploy script:
1. Backs up database to `backups/`
2. Pulls latest code from Git
3. Updates Python dependencies
4. Builds CSS (if Tailwind CLI present)
5. Restarts application (systemd/Docker/pm2)
6. Runs health check
7. Auto-rolls back on failure

### Manual

```bash
cd /var/www/zcore

# Backup
cp data/zcore.db backups/zcore_$(date +%Y%m%d_%H%M%S).db

# Update
git pull origin main
source venv/bin/activate
pip install -q -r requirements.txt

# Restart
sudo systemctl restart zcore
```

## Database Backup

### Automated (cron)

```bash
# Add to crontab
crontab -e

# Daily backup at 3 AM
0 3 * * * /var/www/zcore/scripts/backup.sh >> /var/log/zcore-backup.log 2>&1
```

### Manual

```bash
./scripts/backup.sh
# Creates: backups/zcore_20260502_100000.db.gz
```

### Restore

```bash
# Stop app
sudo systemctl stop zcore

# Restore database
gunzip backups/zcore_20260502_100000.db.gz
cp backups/zcore_20260502_100000.db data/zcore.db

# Start app
sudo systemctl start zcore
```

## Performance Tuning

### Uvicorn Workers

```bash
# In systemd service, adjust --workers based on CPU cores
ExecStart=... --workers 2  # 1-2 for small VPS
ExecStart=... --workers 4  # 4 for 4-core server
```

Rule of thumb: `workers = 2 * CPU_CORES + 1`

### SQLite Optimization

Already configured in database.py:
```sql
PRAGMA journal_mode=WAL;      -- Concurrent reads
PRAGMA foreign_keys=ON;        -- Data integrity
PRAGMA busy_timeout=5000;      -- Wait on lock
```

For large databases (>1GB), add:
```sql
PRAGMA cache_size=-64000;      -- 64MB cache
PRAGMA mmap_size=268435456;    -- 256MB memory-mapped I/O
```

### Nginx Caching

Add to nginx.conf for static assets:
```nginx
location /static/ {
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;
}
```

## Monitoring

### Health Check

```bash
# HTTP health check
curl -sf http://localhost:8000/ || echo "DOWN"

# Database check
sqlite3 data/zcore.db "SELECT COUNT(*) FROM products;"
```

### Logs

```bash
# Application logs (systemd)
journalctl -u zcore -f

# Nginx logs
tail -f /var/log/nginx/zcore_access.log
tail -f /var/log/nginx/zcore_error.log
```

### Disk Usage

```bash
# Database size
du -sh data/zcore.db

# Uploads size
du -sh app/static/uploads/

# Total app size
du -sh /var/www/zcore/
```

## Troubleshooting

### Port Already in Use

```bash
# Find process on port 8000
lsof -i :8000
# Kill it
kill <pid>
```

### Permission Denied

```bash
# Fix data directory permissions
sudo chown -R www-data:www-data /var/www/zcore/data
sudo chown -R www-data:www-data /var/www/zcore/app/static/uploads
```

### Database Locked

```bash
# Check for zombie connections
lsof data/zcore.db
# Restart app
sudo systemctl restart zcore
```

### 502 Bad Gateway

```bash
# Check if app is running
sudo systemctl status zcore

# Check if app listens on correct port
ss -tlnp | grep 8000

# Check Nginx config
sudo nginx -t
```

### SSL Issues

```bash
# Renew certificate
sudo certbot renew

# Check certificate
sudo certbot certificates
```
