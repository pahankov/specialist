from pydantic import BaseModel
from typing import Optional

class ClientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None

class ClientResponse(BaseModel):
    id: int
    name: str
    phone: str
    class Config:
        from_attributes = True
