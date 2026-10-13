FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# modello di segmentazione dei personaggi cartoon (isnet-anime), scaricato in fase di build
ENV U2NET_HOME=/srv/models
RUN mkdir -p /srv/models && curl -fsSL -o /srv/models/isnet-anime.onnx \
    https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
COPY app ./app
ENV DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
