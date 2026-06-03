FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install uv && uv pip install --system -r pyproject.toml

RUN mkdir -p data/checkpoints/labels data/checkpoints/embeddings

COPY . .
