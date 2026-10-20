"""Current panel user profile (names + city for form defaults)."""
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies.auth import require_master
from app.middleware.rate_limit import limiter
from app.models.city import City
from app.models.master_profile import MasterProfile
from app.models.user import User, UserRole
from app.models.user_contact import UserContact
from app.modules.admin.helpers import get_master_profile_id
from app.services.audit import log_action
from app.services.contacts import (
    ContactTaken,
    InvalidContact,
    attach_contact,
    get_contacts,
    remove_contact,
    set_primary,
)
from app.services.email_verify import (
    finish_email_verification,
    require_email_contact,
    start_email_verification,
)
from app.services.master_profile_view import contact_out as _contact_out
from app.services.master_profile_view import master_profile_snapshot
from app.services.names import set_names
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                          "static", "avatars")
AVATAR_URL_PREFIX = "/static/avatars"
# Phone photos can be 5-12MB (and iPhone HEIC often >5MB). The image is
# downscaled to <=1024px before storage, so the upload itself may be larger.
MAX_AVATAR_BYTES = 15 * 1024 * 1024
IMAGE_TYPE_ERROR = "Только изображения: JPEG, PNG, WebP или HEIC"
IMAGE_SIZE_ERROR = "Файл больше 15 МБ"


def is_image_content_type(content_type: Optional[str]) -> bool:
    """Accept phone picker quirks; Pillow validates the actual bytes.

    iOS may send image/heic, an empty string, or application/octet-stream
    depending on the browser/version. Non-image MIME types are rejected
    early, while everything image-like is decoded and re-encoded.
    """
    ct = (content_type or "").strip().lower()
    return (
        not ct
        or ct.startswith("image/")
        or ct in {"application/octet-stream", "binary/octet-stream"}
    )
# Built-in avatars (stored as-is in master_profiles.avatar_preset,
# mutually exclusive with an uploaded photo).
AVATAR_PRESETS = ["🐱", "🐶", "🐥", "🦅", "🦊", "🐼", "🐸", "🦁",
                  "🐯", "🐰", "🐷", "🐮", "🐵", "🐔", "🦄", "🐙"]


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
    """Own profile — shared shape with the client-side master draft."""
    mp = None
    if master.role == UserRole.MASTER:
        mp_id = await get_master_profile_id(db, master)
        mp = (await db.execute(
            select(MasterProfile).where(MasterProfile.id == mp_id)
        )).scalar_one_or_none()
    out, _ = await master_profile_snapshot(db, master, mp)
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
    # Login landing: straight to the master panel after sign-in (1.82.0).
    prefer_master_cabinet: Optional[bool] = Field(default=None)
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
        set_names(master, first, last)
    elif data.last_name is not None:
        first = master.name.split(" ")[0] if master.name else ""
        set_names(master, first, data.last_name)
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
        if data.prefer_master_cabinet is not None:
            mp.prefer_master_cabinet = bool(data.prefer_master_cabinet)
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
    """Upload own photo (JPEG/PNG/WebP/HEIC, ≤15MB). Returns public url.

    Stored under backend/static/avatars, served same-origin at /static.
    kind=avatar replaces the profile photo (old file removed best-effort).
    kind=cert is a standalone file (e.g. certificate photo): it never
    touches avatar_url and never deletes anything — sharing one endpoint
    used to wipe previously saved files on every new upload.
    """
    if kind not in ("avatar", "cert"):
        raise HTTPException(status_code=400, detail="kind: avatar|cert")
    if not is_image_content_type(file.content_type):
        raise HTTPException(status_code=400, detail=IMAGE_TYPE_ERROR)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail=IMAGE_SIZE_ERROR)
    from app.utils.images import downscale_image
    try:
        data, ext = downscale_image(data, file.content_type)
    except ValueError:
        logger.warning("Invalid image upload rejected: user=%s", master.id)
        raise HTTPException(
            status_code=400,
            detail="Не удалось распознать изображение. JPEG, PNG, WebP или HEIC.",
        )
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


# ─── Own email confirmation («Подтвердить почту») ─────────────────────


