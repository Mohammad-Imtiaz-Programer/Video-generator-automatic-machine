# Halal Cartoon Factory — container image for Hugging Face Spaces (Docker SDK)
# or any other Docker host (Render, Fly.io, Cloud Run, your own VPS, etc.)

FROM python:3.11-slim

# System packages needed by opencv-python, moviepy/ffmpeg, and Pillow's
# font rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face Spaces (Docker SDK) routes traffic to this port by default —
# see the "app_port: 7860" line in the README.md frontmatter below.
ENV PORT=7860
EXPOSE 7860

# Spaces containers run as a non-root user, so pre-create and open up the
# folders the app writes to at runtime.
RUN mkdir -p assets output models config && chmod -R 777 assets output models config

# `python -m waitress` (rather than the bare `waitress-serve` script)
# guarantees the current directory is on sys.path, so `backend_server.server`
# resolves correctly. Single process by default — see the note in
# backend_server/server.py about why this app must not run with multiple
# worker processes (its job-progress tracking is in-memory).
CMD ["python", "-m", "waitress", "--host=0.0.0.0", "--port=7860", "backend_server.server:app"]
