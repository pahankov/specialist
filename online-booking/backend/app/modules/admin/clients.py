"""Admin client CRUD endpoints with pagination."""
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload
from typing import List, Optional

from app.database import get_db
from app.models.client_profile import ClientProfile
from app.models.user import User, UserRole
from app.models.appointment import Appointment
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_admin, require_master
from app.dependencies.crud import get_or_404
from app.modules.admin.helpers import get_master_profile_id, own_client_user_ids
from app.services.audit import log_action
from app.logging_config import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)

router = APIRouter()


async def _require_own_client(db: AsyncSession, master: User, user: User) -> None:
    """403 unless the client is the master's own (booked or created).

    Uses 404 (not 403) so one master cannot probe another's book.
    """
    if master.role == UserRole.ADMIN:
        return
    if user.created_by == master.id:
        return
    mp_id = await get_master_profile_id(db, master)
    hit = await db.execute(
        select(Appointment.id)
        .join(ClientProfile, Appointment.client_id == ClientProfile.id)
        .where(Appointment.master_id == mp_id, ClientProfile.user_id == user.id)
        .limit(1)
    )
    if hit.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Client not found")


async def _resolve_city(db: AsyncSession, city_name: str) -> tuple[Optional[int], Optional[str]]:
    """Resolve a city name (e.g. parsed from a DaData address) to (id, name).

    Returns (None, None) when no local match — the address is still stored,
    and city matching falls back to it.
    """
    from app.models.city import City

    row = await db.execute(
        select(City.id, City.name_ru).where(City.name_ru == city_name.strip())
    )
    hit = row.one_or_none()
    if hit is None:
        return None, None
    return hit[0], hit[1]


