from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from fastapi.staticfiles import StaticFiles
from .routes.dashboard import router as dashboard_router
from .database import Base, engine
from . import models
from .exceptions import AppException
from .routes.patients import router as patients_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Voice AI Patient Registration API",
    description="REST API for the Voice AI Patient Registration System",
    version="1.0.0",
)

app.include_router(dashboard_router)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)
# ----------------------------
# Exception handlers
# ----------------------------

@app.exception_handler(AppException)
async def app_exception_handler(
    request: Request,
    exc: AppException
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "error": {
                "message": exc.message
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    errors = []

    for error in exc.errors():
        field = ".".join(
            str(item)
            for item in error["loc"]
            if item != "body"
        )

        errors.append({
            "field": field,
            "message": error["msg"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "data": None,
            "error": {
                "message": "Validation failed.",
                "details": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception
):
    print(f"Unexpected error: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "error": {
                "message": "An internal server error occurred."
            }
        },
    )


# ----------------------------
# Routes
# ----------------------------

app.include_router(patients_router)


@app.get("/")
def root():
    return {
        "data": {
            "message": "Patient Registration API is running"
        },
        "error": None,
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "data": {
                "status": "healthy",
                "database": "connected",
            },
            "error": None,
        }

    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {
                    "message": "Database connection failed."
                }
            },
        )