class ContactVerify(BaseModel):
    """Six digits from the letter (a little room for pasted codes)."""
    code: str = Field(min_length=1, max_length=12)


async def _own_contact_or_404(
    db: AsyncSession, user_id: int, contact_id: int
) -> UserContact:
    contact = (await db.execute(
        select(UserContact).where(
            UserContact.id == contact_id,
            UserContact.user_id == user_id,
        )
    )).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Контакт не найден")
    return contact


@router.post("/profile/contacts/{contact_id}/send-code", response_model=dict)
@limiter.limit("5/minute")
async def send_my_contact_code(
    request: Request,
    contact_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Email a confirm code for an own email contact (superadmin included)."""
    contact = await _own_contact_or_404(db, master.id, contact_id)
    require_email_contact(contact)
    await start_email_verification(db, contact)
    return {"ok": True}


@router.post("/profile/contacts/{contact_id}/verify-code")
async def verify_my_contact_code(
    contact_id: int,
    data: ContactVerify,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Check the emailed code and mark the contact verified."""
    contact = await _own_contact_or_404(db, master.id, contact_id)
    require_email_contact(contact)
    contact = await finish_email_verification(db, contact, data.code)
    await log_action(db, master.id, "contact_verify", "user_contact", contact.id,
                     f"Почта подтверждена: {contact.value}", level="info")
    await db.commit()
    return _contact_out(contact)


# ─── Own contacts: add / remove / promote (same model as the cabinet) ──


class ProfileContactCreate(BaseModel):
    contact_type: str = Field(pattern="^(phone|email)$")
    value: str = Field(min_length=1, max_length=255)


@router.post("/profile/contacts", status_code=201)
@limiter.limit("10/minute")
async def add_my_contact(
    request: Request,
    data: ProfileContactCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Add a phone/email to own profile (lands unverified by design).

    Self-typed values never verify themselves — confirmation comes from
    social logins or emailed codes. A value held by another account is
    rejected (409): transfers happen only on provider-confirmed logins.
    """
    from app.services.contacts import find_user_by_contact

    holder = await find_user_by_contact(db, data.contact_type, data.value)
    if holder is not None and holder.id != master.id:
        raise HTTPException(
            status_code=409,
            detail="Этот контакт уже привязан к другому аккаунту",
        )
    try:
        contact, _ = await attach_contact(db, master, data.contact_type, data.value)
    except InvalidContact:
        raise HTTPException(
            status_code=422,
            detail=("Некорректный телефон" if data.contact_type == "phone"
                    else "Некорректный email"),
        )
    except ContactTaken:
        raise HTTPException(
            status_code=409,
            detail="Этот контакт уже привязан к другому аккаунту",
        )
    await log_action(db, master.id, "contact_add", "user_contact", contact.id,
                     f"Добавлен контакт {contact.contact_type}", level="info")
    await db.commit()
    return _contact_out(contact)


@router.delete("/profile/contacts/{contact_id}", response_model=dict)
async def remove_my_contact(
    contact_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Detach an own contact (another of the type becomes primary).

    A password account must keep at least one contact — otherwise no
    identifier maps to it and password login becomes impossible.
    """
    contact = await _own_contact_or_404(db, master.id, contact_id)
    if master.hashed_password is not None:
        all_contacts = await get_contacts(db, master.id)
        if len(all_contacts) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Это последний контакт аккаунта — иначе вход по "
                       "паролю станет невозможен. Сначала добавьте другой.",
            )
    removed_type = contact.contact_type
    await remove_contact(db, master, contact.contact_type, contact.value)
    await log_action(db, master.id, "contact_remove", "user_contact", contact_id,
                     f"Удалён контакт {removed_type}", level="info")
    await db.commit()
    return {"ok": True}


@router.post("/profile/contacts/{contact_id}/primary")
async def make_my_contact_primary(
    contact_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Move a contact into the primary slot of its type."""
    contact = await _own_contact_or_404(db, master.id, contact_id)
    contact = await set_primary(db, master, contact.contact_type, contact.value)
    await db.commit()
    return _contact_out(contact)
