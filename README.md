# TalentaPro Video Transcription Worker


**TalentaPro Video Transcription Worker** es el microservicio encargado de procesar y transcribir videos de entrevistas en la plataforma TalentaPro, usando inteligencia artificial de última generación (OpenAI Whisper).

---

## 🎯 ¿Para qué sirve este worker?
- Automatiza la transcripción de respuestas en video de los candidatos.
- Recibe webhooks desde la app principal TalentaPro y procesa en background.
- Actualiza la base de datos PostgreSQL con transcripciones y metadatos.
- Permite a RRHH analizar respuestas de video de forma eficiente y accesible.

---

## 🏗️ Arquitectura y Diseño
- **Python + FastAPI:** API robusta, asíncrona y fácil de mantener.
- **OpenAI Whisper:** Transcripción automática de audio/video con alta precisión.
- **PostgreSQL:** Base de datos robusta para almacenamiento de transcripciones.
- **Procesamiento desacoplado:** El worker es independiente, escalable y puede correr en cualquier infraestructura (Render, Railway, Docker, local).
- **Logging detallado:** Para debugging y monitoreo en producción.

### Diagrama de flujo
```
[App TalentaPro] --(webhook: response_id)--> [Worker]
    |                                      |
    |<-- UPDATE: transcript, status -------|
[PostgreSQL Database] <--- conexión ---> [Worker]
```

---

## 🚀 Características principales
- Webhook endpoint para recibir `response_id`
- Procesa videos almacenados en base64 en la base de datos
- Transcribe con OpenAI Whisper (texto y timestamps)
- Actualiza estado y transcripción en la base de datos PostgreSQL
- Procesamiento asíncrono y seguro
- Logging detallado para debugging

---

## 🛠️ Instalación y Despliegue

### Requisitos
- Python 3.8+
- Base de datos PostgreSQL
- API Key de OpenAI

### Instalación local
```bash
cd worker
pip install -r requirements.txt
```

### Configuración de variables de entorno
Crea un archivo `.env`:
```env
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
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
docker build -t talentapro-worker .
docker run -p 8000:8000 --env-file .env talentapro-worker
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
2. Obtiene datos de la tabla `responses` en PostgreSQL
3. Marca como `processing`
4. Extrae video base64 de los datos almacenados
5. Decodifica y guarda temporalmente el video
6. Transcribe con Whisper
7. Actualiza respuesta con transcripción y timestamps
8. Marca como `completed` o `failed`

---

## 🗄️ Estructura de Datos
El worker actualiza el campo JSONB `data` en la tabla `responses`:
```json
{
  "response": {
    "type": "video",
    "data": "data:video/webm;base64,..."
  },
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
- Las credenciales de PostgreSQL deben mantenerse **privadas** (nunca en frontend)
- Considera agregar autenticación al webhook en producción
- Usa HTTPS en producción
- Manejo robusto de errores y logs

---

## 💰 Costos
- **OpenAI Whisper API:** $0.006 por minuto de audio (ver [precios oficiales](https://openai.com/pricing))
- Ejemplo: Video de 2 minutos = $0.012

---

## 🐛 Troubleshooting
- **No se encontró video base64:** Verifica que el campo `data.response.data` existe en la respuesta
- **Error de transcripción:** Verifica el API Key de OpenAI y que el video tenga audio
- **Worker no procesa:** Revisa los logs y la conexión con PostgreSQL

---

## 👨‍💻 Créditos y Contacto
- **Desarrollo & Integración:** Molu Sáez (github.com/Msaezcardenas)
- **Contacto:** soporte@talentapro.com

---

## 📝 Licencia
MIT
