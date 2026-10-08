-- ============================================================
-- SQL для ручного вброса данных в БД beauty-specialist.ru
-- ============================================================
-- Выполнить на сервере:
--   sudo -u postgres psql -d online_booking -f seed_data.sql
-- ============================================================

-- 1. Страны
INSERT INTO countries (code, name_ru, name_en, phone_prefix, is_active)
VALUES
    ('RU', 'Россия', 'Russia', '+7', true),
    ('KZ', 'Казахстан', 'Kazakhstan', '+7', true),
    ('BY', 'Беларусь', 'Belarus', '+375', true)
ON CONFLICT (code) DO NOTHING;

-- 2. Города России
INSERT INTO cities (country_id, name_ru, name_en, slug, is_active)
SELECT 
    c.id,
    city_name,
    city_name,
    LOWER(city_name),
    true
FROM countries c
CROSS JOIN (VALUES
    ('Москва'), ('Санкт-Петербург'), ('Новосибирск'), ('Екатеринбург'),
    ('Казань'), ('Нижний Новгород'), ('Челябинск'), ('Самара'),
    ('Омск'), ('Ростов-на-Дону'), ('Уфа'), ('Красноярск'),
    ('Воронеж'), ('Пермь'), ('Волгоград')
) AS cities(city_name)
WHERE c.code = 'RU'
ON CONFLICT DO NOTHING;

-- 3. Создать 5 завершённых записей для отзывов (если нет)
-- Сначала проверим, есть ли записи
DO $$
DECLARE
    appt_count INTEGER;
    master_id INTEGER;
    client_user_id INTEGER;
BEGIN
    SELECT count(*) INTO appt_count FROM appointments;
    
    IF appt_count = 0 THEN
        -- Берём первого мастера
        SELECT mp.id INTO master_id 
        FROM master_profiles mp 
        JOIN users u ON mp.user_id = u.id 
        WHERE u.role = 'MASTER' 
        LIMIT 1;
        
        -- Создаём тестового клиента
        INSERT INTO users (name, phone, role, hashed_password, is_active, is_verified, created_at)
        VALUES ('Тестовый клиент', '+79990000000', 'CLIENT', NULL, true, true, NOW())
        RETURNING id INTO client_user_id;
        
        INSERT INTO client_profiles (user_id, no_show_count, created_at)
        VALUES (client_user_id, 0, NOW());
        
        -- Создаём 5 завершённых записей
        INSERT INTO appointments (master_id, service_id, client_id, appointment_date, status, notes, created_at)
        SELECT 
            master_id,
            s.id,
            client_user_id,
            NOW() - (random() * 90 || ' days')::interval,
            'completed',
            'Тестовая запись',
            NOW() - (random() * 30 || ' days')::interval
        FROM services s
        WHERE s.is_active = true
        LIMIT 5;
        
        RAISE NOTICE 'Created 5 test appointments';
    END IF;
END $$;

-- 4. Отзывы для завершённых записей
DO $$
DECLARE
    review_count INTEGER;
    appt RECORD;
    client_name TEXT;
BEGIN
    SELECT count(*) INTO review_count FROM reviews;
    
    IF review_count = 0 THEN
        FOR appt IN 
            SELECT a.id, a.master_id, a.client_id, a.appointment_date
            FROM appointments a
            WHERE a.status = 'completed'
            LIMIT 5
        LOOP
            -- Получаем имя клиента
            SELECT u.name INTO client_name
            FROM users u
            JOIN client_profiles cp ON cp.user_id = u.id
            WHERE u.id = appt.client_id
            LIMIT 1;
            
            client_name := COALESCE(client_name, 'Клиент');
            
            INSERT INTO reviews (
                appointment_id, master_id, client_name, client_phone,
                rating, comment, is_published, created_at
            ) VALUES (
                appt.id,
                appt.master_id,
                client_name,
                '+7***',
                CASE random()
                    WHEN true THEN 5
                    ELSE 4
                END,
                CASE random()
                    WHEN true THEN 'Отличный мастер! Рекомендую!'
                    WHEN false THEN 'Очень довольна результатом'
                    ELSE 'Буду приходить ещё'
                END,
                true,
                appt.appointment_date + (random() * 7 || ' days')::interval
            );
        END LOOP;
        
        RAISE NOTICE 'Created reviews for completed appointments';
    END IF;
END $$;

-- 5. Проверка результатов
SELECT 'countries' as table_name, count(*) FROM countries
UNION ALL
SELECT 'cities', count(*) FROM cities
UNION ALL
SELECT 'reviews', count(*) FROM reviews
UNION ALL
SELECT 'appointments', count(*) FROM appointments
UNION ALL
SELECT 'masters', count(*) FROM users WHERE role = 'MASTER';
