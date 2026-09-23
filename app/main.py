from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.http import health
from app.adapters.inbound.http import routes as weather_routes
from app.adapters.inbound.http.errors import register_error_handlers
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

# Both mounted at the root: /health stays stable for uptime checks, and the
# weather paths match the ones the service specifies.
app.include_router(health.router)
app.include_router(weather_routes.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API", "docs": "/docs"}
