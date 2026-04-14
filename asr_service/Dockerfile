FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV ASR_MODEL=iic/SenseVoiceSmall
ENV ASR_DEVICE=cuda

RUN apt-get update -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    git \
    python3 \
    python3-pip && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY main.py ./main.py

RUN chown -R app:app /app /home/app

USER app

EXPOSE 8900

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8900"]
