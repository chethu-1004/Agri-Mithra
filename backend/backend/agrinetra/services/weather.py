from datetime import datetime, timezone

import httpx
from fastapi import HTTPException


async def find_weather_location(name: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                'https://geocoding-api.open-meteo.com/v1/search',
                params={'name': name, 'count': 1, 'language': 'en', 'format': 'json'},
            )
            response.raise_for_status()
            results = response.json().get('results') or []
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, 'Location search is unavailable.') from exc

    if not results:
        raise HTTPException(404, 'No matching place was found. Try a nearby town or district.')

    result = results[0]
    label = ', '.join(dict.fromkeys(
        part for part in (result.get('name'), result.get('admin1'), result.get('country')) if part
    ))
    return {'name': label or name, 'latitude': result['latitude'], 'longitude': result['longitude']}


async def fetch_weather(latitude: float, longitude: float, history_days: int, forecast_days: int) -> dict:
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m',
        'hourly': 'temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m',
        'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code,sunrise,sunset',
        'timezone': 'auto',
        'past_days': history_days,
        'forecast_days': forecast_days,
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get('https://api.open-meteo.com/v1/forecast', params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, 'Weather provider is unavailable.') from exc

    current_date = str((data.get('current') or {}).get('time') or '')[:10]
    daily = data.get('daily') or {}
    fields = ('temperature_2m_max', 'temperature_2m_min', 'precipitation_probability_max',
              'precipitation_sum', 'weather_code', 'sunrise', 'sunset')
    columns = {name: daily.get(name) or [] for name in fields}
    daily_rows = []
    for index, date in enumerate(daily.get('time') or []):
        row = {'date': date}
        for name in fields:
            target = {
                'temperature_2m_max': 'temperature_max',
                'temperature_2m_min': 'temperature_min',
                'precipitation_probability_max': 'precipitation_probability',
                'precipitation_sum': 'precipitation_sum',
                'weather_code': 'weather_code', 'sunrise': 'sunrise', 'sunset': 'sunset',
            }[name]
            values = columns[name]
            row[target] = values[index] if index < len(values) else None
        daily_rows.append(row)

    data['history'] = [row for row in daily_rows if row['date'] < current_date][-history_days:]
    data['forecast'] = [row for row in daily_rows if row['date'] >= current_date]
    data['updated_at'] = datetime.now(timezone.utc).isoformat()
    return data
