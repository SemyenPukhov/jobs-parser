from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.db import get_session
from app.analytics import send_daily_analytics
from app.auth import get_current_user
from app.models import User

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)


@router.post("/daily-report")
async def trigger_daily_report(
    db: Session = Depends(get_session),
    # current_user: User = Depends(get_current_user)
):
    """
    Ручной запуск ежедневного отчета.
    Отчет будет отправлен в Slack.
    """
    try:
        await send_daily_analytics()
        return {"status": "success", "message": "Отчет успешно отправлен в Slack"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при отправке отчета: {str(e)}"
        )
