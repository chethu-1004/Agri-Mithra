import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ai", tags=["AI Chatbot"])

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:3b"
)

SYSTEM_PROMPT = """
You are Agri Mitra, a multilingual agriculture assistant.

Your responsibilities:
- Answer agriculture and general knowledge questions.
- Support English, Kannada, Hindi, and other supported languages.
- Explain plant diseases, crop care, watering, soil health, and fertilizers.
- Use simple language suitable for farmers.
- Ask clarifying questions when crop or disease information is insufficient.
- Never invent sensor readings, leaf moisture percentages, or health percentages.
- Treat plant disease predictions as estimates, not confirmed diagnoses.
- Never invent current weather, market prices, government schemes, or sources.
- Provide cautious, practical agricultural advice.
- For fertilizer and pesticide recommendations, account for crop,
  disease, product instructions, and local regulations.
- Explain when current information needs external verification.
"""

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="English", max_length=40)
    context: str | None = Field(default=None, max_length=3000)

@router.get("/health")
async def ai_health():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{OLLAMA_URL}/api/tags"
            )
            response.raise_for_status()
            data = response.json()

        models = [
            model.get("name")
            for model in data.get("models", [])
        ]

        return {
            "status": "connected",
            "provider": "Ollama",
            "configured_model": OLLAMA_MODEL,
            "available_models": models
        }

    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not reachable. Start Ollama first."
        )

@router.post("/chat")
async def chat(request: ChatRequest):
    prompt = f"""
Respond in {request.language}.

User question:
{request.message}
"""

    if request.context:
        prompt += f"""

Additional Agri Mitra context:
{request.context}

Use this context carefully. Do not assume that unverified
predictions or measurements are confirmed facts.
"""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload
            )

            response.raise_for_status()
            result = response.json()

        return {
            "answer": result["message"]["content"],
            "language": request.language,
            "provider": "Ollama",
            "model": OLLAMA_MODEL,
            "sources": []
        }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="The AI took too long to respond. Try again."
        )

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="Ollama returned an error. Check the model and server."
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Check that it is running."
        )