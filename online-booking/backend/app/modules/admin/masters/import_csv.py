"""CSV import for masters."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import csv
import io

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_super_admin
from app.services.auth import hash_password

router = APIRouter()


@router.post("/import")
async def import_masters_from_csv(
    file: UploadFile = File(...),
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Import masters from CSV file.

    CSV format: name,email,password,phone,telegram_username
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        try:
            name = row.get("name", "").strip()
            email = row.get("email", "").strip()
            password = row.get("password", "").strip()
            phone = row.get("phone", "").strip() or None
            telegram = row.get("telegram_username", "").strip() or None

            if not name or not email or not password:
                errors.append({"row": i, "error": "name, email, password are required"})
                continue

            existing = await db.execute(
                select(User).where(User.email == email, User.role == UserRole.MASTER)
            )
            if existing.scalar_one_or_none():
                errors.append({"row": i, "error": f"Email {email} already exists"})
                continue

            user = User(
                name=name,
                email=email,
                hashed_password=hash_password(password),
                phone=phone,
                role=UserRole.MASTER,
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)

            mp = MasterProfile(
                user_id=user.id,
                telegram_username=telegram,
            )
            db.add(mp)
            imported += 1

        except Exception as e:
            errors.append({"row": i, "error": str(e)})

    await db.commit()

    return {
        "imported": imported,
        "errors": errors,
        "total_rows": imported + len(errors)
    }
