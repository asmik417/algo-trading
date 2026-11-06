"""Aggregates every v1 resource router into one APIRouter mounted at /api/v1.
Add each new resource router here and nowhere else; anything not in PUBLIC requires a login session.
"""
from fastapi import APIRouter, Depends

from app.api.v1 import (auth, backtests, health, jobs, market, pick_lists, positions, profiles, reviews, runs,
                        stocks, suggestions)
from app.api.v1.deps import require_session

api_router = APIRouter()

# Public: health checks and the login endpoints themselves (/auth/me does its own check).
for public in (health.router, auth.router):
    api_router.include_router(public)

# Everything else: 401 {"detail": "Not authenticated"} without a valid session cookie.
for protected in (profiles.router, runs.router, suggestions.router, stocks.router, positions.router,
                  reviews.router, jobs.router, pick_lists.router, backtests.router, market.router):
    api_router.include_router(protected, dependencies=[Depends(require_session)])
