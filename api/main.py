"""Asool API (Phase 0: health endpoint only)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.settings import settings

app = FastAPI(
    title="Asool API",
    version="0.1.0",
    description=(
        "أصول: بحث وأجوبة موثقة من صفحات الكتب المطبوعة الأصلية. أداة مدعومة بالذكاء الاصطناعي."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "asool-api", "version": app.version}
