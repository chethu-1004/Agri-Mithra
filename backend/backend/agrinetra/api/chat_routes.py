from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from agrinetra.api.schemas import ChatIn, ChatScanIn
from agrinetra.auth.dependencies import get_current_user
from agrinetra.config import settings
from agrinetra.database.connection import get_db
from agrinetra.database.models import ChatMessage, ChatSession, DiseaseScan, User
from agrinetra.services.chat_context import build_farmer_context
from agrinetra.services.chat_rate_limit import check_chat_rate_limit
from agrinetra.services.chatbot import (
    ChatbotConfigurationError,
    ChatbotProviderError,
    ChatbotRateLimitError,
    ChatbotTimeoutError,
    chatbot_is_configured,
    get_chatbot,
)
from agrinetra.services.knowledge_base import retrieve_evidence

router = APIRouter(prefix='/api/chat', tags=['farmer assistance'])


@router.get('/status')
def chatbot_status(user: User = Depends(get_current_user)):
    del user
    return {
        'provider': settings.chatbot_provider,
        'model_configured': bool(settings.openai_model or settings.chatbot_model),
        'llm_enabled': chatbot_is_configured(),
        'rag_enabled': bool(settings.agri_rag_enabled),
    }


@router.post('')
async def send_message(
    payload: ChatIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = None
    if payload.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.session_id,
            ChatSession.user_id == user.id,
        ).first()
        if not session:
            raise HTTPException(404, 'Chat session not found.')
    else:
        session = ChatSession(user_id=user.id, title=payload.message[:80])
        db.add(session)
        db.flush()

    retry_after = check_chat_rate_limit(user.id, settings.chatbot_requests_per_minute)
    if retry_after:
        raise HTTPException(
            429,
            'You have sent several questions recently. Please wait briefly and try again.',
            headers={'Retry-After': str(retry_after)},
        )

    try:
        context = build_farmer_context(db, user, payload.message, payload.scan_id)
    except LookupError:
        raise HTTPException(404, 'Scan not found.') from None
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id, ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(max(1, min(settings.chatbot_history_messages, 24)))
        .all()
    )
    history_rows.reverse()
    history = [
        {
            'role': 'user' if row.role == 'USER' else 'assistant',
            'content': row.content,
        }
        for row in history_rows
        if row.role in {'USER', 'ASSISTANT'}
    ]
    evidence = await retrieve_evidence(payload.message)

    try:
        reply = await get_chatbot().reply(
            payload.message,
            payload.language,
            history=history,
            farmer_context=context,
            evidence=evidence,
        )
    except ChatbotConfigurationError as exc:
        raise HTTPException(503, str(exc)) from None
    except ChatbotRateLimitError as exc:
        raise HTTPException(429, str(exc), headers={'Retry-After': '10'}) from None
    except ChatbotTimeoutError as exc:
        raise HTTPException(504, str(exc)) from None
    except ChatbotProviderError as exc:
        raise HTTPException(502, str(exc)) from None

    message_time = datetime.now(timezone.utc)
    db.add_all([
        ChatMessage(
            session_id=session.id,
            user_id=user.id,
            role='USER',
            content=payload.message,
            created_at=message_time,
        ),
        ChatMessage(
            session_id=session.id,
            user_id=user.id,
            role='ASSISTANT',
            content=reply,
            created_at=message_time + timedelta(microseconds=1),
        ),
    ])
    db.commit()
    return {
        'success': True,
        'session_id': session.id,
        'reply': reply,
        'language': payload.language,
        'sources': list(dict.fromkeys(str(item.get('source', 'Agricultural reference')) for item in evidence)),
    }


@router.post('/scan-result')
def record_scan_result(
    payload: ChatScanIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan = db.query(DiseaseScan).filter(
        DiseaseScan.id == payload.scan_id,
        DiseaseScan.user_id == user.id,
    ).first()
    if not scan:
        raise HTTPException(404, 'Scan not found.')

    session = None
    if payload.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.session_id,
            ChatSession.user_id == user.id,
        ).first()
        if not session:
            raise HTTPException(404, 'Chat session not found.')

    retry_after = check_chat_rate_limit(user.id, settings.chatbot_requests_per_minute)
    if retry_after:
        raise HTTPException(
            429,
            'You have saved several chat items recently. Please wait briefly and try again.',
            headers={'Retry-After': str(retry_after)},
        )

    if scan.status == 'NON_CROP' or (scan.predicted_class or '').casefold() == 'human detected':
        reply = 'Human detected. This image is not a crop leaf photo.'
    elif scan.status == 'UNCERTAIN' or scan.confidence < settings.prediction_threshold:
        reply = 'Image analysis is uncertain. I could not confidently identify this image as a crop result. Try a clear, close photo of one leaf in natural light.'
    else:
        label = scan.predicted_disease or scan.predicted_class or 'No label returned'
        reply = (
            f'Image analysis result: {label}. Model score: {scan.confidence:.0%} (not a calibrated probability). '
            'No validated leaf-health percentage or evidence-supported fertilizer rate is available from this scan. '
            'Confirm symptoms and check crop stage and soil before choosing an input.'
        )

    if session is None:
        session = ChatSession(user_id=user.id, title='Crop image analysis')
        db.add(session)
        db.flush()
    message_time = datetime.now(timezone.utc)
    db.add(ChatMessage(
        session_id=session.id,
        user_id=user.id,
        role='ASSISTANT',
        content=reply,
        created_at=message_time,
    ))
    db.commit()
    return {'success': True, 'session_id': session.id, 'scan_id': scan.id, 'reply': reply}


@router.get('/history')
def chat_history(
    session_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=30),
    message_limit: int = Query(default=30, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ChatSession).filter(ChatSession.user_id == user.id)
    if session_id:
        query = query.filter(ChatSession.id == session_id)
    sessions = query.order_by(ChatSession.created_at.desc()).limit(limit).all()
    response = []
    for item in sessions:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == item.id, ChatMessage.user_id == user.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(message_limit)
            .all()
        )
        messages.reverse()
        response.append({
            'id': item.id,
            'title': item.title,
            'created_at': item.created_at,
            'messages': [
                {'role': row.role, 'content': row.content, 'created_at': row.created_at}
                for row in messages
            ],
        })
    return response
