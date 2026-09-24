from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Patient


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

templates = Jinja2Templates(
    directory="app/templates"
)


# =========================================================
# DASHBOARD HOME
# =========================================================

@router.get(
    "",
    response_class=HTMLResponse,
)
def dashboard(
    request: Request,
    search: str | None = None,
    state: str | None = None,
    sex: str | None = None,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    week_start = now - timedelta(days=7)

    recent_update_cutoff = now - timedelta(hours=24)

    # -----------------------------------------------------
    # BASE QUERY
    # -----------------------------------------------------

    active_query = db.query(Patient).filter(
        Patient.deleted_at.is_(None)
    )

    # -----------------------------------------------------
    # DASHBOARD STATISTICS
    # -----------------------------------------------------

    total_patients = active_query.count()

    registrations_today = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            Patient.created_at >= today_start,
        )
        .count()
    )

    registrations_week = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            Patient.created_at >= week_start,
        )
        .count()
    )

    recently_updated = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            Patient.updated_at >= recent_update_cutoff,
        )
        .count()
    )

    # -----------------------------------------------------
    # PATIENT SEARCH / FILTERS
    # -----------------------------------------------------

    query = db.query(Patient).filter(
        Patient.deleted_at.is_(None)
    )

    if search:
        search = search.strip()

        query = query.filter(
            or_(
                Patient.first_name.ilike(f"%{search}%"),
                Patient.last_name.ilike(f"%{search}%"),
                Patient.phone_number.ilike(f"%{search}%"),
                Patient.email.ilike(f"%{search}%"),
            )
        )

    if state:
        query = query.filter(
            Patient.state == state
        )

    if sex:
        query = query.filter(
            Patient.sex == sex
        )

    patients = (
        query
        .order_by(Patient.created_at.desc())
        .all()
    )

    # -----------------------------------------------------
    # AVAILABLE STATES FOR FILTER
    # -----------------------------------------------------

    states = (
        db.query(Patient.state)
        .filter(
            Patient.deleted_at.is_(None)
        )
        .distinct()
        .order_by(Patient.state)
        .all()
    )

    states = [
        row[0]
        for row in states
        if row[0]
    ]

    # -----------------------------------------------------
    # RECENT REGISTRATIONS
    # -----------------------------------------------------

    recent_patients = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None)
        )
        .order_by(
            Patient.created_at.desc()
        )
        .limit(5)
        .all()
    )

    # -----------------------------------------------------
    # STATE DISTRIBUTION
    # -----------------------------------------------------

    state_distribution = (
        db.query(
            Patient.state,
            func.count(Patient.patient_id),
        )
        .filter(
            Patient.deleted_at.is_(None)
        )
        .group_by(Patient.state)
        .order_by(
            func.count(Patient.patient_id).desc()
        )
        .limit(8)
        .all()
    )

    state_labels = [
        row[0] or "Unknown"
        for row in state_distribution
    ]

    state_values = [
        row[1]
        for row in state_distribution
    ]

    # -----------------------------------------------------
    # SEX DISTRIBUTION
    # -----------------------------------------------------

    sex_distribution = (
        db.query(
            Patient.sex,
            func.count(Patient.patient_id),
        )
        .filter(
            Patient.deleted_at.is_(None)
        )
        .group_by(Patient.sex)
        .all()
    )

    sex_labels = [
        row[0] or "Unknown"
        for row in sex_distribution
    ]

    sex_values = [
        row[1]
        for row in sex_distribution
    ]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "patients": patients,
            "recent_patients": recent_patients,

            "total_patients": total_patients,
            "registrations_today": registrations_today,
            "registrations_week": registrations_week,
            "recently_updated": recently_updated,

            "search": search or "",
            "selected_state": state or "",
            "selected_sex": sex or "",
            "states": states,

            "state_labels": state_labels,
            "state_values": state_values,

            "sex_labels": sex_labels,
            "sex_values": sex_values,
        },
    )


# =========================================================
# PATIENT DETAIL
# =========================================================

@router.get(
    "/patients/{patient_id}",
    response_class=HTMLResponse,
)
def patient_detail(
    patient_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    patient = (
        db.query(Patient)
        .filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    if patient is None:
        return templates.TemplateResponse(
            request=request,
            name="patient_detail.html",
            context={
                "patient": None,
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="patient_detail.html",
        context={
            "patient": patient,
        },
    )