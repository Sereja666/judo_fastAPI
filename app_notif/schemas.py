from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    telegram_id: int
    telegram_username: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    get_news: Optional[bool] = None
    get_pays_notif: Optional[bool] = None
    get_info_student: Optional[bool] = None
    rejection_reason: Optional[str] = None


class User(UserBase):
    id: int
    date_reg: datetime
    is_active: bool
    get_news: bool
    get_pays_notif: bool
    get_info_student: bool
    last_login: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class StudentInfo(BaseModel):
    id: int
    name: str
    active: bool


class UserWithStudents(User):
    students: list[StudentInfo] = []

