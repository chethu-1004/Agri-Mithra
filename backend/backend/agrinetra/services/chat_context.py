from datetime import datetime, timedelta, timezone

from agrinetra.database.models import Crop, DiseaseScan, Farm, MarketProduct, WeatherRecord


WEATHER_TERMS = (
    'weather', 'rain', 'forecast', 'irrigat', 'hourly', 'ಮಳೆ', 'ಹವಾಮಾನ', 'ನೀರಾವರಿ',
    'வானிலை', 'மழை', 'பாசனம்', 'వాతావరణం', 'వర్షం', 'నీటిపారుదల',
    'मौसम', 'बारिश', 'सिंचाई',
)
DISEASE_TERMS = (
    'disease', 'pest', 'leaf', 'spot', 'yellow', 'symptom', 'scan', 'diagnos',
    'ರೋಗ', 'ಕೀಟ', 'ಎಲೆ', 'ம நோய்', 'நோய்', 'பூச்சி', 'ఆకు', 'వ్యాధి', 'తెగులు',
    'रोग', 'कीट', 'पत्ता', 'लक्षण',
)
MARKET_TERMS = (
    'market', 'price', 'mandi', 'fertiliz', 'supplier', 'buyer', 'product',
    'ಮಾರುಕಟ್ಟೆ', 'ಬೆಲೆ', 'ಗೊಬ್ಬರ', 'ರಸಗೊಬ್ಬರ', 'சந்தை', 'விலை', 'உரம்',
    'మార్కెట్', 'ధర', 'ఎరువు', 'बाजार', 'मंडी', 'भाव', 'खाद', 'उर्वरक',
)


def _iso(value):
    return value.isoformat() if value else None


def _utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _scan_summary(scan: DiseaseScan, crop_name: str | None = None) -> dict:
    summary = {
        'recorded_at': _iso(scan.created_at),
        'status': scan.status,
        'predicted_disease': scan.predicted_disease,
        'predicted_label': scan.predicted_class or scan.predicted_disease,
        'confidence': scan.confidence,
        'confidence_type': 'uncalibrated_model_score' if scan.status != 'NON_CROP' and scan.confidence is not None else None,
        'model_version': scan.model_version,
        'leaf_health': {
            'score_percent': None,
            'condition': 'assessment_unavailable' if scan.status != 'NON_CROP' else 'not_applicable',
            'assessment_confidence': None,
        },
        'leaf_water_status': {
            'water_content_percent': None,
            'water_content_metric': None,
            'measurement_source': 'unavailable',
            'moisture_assessment': 'uncertain' if scan.status != 'NON_CROP' else 'not_applicable',
            'visual_water_stress': 'not_assessed' if scan.status != 'NON_CROP' else 'not_applicable',
            'confidence_percent': None,
            'explanation': 'No water-status measurement or validated visual assessment is stored for this scan; do not infer moisture from its image.',
            'next_steps': [
                'Check soil moisture directly or use a calibrated soil sensor.',
                'Consider crop stage, recent irrigation and rainfall, and other possible causes of wilting before changing irrigation.',
            ] if scan.status != 'NON_CROP' else [],
            'soil_moisture': {
                'value': None,
                'unit': None,
                'status': 'not_measured' if scan.status != 'NON_CROP' else 'not_applicable',
                'source': 'unavailable',
            },
        },
        'fertilizer_recommendation': {
            'evidence_quality': 'insufficient' if scan.status != 'NON_CROP' else 'not_applicable',
            'confidence_percent': None,
            'application_rate': None,
            'application_unit': None,
            'concentration_percent': None,
        },
    }
    if crop_name:
        summary['crop_name'] = crop_name
    return summary


def _owner_scan_summary(db, user, scan: DiseaseScan) -> dict:
    crop_name = None
    if scan.crop_id:
        crop = db.query(Crop).filter(Crop.id == scan.crop_id, Crop.user_id == user.id).first()
        crop_name = crop.crop_name if crop else None
    return _scan_summary(scan, crop_name)


