# Build context is the REPOSITORY ROOT, not apps/api: the API reads db/, knowledge/ and
# eval/ from the repo root at runtime, so they have to be inside the image.
#   docker build -f apps/api/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so edits to application code reuse the cached layer.
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/app apps/api/app
# Editable keeps the source tree in place, which is what lets app/core/config.py resolve
# /app/knowledge and /app/eval relative to its own file.
RUN pip install -e ./apps/api

COPY db ./db
COPY knowledge ./knowledge
COPY eval ./eval

WORKDIR /app/apps/api

# Railway, Render and Fly inject $PORT; default to 8000 for a plain `docker run`.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
