# Docker Run Guide

This project can run in Docker with the web UI exposed on port 8000.

## Build and Start

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Stop:

```bash
docker compose down
```

## Default Container Profile

The default image is a CPU-friendly web profile:

- Eel serves the UI on `0.0.0.0:8000`.
- Whisper runs on CPU.
- Translation is disabled by default: `TRANSLATION_ENABLED=0`.
- If translation is enabled, `PRELOAD_MODELS=1` downloads/loads the translation
  model before capture can start.
- TTS is disabled by default: `TTS_ENABLED=0`.
- Model/cache files are stored in the `soundbe-cache` Docker volume.

You can override settings when starting Compose:

```bash
WHISPER_MODEL=tiny TRANSLATION_ENABLED=0 docker compose up --build
```

Enable translation and preload the model before capture:

```bash
TRANSLATION_ENABLED=1 PRELOAD_MODELS=1 docker compose up --build
```

On Windows PowerShell:

```powershell
$env:WHISPER_MODEL="tiny"
$env:TRANSLATION_ENABLED="1"
$env:PRELOAD_MODELS="1"
docker compose up --build
```

## Audio Devices

Microphone passthrough depends on the host OS and Docker runtime. The default
Compose file starts the UI reliably, but Docker Desktop on Windows does not
provide simple direct microphone passthrough to Linux containers.

For full real-time audio capture on Windows, run the app locally or use WSL/Linux
with an audio setup that exposes input devices to the container. On Linux, a
custom Compose override can mount `/dev/snd` and configure PulseAudio/PipeWire.

## vLLM and GPU

The default Docker image does not install vLLM because it has strict CUDA, torch,
and GPU runtime requirements. To use vLLM, build a separate GPU image based on an
NVIDIA CUDA runtime, install a compatible vLLM/torch pair, and set:

```text
USE_VLLM=true
TRANSLATION_ENABLED=1
```
