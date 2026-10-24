from pydantic import BaseModel
from typing import Optional

class StaffOut(BaseModel):
    id: str
    name: str
    role: str
    employee_code: str
    avatar_url: str
    is_active: bool = True

class StaffLoginRequest(BaseModel):
    employee_code: str
    pin: Optional[str] = None
