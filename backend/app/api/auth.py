from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.master import Master
from app.schemas.master import MasterCreate, MasterResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from app.config import settings

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=MasterResponse, status_code=status.HTTP_201_CREATED)
async def register_master(master: MasterCreate, db: AsyncSession = Depends(get_db)):
    """Register a new master."""
    result = await db.execute(select(Master).where(Master.email == master.email))
    existing_master = result.scalar_one_or_none()
    if existing_master:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master with this email already exists"
        )
    
    hashed_password = pwd_context.hash(master.password)
    
    new_master = Master(
        name=master.name,
        email=master.email,
        hashed_password=hashed_password,
        phone=master.phone,
        telegram_username=master.telegram_username
    )
    
    db.add(new_master)
    await db.commit()
    await db.refresh(new_master)
    
    return new_master

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login and get access + refresh tokens."""
    result = await db.execute(select(Master).where(Master.email == req.email))
    master = result.scalar_one_or_none()
    
    if not master or not pwd_context.verify(req.password, master.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(
        data={"sub": master.email, "master_id": master.id}
    )
    refresh_token = create_refresh_token(
        data={"sub": master.email, "master_id": master.id}
    )
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: dict):
    """Refresh access token using refresh token."""
    token = req.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh_token")
    
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        master_id = payload.get("master_id")
        email = payload.get("sub")
        
        if not master_id or not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        new_access_token = create_access_token(
            data={"sub": email, "master_id": master_id}
        )
        
        return {"access_token": new_access_token, "refresh_token": token, "token_type": "bearer"}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
