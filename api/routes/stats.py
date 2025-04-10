from fastapi import APIRouter, Depends
from api.deps import get_admin_user, get_current_active_user
from db.models import User
from services.stats_service import (
    get_admin_dashboard_stats,
    get_user_stats,
    get_revenue_history
)

router = APIRouter()

@router.get("/admin-dashboard")
async def get_admin_stats(
    current_user: User = Depends(get_admin_user)
):
    stats = await get_admin_dashboard_stats()
    return stats

@router.get("/revenue-history")
async def get_revenue_data(
    days: int = 30,
    current_user: User = Depends(get_admin_user)
):
    history = await get_revenue_history(days)
    return history

@router.get("/user-stats")
async def get_user_statistics(
    current_user: User = Depends(get_current_active_user)
):
    stats = await get_user_stats(str(current_user.id))
    return stats