@router.get("/clients", response_model=PaginatedResponse[ClientResponse])
async def get_admin_clients(
    master: User = Depends(require_master),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or phone"),
    master_id: Optional[int] = Query(None, description="Filter by master ID (clients who booked with this master)"),
    sort_by: Optional[str] = Query(None, description="Sort column: name|no_show|created_at"),
    sort_dir: str = Query("asc", description="Sort direction: asc|desc"),
    include_hidden: bool = Query(
        default=False,
        description="Master view: also list archived (hidden, not blocked) "
                    "clients with their archive reason."),
    db: AsyncSession = Depends(get_db)
):
    """Get all clients (paginated with total count)."""
    logger.info("Get clients: master=%s, page=%d, page_size=%d, search=%s, master_id=%s",
                master.id, page, page_size, search, master_id)
    offset = (page - 1) * page_size

    # Base query
    base_query = (
        select(ClientProfile)
        .join(ClientProfile.user)
        .options(joinedload(ClientProfile.user))
    )

    is_admin = master.role == UserRole.ADMIN

    # Master may list all clients (needed to book newcomers with no
    # appointments yet). A master_id filter from a non-admin is forced to
    # their own profile so one master cannot enumerate another's book.
    # Superadmin sees all unless master_id narrows it.
    effective_master_id = master_id
    if not is_admin and master_id is not None:
        effective_master_id = await get_master_profile_id(db, master)

    # Regular master: strictly OWN clients (booked with them or created
    # by them). Hidden ones stay out — except blocked (manageable badge)
    # and, on ?include_hidden=true, archived with their reason.
    if not is_admin:
        from app.models.master_hidden_client import MasterHiddenClient
        own_ids = await own_client_user_ids(db, master)
        _mp_id = await get_master_profile_id(db, master)
        _hidden = await db.execute(
            select(MasterHiddenClient.client_profile_id,
                   MasterHiddenClient.is_blocked).where(
                MasterHiddenClient.master_profile_id == _mp_id)
        )
        _extra_cp_ids = [r[0] for r in _hidden.all()
                         if r[1] or include_hidden]
        if _extra_cp_ids:
            _extra_users = await db.execute(
                select(ClientProfile.user_id).where(
                    ClientProfile.id.in_(_extra_cp_ids))
            )
            own_ids |= {r[0] for r in _extra_users.all()}
        if not own_ids:
            return PaginatedResponse(items=[], total=0, page=page,
                                     page_size=page_size, total_pages=0)
        base_query = base_query.where(ClientProfile.user_id.in_(own_ids))
        effective_master_id = None

    # If master_id filter is specified, only return clients who have appointments with this master
    if effective_master_id is not None:
        base_query = base_query.where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == effective_master_id)
            )
        )

    # Search filter
    if search:
        search_term = f"%{search}%"
        base_query = base_query.where(
            (User.name.ilike(search_term)) | (User.phone.ilike(search_term))
        )

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Data query (whitelisted sort column — never raw user input in ORDER BY)
    sort_map = {
        "name": User.name,
        "no_show": ClientProfile.no_show_count,
        "created_at": User.created_at,
    }
    if sort_by:
        sort_col = sort_map.get(sort_by, User.name)
        order = sort_col.desc() if str(sort_dir).lower() == "desc" else sort_col.asc()
    else:
        order = User.name.asc()  # legacy default
    data_query = (
        base_query
        # id tiebreak: names repeat (seed clones), without it rows jump
        # between pages and the same names reappear on every page
        .order_by(order, User.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_query)
    profiles = result.scalars().unique().all()

    # Bulk city names (one query, no N+1)
    from app.models.city import City
    city_ids = {cp.user.city_id for cp in profiles if cp.user.city_id is not None}
    city_names: dict = {}
    if city_ids:
        city_rows = await db.execute(
            select(City.id, City.name_ru).where(City.id.in_(city_ids))
        )
        city_names = dict(city_rows.all())

    # Build response
    blocked_by_cp: dict = {}
    hidden_by_cp: dict = {}
    # Attribution: which masters hid/blocked, with causes and notes.
    hidden_details: dict = {}
    from app.models.master_hidden_client import MasterHiddenClient
    from app.models.master_profile import MasterProfile
    if not is_admin:
        _mp_id = await get_master_profile_id(db, master)
        _rows = await db.execute(
            select(MasterHiddenClient).where(
                MasterHiddenClient.master_profile_id == _mp_id)
        )
        _all_rows = _rows.scalars().all()
    else:
        # Superadmin: badge when blocked anywhere.
        _rows = await db.execute(select(MasterHiddenClient))
        _all_rows = _rows.scalars().all()
    _mp_ids = list({r.master_profile_id for r in _all_rows})
    _mp_names: dict = {}
    if _mp_ids:
        _mps = await db.execute(
            select(MasterProfile.id, User.name).join(
                User, User.id == MasterProfile.user_id).where(
                MasterProfile.id.in_(_mp_ids))
        )
        _mp_names = dict(_mps.all())
    for _r in _all_rows:
        blocked_by_cp[_r.client_profile_id] = (
            blocked_by_cp.get(_r.client_profile_id, False)
            or bool(_r.is_blocked))
        hidden_by_cp.setdefault(_r.client_profile_id, _r.hidden_reason)
        hidden_details.setdefault(_r.client_profile_id, []).append({
            "master_id": _r.master_profile_id,
            "master_name": _mp_names.get(_r.master_profile_id),
            "is_blocked": bool(_r.is_blocked),
            "reason": _r.hidden_reason,
            "block_reason": _r.block_reason,
            "note": _r.block_note,
        })
    items = [
        {
            "id": cp.user.id,
            "name": cp.user.name,
            "phone": cp.user.phone,
            "email": cp.user.email,
            "no_show_count": cp.no_show_count or 0,
            "is_active": cp.user.is_active,
            "is_blocked": bool(blocked_by_cp.get(cp.id, False)),
            "is_hidden": cp.id in hidden_by_cp,
            "hidden_reason": hidden_by_cp.get(cp.id),
            "hidden_by": hidden_details.get(cp.id, []),
            "city_id": cp.user.city_id,
            "city_name": city_names.get(cp.user.city_id),
            "address": cp.address,
            "created_at": cp.user.created_at.isoformat() if cp.user.created_at else None,
            "updated_at": cp.user.updated_at.isoformat() if cp.user.updated_at else None,
        }
        for cp in profiles
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )


@router.post("/clients", response_model=ClientResponse, status_code=201)
async def create_admin_client(
    data: ClientCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new client with duplicate check."""
    result = await db.execute(select(User).where(User.phone == data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")
    if data.city_id is not None:
        from app.models.city import City
        city_row = await db.execute(select(City).where(City.id == data.city_id))
        city_obj = city_row.scalar_one_or_none()
        if city_obj is None:
            raise HTTPException(status_code=400, detail="Город не найден")
        city_id = data.city_id
        city_name = city_obj.name_ru
    elif data.city_name:
        city_id, city_name = await _resolve_city(db, data.city_name)
    else:
        city_id, city_name = None, None

    user = User(name=data.name, phone=data.phone, email=data.email, role=UserRole.CLIENT, city_id=city_id, created_by=master.id)
    db.add(user)
    await db.flush()

    client_profile = ClientProfile(user_id=user.id, address=(data.address or None))
    db.add(client_profile)
    await db.flush()
    await db.refresh(user)

    await log_action(db, master.id, "create", "client", user.id, data.name, level="info")
    await db.commit()

    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "no_show_count": 0,
        "is_active": user.is_active,
        "city_id": city_id,
        "city_name": city_name,
        "address": data.address or None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.patch("/clients/{client_id}", response_model=ClientResponse)
async def update_admin_client(
    client_id: int,
    data: ClientUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a client with duplicate check."""
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    await _require_own_client(db, master, user)

    if data.phone and data.phone != user.phone:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")
    if data.email and data.email != (user.email or ''):
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")
    if data.city_id is not None:
        from app.models.city import City
        city = await db.execute(select(City).where(City.id == data.city_id))
        if city.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="Город не найден")
    elif data.city_name:
        resolved_id, _ = await _resolve_city(db, data.city_name)
        data = data.model_copy(update={"city_id": resolved_id})

    for field, value in data.model_dump(exclude_unset=True).items():
        if field in ("city_name", "address"):
            continue  # not User columns — handled below
        setattr(user, field, value)

    profile_result = await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is not None and data.address is not None:
        profile.address = data.address.strip() or None
    
    await log_action(db, master.id, "update", "client", client_id, f"Обновлены поля: {', '.join(data.model_dump(exclude_unset=True).keys())}", level="info")
    await db.commit()
    await db.refresh(user)
    if profile is not None:
        await db.refresh(profile)

    city_name = None
    if user.city_id is not None:
        from app.models.city import City
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == user.city_id)
        )).scalar_one_or_none()
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "no_show_count": profile.no_show_count if profile else 0,
        "is_active": user.is_active,
        "city_id": user.city_id,
        "city_name": city_name,
        "address": profile.address if profile else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.post("/clients/{client_id}/toggle-active", response_model=ClientResponse)
