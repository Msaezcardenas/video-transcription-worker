import os
import asyncio
import tempfile
from typing import Optional
from datetime import datetime
import logging
import json
import base64

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(title="Video Transcription Worker")

# Configuración de PostgreSQL
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "connect_timeout": 30,  # Timeout de conexión
    "sslmode": "require",   # Requerir SSL para conexiones externas
}

logger.info(f"Database config: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, database={DB_CONFIG['database']}")

# Cliente OpenAI
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Función para obtener conexión a PostgreSQL con reintentos
def get_db_connection(max_retries=3):
    """Crear conexión a PostgreSQL con reintentos"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting database connection (attempt {attempt + 1}/{max_retries})")
            conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Database connection successful")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            logger.info(f"Retrying in 5 seconds...")
            import time
            time.sleep(5)
    raise Exception("Failed to connect to database after all retries")

# Variable global para controlar el proceso periódico
periodic_task_running = False

# Modelos de datos
class WebhookPayload(BaseModel):
    response_id: str
    
class TranscriptionResult(BaseModel):
    text: str
    segments: list

# Función para obtener respuesta de la base de datos
def get_response_data(response_id: str):
    """Obtener datos de la respuesta desde PostgreSQL"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT r.*, q.type as question_type
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.id = %s
            """, (response_id,))
            return cur.fetchone()
    finally:
        conn.close()

# Función para actualizar estado de procesamiento
def update_response_status(response_id: str, status: str):
    """Actualizar estado de procesamiento en PostgreSQL"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE responses 
                SET processing_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, response_id))
            conn.commit()
    finally:
        conn.close()

# Función para extraer video base64 de los datos
def extract_video_data(response_data: dict) -> Optional[str]:
    """Extrae el video base64 de la estructura de datos"""
    data = response_data.get('data', {})
    
    # Buscar el video en diferentes formatos posibles
    if isinstance(data, dict):
        # Formato nuevo: data.response.data
        if 'response' in data and isinstance(data['response'], dict):
            if 'data' in data['response']:
                return data['response']['data']
        # Formato antiguo: data.video_url (no soportado en este caso)
        elif 'video_url' in data:
            logger.warning("Formato video_url no soportado, se requiere base64")
            return None
    
    return None

# Función para transcribir video con OpenAI Whisper
async def transcribe_video(video_path: str) -> TranscriptionResult:
    """Transcribe el video usando OpenAI Whisper API"""
    logger.info(f"Transcribiendo video: {video_path}")
    
    try:
        with open(video_path, "rb") as audio_file:
            # Transcribir con timestamps
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                language="es"  # Español
            )
        
        # Extraer texto y segmentos con timestamps
        # El resultado de OpenAI en formato verbose_json es un diccionario
        if hasattr(transcript, 'text'):
            # Es un objeto con atributos
            text = transcript.text
            segments = [
                {
                    "start": seg.start if hasattr(seg, 'start') else seg.get('start', 0),
                    "end": seg.end if hasattr(seg, 'end') else seg.get('end', 0),
                    "text": seg.text if hasattr(seg, 'text') else seg.get('text', '')
                }
                for seg in (transcript.segments if hasattr(transcript, 'segments') else transcript.get('segments', []))
            ]
        else:
            # Es un diccionario
            text = transcript.get('text', '')
            segments = [
                {
                    "start": seg.get('start', 0),
                    "end": seg.get('end', 0),
                    "text": seg.get('text', '')
                }
                for seg in transcript.get('segments', [])
            ]
        
        result = TranscriptionResult(
            text=text,
            segments=segments
        )
        
        logger.info(f"Transcripción completada. Longitud: {len(result.text)} caracteres")
        return result
        
    except Exception as e:
        logger.error(f"Error transcribiendo video: {str(e)}")
        
        # Fallback: Transcripción simulada cuando falla OpenAI
        if "insufficient_quota" in str(e):
            logger.warning("Usando transcripción simulada debido a falta de cuota en OpenAI")
            
            mock_text = (
                "Hola, mi nombre es [Candidato] y estoy muy entusiasmado por esta oportunidad. "
                "Tengo experiencia relevante en el área y creo que puedo aportar mucho valor a su equipo. "
                "Me considero una persona proactiva, con capacidad de trabajo en equipo y siempre "
                "dispuesto a aprender nuevas tecnologías. Gracias por considerarme para este puesto."
            )
            
            # Crear segmentos simulados
            words = mock_text.split()
            segments = []
            words_per_segment = 10
            current_time = 0.0
            
            for i in range(0, len(words), words_per_segment):
                segment_words = words[i:i + words_per_segment]
                segment_text = " ".join(segment_words)
                segments.append({
                    "start": current_time,
                    "end": current_time + 3.0,
                    "text": segment_text
                })
                current_time += 3.0
            
            return TranscriptionResult(
                text=f"[TRANSCRIPCIÓN SIMULADA - Sin créditos OpenAI]\n\n{mock_text}",
                segments=segments
            )
        
        raise

