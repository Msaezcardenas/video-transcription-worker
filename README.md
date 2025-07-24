# Talium Video Transcription Worker

<p align="center">
  <img src="/public/next.svg" alt="Talium Worker Logo" width="120" />
</p>

**Talium Video Transcription Worker** es el microservicio encargado de procesar y transcribir videos de entrevistas en la plataforma Talium, usando inteligencia artificial de última generación (OpenAI Whisper).

---

## 🎯 ¿Para qué sirve este worker?
- Automatiza la transcripción de respuestas en video de los candidatos.
- Recibe webhooks desde la app principal Talium y procesa en background.
- Actualiza la base de datos de Supabase con transcripciones y metadatos.
- Permite a RRHH analizar respuestas de video de forma eficiente y accesible.

---

## 🏗️ Arquitectura y Diseño
- **Python + FastAPI:** API robusta, asíncrona y fácil de mantener.
- **OpenAI Whisper:** Transcripción automática de audio/video con alta precisión.
- **Supabase:** Fuente de datos y almacenamiento seguro de videos.
- **Procesamiento desacoplado:** El worker es independiente, escalable y puede correr en cualquier infraestructura (Render, Railway, Docker, local).
- **Logging detallado:** Para debugging y monitoreo en producción.

### Diagrama de flujo
```
[App Talium] --(webhook: response_id)--> [Worker]
    |                                 |
    |<-- PATCH: transcript, status ---|
[Supabase Storage] <--- descarga ---> [Worker]
```

---

## 🚀 Características principales
- Webhook endpoint para recibir `response_id`
- Descarga videos desde Supabase Storage
- Transcribe con OpenAI Whisper (texto y timestamps)
- Actualiza estado y transcripción en la base de datos
- Procesamiento asíncrono y seguro
- Logging detallado para debugging

---

## 🛠️ Instalación y Despliegue

### Requisitos
- Python 3.8+
- Cuenta de Supabase con Service Key
- API Key de OpenAI

### Instalación local
```bash
cd worker
pip install -r requirements.txt
```

### Configuración de variables de entorno
Crea un archivo `.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
OPENAI_API_KEY=sk-your-openai-api-key
```

### Ejecución
```bash
# Desarrollo
python main.py
# O con uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Despliegue en producción
- **Render:** Deploy directo con Dockerfile incluido
- **Railway:** Compatible con railway up
- **Heroku:** Soportado (ver ejemplo en este README)
- **Docker:**
```bash
docker build -t talium-worker .
docker run -p 8000:8000 --env-file .env talium-worker
```

---

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

---

## 🔄 Flujo de Procesamiento
1. Recibe webhook con `response_id`
2. Obtiene datos de la tabla `responses` en Supabase
3. Marca como `processing`
4. Descarga video desde `video_url`
5. Transcribe con Whisper
6. Actualiza respuesta con transcripción y timestamps
7. Marca como `completed` o `failed`

---

## 🗄️ Estructura de Datos
El worker actualiza el campo JSONB `data` en la tabla `responses`:
```json
{
  "video_url": "url-existente",
  "transcript": "Texto completo de la transcripción",
  "timestamped_transcript": [
    { "start": 0.0, "end": 3.5, "text": "Segmento de texto" }
  ],
  "transcription_method": "openai_whisper",
  "transcribed_at": "2024-01-15T10:30:00Z"
}
```

---

## 🧪 Testing y Debug
- **Verificar salud:**
  ```bash
  curl http://localhost:8000/health
  ```
- **Enviar webhook de prueba:**
  ```bash
  curl -X POST http://localhost:8000/webhook \
    -H "Content-Type: application/json" \
    -d '{"response_id": "tu-response-id-aqui"}'
  ```
- **Ver logs:**
  Los logs muestran el progreso y errores detallados.

---

## 🔐 Seguridad y Buenas Prácticas
- El Service Key de Supabase debe mantenerse **privado** (nunca en frontend)
- Considera agregar autenticación al webhook en producción
- Usa HTTPS en producción
- Manejo robusto de errores y logs

---

## 💰 Costos
- **OpenAI Whisper API:** $0.006 por minuto de audio (ver [precios oficiales](https://openai.com/pricing))
- Ejemplo: Video de 2 minutos = $0.012

---

## 🐛 Troubleshooting
- **No se encontró video_url:** Verifica que el campo `data.video_url` existe en la respuesta
- **Error de transcripción:** Verifica el API Key de OpenAI y que el video tenga audio
- **Worker no procesa:** Revisa los logs y la conexión con Supabase

---

## 👨‍💻 Créditos y Contacto
- **Desarrollo & Integración:** Molu Sáez (github.com/Msaezcardenas)
- **Contacto:** soporte@talium.com

---

## 📝 Licencia
MIT 
- Verifica conexión con Supabase 