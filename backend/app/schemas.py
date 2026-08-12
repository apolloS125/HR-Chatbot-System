from typing import Literal

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    work_email: str = Field(min_length=3, max_length=255)
    role: Literal["employee", "hr", "admin"] = "employee"


class ActiveUpdate(BaseModel):
    active: bool


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(min_length=1, max_length=120)


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)
