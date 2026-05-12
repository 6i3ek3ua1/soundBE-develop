FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UI_PORT=8000 \
    EEL_HOST=0.0.0.0 \
    EEL_MODE=none \
    PRELOAD_MODELS=1 \
    TRANSLATION_ENABLED=0 \
    TRANSLATION_MODEL=Qwen/Qwen2.5-1.5B-Instruct \
    TARGET_LANGUAGE=English \
    TTS_ENABLED=0 \
    XDG_CACHE_HOME=/app/.cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        espeak-ng \
        ffmpeg \
        git \
        libasound2 \
        libportaudio2 \
        libsndfile1 \
        portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt .

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install -r requirements-docker.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py", "--ui-port", "8000"]