async def toggle_client_active(
    client_id: int,
    master: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Block/unblock a client account service-wide (flips User.is_active).

    Superadmin only: masters have archive/blacklist for their own book,
    but only the admin may switch an account off entirely.
    """
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")

    user.is_active = not user.is_active
    await log_action(
        db, master.id, "toggle_active", "client", client_id,
        "Разблокирован" if user.is_active else "Заблокирован", level="warning",
    )
    await db.commit()
    await db.refresh(user)

    profile_result = await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    city_name = None
    if user.city_id is not None:
        from app.models.city import City
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == user.city_id)
        )).scalar_one_or_none()
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "no_show_count": profile.no_show_count if profile else 0,
        "is_active": user.is_active,
        "city_id": user.city_id,
        "city_name": city_name,
        "address": profile.address if profile else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


class BulkCityUpdate(BaseModel):
    city_id: int
    search: Optional[str] = None
    master_id: Optional[int] = None


@router.post("/clients/bulk-city", response_model=dict)
async def bulk_set_client_city(
    data: BulkCityUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Assign a city to all clients matching the filter (same semantics as list).

    Used to backfill cities for thousands of seed rows at once.
    """
    from app.models.city import City
    city_row = await db.execute(select(City).where(City.id == data.city_id))
    city_obj = city_row.scalar_one_or_none()
    if city_obj is None:
        raise HTTPException(status_code=400, detail="Город не найден")

    sub = (
        select(ClientProfile.user_id)
        .join(ClientProfile.user)
    )
    if master.role != UserRole.ADMIN:
        # Strict own-scope: booked with me or created by me.
        own_ids = await own_client_user_ids(db, master)
        if not own_ids:
            return {"updated": 0, "city_id": data.city_id, "city_name": city_obj.name_ru}
        sub = sub.where(ClientProfile.user_id.in_(own_ids))
    elif data.master_id is not None:
        sub = sub.where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == data.master_id)
            )
        )
    if data.search:
        search_term = f"%{data.search}%"
        sub = sub.where(
            (User.name.ilike(search_term)) | (User.phone.ilike(search_term))
        )
    ids_result = await db.execute(sub)
    user_ids = list({row[0] for row in ids_result.all()})
    if not user_ids:
        return {"updated": 0, "city_id": data.city_id, "city_name": city_obj.name_ru}

    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(User).where(User.id.in_(user_ids)).values(city_id=data.city_id)
    )
    await log_action(
        db, master.id, "bulk_city", "client", None,
        f"Город {city_obj.name_ru} назначен {len(user_ids)} клиентам", level="warning",
    )
    await db.commit()
    return {"updated": len(user_ids), "city_id": data.city_id, "city_name": city_obj.name_ru}


