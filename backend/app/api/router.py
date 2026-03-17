from fastapi import APIRouter

from app.api.routes import cases, courts, flags, judges, stats

api_router = APIRouter()
api_router.include_router(courts.router, tags=["courts"])
api_router.include_router(cases.router, tags=["cases"])
api_router.include_router(judges.router, tags=["judges"])
api_router.include_router(stats.router, tags=["stats"])
api_router.include_router(flags.router, tags=["flags"])
