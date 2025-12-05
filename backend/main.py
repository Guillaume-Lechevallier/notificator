import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from .database import init_database
from .models import HealthCheck
from .routers import businesses, notifications, qrcodes, settings

init_database()

app = FastAPI(title="Notificator", version="0.1.0")

security = HTTPBasic()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")


def _is_admin_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return normalized in {"/admin.html", "/admin"}


def _check_admin_credentials(credentials: HTTPBasicCredentials) -> None:
    if not (ADMIN_USERNAME and ADMIN_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Les identifiants administrateur ne sont pas configurés.",
        )

    is_valid = secrets.compare_digest(credentials.username, ADMIN_USERNAME) and secrets.compare_digest(
        credentials.password, ADMIN_PASSWORD
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise pour accéder à l'administration.",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.middleware("http")
async def protect_admin_page(request: Request, call_next):
    if _is_admin_path(request.url.path):
        try:
            credentials = await security(request)
            _check_admin_credentials(credentials)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers={**exc.headers} if exc.headers else None,
            )

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications.router)
app.include_router(businesses.router)
app.include_router(qrcodes.router)
app.include_router(settings.router)

frontend_path = Path(__file__).resolve().parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