@router.post("/clients/{client_id}/block", status_code=200)
async def block_client(
    client_id: int,
    master_id: Optional[int] = Query(
        default=None,
        description="Superadmin only: MasterProfile.id to block for. "
                    "Omitted = block at every master (global blacklist)."),
    reason: Optional[str] = Query(
        default=None,
        description="Archive reason: moved | left | inactive | deceased | other."),
    block_reason: Optional[str] = Query(
        default=None,
        description="Block cause: no_show | rude | spam | debt | other."),
    note: Optional[str] = Query(
        default=None, max_length=500,
        description="Free text for 'other' (or any extra context)."),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Blacklist an own client: hide + bar new bookings (idempotent).

    Masters block for themselves. Superadmins block for the selected
    master (?master_id=) or everywhere at once (no master_id).
    History stays, rendered as «Удалённый клиент». A new booking
    (by either side) lifts the block.
    """
    from app.services.client_visibility import (
        BLOCK_REASONS, HIDE_REASONS, block_client_from_master,
    )
    if reason is not None and reason not in HIDE_REASONS:
        raise HTTPException(status_code=422,
                            detail=f"reason: one of {', '.join(HIDE_REASONS)}")
    if block_reason is not None and block_reason not in BLOCK_REASONS:
        raise HTTPException(
            status_code=422,
            detail=f"block_reason: one of {', '.join(BLOCK_REASONS)}")
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    await _require_own_client(db, master, user)

    from app.models.master_profile import MasterProfile
    if master.role == UserRole.ADMIN:
        if master_id is not None:
            mp_ids = [master_id]
        else:
            mp_ids = (await db.execute(select(MasterProfile.id))).scalars().all()
        total = 0
        for mp_id in mp_ids:
            total += await block_client_from_master(db, master, mp_id, user,
                                                    reason, block_reason,
                                                    note)
        return {"blocked": True, "cancelled_appointments": total,
                "masters": len(mp_ids)}
    mp_id = await get_master_profile_id(db, master)
    cancelled = await block_client_from_master(db, master, mp_id, user,
                                               reason, block_reason, note)
    return {"blocked": True, "cancelled_appointments": cancelled}


@router.delete("/clients/{client_id}/block", status_code=200)
async def unblock_client_endpoint(
    client_id: int,
    master_id: Optional[int] = Query(
        default=None,
        description="Superadmin only: MasterProfile.id to unblock for. "
                    "Omitted = unblock everywhere."),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Lift the blacklist: the client is fully visible again."""
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    await _require_own_client(db, master, user)

    from app.services.client_visibility import unblock_client
    from app.models.master_profile import MasterProfile
    cp = (await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )).scalar_one_or_none()
    if cp is None:
        return {"blocked": False, "was_blocked": False}
    if master.role == UserRole.ADMIN:
        mp_ids = ([master_id] if master_id is not None
                  else (await db.execute(select(MasterProfile.id))).scalars().all())
        lifted = False
        for mp_id in mp_ids:
            lifted = await unblock_client(db, mp_id, cp.id) or lifted
        return {"blocked": False, "was_blocked": lifted}
    mp_id = await get_master_profile_id(db, master)
    existed = await unblock_client(db, mp_id, cp.id)
    return {"blocked": False, "was_blocked": existed}


