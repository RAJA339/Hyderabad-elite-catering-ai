# This lives at the repository root for two reasons: the build context has to be the root
# (the API reads db/, knowledge/ and eval/ at runtime, so they must be inside the image),
# and platforms like Railway pick up a root Dockerfile automatically, with no build config.
#   docker build .
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