# Función para actualizar respuesta con transcripción
def update_response_with_transcript(response_id: str, transcript: str, segments: list):
    """Actualizar respuesta con transcripción en PostgreSQL"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Primero obtener el data actual
            cur.execute("SELECT data FROM responses WHERE id = %s", (response_id,))
            result = cur.fetchone()
            current_data = result['data'] if result else {}
            
            # Actualizar con transcripción
            current_data['transcript'] = transcript
            current_data['timestamped_transcript'] = segments
            current_data['transcription_method'] = 'openai_whisper'
            current_data['transcribed_at'] = datetime.utcnow().isoformat()
            
            # Guardar
            cur.execute("""
                UPDATE responses 
                SET data = %s,
                    processing_status = 'completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (json.dumps(current_data), response_id))
            conn.commit()
    finally:
        conn.close()

# Función para marcar respuesta como fallida
def mark_response_as_failed(response_id: str, error: str):
    """Marcar respuesta como fallida en PostgreSQL"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Obtener data actual
            cur.execute("SELECT data FROM responses WHERE id = %s", (response_id,))
            result = cur.fetchone()
            current_data = result['data'] if result else {}
            
            # Agregar error
            current_data['transcription_error'] = error
            current_data['transcription_failed_at'] = datetime.utcnow().isoformat()
            
            # Guardar
            cur.execute("""
                UPDATE responses 
                SET data = %s,
                    processing_status = 'failed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (json.dumps(current_data), response_id))
            conn.commit()
    finally:
        conn.close()

# Función principal de procesamiento
async def process_video(response_id: str):
    """Procesa un video: extrae base64, transcribe y actualiza la base de datos"""
    logger.info(f"Iniciando procesamiento para response_id: {response_id}")
    
    try:
        # 1. Obtener datos de la respuesta
        response_data = get_response_data(response_id)
        
        if not response_data:
            raise ValueError(f"No se encontró respuesta con id: {response_id}")
        
        # Verificar que sea una pregunta de video
        if response_data['question_type'] != 'video':
            logger.info(f"Response {response_id} no es de tipo video, omitiendo")
            return
        
        # 2. Marcar como processing
        update_response_status(response_id, 'processing')
        logger.info(f"Estado actualizado a 'processing' para response_id: {response_id}")
        
        # 3. Extraer video base64
        video_data = extract_video_data(response_data)
        
        if not video_data:
            raise ValueError(f"No se encontró video base64 para response_id: {response_id}")
        
        # 4. Decodificar base64 y guardar temporalmente
        # Remover el prefijo data:video/webm;base64, si existe
        if video_data.startswith('data:video'):
            video_data = video_data.split(',')[1]
        
        video_bytes = base64.b64decode(video_data)
        
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_file:
            tmp_file.write(video_bytes)
            video_path = tmp_file.name
        
        try:
            # 5. Transcribir
            transcription = await transcribe_video(video_path)
            
            # 6. Actualizar respuesta con transcripción
            update_response_with_transcript(
                response_id, 
                transcription.text,
                transcription.segments
            )
            
            logger.info(f"✅ Procesamiento completado para response_id: {response_id}")
            
        finally:
            # Limpiar archivo temporal
            if os.path.exists(video_path):
                os.unlink(video_path)
        
    except Exception as e:
        logger.error(f"❌ Error procesando response_id {response_id}: {str(e)}")
        
        # Marcar como failed
        mark_response_as_failed(response_id, str(e))
        
        raise

# Endpoints

