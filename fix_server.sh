#!/bin/bash
# Quick fix script for beauty-specialist.ru
# Run on server: bash fix_server.sh

echo "=== Checking services ==="
systemctl is-active beauty-backend
systemctl is-active nginx
systemctl is-active postgresql

echo ""
echo "=== Restarting backend ==="
sudo systemctl restart beauty-backend
sleep 2
sudo systemctl status beauty-backend --no-pager -l

echo ""
echo "=== Checking database connection ==="
sudo -u postgres psql -d online_booking -c "SELECT count(*) FROM users;" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT count(*) FROM countries;" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT count(*) FROM reviews;" 2>&1

echo ""
echo "=== Running fix scripts ==="
cd /var/www/beauty-specialist/online-booking/backend
source venv/bin/activate
python3.12 fix_production_db.py
python3.12 create_minimal_reviews.py

echo ""
echo "=== Restarting backend again ==="
sudo systemctl restart beauty-backend
sleep 2

echo ""
echo "=== Testing API ==="
curl -s http://127.0.0.1:8000/api/v1/countries/ | head -c 500
echo ""
curl -s http://127.0.0.1:8000/api/v1/reviews/ | head -c 500
echo ""

echo ""
echo "=== DONE ==="
