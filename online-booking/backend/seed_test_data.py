"""Seed script: 20 masters, 60 clients, appointments, reviews, working hours."""
import asyncio
import random
from datetime import datetime, timedelta, date, time, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile, MasterStatus
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.working_hour import WorkingHour
from app.models.review import Review
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── Data pools ────────────────────────────────────────────────────────

MASTER_NAMES = [
    "Анна Смирнова", "Елена Козлова", "Мария Петрова", "Ольга Иванова",
    "Наталья Сидорова", "Ирина Попова", "Татьяна Морозова", "Екатерина Волкова",
    "Светлана Новикова", "Юлия Кузнецова", "Людмила Соколова", "Алексей Волков",
    "Дмитрий Козлов", "Сергей Петров", "Андрей Сидоров", "Михаил Иванов",
    "Владимир Смирнов", "Александр Козлов", "Павел Новиков", "Виктор Морозов",
]

MASTER_DESCRIPTIONS = [
    "Профессиональный мастер с опытом более 10 лет. Специализация — сложные техники окрашивания.",
    "Мастер маникюра и педикюра. Индивидуальный подход к каждому клиенту.",
    "Стилист-колорист. Работаю с премиальными материалами.",
    "Мастер бровей и ресниц. Сертифицированный тренер.",
    "Мастер маникюра с опытом 5 лет. Работаю только на качественных материалах.",
    "Косметолог-эстетист. Чистки, пилинги, уходовые процедуры.",
    "Барбер. Мужские стрижки и бороды.",
    "Мастер nail-сервиса. Французский маникюр, гель-лак, наращивание.",
]

MASTER_TELEGRAM = [
    "@anna_nail", "@elena_style", "@maria_brows", "@olga_kosmetolog",
    "@natasha_mani", "@irina_barber", "@tanya_nail", "@ekaterina_color",
    "@svetlana_beauty", "@yulia_stylist", "@lyudmila_nail", "@alexey_barber",
    "@dmitry_master", "@sergey_stylist", "@andrey_nail", "@mikhail_barber",
    "@vladimir_master", "@alexey_stylist", "@pavel_nail", "@victor_master",
]

CLIENT_FIRST_NAMES = [
    "Анна", "Мария", "Елена", "Ольга", "Наталья", "Ирина", "Татьяна", "Екатерина",
    "Светлана", "Юлия", "Людмила", "Вера", "Надежда", "Лариса", "Галина", "Тамара",
    "Кристина", "Дарья", "Алина", "Полина", "Виктория", "Анастасия", "Ксения", "Валентина",
]

CLIENT_LAST_NAMES = [
    "Иванова", "Петрова", "Сидорова", "Козлова", "Новикова", "Морозова", "Попова", "Волкова",
    "Смирнова", "Соколова", "Кузнецова", "Павлова", "Семёнова", "Голубева", "Виноградова", "Богданова",
    "Кузнецова", "Попова", "Михайлова", "Фёдорова", "Николаева", "Воронова", "Савельева", "Орлова",
]

SERVICE_TEMPLATES = [
    ("Маникюр классический", 60, 1500),
    ("Маникюр гель-лак", 90, 2500),
    ("Педикюр полный", 120, 3500),
    ("Наращивание ногтей", 150, 4500),
    ("Дизайн ногтей (1 ноготь)", 15, 100),
    ("Снятие гель-лака", 20, 500),
    ("Окрашивание волос", 120, 5000),
    ("Стрижка женская", 60, 2000),
    ("Укладка", 45, 1500),
    ("Брови архитектура + окрашивание", 60, 2000),
    ("Ресницы наращивание", 120, 4000),
    ("Чистка лица", 90, 3000),
    ("Пилинг", 60, 2500),
    ("Массаж лица", 45, 2000),
    ("Барбер-стрижка", 45, 1500),
    ("Борода оформление", 30, 1000),
]

STATUSES = ["pending", "confirmed", "completed", "cancelled"]
STATUS_WEIGHTS = [0.1, 0.25, 0.55, 0.1]