@router.post("/clients/{client_id}/restore", status_code=200)
async def restore_client(
    client_id: int,
    master_id: Optional[int] = Query(
        default=None,
        description="Superadmin only: MasterProfile.id to restore for. "
                    "Omitted = restore everywhere."),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Return an archived client to the lists (lifts hide and block)."""
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    await _require_own_client(db, master, user)

    from app.services.client_visibility import unblock_client
    from app.models.master_profile import MasterProfile
    cp = (await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )).scalar_one_or_none()
    if cp is None:
        return {"restored": False}
    if master.role == UserRole.ADMIN:
        mp_ids = ([master_id] if master_id is not None
                  else (await db.execute(select(MasterProfile.id))).scalars().all())
        lifted = False
        for mp_id in mp_ids:
            lifted = await unblock_client(db, mp_id, cp.id) or lifted
        await log_action(db, master.id, "restore", "client", client_id,
                         user.name, level="info")
        return {"restored": lifted}
    mp_id = await get_master_profile_id(db, master)
    restored = await unblock_client(db, mp_id, cp.id)
    await log_action(db, master.id, "restore", "client", client_id,
                     user.name, level="info")
    return {"restored": restored}


@router.delete("/clients/{client_id}", status_code=204)
async def delete_admin_client(
    client_id: int,
    purge: bool = Query(
        default=False,
        description="Superadmin only: true = irreversible full erasure "
                    "(account + appointments). Default = reversible block "
                    "everywhere (superadmin) or archive (master)."),
    reason: Optional[str] = Query(
        default=None,
        description="Archive reason: moved | left | inactive | deceased | other."),
    note: Optional[str] = Query(
        default=None, max_length=500,
        description="Free text for 'other' (or any extra context)."),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Remove a client from the master's lists (archive, history kept).

    Regular masters archive with an optional reason: the account stays
    active, past appointments render as «Удалённый клиент», future ones
    with this master are cancelled.
    Superadmins block everywhere instead (reversible). Pass ?purge=true
    for the irreversible full erasure (account + appointments) — legal
    erasure requests only, logged as a warning.
    """
    from app.services.client_visibility import (
        HIDE_REASONS, block_client_from_master, hide_client_from_master,
    )
    if reason is not None and reason not in HIDE_REASONS:
        raise HTTPException(status_code=422,
                            detail=f"reason: one of {', '.join(HIDE_REASONS)}")
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    await _require_own_client(db, master, user)

    if master.role != UserRole.ADMIN:
        mp_id = await get_master_profile_id(db, master)
        await hide_client_from_master(db, master, mp_id, user, reason, note)
        return None

    if not purge:
        from app.models.master_profile import MasterProfile
        mp_ids = (await db.execute(select(MasterProfile.id))).scalars().all()
        for mp_id in mp_ids:
            await block_client_from_master(db, master, mp_id, user, reason,
                                           None, note)
        return None

    # Also delete the client_profile
    profile_result = await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == client_id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile:
        # Full erasure: drop the client's appointments explicitly first —
        # leaving ORM to nullify client_id hits the NOT NULL constraint (500).
        from sqlalchemy import delete as sa_delete
        from app.models.master_hidden_client import MasterHiddenClient
        await db.execute(sa_delete(Appointment).where(
            Appointment.client_id == profile.id))
        await db.execute(sa_delete(MasterHiddenClient).where(
            MasterHiddenClient.client_profile_id == profile.id))
        await db.delete(profile)

    await log_action(db, master.id, "delete", "client", client_id, user.name, level="warning")
    await db.delete(user)
    await db.commit()
    return None
