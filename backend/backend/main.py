from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from agrinetra.species_detection.predictor import (predictor as species_predictor)
from agrinetra.config import settings
from agrinetra.disease_detection.model_loader import predictor
from agrinetra.api import (
    ai_routes,
    auth_routes,
    farm_crop_routes,
    disease_routes,
    weather_notification_routes,
    chat_routes,
    admin_routes,
    species_routes,
    market_routes,
)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Existing disease model
    predictor.load()

    # New species model
    species_predictor.load()

    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Agri Mitra farmer and admin API",
    lifespan=lifespan,
)


class AiRequestSizeLimitMiddleware:
    """Buffer and cap request bodies only for the AI chat endpoint."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http' or scope.get('path') != '/api/ai/chat' or scope.get('method') != 'POST':
            await self.app(scope, receive, send)
            return

        from starlette.responses import JSONResponse

        limit = max(1024, int(settings.ai_max_request_bytes))
        headers = {key.lower(): value for key, value in scope.get('headers', [])}
        try:
            declared_size = int(headers.get(b'content-length', b'0'))
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size > limit:
            response = JSONResponse({'detail': 'AI chat request is too large.'}, status_code=413)
            await response(scope, receive, send)
            return

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > limit:
                response = JSONResponse({'detail': 'AI chat request is too large.'}, status_code=413)
                await response(scope, receive, send)
                return
            more_body = message.get('more_body', False)

        sent_body = False

        async def receive_buffered():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, receive_buffered, send)


app.add_middleware(AiRequestSizeLimitMiddleware)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

origins = []

for value in (
    settings.user_frontend_url,
    settings.admin_frontend_url,
):
    origins.extend(
        x.strip()
        for x in value.split(",")
        if x.strip()
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(origins)),
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


# ---------------------------------------------------------
# API ROUTERS
# ---------------------------------------------------------

for router in (
    ai_routes.router,
    auth_routes.router,
    farm_crop_routes.router,
    disease_routes.router,
    weather_notification_routes.router,
    chat_routes.router,
    admin_routes.router,
    species_routes.router,
    market_routes.router,
):
    app.include_router(router)


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "service": "agrinetra-api",

        "disease_model": (
            "READY"
            if predictor.model is not None
            else "MODEL_NOT_INSTALLED"
        ),

        "species_model": (
            "READY"
            if species_predictor.model is not None
            else "MODEL_NOT_INSTALLED"
        )
    }

# ---------------------------------------------------------
# ROOT
# ---------------------------------------------------------

@app.get("/", tags=["system"])
def root():
    return {
        "status": "success",
        "message": "Agri Mitra API is running",
        "docs": "/docs",
        "health": "/health",
    }
