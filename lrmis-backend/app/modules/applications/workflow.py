from app.common.enums import ApplicationStatus

ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.submitted: {
        ApplicationStatus.pre_checked,
        ApplicationStatus.rejected,
        ApplicationStatus.missing_documents,
        ApplicationStatus.on_hold,
    },
    ApplicationStatus.pre_checked: {
        ApplicationStatus.survey_required,
        ApplicationStatus.legal_review,
        ApplicationStatus.rejected,
        ApplicationStatus.on_hold,
        ApplicationStatus.missing_documents,
    },
    ApplicationStatus.survey_required: {
        ApplicationStatus.surveyed,
        ApplicationStatus.on_hold,
        ApplicationStatus.rejected,
        ApplicationStatus.missing_documents,
    },
    ApplicationStatus.surveyed: {
        ApplicationStatus.legal_review,
        ApplicationStatus.survey_required,
        ApplicationStatus.on_hold,
        ApplicationStatus.under_objection,
    },
    ApplicationStatus.legal_review: {
        ApplicationStatus.approved,
        ApplicationStatus.rejected,
        ApplicationStatus.on_hold,
        ApplicationStatus.under_objection,
        ApplicationStatus.missing_documents,
    },
    ApplicationStatus.approved: {
        ApplicationStatus.certificate_issued,
        ApplicationStatus.on_hold,
    },
    ApplicationStatus.certificate_issued: {
        ApplicationStatus.closed,
    },
    ApplicationStatus.closed: set(),
    ApplicationStatus.rejected: set(),
    ApplicationStatus.on_hold: {
        ApplicationStatus.pre_checked,
        ApplicationStatus.survey_required,
        ApplicationStatus.legal_review,
        ApplicationStatus.rejected,
    },
    ApplicationStatus.missing_documents: {
        ApplicationStatus.pre_checked,
        ApplicationStatus.survey_required,
        ApplicationStatus.legal_review,
    },
    ApplicationStatus.under_objection: {
        ApplicationStatus.legal_review,
        ApplicationStatus.rejected,
        ApplicationStatus.on_hold,
    },
}


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def guard(app_doc: dict, target: ApplicationStatus) -> tuple[bool, str]:
    """
    Validates business rules before a transition is committed.
    Returns (True, "") when the transition may proceed.
    """
    current = ApplicationStatus(app_doc.get("status"))

    if not can_transition(current, target):
        return False, f"Transition from '{current}' to '{target}' is not allowed"

    # Enforced: a certificate can only be issued from the approved state.
    if target == ApplicationStatus.certificate_issued:
        if app_doc.get("status") != ApplicationStatus.approved:
            return False, "Certificate can only be issued for approved applications"

    # TODO: guard — all required documents must be present before pre_checked
    # TODO: guard — a completed survey task must exist before survey_required -> surveyed
    # TODO: guard — registrar sign-off must be recorded before legal_review -> approved
    # TODO: guard — fee payment must be confirmed before certificate_issued
    # TODO: guard — objection must be formally resolved before under_objection -> legal_review

    return True, ""
