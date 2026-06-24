from typing import List, Optional

from pydantic import BaseModel, Field

from app.common.enums import SurveyMilestone, StaffRole


class StaffSchedule(BaseModel):
    working_days: List[str] = Field(default=["Mon", "Tue", "Wed", "Thu", "Fri"])
    shift_start: str = "08:00"
    shift_end: str = "16:00"
    max_concurrent_tasks: int = Field(default=3, ge=1, le=20)


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2)
    role: StaffRole
    national_id: str = Field(min_length=5)
    email: Optional[str] = None
    phone: Optional[str] = None
    # zones the surveyor is authorized to work in; can be empty for registrars
    coverage_zones: List[str] = Field(default=[])
    skills: List[str] = Field(default=[])
    schedule: Optional[StaffSchedule] = None


class SurveyMilestoneRequest(BaseModel):
    milestone: SurveyMilestone
    surveyor_id: str
    notes: Optional[str] = None
    # ISO date string, only relevant when milestone == visit_scheduled
    scheduled_date: Optional[str] = None


class SurveyReportCreate(BaseModel):
    surveyor_id: str
    findings: str = Field(min_length=10)
    parcel_area_sqm: Optional[float] = None
    boundary_confirmed: bool = False
    coordinates_verified: bool = False
    field_notes: Optional[str] = None
    recommendations: Optional[str] = None


class RegistrarReviewRequest(BaseModel):
    registrar_id: str
    decision: str = Field(pattern="^(approved|rejected|needs_revision)$")
    notes: Optional[str] = None


class ReassignRequest(BaseModel):
    surveyor_id: str
    reason: Optional[str] = None