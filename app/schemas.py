import re
from datetime import date, datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    field_validator,
)


# =========================================================
# U.S. STATES
# =========================================================

US_STATES = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
}


VALID_SEX_VALUES = {
    "Male",
    "Female",
    "Other",
    "Decline to Answer",
}


# =========================================================
# HELPER VALIDATION FUNCTIONS
# =========================================================

def validate_name(value: str) -> str:
    value = value.strip()

    if not re.fullmatch(r"[A-Za-z'-]{1,50}", value):
        raise ValueError(
            "Name must contain only letters, hyphens, or apostrophes."
        )

    return value


def validate_dob(value: date) -> date:
    if value > date.today():
        raise ValueError(
            "Date of birth cannot be in the future."
        )

    return value


def normalize_phone(value: str) -> str:
    """
    Convert common U.S. phone number formats into 10 digits.

    Examples:
    (646) 555-0132 -> 6465550132
    +1 646 555 0132 -> 6465550132
    """

    digits = re.sub(r"\D", "", value)

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        raise ValueError(
            "Phone number must contain exactly 10 U.S. digits."
        )

    return digits


def validate_state(value: str) -> str:
    """
    Accept either:
    California
    california
    CA
    ca

    Always return:
    CA
    """

    value = value.strip()

    abbreviation = value.upper()

    if abbreviation in US_STATES.values():
        return abbreviation

    for state_name, state_code in US_STATES.items():
        if value.lower() == state_name.lower():
            return state_code

    raise ValueError(
        "State must be a valid U.S. state name "
        "or 2-letter abbreviation."
    )


def validate_zip(value: str) -> str:
    value = value.strip()

    if not re.fullmatch(r"\d{5}(-\d{4})?", value):
        raise ValueError(
            "ZIP code must be 5 digits or ZIP+4."
        )

    return value


def empty_to_none(value):
    """
    Vapi sometimes sends optional fields as "" instead of null.

    Convert:
        ""

    Into:
        None
    """

    if isinstance(value, str) and not value.strip():
        return None

    return value


# =========================================================
# CREATE PATIENT SCHEMA
# =========================================================

class PatientCreate(BaseModel):

    # -------------------------
    # Required fields
    # -------------------------

    first_name: str
    last_name: str

    date_of_birth: date

    sex: str

    phone_number: str

    address_line_1: str

    city: str
    state: str
    zip_code: str

    # -------------------------
    # Optional fields
    # -------------------------

    email: Optional[EmailStr] = None

    address_line_2: Optional[str] = None

    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None

    preferred_language: str = "English"

    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # =====================================================
    # Handle empty optional fields from Vapi
    # =====================================================

    @field_validator(
        "email",
        "address_line_2",
        "insurance_provider",
        "insurance_member_id",
        "emergency_contact_name",
        "emergency_contact_phone",
        mode="before",
    )
    @classmethod
    def convert_empty_optional_fields(cls, value):
        return empty_to_none(value)

    # =====================================================
    # Preferred language
    # =====================================================

    @field_validator(
        "preferred_language",
        mode="before",
    )
    @classmethod
    def default_language(cls, value):

        if value is None:
            return "English"

        if isinstance(value, str) and not value.strip():
            return "English"

        return value.strip()

    # =====================================================
    # Name validation
    # =====================================================

    @field_validator(
        "first_name",
        "last_name",
    )
    @classmethod
    def check_names(cls, value):
        return validate_name(value)

    # =====================================================
    # DOB
    # =====================================================

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, value):
        return validate_dob(value)

    # =====================================================
    # Sex
    # =====================================================

    @field_validator("sex")
    @classmethod
    def check_sex(cls, value):

        value = value.strip()

        # Accept small variations from the LLM
        normalized_values = {
            "male": "Male",
            "female": "Female",
            "other": "Other",
            "decline to answer": "Decline to Answer",
        }

        normalized = normalized_values.get(
            value.lower()
        )

        if normalized is None:
            raise ValueError(
                "Sex must be Male, Female, Other, "
                "or Decline to Answer."
            )

        return normalized

    # =====================================================
    # Phone
    # =====================================================

    @field_validator("phone_number")
    @classmethod
    def check_phone(cls, value):
        return normalize_phone(value)

    # =====================================================
    # Emergency phone
    # =====================================================

    @field_validator("emergency_contact_phone")
    @classmethod
    def check_emergency_phone(cls, value):

        if value is None:
            return None

        return normalize_phone(value)

    # =====================================================
    # State
    # =====================================================

    @field_validator("state")
    @classmethod
    def check_state(cls, value):
        return validate_state(value)

    # =====================================================
    # ZIP
    # =====================================================

    @field_validator("zip_code")
    @classmethod
    def check_zip(cls, value):
        return validate_zip(value)

    # =====================================================
    # City
    # =====================================================

    @field_validator("city")
    @classmethod
    def check_city(cls, value):

        value = value.strip()

        if not 1 <= len(value) <= 100:
            raise ValueError(
                "City must contain between 1 and 100 characters."
            )

        return value

    # =====================================================
    # Address
    # =====================================================

    @field_validator("address_line_1")
    @classmethod
    def check_address(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "Street address is required."
            )

        return value


