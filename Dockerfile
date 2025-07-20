FROM python:3.9-slim

# Instalar ffmpeg (necesario para algunos formatos de video)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements primero para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Puerto por defecto
ENV PORT=8000

# Comando para ejecutar el servidor
CMD uvicorn main:app --host 0.0.0.0 --port $PORT 