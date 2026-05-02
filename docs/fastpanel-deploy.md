# Z-Core — FastPanel Deployment Guide

## Prerequisites

- FastPanel installed on server
- Python 3.11+
- Domain pointed to server IP

## Step 1: SSH into Server

```bash
ssh root@your-server-ip
```

## Step 2: Clone Repository

```bash
cd /var/www/
git clone https://github.com/dinhhieudl/lightcms.git zcore
cd zcore
```

## Step 3: Run Setup

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

This will:
- Create Python virtual environment
- Install dependencies
- Generate `.env` with secure secret key
- Initialize SQLite database
- Create admin user

## Step 4: Configure Environment

```bash
nano .env
```

Update these values:
```
ZCORE_SITE_URL=https://your-domain.com
ZCORE_SITE_TITLE=Your Store Name
ZCORE_SECRET_KEY=<generated-automatically>
ZCORE_TELEGRAM_BOT_TOKEN=your-bot-token
ZCORE_TELEGRAM_CHAT_ID=your-chat-id
```

## Step 5: Create Systemd Service

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

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /var/www/zcore/data
sudo systemctl daemon-reload
sudo systemctl enable zcore
sudo systemctl start zcore
```

## Step 6: Nginx Config in FastPanel

1. Go to **FastPanel** → **Sites** → Select your domain
2. Go to **Nginx Settings** → **Custom config**
3. Paste the content from `config/nginx.conf`
4. Update `server_name` and `alias` paths
5. Save and restart Nginx

Or manually:
```bash
cp config/nginx.conf /etc/nginx/sites-available/zcore.conf
# Edit paths in the file
nano /etc/nginx/sites-available/zcore.conf
ln -s /etc/nginx/sites-available/zcore.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

## Step 7: SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## Step 8: Verify

```bash
# Check app
curl -I https://your-domain.com

# Check admin
curl -I https://your-domain.com/admin

# Check logs
journalctl -u zcore -f
```

## Updates

```bash
cd /var/www/zcore
./scripts/deploy.sh
```

## Backups

```bash
./scripts/backup.sh
```

Backups are stored in `backups/` directory. Deploy script auto-backs up before each deploy.
