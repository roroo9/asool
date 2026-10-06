# Asool API (FastAPI): an always-on container. Built from the public GitHub repository, so it
# never contains the book PDF or page images (the website serves the page images).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api ./api
COPY pipeline ./pipeline
COPY eval ./eval
COPY scripts ./scripts
COPY data ./data

# Reference data not redistributed in the repo: King Fahd Complex Hafs v3.0 and «التفسير الميسر»
# (QuranEnc), then the Mushaf verse-search vectors from the project's GitHub release.
RUN ./scripts/fetch_references.sh \
    && curl -fsSL -o data/index/quran16.npy https://github.com/roroo9/asool/releases/download/data-v1/quran16.npy \
    && curl -fsSL -o data/index/quran_ids.json https://github.com/roroo9/asool/releases/download/data-v1/quran_ids.json

ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS http://localhost:${PORT}/health || exit 1
CMD ["sh", "-c", "uv run --no-dev uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
