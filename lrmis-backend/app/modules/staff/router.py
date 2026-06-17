from typing import Any

from fastapi import APIRouter

from app.common.schemas import Envelope, Message

router = APIRouter(tags=["Staff, Survey & Assignment (Student 3)"])


@router.post("/staff/", response_model=Message)
def create_staff():
    # TODO: validate payload, insert into staff_members, enforce unique staff_code
    return Message(message="TODO: create staff member")


@router.get("/staff/{staff_id}", response_model=Message)
def get_staff(staff_id: str):
    # TODO: fetch from staff_members by staff_id
    return Message(message=f"TODO: get staff {staff_id}")


@router.post("/applications/{application_id}/auto-assign-surveyor", response_model=Message)
def auto_assign_surveyor(application_id: str):
    # TODO: load application, call assignment.pick_surveyor(zone_id, skill),
    #       create survey_task doc, advance to survey_required, call log_event
    return Message(message=f"TODO: auto-assign surveyor for application {application_id}")


@router.patch("/applications/{application_id}/survey-milestone", response_model=Message)
def update_survey_milestone(application_id: str):
    # TODO: validate SurveyMilestone value, update survey_tasks doc, call log_event
    return Message(message=f"TODO: update survey milestone for application {application_id}")


@router.post("/applications/{application_id}/survey-report", response_model=Message)
def upload_survey_report(application_id: str):
    # TODO: store report reference, advance milestone to report_uploaded, call log_event
    return Message(message=f"TODO: upload survey report for application {application_id}")


@router.patch("/applications/{application_id}/registrar-review", response_model=Message)
def registrar_review(application_id: str):
    # TODO: record registrar decision, advance milestone to registrar_reviewed, call log_event
    return Message(message=f"TODO: registrar review for application {application_id}")
