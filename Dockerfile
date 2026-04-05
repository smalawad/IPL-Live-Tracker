# -------------- Stage 1: Builder --------------
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# -------------- Stage 2: Runtime --------------
FROM python:3.11-slim

LABEL maintainer="your-name" \
      version="1.0" \
      description="IPL Live Score - Flask + Redis"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/install/lib/python3.11/site-packages \
    PATH=/install/bin:$PATH

COPY --from=builder /install /install

COPY . .

RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--workers", "5", "--timeout", "120", "--bind", "0.0.0.0:5000", "main:app"]