def build_farmer_context(db, user, message: str, scan_id: str | None = None) -> dict:
    """Build small, owner-scoped, non-identifying context for a single model request."""
    context: dict = {}
    farms = db.query(Farm).filter(Farm.user_id == user.id).order_by(Farm.created_at.desc()).limit(5).all()
    farm_ids = [farm.id for farm in farms]
    if farms:
        context['farms'] = [
            {'location': farm.location, 'area_acres': farm.area}
            for farm in farms
        ]
    crop_query = db.query(Crop).filter(Crop.user_id == user.id)
    if farm_ids:
        crop_query = crop_query.filter(Crop.farm_id.in_(farm_ids))
    crops = crop_query.order_by(Crop.created_at.desc()).limit(12).all()
    if crops:
        context['crops'] = [
            {
                'crop': crop.crop_name,
                'variety': crop.variety,
                'sowing_date': _iso(crop.sowing_date),
                'expected_harvest_date': _iso(crop.expected_harvest_date),
            }
            for crop in crops
        ]

    if scan_id:
        scan = db.query(DiseaseScan).filter(
            DiseaseScan.id == scan_id,
            DiseaseScan.user_id == user.id,
        ).first()
        if not scan:
            raise LookupError('Scan not found.')
        context['requested_image_analysis'] = _owner_scan_summary(db, user, scan)
    elif any(term in message.casefold() for term in DISEASE_TERMS):
        scan = db.query(DiseaseScan).filter(DiseaseScan.user_id == user.id).order_by(
            DiseaseScan.created_at.desc()
        ).first()
        if scan:
            context['latest_historical_image_analysis'] = _owner_scan_summary(db, user, scan)

    message_folded = message.casefold()
    if any(term in message_folded for term in WEATHER_TERMS):
        record = db.query(WeatherRecord).filter(WeatherRecord.user_id == user.id).order_by(
            WeatherRecord.created_at.desc()
        ).first()
        now = datetime.now(timezone.utc)
        is_fresh = bool(record and _utc(record.created_at) and now - _utc(record.created_at) <= timedelta(hours=24))
        if is_fresh:
            payload = record.payload if isinstance(record.payload, dict) else {}
            weather = {
                'recorded_at': _iso(record.created_at),
                'fresh_for_chat': True,
                'current': payload.get('current') or {},
                'past_7_days': (payload.get('history') or [])[-7:],
                'next_7_days': (payload.get('forecast') or [])[:8],
            }
            if 'hour' in message_folded or 'ಗಂಟೆ' in message or 'மணி' in message or 'గంట' in message or 'घंटे' in message:
                hourly = payload.get('hourly') or {}
                times = hourly.get('time') or []
                fields = (
                    'temperature_2m', 'relative_humidity_2m', 'precipitation_probability',
                    'precipitation', 'weather_code', 'wind_speed_10m',
                )
                current_time = str((payload.get('current') or {}).get('time') or '')
                start = next((i for i, hour in enumerate(times) if str(hour) >= current_time), 0) if times else 0
                weather['next_hours'] = [
                    {'time': times[i], **{field: (hourly.get(field) or [])[i] if i < len(hourly.get(field) or []) else None for field in fields}}
                    for i in range(start, min(start + 24, len(times)))
                ]
            context['weather_snapshot'] = weather
        else:
            context['weather_snapshot'] = {
                'fresh_for_chat': False,
                'message': 'No weather snapshot recorded for this account in the last 24 hours.',
            }

    if any(term in message_folded for term in MARKET_TERMS):
        products = db.query(MarketProduct).filter(MarketProduct.is_active.is_(True)).order_by(
            MarketProduct.created_at.desc()
        ).limit(8).all()
        context['marketplace_products'] = {
            'note': 'These are published Agri Mitra marketplace products and listed prices, not live mandi prices.',
            'items': [
                {'name': product.name, 'category': product.category, 'brand': product.brand, 'price_inr': product.price}
                for product in products
            ],
        }
    return context
