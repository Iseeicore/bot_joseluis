FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

RUN python -c "from rapidocr import RapidOCR; RapidOCR()"

RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir -p /app/data \
    && chown app:app /app/data

COPY config ./config
COPY migrations ./migrations
COPY src ./src

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["uvicorn", "src.app.main:build_default_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
