from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings

FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "frontend"
    return f"{tag}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Serve the Vite bundle from the same origin as the API.  ``app.frontend``
# is convenient, but its generated route is not reliably registered when the
# application is started through the development CLI.  Explicit routes keep
# the API routing and the SPA fallback behavior deterministic.
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_DIR / "assets"),
    name="frontend-assets",
)


@app.get("/{path:path}", include_in_schema=False)
def serve_frontend(path: str) -> FileResponse:
    """Return static frontend files and fall back to the SPA entry point."""
    api_prefix = settings.API_V1_STR.strip("/")
    if path == api_prefix or path.startswith(f"{api_prefix}/"):
        raise HTTPException(status_code=404, detail="Not Found")

    frontend_root = FRONTEND_DIR.resolve()
    requested = (frontend_root / path).resolve()

    # Do not allow a URL path to escape the frontend bundle directory.
    if frontend_root not in requested.parents and requested != frontend_root:
        return FileResponse(frontend_root / "index.html")

    if path and requested.is_file():
        return FileResponse(requested)
    return FileResponse(frontend_root / "index.html")