async def create_seed_data():
    """Create 20 masters, 60 clients, appointments, reviews, working hours."""
    async with AsyncSessionLocal() as db:
        # Check if data already exists
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Data already exists. Clearing...")
            await db.execute(text("DELETE FROM reviews"))
            await db.execute(text("DELETE FROM appointments"))
            await db.execute(text("DELETE FROM working_hours"))
            await db.execute(text("DELETE FROM services"))
            await db.execute(text("DELETE FROM master_profiles"))
            await db.execute(text("DELETE FROM client_profiles"))
            await db.execute(text("DELETE FROM users"))
            await db.commit()

        random.seed(42)
        now = datetime.now(timezone.utc)
        
        master_profiles = []
        client_profiles = []
        services = []
        
        # ─── 1. Create 20 masters ──────────────────────────────────────
        print("Creating 20 masters...")
        for i in range(20):
            name = MASTER_NAMES[i]
            email = f"master{i}@beauty.ru"
            phone = f"+7900{1000000 + i:06d}"
            password = pwd_context.hash("password123")
            
            user = User(
                name=name,
                email=email,
                phone=phone,
                hashed_password=password,
                role=UserRole.MASTER,
                is_active=True,
                is_verified=True,
                created_at=now - timedelta(days=random.randint(30, 365)),
            )
            db.add(user)
            await db.flush()
            
            mp = MasterProfile(
                user_id=user.id,
                description=random.choice(MASTER_DESCRIPTIONS),
                avatar_url=f"https://i.pravatar.cc/150?img={i+10}",
                telegram_username=MASTER_TELEGRAM[i],
                experience_years=random.randint(1, 15),
                status=MasterStatus.ACTIVE if random.random() > 0.1 else MasterStatus.INACTIVE,
                is_active=True,
                created_at=user.created_at,
            )
            db.add(mp)
            await db.flush()
            master_profiles.append(mp)
        
        await db.commit()
        print(f"  [OK] Created {len(master_profiles)} masters")
        
        # ─── 2. Create services for each master ────────────────────────
        print("Creating services...")
        for mp in master_profiles:
            num_services = random.randint(3, 6)
            chosen = random.sample(SERVICE_TEMPLATES, min(num_services, len(SERVICE_TEMPLATES)))
            for svc_name, duration, price in chosen:
                svc = Service(
                    master_id=mp.id,
                    name=svc_name,
                    description=f"Услуга от мастера (master_id={mp.user_id})",
                    duration_minutes=duration,
                    price=price,
                    is_active=random.random() > 0.1,
                    created_at=now - timedelta(days=random.randint(10, 300)),
                )
                db.add(svc)
                services.append(svc)
        
        await db.commit()
        print(f"  [OK] Created {len(services)} services")
        
        # ─── 3. Create 60 clients ──────────────────────────────────────
        print("Creating 60 clients...")
        for i in range(60):
            first_name = random.choice(CLIENT_FIRST_NAMES)
            last_name = random.choice(CLIENT_LAST_NAMES)
            name = f"{first_name} {last_name}"
            phone = f"+7911{2000000 + i:06d}"
            email = f"client{i}@mail.ru"
            
            user = User(
                name=name,
                email=email,
                phone=phone,
                hashed_password=None,  # OTP-only
                role=UserRole.CLIENT,
                is_active=True,
                is_verified=True,
                created_at=now - timedelta(days=random.randint(5, 300)),
            )
            db.add(user)
            await db.flush()
            
            cp = ClientProfile(
                user_id=user.id,
                no_show_count=random.choices([0, 0, 0, 1, 2], k=1)[0],
                preferred_service_ids=random.sample([s.id for s in services], min(random.randint(1, 3), len(services))),
                created_at=user.created_at,
            )
            db.add(cp)
            await db.flush()
            client_profiles.append(cp)
        
        await db.commit()
        print(f"  [OK] Created {len(client_profiles)} clients")
        
        # ─── 4. Create working hours ───────────────────────────────────
        print("Creating working hours...")
        wh_count = 0
        for mp in master_profiles:
            # 5-15 working days per master
            num_days = random.randint(5, 15)
            start_date = (now - timedelta(days=30)).date()
            used_dates = set()
            for _ in range(num_days * 3):  # try up to 3x to avoid duplicates
                if len(used_dates) >= num_days:
                    break
                rand_date = start_date + timedelta(days=random.randint(0, 60))
                if rand_date in used_dates:
                    continue
                used_dates.add(rand_date)
                wh = WorkingHour(
                    master_id=mp.id,
                    schedule_date=rand_date,
                    start_time=time(hour=random.choice([8, 9, 10]), minute=0),
                    end_time=time(hour=random.choice([16, 17, 18, 19, 20]), minute=0),
                    is_active=True,
                    created_at=now - timedelta(days=random.randint(1, 30)),
                )
                db.add(wh)
                wh_count += 1
        
        await db.commit()
        print(f"  [OK] Created {wh_count} working hours")
        
        # ─── 5. Create 400-600 appointments ────────────────────────────
        print("Creating appointments...")
        appt_count = 0
        completed_ids = []
        for _ in range(random.randint(400, 600)):
            mp = random.choice(master_profiles)
            cp = random.choice(client_profiles)
            mp_services = [s for s in services if s.master_id == mp.id and s.is_active]
            if not mp_services:
                continue
            svc = random.choice(mp_services)
            
            # Random date in last 6 months
            days_ago = random.randint(-180, 30)
            appt_date = now + timedelta(days=days_ago, hours=random.randint(8, 20), minutes=random.randint(0, 59))
            
            status = random.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
            if status == "completed":
                completed_ids.append(None)  # placeholder
            
            notes_options = [
                None,
                "Позвонила заранее",
                "Первый визит",
                "Постоянный клиент",
                "Через сайт",
                "По рекомендации",
                None,
                None,
            ]
            
            appt = Appointment(
                master_id=mp.id,
                service_id=svc.id,
                client_id=cp.id,
                appointment_date=appt_date,
                status=status,
                notes=random.choice(notes_options),
                created_at=appt_date - timedelta(days=random.randint(1, 10)),
            )
            db.add(appt)
            await db.flush()
            appt_count += 1
            if status == "completed":
                completed_ids.append(appt.id)
        
        await db.commit()
        print(f"  [OK] Created {appt_count} appointments")
        
        # ─── 6. Create reviews for completed appointments ──────────────
        print("Creating reviews...")
        review_count = 0
        for appt_id in completed_ids:
            if appt_id is None:
                continue
            if random.random() > 0.4:  # 40% of completed have reviews
                # Get appointment to find master
                appt_result = await db.execute(select(Appointment).where(Appointment.id == appt_id))
                appt = appt_result.scalar_one_or_none()
                if not appt:
                    continue
                
                rating = random.choices([3, 4, 5], weights=[0.1, 0.3, 0.6], k=1)[0]
                comments = [
                    None,
                    "Отличный мастер! Рекомендую!",
                    "Очень довольна результатом",
                    "Буду приходить ещё",
                    "Профессиональный подход",
                    "Всё понравилось, спасибо!",
                    "Хороший сервис",
                    "Мастер — золото!",
                    None,
                    None,
                ]
                
                # Get client name from profile
                cp_result = await db.execute(
                    select(User).where(User.id == appt.client_profile.user_id)
                )
                user = cp_result.scalar_one_or_none()
                client_name = user.name if user else "Аноним"
                client_phone = user.phone if user else "+7***"
                
                review = Review(
                    appointment_id=appt_id,
                    master_id=appt.master_id,
                    client_name=client_name,
                    client_phone=client_phone,
                    rating=rating,
                    comment=random.choice(comments),
                    is_published=random.random() > 0.15,  # 85% published
                    created_at=appt.appointment_date + timedelta(days=random.randint(1, 7)),
                )
                db.add(review)
                review_count += 1
        
        await db.commit()
        print(f"  [OK] Created {review_count} reviews")
        
        # ─── Summary ───────────────────────────────────────────────────
        print("\n" + "="*60)
        print("SEED SUMMARY:")
        print(f"  Masters:     {len(master_profiles)}")
        print(f"  Services:    {len(services)}")
        print(f"  Clients:     {len(client_profiles)}")
        print(f"  Working hrs: {wh_count}")
        print(f"  Appointments:{appt_count}")
        print(f"  Reviews:     {review_count}")
        print("="*60)
        print("\nMaster login credentials:")
        print("  Email: master0@beauty.ru ... master19@beauty.ru")
        print("  Password: password123")
        print("\nDone!")


if __name__ == "__main__":
    asyncio.run(create_seed_data())