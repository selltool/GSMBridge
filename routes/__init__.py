from fastapi import FastAPI

from .health import router as health_router
from .root import router as root_router
from .sim import router as sim_router


def register_routes(app: FastAPI) -> None:
    app.include_router(root_router)
    app.include_router(health_router)
    app.include_router(sim_router)
