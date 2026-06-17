from typing import Any

from fastapi import APIRouter

from app.common.schemas import Envelope, Message

router = APIRouter(tags=["Applicants & Portal (Student 2)"])


@router.post("/applicants/", response_model=Message)
def create_applicant():
    # TODO: validate payload, insert into applicants, enforce unique national_id
    return Message(message="TODO: create applicant")


@router.get("/applicants/{applicant_id}", response_model=Message)
def get_applicant(applicant_id: str):
    # TODO: fetch from applicants by applicant_id
    return Message(message=f"TODO: get applicant {applicant_id}")


@router.get("/applicants/{applicant_id}/applications", response_model=Envelope[Any])
def get_applicant_applications(applicant_id: str):
    # TODO: list land_applications where applicant_ref == applicant_id; paginate
    return Envelope(data=[], total=0, page=1, limit=20)


@router.post("/applications/{application_id}/documents", response_model=Message)
def upload_document(application_id: str):
    # TODO: handle multipart file, store metadata in documents sub-collection, call log_event
    return Message(message=f"TODO: upload document for application {application_id}")


@router.post("/applications/{application_id}/comments", response_model=Message)
def add_comment(application_id: str):
    # TODO: append comment object to application's comments array, call log_event
    return Message(message=f"TODO: add comment to application {application_id}")


@router.post("/applications/{application_id}/objections", response_model=Message)
def raise_objection(application_id: str):
    # TODO: call guard(doc, under_objection), store objection details, call log_event
    return Message(message=f"TODO: raise objection for application {application_id}")


@router.get("/applications/{application_id}/timeline", response_model=Envelope[Any])
def get_timeline(application_id: str):
    # TODO: fetch and sort events from performance_logs for this application_id
    return Envelope(data=[], total=0, page=1, limit=100)
