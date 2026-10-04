#!/bin/bash
# Write nginx config with SSL
cat > /etc/nginx/sites-enabled/beauty-specialist << 'EOF'
server {
    listen 80;
    server_name beauty-specialist.ru www.beauty-specialist.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name beauty-specialist.ru www.beauty-specialist.ru;

    ssl_certificate /etc/letsencrypt/live/beauty-specialist.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/beauty-specialist.ru/privkey.pem;

    root /var/www/beauty-specialist/frontend/dist;
    index index.html;

    location ~* \.(js|css)$ {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    location /api/dadata/ {
        proxy_pass https://suggestions.dadata.ru/suggestions/api/v4/rich/;
        proxy_set_header Host suggestions.dadata.ru;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header X-Secret $http_x_secret;
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

nginx -t && systemctl restart nginx
echo "nginx config written and restarted"
