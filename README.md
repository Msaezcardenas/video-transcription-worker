# Video Transcription Worker

Worker en Python con FastAPI que recibe webhooks y procesa videos usando OpenAI Whisper API.

## 🚀 Características

- **Webhook endpoint** para recibir `response_id`
- **Descarga videos** desde Supabase Storage
- **Transcribe con OpenAI Whisper** (incluye timestamps)
- **Actualiza estado** en la base de datos
- **Procesamiento asíncrono** en background
- **Logging detallado** para debugging

## 📋 Requisitos

- Python 3.8+
- Cuenta de Supabase con Service Key
- API Key de OpenAI

## 🔧 Instalación

### 1. Instalar dependencias

```bash
cd worker
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Crea un archivo `.env`:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
```

### 3. Ejecutar el worker

```bash
# Desarrollo
python main.py

# O con uvicorn directamente
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 Uso del Webhook

### Endpoint principal

```
POST http://localhost:8000/webhook
```

### Payload

```json
{
  "response_id": "uuid-de-la-respuesta"
}
```

### Respuesta

```json
{
  "status": "accepted",
  "response_id": "uuid-de-la-respuesta",
  "message": "Video queued for processing"
}
```

## 🔄 Flujo de Procesamiento

1. **Recibe webhook** con `response_id`
2. **Obtiene datos** de la tabla `responses`
3. **Marca como `processing`**
4. **Descarga video** desde `video_url`
5. **Transcribe con Whisper**
6. **Actualiza respuesta** con transcripción
7. **Marca como `completed`** o `failed`

## 🗄️ Estructura de Datos

El worker actualiza el campo JSONB `data` con:

```json
{
  "video_url": "url-existente",
  "transcript": "Texto completo de la transcripción",
  "timestamped_transcript": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Segmento de texto"
    }
  ],
  "transcription_method": "openai_whisper",
  "transcribed_at": "2024-01-15T10:30:00Z"
}
```

## 🧪 Testing

### Verificar salud del servicio

```bash
curl http://localhost:8000/health
```

### Enviar webhook de prueba

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"response_id": "tu-response-id-aqui"}'
```

### Ver logs

Los logs mostrarán el progreso:

```
2024-01-15 10:30:00 - INFO - Webhook recibido para response_id: xxx
2024-01-15 10:30:01 - INFO - Iniciando procesamiento para response_id: xxx
2024-01-15 10:30:02 - INFO - Descargando video desde: https://...
2024-01-15 10:30:05 - INFO - Transcribiendo video: /tmp/xxx.webm
2024-01-15 10:30:15 - INFO - ✅ Procesamiento completado para response_id: xxx
```

## 🚀 Deploy

### Opción 1: Railway

```bash
railway login
railway link
railway up
```

### Opción 2: Render

1. Crear `Dockerfile`:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Deploy en Render como Web Service

### Opción 3: Heroku

```bash
heroku create tu-worker-app
heroku config:set SUPABASE_URL=xxx
heroku config:set SUPABASE_SERVICE_KEY=xxx
heroku config:set OPENAI_API_KEY=xxx
git push heroku main
```

## 🔐 Seguridad

- El Service Key de Supabase debe mantenerse **privado**
- Considera agregar autenticación al webhook
- Usa HTTPS en producción

## 💰 Costos

- **OpenAI Whisper API**: $0.006 por minuto de audio
- Ejemplo: Video de 2 minutos = $0.012

## 🐛 Troubleshooting

### Error: "No se encontró video_url"
- Verifica que el campo `data.video_url` existe en la respuesta

### Error de transcripción
- Verifica que el API Key de OpenAI es válido
- Confirma que el video tiene audio

### Worker no procesa
- Revisa los logs para errores
- Verifica conexión con Supabase 