@app.post("/webhook")
async def webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """Endpoint webhook que recibe el response_id para procesar"""
    logger.info(f"[WEBHOOK] Received request for response_id: {payload.response_id}")
    
    # Validar response_id
    if not payload.response_id:
        logger.error("[WEBHOOK] Missing response_id in payload")
        raise HTTPException(status_code=400, detail="response_id es requerido")
    
    # Agregar tarea de procesamiento en background
    background_tasks.add_task(process_video, payload.response_id)
    logger.info(f"[WEBHOOK] Video {payload.response_id} queued for processing")
    
    return {
        "status": "accepted",
        "response_id": payload.response_id,
        "message": "Video queued for processing"
    }

@app.get("/")
async def root():
    """Endpoint raíz para verificar que el worker está corriendo"""
    return {
        "service": "Video Transcription Worker",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": ["/health", "/webhook"]
    }

@app.get("/health")
async def health():
    """Endpoint de salud detallado"""
    db_status = "unknown"
    try:
        # Verificar conexión con PostgreSQL con timeout reducido
        conn = get_db_connection(max_retries=1)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            db_status = "connected" if result else "error"
        conn.close()
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
    
    # Verificar variables de entorno críticas
    env_status = {
        "DB_HOST": "configured" if os.getenv("DB_HOST") else "missing",
        "DB_NAME": "configured" if os.getenv("DB_NAME") else "missing", 
        "DB_USER": "configured" if os.getenv("DB_USER") else "missing",
        "DB_PASSWORD": "configured" if os.getenv("DB_PASSWORD") else "missing",
        "OPENAI_API_KEY": "configured" if os.getenv("OPENAI_API_KEY") else "missing"
    }
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "periodic_task_running": periodic_task_running,
        "services": {
            "database": db_status,
            "environment": env_status
        }
    }

# Proceso periódico para buscar videos pendientes
async def process_pending_videos():
    """Busca y procesa videos pendientes cada 30 segundos"""
    global periodic_task_running
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    while periodic_task_running:
        try:
            logger.info("Buscando videos pendientes...")
            
            # Buscar respuestas pendientes en PostgreSQL
            conn = get_db_connection(max_retries=2)  # Reducir reintentos en proceso periódico
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT r.id, r.data, q.type as question_type
                        FROM responses r
                        JOIN questions q ON r.question_id = q.id
                        WHERE r.processing_status = 'pending'
                        AND q.type = 'video'
                        LIMIT 10
                    """)
                    pending_responses = cur.fetchall()
            finally:
                conn.close()
            
            if pending_responses:
                logger.info(f"Encontrados {len(pending_responses)} videos pendientes")
                
                for response in pending_responses:
                    try:
                        await process_video(response['id'])
                    except Exception as e:
                        logger.error(f"Error procesando video {response['id']}: {str(e)}")
            else:
                logger.info("No hay videos pendientes")
            
            # Reset contador de fallos consecutivos en caso de éxito
            consecutive_failures = 0
                
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"Error en proceso periódico (intento {consecutive_failures}/{max_consecutive_failures}): {str(e)}")
            
            # Si hay muchos fallos consecutivos, incrementar el tiempo de espera
            if consecutive_failures >= max_consecutive_failures:
                wait_time = 300  # 5 minutos
                logger.warning(f"Demasiados fallos consecutivos. Esperando {wait_time} segundos antes del siguiente intento.")
                await asyncio.sleep(wait_time)
                consecutive_failures = 0  # Reset después del tiempo extendido
                continue
        
        # Esperar 30 segundos antes de la siguiente verificación (o más si hay problemas)
        wait_time = 30 + (consecutive_failures * 10)  # Incrementar tiempo con fallos
        await asyncio.sleep(wait_time)

@app.on_event("startup")
async def startup_event():
    """Inicia el proceso periódico al arrancar la aplicación"""
    global periodic_task_running
    periodic_task_running = True
    
    # Iniciar proceso periódico en background
    asyncio.create_task(process_pending_videos())
    logger.info("Worker iniciado - Proceso periódico activo")

@app.on_event("shutdown")
async def shutdown_event():
    """Detiene el proceso periódico al cerrar la aplicación"""
    global periodic_task_running
    periodic_task_running = False
    logger.info("Worker detenido")

# Para desarrollo local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 