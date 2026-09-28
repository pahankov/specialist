"""Create/update superuser for production.

Usage:
    python create_superuser.py

Uses bcrypt directly (not passlib).
"""
import sys, os, bcrypt

sys.path.insert(0, os.path.dirname(__file__))
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', '')
os.environ['APP_ENV'] = 'production'

from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.database import Base

engine = create_engine(os.environ['DATABASE_URL'])
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(engine)

SUPERUSER_EMAIL = 'pahankov@mail.ru'
SUPERUSER_PASSWORD = 'REDACTED_SUPERUSER_PASSWORD'
SUPERUSER_NAME = 'Павел'
TELEGRAM_USERNAME = 'pahankov'


def _hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def main():
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.email == SUPERUSER_EMAIL)).scalar_one_or_none()
        if user:
            user.hashed_password = _hash_pw(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            print('Superuser updated:')
        else:
            user = User(
                name=SUPERUSER_NAME,
                email=SUPERUSER_EMAIL,
                hashed_password=_hash_pw(SUPERUSER_PASSWORD),
                phone='+79615202311',
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            session.flush()
            master_profile = MasterProfile(
                user_id=user.id,
                telegram_username=TELEGRAM_USERNAME,
                description='Суперпользователь',
            )
            session.add(master_profile)
            print('Superuser created:')
        session.commit()
        print(f'   Email: {user.email}')
        print(f'   ID: {user.id}')
        print(f'   Role: {user.role.value}')


if __name__ == '__main__':
    main()
