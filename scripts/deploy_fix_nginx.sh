#!/bin/bash
# Write nginx config with SSL
NGINX_CONF="/etc/nginx/sites-enabled/beauty-specialist"

sudo tee "$NGINX_CONF" > /dev/null << 'EOF'

server {
    listen 80;
    server_name beauty-specialist.ru www.beauty-specialist.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name beauty-specialist.ru www.beauty-specialist.ru;

    # Phone photos (JPEG/HEIC) are often 5-15MB. Nginx defaults to 1MB,
    # which rejected uploads with HTML 413 before FastAPI could downscale
    # them. Keep this above backend MAX_AVATAR_BYTES (15MB).
    client_max_body_size 20m;

    ssl_certificate /etc/letsencrypt/live/beauty-specialist.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/beauty-specialist.ru/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    root /var/www/beauty-specialist/frontend/dist;
    index index.html;

    # Hashed assets (Vite) — cache permanently, immutable
    location ~* \.(js|css)$ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        add_header Pragma "no-cache";
        add_header Expires "0";
        expires -1;
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
        expires -1;
    }

    # Uploaded avatars and certificates are stored by FastAPI and must not
    # fall through to the SPA (index.html).
    location /static/ {
        proxy_pass http://127.0.0.1:8000/static/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/dadata/ {
        proxy_pass http://127.0.0.1:8000/api/dadata/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
EOF

# Validate nginx config before restarting
if sudo nginx -t 2>&1; then
    echo "✓ nginx config is valid"
    if sudo systemctl restart nginx 2>&1; then
        echo "✓ nginx restarted successfully"
    else
        echo "ERROR: nginx failed to restart!"
        exit 1
    fi
else
    echo "ERROR: nginx config test failed!"
    sudo nginx -t 2>&1
    exit 1
fi
echo "nginx config written and restarted"
