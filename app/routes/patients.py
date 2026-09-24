from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..exceptions import AppException
from ..models import Patient
from ..schemas import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    normalize_phone,
)


router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)


# =========================================================
# HELPER RESPONSE
# =========================================================

def success_response(data):
    return {
        "data": data,
        "error": None,
    }


# =========================================================
# POST /patients
# CREATE A NEW PATIENT
# =========================================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new patient.

    Duplicate active patients are detected using the phone number.
    """

    existing_patient = (
        db.query(Patient)
        .filter(
            Patient.phone_number == patient_data.phone_number,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    if existing_patient:
        raise AppException(
            status_code=409,
            message=(
                "A patient with this phone number already exists."
            ),
        )

    try:
        patient = Patient(
            **patient_data.model_dump()
        )

        db.add(patient)
        db.commit()
        db.refresh(patient)

    except SQLAlchemyError as exc:
        db.rollback()

        print(
            f"Database error while creating patient: {exc}"
        )

        raise AppException(
            status_code=500,
            message="Unable to save patient record.",
        )

    response = PatientResponse.model_validate(
        patient
    )

    print(
        "Patient created successfully:",
        response.model_dump(),
    )

    return {
        "data": {
            "success": True,
            "message": (
                "Patient registration saved successfully."
            ),
            **response.model_dump(),
        },
        "error": None,
    }


# =========================================================
# POST /patients/lookup
# LOOKUP PATIENT BY PHONE NUMBER
# =========================================================

@router.post("/lookup")
def lookup_patient(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Search for an existing active patient using their phone number.

    Mainly used by the Vapi voice agent for duplicate detection.
    """

    phone_number = payload.get(
        "phone_number"
    )

    if not phone_number:
        raise AppException(
            status_code=400,
            message="Phone number is required.",
        )

    try:
        normalized_phone = normalize_phone(
            phone_number
        )

    except ValueError as exc:
        raise AppException(
            status_code=400,
            message=str(exc),
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.phone_number == normalized_phone,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    # Patient does not exist
    if patient is None:
        return success_response(
            {
                "found": False,
                "message": (
                    "No existing patient was found "
                    "with this phone number."
                ),
            }
        )

    # Patient exists
    response = PatientResponse.model_validate(
        patient
    )

    return success_response(
        {
            "found": True,
            "message": (
                "An existing patient record was found."
            ),
            "patient": response.model_dump(),
        }
    )

# =========================================================
# POST /patients/update
# VOICE AGENT UPDATE HELPER
# =========================================================

@router.post("/update")
def voice_update_patient(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Helper endpoint for the voice agent.

    Expected payload example:

    {
        "patient_id": "...",
        "city": "Los Angeles",
        "state": "California"
    }
    """

    patient_id = payload.pop("patient_id", None)

    if not patient_id:
        raise AppException(
            status_code=400,
            message="patient_id is required.",
        )

    patient = (
        db.query(Patient)
        .filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    if patient is None:
        raise AppException(
            status_code=404,
            message="Patient not found.",
        )

    # Vapi may send optional fields as empty strings.
    # Ignore fields that were not actually provided.
    cleaned_payload = {
        key: value
        for key, value in payload.items()
        if value is not None
        and not (
            isinstance(value, str)
            and not value.strip()
        )
    }

    if not cleaned_payload:
        raise AppException(
            status_code=400,
            message="No update fields were provided.",
        )

    try:
        # Reuse our Pydantic validation
        patient_data = PatientUpdate(
            **cleaned_payload
        )

    except Exception as exc:
        raise AppException(
            status_code=422,
            message=str(exc),
        )

    update_data = patient_data.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    # Prevent duplicate phone numbers
    new_phone = update_data.get("phone_number")

    if new_phone:
        duplicate = (
            db.query(Patient)
            .filter(
                Patient.phone_number == new_phone,
                Patient.patient_id != patient_id,
                Patient.deleted_at.is_(None),
            )
            .first()
        )

        if duplicate:
            raise AppException(
                status_code=409,
                message=(
                    "Another patient already uses "
                    "this phone number."
                ),
            )

    for field, value in update_data.items():
        setattr(patient, field, value)

    patient.updated_at = datetime.now(
        timezone.utc
    )

    try:
        db.commit()
        db.refresh(patient)

    except SQLAlchemyError as exc:
        db.rollback()

        print(
            f"Database error while updating patient: {exc}"
        )

        raise AppException(
            status_code=500,
            message="Unable to update patient record.",
        )

    response = PatientResponse.model_validate(
        patient
    )

    return {
        "data": {
            "success": True,
            "message": "Patient record updated successfully.",
            **response.model_dump(),
        },
        "error": None,
    }

# =========================================================
# GET /patients
# LIST / FILTER PATIENTS
# =========================================================

@router.get("")
def list_patients(
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    phone_number: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all active patients.

    Optional filters:
    - last_name
    - date_of_birth
    - phone_number
    """

    query = (
        db.query(Patient)
        .filter(
            Patient.deleted_at.is_(None)
        )
    )

    if last_name:
        query = query.filter(
            Patient.last_name == last_name
        )

    if date_of_birth:
        query = query.filter(
            Patient.date_of_birth
            == date_of_birth
        )

    if phone_number:
        try:
            normalized_phone = normalize_phone(
                phone_number
            )

        except ValueError as exc:
            raise AppException(
                status_code=400,
                message=str(exc),
            )

        query = query.filter(
            Patient.phone_number
            == normalized_phone
        )

    try:
        patients = query.all()

    except SQLAlchemyError as exc:
        print(
            f"Database error while listing patients: {exc}"
        )

        raise AppException(
            status_code=500,
            message="Unable to retrieve patients.",
        )

    data = [
        PatientResponse
        .model_validate(patient)
        .model_dump()
        for patient in patients
    ]

    return success_response(data)


# =========================================================
# GET /patients/{patient_id}
# GET ONE PATIENT
# =========================================================

@router.get("/{patient_id}")
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve one active patient using patient_id.
    """

    patient = (
        db.query(Patient)
        .filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    if patient is None:
        raise AppException(
            status_code=404,
            message="Patient not found.",
        )

    response = PatientResponse.model_validate(
        patient
    )

    return success_response(
        response.model_dump()
    )


# =========================================================
# PUT /patients/{patient_id}
# UPDATE PATIENT
# =========================================================

@router.put("/{patient_id}")
def update_patient(
    patient_id: str,
    patient_data: PatientUpdate,
    db: Session = Depends(get_db),
):
    """
    Partially update an existing patient.

    Only fields included in the request are modified.
    """

    patient = (
        db.query(Patient)
        .filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    if patient is None:
        raise AppException(
            status_code=404,
            message="Patient not found.",
        )

    update_data = (
        patient_data.model_dump(
            exclude_unset=True
        )
    )

    # If phone number is being changed,
    # prevent duplicate active records.
    new_phone = update_data.get(
        "phone_number"
    )

    if new_phone:
        duplicate = (
            db.query(Patient)
            .filter(
                Patient.phone_number
                == new_phone,
                Patient.patient_id
                != patient_id,
                Patient.deleted_at.is_(None),
            )
            .first()
        )

        if duplicate:
            raise AppException(
                status_code=409,
                message=(
                    "Another patient already uses "
                    "this phone number."
                ),
            )

    for field, value in update_data.items():
        setattr(
            patient,
            field,
            value,
        )

    patient.updated_at = datetime.now(
        timezone.utc
    )

    try:
        db.commit()
        db.refresh(patient)

    except SQLAlchemyError as exc:
        db.rollback()

        print(
            f"Database error while updating patient: {exc}"
        )

        raise AppException(
            status_code=500,
            message="Unable to update patient record.",
        )

    response = PatientResponse.model_validate(
        patient
    )

    return {
        "data": {
            "success": True,
            "message": (
                "Patient record updated successfully."
            ),
            **response.model_dump(),
        },
        "error": None,
    }


# =========================================================
# DELETE /patients/{patient_id}
# SOFT DELETE PATIENT
# =========================================================

@router.delete("/{patient_id}")
def delete_patient(
    patient_id: str,
    db: Session = Depends(get_db),
):
    """
    Soft-delete a patient.

    The record remains in MySQL,
    but deleted_at is populated.
    """

    patient = (
        db.query(Patient)
        .filter(
            Patient.patient_id == patient_id,
            Patient.deleted_at.is_(None),
        )
        .first()
    )

    if patient is None:
        raise AppException(
            status_code=404,
            message="Patient not found.",
        )

    now = datetime.now(
        timezone.utc
    )

    patient.deleted_at = now
    patient.updated_at = now

    try:
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()

        print(
            f"Database error while deleting patient: {exc}"
        )

        raise AppException(
            status_code=500,
            message="Unable to delete patient record.",
        )

    return success_response(
        {
            "success": True,
            "message": (
                "Patient deleted successfully."
            ),
        }
    )