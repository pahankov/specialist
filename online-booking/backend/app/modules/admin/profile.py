"""Current panel user profile (names + city for form defaults)."""
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies.auth import require_master
from app.models.city import City
from app.models.master_profile import MasterProfile
from app.models.user import User, UserRole
from app.modules.admin.helpers import get_master_profile_id
from app.services.audit import log_action
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          "static", "avatars")
AVATAR_URL_PREFIX = "/static/avatars"
MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
# Built-in avatars (stored as-is in master_profiles.avatar_preset,
# mutually exclusive with an uploaded photo).
AVATAR_PRESETS = ["🐱", "🐶", "🐥", "🦅", "🦊", "🐼", "🐸", "🦁"]


def _delete_avatar_file(url: Optional[str]) -> None:
    if url and url.startswith(AVATAR_URL_PREFIX + "/"):
        try:
            os.remove(os.path.join(AVATAR_DIR, os.path.basename(url)))
        except OSError:
            pass


class Certificate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: Optional[str]) -> Optional[str]:
        # Stored XSS guard: cert urls render as <a href>/<img src> in other
        # users' browsers — only backend paths and http(s) allowed.
        if v is None:
            return v
        s = v.strip()
        if not (s.startswith("/") or s.startswith("http://")
                or s.startswith("https://")):
            raise ValueError("URL сертификата: только /static/... или http(s)")
        return s


@router.get("/profile")
async def get_my_profile(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Own id/name/city — lets panels prefill (e.g. client city = master's)."""
    city_name = None
    if master.city_id:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == master.city_id)
        )).scalar_one_or_none()
    out = {
        "id": master.id,
        "name": master.name,
        "last_name": master.last_name,
        "city_id": master.city_id,
        "city_name": city_name,
    }
    if master.role == UserRole.MASTER:
        mp_id = await get_master_profile_id(db, master)
        mp = (await db.execute(
            select(MasterProfile).where(MasterProfile.id == mp_id)
        )).scalar_one_or_none()
        if mp is not None:
            out.update({
                "telegram_username": mp.telegram_username,
                "description": mp.description,
                "avatar_url": mp.avatar_url,
                "avatar_preset": mp.avatar_preset,
                "experience_years": mp.experience_years,
                "cabinet_address": mp.cabinet_address,
                "certificates": mp.certificates or [],
                "auto_confirm": bool(mp.auto_confirm),
                "auto_complete": bool(mp.auto_complete),
                "profile_id": mp.id,
                "tariff": mp.tariff or "trial",
                "trial_ends_at": mp.trial_ends_at.isoformat() if mp.trial_ends_at else None,
            })
    return out


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    city_id: Optional[int] = None
    telegram_username: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    experience_years: Optional[int] = Field(default=None, ge=0, le=80)
    cabinet_address: Optional[str] = Field(default=None, max_length=500)
    certificates: Optional[List[Certificate]] = Field(default=None, max_length=20)
    # Auto-confirm client-initiated bookings (switch in profile).
    auto_confirm: Optional[bool] = Field(default=None)
    # Auto-complete past bookings (switch next to auto-confirm).
    auto_complete: Optional[bool] = Field(default=None)
    # Built-in avatar emoji (validated against AVATAR_PRESETS). Explicit null
    # clears it; absent key = no change (checked via model_fields_set).
    avatar_preset: Optional[str] = Field(default=None, max_length=12)


