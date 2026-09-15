from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.master import Master
from app.schemas.master import MasterCreate, MasterResponse
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
from app.config import settings

# JWT configuration
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=MasterResponse, status_code=status.HTTP_201_CREATED)
async def register_master(master: MasterCreate, db: AsyncSession = Depends(get_db)):
    # Check if master already exists
    result = await db.execute(select(Master).where(Master.email == master.email))
    existing_master = result.scalar_one_or_none()
    if existing_master:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master with this email already exists"
        )
    
    # Hash password
    hashed_password = pwd_context.hash(master.password)
    
    # Create new master
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

@router.post("/login")
async def login(email: str, password: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Master).where(Master.email == email))
    master = result.scalar_one_or_none()
    
    if not master or not pwd_context.verify(password, master.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(
        data={"sub": master.email, "master_id": master.id}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}