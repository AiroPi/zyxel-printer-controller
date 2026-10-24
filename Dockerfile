FROM ghcr.io/astral-sh/uv:alpine
WORKDIR /app
RUN --mount=type=bind,source=./pyproject.toml,target=./pyproject.toml \
    --mount=type=bind,source=./uv.lock,target=./uv.lock \
  uv sync --locked --no-dev
COPY ./server.py ./
CMD ["uv", "run", "server.py"]
