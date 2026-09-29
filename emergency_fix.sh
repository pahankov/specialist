#!/bin/bash
# ============================================================
# АВАРИЙНЫЙ СЦЕНАРИЙ — beauty-specialist.ru
# ============================================================
# Запустить на сервере:
#   sudo bash emergency_fix.sh
# ============================================================

set -e

echo "=========================================="
echo " EMERGENCY FIX — beauty-specialist.ru"
echo "=========================================="

# 1. Проверка сервисов
echo ""
echo "[$(date)] 1. Проверка сервисов..."
for svc in postgresql beauty-backend nginx; do
    state=$(systemctl is-active $svc 2>/dev/null || echo "inactive")
    echo "  $svc: $state"
done

# 2. Перезапуск PostgreSQL
echo ""
echo "[$(date)] 2. Перезапуск PostgreSQL..."
sudo systemctl restart postgresql
sleep 2
sudo systemctl status postgresql --no-pager | head -5

# 3. Проверка БД
echo ""
echo "[$(date)] 3. Проверка базы данных..."
sudo -u postgres psql -d online_booking -c "SELECT count(*) as users FROM users;" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT count(*) as countries FROM countries;" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT count(*) as cities FROM cities;" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT count(*) as masters FROM users WHERE role='MASTER';" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT count(*) as reviews FROM reviews;" 2>&1

# 4. Проверка ENUM типов
echo ""
echo "[$(date)] 4. Проверка ENUM типов..."
sudo -u postgres psql -d online_booking -c "SELECT enum_range(NULL::userrole);" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT enum_range(NULL::masterstatus);" 2>&1

# 5. Проверка суперпользователя
echo ""
echo "[$(date)] 5. Проверка суперпользователя..."
sudo -u postgres psql -d online_booking -c "SELECT id, email, role, is_active FROM users WHERE email='pahankov@mail.ru';" 2>&1
sudo -u postgres psql -d online_booking -c "SELECT mp.id, mp.user_id FROM master_profiles mp JOIN users u ON mp.user_id=u.id WHERE u.email='pahankov@mail.ru';" 2>&1

# 6. Перезапуск бэкенда
echo ""
echo "[$(date)] 6. Перезапуск бэкенда..."
cd /var/www/beauty-specialist/online-booking/backend
source venv/bin/activate

# Проверка логов перед перезапуском
echo "  Логи перед перезапуском:"
sudo journalctl -u beauty-backend --no-pager -n 20 --since "5 minutes ago" 2>/dev/null || echo "  Нет логов"

sudo systemctl restart beauty-backend
sleep 3

# Проверка после перезапуска
echo ""
echo "[$(date)] 7. Проверка после перезапуска..."
sudo systemctl status beauty-backend --no-pager | head -10

# 8. Тест API
echo ""
echo "[$(date)] 8. Тест API..."
echo "  Health:"
curl -s http://127.0.0.1:8000/health 2>&1 || echo "  FAIL"

echo ""
echo "  Countries:"
curl -s http://127.0.0.1:8000/api/v1/countries/ 2>&1 | head -c 300 || echo "  FAIL"

echo ""
echo "  Reviews:"
curl -s http://127.0.0.1:8000/api/v1/reviews/ 2>&1 | head -c 300 || echo "  FAIL"

echo ""
echo "=========================================="
echo " DONE — Проверьте результат выше"
echo "=========================================="