# =========================================================
# UPDATE PATIENT SCHEMA
# =========================================================

class PatientUpdate(BaseModel):

    first_name: Optional[str] = None
    last_name: Optional[str] = None

    date_of_birth: Optional[date] = None

    sex: Optional[str] = None

    phone_number: Optional[str] = None

    email: Optional[EmailStr] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None

    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None

    preferred_language: Optional[str] = None

    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # =====================================================
    # Convert empty strings to None
    # =====================================================

    @field_validator(
        "email",
        "address_line_2",
        "insurance_provider",
        "insurance_member_id",
        "preferred_language",
        "emergency_contact_name",
        "emergency_contact_phone",
        mode="before",
    )
    @classmethod
    def convert_empty_optional_fields(cls, value):
        return empty_to_none(value)

    # =====================================================
    # Names
    # =====================================================

    @field_validator(
        "first_name",
        "last_name",
    )
    @classmethod
    def check_names(cls, value):

        if value is None:
            return None

        return validate_name(value)

    # =====================================================
    # DOB
    # =====================================================

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, value):

        if value is None:
            return None

        return validate_dob(value)

    # =====================================================
    # Sex
    # =====================================================

    @field_validator("sex")
    @classmethod
    def check_sex(cls, value):

        if value is None:
            return None

        normalized_values = {
            "male": "Male",
            "female": "Female",
            "other": "Other",
            "decline to answer": "Decline to Answer",
        }

        normalized = normalized_values.get(
            value.strip().lower()
        )

        if normalized is None:
            raise ValueError(
                "Sex must be Male, Female, Other, "
                "or Decline to Answer."
            )

        return normalized

    # =====================================================
    # Phone numbers
    # =====================================================

    @field_validator(
        "phone_number",
        "emergency_contact_phone",
    )
    @classmethod
    def check_phone(cls, value):

        if value is None:
            return None

        return normalize_phone(value)

    # =====================================================
    # State
    # =====================================================

    @field_validator("state")
    @classmethod
    def check_state(cls, value):

        if value is None:
            return None

        return validate_state(value)

    # =====================================================
    # ZIP
    # =====================================================

    @field_validator("zip_code")
    @classmethod
    def check_zip(cls, value):

        if value is None:
            return None

        return validate_zip(value)

    # =====================================================
    # City
    # =====================================================

    @field_validator("city")
    @classmethod
    def check_city(cls, value):

        if value is None:
            return None

        value = value.strip()

        if not 1 <= len(value) <= 100:
            raise ValueError(
                "City must contain between 1 and 100 characters."
            )

        return value

    # =====================================================
    # Address
    # =====================================================

    @field_validator("address_line_1")
    @classmethod
    def check_address(cls, value):

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "Street address cannot be empty."
            )

        return value


# =========================================================
# RESPONSE SCHEMA
# =========================================================

class PatientResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    patient_id: str

    first_name: str
    last_name: str

    date_of_birth: date

    sex: str

    phone_number: str

    email: Optional[str]

    address_line_1: str
    address_line_2: Optional[str]

    city: str
    state: str
    zip_code: str

    insurance_provider: Optional[str]
    insurance_member_id: Optional[str]

    preferred_language: Optional[str]

    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]

    created_at: datetime
    updated_at: datetime

    deleted_at: Optional[datetime]