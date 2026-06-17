from typing import Any

from fastapi import APIRouter

from app.common.schemas import Envelope, Message

router = APIRouter(prefix="/applications", tags=["Applications (Student 1)"])


@router.post("/", response_model=Message)
def create_application():
    # TODO: validate payload, insert into land_applications, call log_event
    return Message(message="TODO: create application")


@router.get("/", response_model=Envelope[Any])
def list_applications():
    # TODO: filter by status/type/zone/date; paginate with page & limit query params
    return Envelope(data=[], total=0, page=1, limit=20)


@router.get("/{application_id}", response_model=Message)
def get_application(application_id: str):
    # TODO: fetch from land_applications by application_id
    return Message(message=f"TODO: get application {application_id}")


@router.patch("/{application_id}/transition", response_model=Message)
def transition_application(application_id: str):
    # TODO: load doc, call workflow.guard(), update status, call log_event
    return Message(message=f"TODO: transition application {application_id}")


@router.post("/{application_id}/hold", response_model=Message)
def hold_application(application_id: str):
    # TODO: call guard(doc, on_hold), update status, persist reason, call log_event
    return Message(message=f"TODO: hold application {application_id}")


@router.post("/{application_id}/reject", response_model=Message)
def reject_application(application_id: str):
    # TODO: call guard(doc, rejected), update status, persist reason, call log_event
    return Message(message=f"TODO: reject application {application_id}")


@router.post("/{application_id}/certificate", response_model=Message)
def issue_certificate(application_id: str):
    # TODO: call guard(doc, certificate_issued), create certificates doc, call log_event
    return Message(message=f"TODO: issue certificate for application {application_id}")
