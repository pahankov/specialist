"""Create superuser script."""
import asyncio
from sqlalchemy import select
from app.database import engine, AsyncSessionLocal, Base
from app.models.master import Master
from app.models.client import Client
from app.models.service import Service
from app.models.working_hour import WorkingHour
from app.models.blocked_slot import BlockedSlot
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken
from app.models.appointment import Appointment
from app.models.review import Review
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def main():
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if user already exists
        result = await session.execute(select(Master).where(Master.email == "pahankov@mail.ru"))
        master = result.scalar_one_or_none()
        
        if master:
            # Update password
            master.hashed_password = pwd_context.hash("Sug@r2026!")
            print("Password updated")
        else:
            # Create new master
            master = Master(
                name="Павел",
                email="pahankov@mail.ru",
                hashed_password=pwd_context.hash("Sug@r2026!"),
                phone="+79001234567",
                telegram_username="pahankov",
                description="Суперпользователь",
                is_active=True,
                is_admin=True,
            )
            session.add(master)
            await session.flush()

            # Create a default service
            service = Service(
                master_id=master.id,
                name="Шугаринг ног полностью",
                description="Полное удаление волос на ногах",
                duration_minutes=60,
                price=2500,
                is_active=True,
            )
            session.add(service)

            # Create a test client
            client = Client(
                name="Тест Клиент",
                phone="+79991234567",
                email="client@test.com",
            )
            session.add(client)

        await session.commit()

        print("Superuser created:")
        print("   Email: pahankov@mail.ru")
        print("   Password: Sug@r2026Secure!")
        print(f"   ID: {master.id}")
        print(f"   Admin: {master.is_admin}")
        print("\nGo to http://localhost:3000 and login!")


if __name__ == "__main__":
    asyncio.run(main())
