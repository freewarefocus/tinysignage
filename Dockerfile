FROM python:3.11-slim

# Install curl for healthcheck and ffmpeg for video thumbnails
RUN apt-get update -qq && apt-get install -y -qq curl ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config.yaml .

# media/, db/ and certs/ are mounted as volumes — create empty dirs
RUN mkdir -p media media/thumbs db logs certs

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -kf https://localhost:8080/health || curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "app.server"]
