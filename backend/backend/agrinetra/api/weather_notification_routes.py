from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agrinetra.auth.dependencies import get_current_user
from agrinetra.config import settings
from agrinetra.database.connection import get_db
from agrinetra.database.models import Notification, User, WeatherRecord
from agrinetra.services.weather import fetch_weather, find_weather_location

router = APIRouter(prefix='/api', tags=['weather and notifications'])


@router.get('/weather/location')
async def weather_location(
    name: str = Query(min_length=2, max_length=120),
    user: User = Depends(get_current_user),
):
    """Resolve a farm town or village to coordinates using Open-Meteo geocoding."""
    del user
    return await find_weather_location(name)


@router.get('/weather')
async def weather(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    history_days: int = Query(default=7, ge=1, le=14),
    forecast_days: int = Query(default=8, ge=1, le=16),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if settings.weather_provider != 'open-meteo':
        raise HTTPException(503, 'Configured weather provider is not implemented.')

    data = await fetch_weather(latitude, longitude, history_days, forecast_days)

    db.add(WeatherRecord(user_id=user.id, latitude=latitude, longitude=longitude, payload=data))
    db.commit()
    return data


@router.get('/notifications')
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user), limit: int = 50):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [
        {'id': n.id, 'title': n.title, 'message': n.message, 'is_read': n.is_read, 'created_at': n.created_at}
        for n in rows
    ]


@router.put('/notifications/{notification_id}/read')
def mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if not item:
        raise HTTPException(404, 'Notification not found.')
    item.is_read = True
    db.commit()
    return {'status': 'success'}
