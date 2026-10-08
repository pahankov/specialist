#!/bin/bash
# Проверка бэкенда на сервере
# Запустить: sudo bash check_backend.sh

echo "=== SERVICE STATUS ==="
systemctl status beauty-backend --no-pager -l 2>&1 | head -20

echo ""
echo "=== JOURNAL LOGS ==="
journalctl -u beauty-backend --no-pager -n 50 2>&1

echo ""
echo "=== PORT CHECK ==="
ss -tlnp | grep 8000 || echo "Port 8000 not listening"

echo ""
echo "=== PYTHON TEST ==="
cd /var/www/beauty-specialist/online-booking/backend
source venv/bin/activate
python3.12 -c "
from app.main import app
print('App loaded successfully')
" 2>&1 | head -20

echo ""
echo "=== DATABASE CHECK ==="
python3.12 -c "
from app.database import engine
try:
    with engine.connect() as conn:
        result = conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        print('Database connected:', result.scalar())
except Exception as e:
    print('Database error:', e)
" 2>&1
