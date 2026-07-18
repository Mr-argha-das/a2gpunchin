from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import (
    auth,
    assets,
    attendance,
    branches,
    companies,
    dashboard,
    departments,
    employees,
    kiosk,
    leaves,
    reports,
    shifts,
    subscriptions,
    web,
)

from app.core.config import settings
from app.core.database import connect_database
from app.middleware.audit import AuditMiddleware
from app.middleware.tenant import TenantMiddleware

from app.services.fast_voice_engine import FastVoiceEngine

voice_engine = FastVoiceEngine(
    data_dir=getattr(settings, "voice_data_dir", "./data/voice"),
    speaker_threshold=getattr(settings, "voice_speaker_threshold", 0.35),
    device=getattr(settings, "voice_device", "cpu"),
)
try:
    voice_engine.initialize()
except Exception as exc:
    voice_engine.last_error = str(exc)

from app.models.face_engine import FaceEngine
from app.routes.attendence import router as face_attendance_router
from app.routes.attendence import set_attendance_service
from app.services.attendence_service import AttendanceService

from app.routes.face_voice import router as face_voice_router
from app.routes.face_voice import set_face_voice_service
from app.services.face_voice_service import FaceVoiceService

face_engine = FaceEngine(
    index_dir=getattr(settings, "face_index_dir", "./data/face_index"),
    threshold=getattr(settings, "similarity_threshold", 0.45),
    gpu_id=getattr(settings, "gpu_id", -1),
    det_size=getattr(settings, "face_det_size", 320),
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_database()

    # Existing face model
    face_engine.initialize()

    # Existing image attendance service
    face_attendance_service = AttendanceService(face_engine)
    set_attendance_service(face_attendance_service)

    # New combined face + voice service
    set_face_voice_service(
        FaceVoiceService(
            face_service=face_attendance_service,
            voice_engine=voice_engine,
        )
    )

    try:
        yield
    finally:
        face_engine.close()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Multi-tenant SaaS GPS attendance management system",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(AuditMiddleware)
    app.add_middleware(TenantMiddleware)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    app.include_router(web.router)
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(assets.router, prefix="/api/assets", tags=["Assets"])
    app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])
    app.include_router(branches.router, prefix="/api/branches", tags=["Branches"])
    app.include_router(departments.router, prefix="/api/departments", tags=["Departments"])
    app.include_router(employees.router, prefix="/api/employees", tags=["Employees"])
    app.include_router(kiosk.router, prefix="/api/kiosk", tags=["Kiosk"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
    app.include_router(leaves.router, prefix="/api/leaves", tags=["Leaves"])
    app.include_router(shifts.router, prefix="/api/shifts", tags=["Shifts"])
    app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
    app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])

    app.include_router(face_attendance_router)
    app.include_router(face_voice_router)

    return app


app = create_app()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": face_engine.is_ready,
        "voice_model_loaded": voice_engine.is_ready,
        "voice_error": voice_engine.last_error,
        "total_indexed_faces": face_engine.total_faces(),
        "similarity_threshold": getattr(settings, "similarity_threshold", 0.45),
    }

@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        detail = getattr(exc, "detail", None)
        if detail and detail != "Not Found":
            return JSONResponse({"detail": detail}, status_code=404)
        return JSONResponse(
            {"detail": "API endpoint not found. Check backend URL and route."},
            status_code=404,
        )

    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(
        "404.html",
        {"request": request},
        status_code=404,
    )
