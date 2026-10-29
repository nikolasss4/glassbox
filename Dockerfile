# --- build the UI -------------------------------------------------------------------------
FROM node:24-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- backend + Chromium -------------------------------------------------------------------
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
RUN uv run --no-dev playwright install --with-deps chromium

COPY src ./src
RUN uv sync --locked --no-dev
COPY --from=ui /ui/dist ./frontend/dist

ENV GLASSBOX_FRONTEND_DIST=/app/frontend/dist
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "glassbox", "serve", "--host", "0.0.0.0", "--port", "8000", "--runs-dir", "/data/runs"]