@router.patch("/profile")
async def update_my_profile(
    data: ProfileUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Edit own personal data: names, city, contacts, cabinet, certificates.

    Names recompose the display `name` ("Имя Фамилия") so every existing
    list/badge keeps working; `last_name` stored separately for structure.
    """
    if data.name is not None:
        first = data.name.strip()
        if not first:
            raise HTTPException(status_code=400, detail="Имя пустое")
        last = data.last_name.strip() if data.last_name is not None else (master.last_name or "")
        master.name = f"{first} {last}".strip() if last else first
        master.last_name = last or None
    elif data.last_name is not None:
        last = data.last_name.strip()
        first = master.name.split(" ")[0] if master.name else ""
        master.name = f"{first} {last}".strip() if last else first
        master.last_name = last or None
    if data.city_id is not None:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == data.city_id)
        )).scalar_one_or_none()
        if city_name is None:
            raise HTTPException(status_code=404, detail="Город не найден")
        master.city_id = data.city_id

    mp = None
    if master.role == UserRole.MASTER:
        mp_id = await get_master_profile_id(db, master)
        mp = (await db.execute(
            select(MasterProfile).where(MasterProfile.id == mp_id)
        )).scalar_one_or_none()
        if mp is None:
            raise HTTPException(status_code=404, detail="Профиль мастера не найден")
        if data.telegram_username is not None:
            mp.telegram_username = data.telegram_username.strip() or None
        if data.description is not None:
            mp.description = data.description.strip() or None
        if data.experience_years is not None:
            mp.experience_years = data.experience_years
        if data.cabinet_address is not None:
            mp.cabinet_address = data.cabinet_address.strip() or None
        if data.certificates is not None:
            mp.certificates = [c.model_dump(exclude_none=True) for c in data.certificates]
        if data.auto_confirm is not None:
            mp.auto_confirm = bool(data.auto_confirm)
        if data.auto_complete is not None:
            mp.auto_complete = bool(data.auto_complete)
        if "avatar_preset" in data.model_fields_set:
            if data.avatar_preset is not None and data.avatar_preset not in AVATAR_PRESETS:
                raise HTTPException(status_code=400, detail="Неизвестный стандартный аватар")
            mp.avatar_preset = data.avatar_preset
            if data.avatar_preset is not None:
                # Preset replaces the uploaded photo (mutually exclusive).
                _delete_avatar_file(mp.avatar_url)
                mp.avatar_url = None

    await log_action(db, master.id, "update", "profile", master.id,
                     "Личные данные обновлены", level="info")
    await db.commit()
    await db.refresh(master)
    return await get_my_profile(master, db)


@router.delete("/profile", status_code=200)
async def delete_my_profile(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Delete own master account (soft delete + PII anonymization).

    Profile disappears from public listings, future appointments are
    cancelled, past history is kept for the 3-year retention in /privacy.
    """
    from app.services.account_deletion import delete_own_account
    return await delete_own_account(db, master)


@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    kind: str = Query("avatar", description="avatar|cert"),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Upload own photo (JPEG/PNG/WebP, ≤5MB). Returns public url.

    Stored under backend/static/avatars, served same-origin at /static.
    kind=avatar replaces the profile photo (old file removed best-effort).
    kind=cert is a standalone file (e.g. certificate photo): it never
    touches avatar_url and never deletes anything — sharing one endpoint
    used to wipe previously saved files on every new upload.
    """
    if kind not in ("avatar", "cert"):
        raise HTTPException(status_code=400, detail="kind: avatar|cert")
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400, detail="Только JPEG, PNG или WebP")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Файл больше 5 МБ")
    from app.utils.images import downscale_image
    try:
        data, ext = downscale_image(data, file.content_type)
    except Exception:
        logger.warning("Image downscale failed, storing as-is")
        ext = EXT_BY_TYPE[file.content_type]
    os.makedirs(AVATAR_DIR, exist_ok=True)
    filename = f"user_{master.id}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(AVATAR_DIR, filename), "wb") as f:
        f.write(data)
    url = f"{AVATAR_URL_PREFIX}/{filename}"

    if master.role == UserRole.MASTER and kind == "avatar":
        mp_id = await get_master_profile_id(db, master)
        mp = (await db.execute(
            select(MasterProfile).where(MasterProfile.id == mp_id)
        )).scalar_one_or_none()
        if mp is None:
            raise HTTPException(status_code=404, detail="Профиль мастера не найден")
        old = mp.avatar_url
        mp.avatar_url = url
        mp.avatar_preset = None  # uploaded photo replaces the preset
        _delete_avatar_file(old)
    await log_action(db, master.id, "update", "profile", master.id,
                     "Фото обновлено", level="info")
    await db.commit()
    logger.info("Avatar uploaded: user=%s url=%s", master.id, url)
    return JSONResponse(content={"avatar_url": url})
