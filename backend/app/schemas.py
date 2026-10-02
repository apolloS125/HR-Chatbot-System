from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    employee_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    work_email: str = Field(min_length=3, max_length=255)
    role: Literal["employee", "hr", "admin"] = "employee"

    @field_validator("employee_code")
    @classmethod
    def valid_code(cls, value):
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", value):
            raise ValueError("รหัสพนักงานใช้ได้เฉพาะตัวอักษรอังกฤษ ตัวเลข _ และ -")
        return value.upper()

    @field_validator("work_email")
    @classmethod
    def valid_email(cls, value):
        import re
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("อีเมลไม่ถูกต้อง")
        return value


class EmployeeUpdate(EmployeeCreate):
    password: str | None = Field(default=None, min_length=10, max_length=128)
    vacation: float = Field(ge=0, le=366)
    sick: float = Field(ge=0, le=366)
    personal: float = Field(ge=0, le=366)
    vacation_entitlement: float = Field(default=10, ge=0, le=366)
    sick_entitlement: float = Field(default=30, ge=0, le=366)
    personal_entitlement: float = Field(default=5, ge=0, le=366)


class HolidayCreate(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=120)


class PolicyQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1500)


class FaqCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    keyword: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=10000)
    active: bool = True


class ActiveUpdate(BaseModel):
    active: bool


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(default="HR", min_length=1, max_length=120)


class AnnouncementCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)
    request_key: str | None = Field(default=None, min_length=16, max_length=128)


class LiffSessionCreate(BaseModel):
    id_token: str = Field(min_length=1)


class LiffLeaveCreate(BaseModel):
    leave_type: Literal["vacation", "sick", "personal"]
    start_date: date
    end_date: date
    reason: str = Field(default="-", max_length=1500)
    attachment_id: str | None = Field(default=None, max_length=64)
    request_key: str = Field(min_length=16, max_length=128)
    half_day: Literal["morning", "afternoon"] | None = None
