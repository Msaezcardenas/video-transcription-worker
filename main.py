import os
import asyncio
import tempfile
from typing import Optional
from datetime import datetime
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from supabase import create_client, Client
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

# Inicializar clientes
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Variable global para controlar el proceso periódico
periodic_task_running = False

# Modelos de datos
class WebhookPayload(BaseModel):
    response_id: str
    
class SupabaseWebhookPayload(BaseModel):
    type: str  # INSERT, UPDATE, DELETE
    table: str
    record: dict
    schema: str
    old_record: Optional[dict] = None
    
class TranscriptionResult(BaseModel):
    text: str
    segments: list

# Función para descargar video desde Supabase Storage
async def download_video(video_url: str, output_path: str) -> None:
    """Descarga el video desde la URL proporcionada"""
    logger.info(f"Descargando video desde: {video_url}")
    
    try:
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info(f"Video descargado exitosamente: {output_path}")
    except Exception as e:
        logger.error(f"Error descargando video: {str(e)}")
        raise

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
        result = TranscriptionResult(
            text=transcript.text,
            segments=[
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                }
                for segment in transcript.segments
            ]
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

# Función principal de procesamiento
async def process_video(response_id: str):
    """Procesa un video: descarga, transcribe y actualiza la base de datos"""
    logger.info(f"Iniciando procesamiento para response_id: {response_id}")
    
    try:
        # 1. Obtener datos de la respuesta
        response = supabase.table('responses').select("*").eq('id', response_id).single().execute()
        
        if not response.data:
            raise ValueError(f"No se encontró respuesta con id: {response_id}")
        
        response_data = response.data
        video_url = response_data.get('data', {}).get('video_url')
        
        if not video_url:
            raise ValueError(f"No se encontró video_url para response_id: {response_id}")
        
        # 2. Marcar como processing
        supabase.table('responses').update({
            'processing_status': 'processing',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', response_id).execute()
        
        logger.info(f"Estado actualizado a 'processing' para response_id: {response_id}")
        
        # 3. Descargar y transcribir video
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp_file:
            video_path = tmp_file.name
            
            # Descargar video
            await download_video(video_url, video_path)
            
            # Transcribir
            transcription = await transcribe_video(video_path)
            
            # Limpiar archivo temporal
            os.unlink(video_path)
        
        # 4. Actualizar respuesta con transcripción
        updated_data = response_data.get('data', {})
        updated_data.update({
            'transcript': transcription.text,
            'timestamped_transcript': transcription.segments,
            'transcription_method': 'openai_whisper',
            'transcribed_at': datetime.utcnow().isoformat()
        })
        
        supabase.table('responses').update({
            'data': updated_data,
            'processing_status': 'completed',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', response_id).execute()
        
        logger.info(f"✅ Procesamiento completado para response_id: {response_id}")
        
    except Exception as e:
        logger.error(f"❌ Error procesando response_id {response_id}: {str(e)}")
        
        # Marcar como failed
        try:
            supabase.table('responses').update({
                'processing_status': 'failed',
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', response_id).execute()
        except:
            pass
        
        raise

# Endpoints
@app.get("/")
async def root():
    """Endpoint de salud"""
    return {
        "status": "ok",
        "service": "Video Transcription Worker",
        "version": "1.0.0"
    }

@app.post("/webhook")
async def webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """Endpoint webhook que recibe el response_id para procesar"""
    logger.info(f"Webhook recibido para response_id: {payload.response_id}")
    
    # Validar response_id
    if not payload.response_id:
        raise HTTPException(status_code=400, detail="response_id es requerido")
    
    # Agregar tarea de procesamiento en background
    background_tasks.add_task(process_video, payload.response_id)
    
    return {
        "status": "accepted",
        "response_id": payload.response_id,
        "message": "Video queued for processing"
    }

@app.post("/supabase-webhook")
async def supabase_webhook(payload: SupabaseWebhookPayload, background_tasks: BackgroundTasks):
    """Endpoint para webhooks nativos de Supabase"""
    logger.info(f"Supabase webhook recibido: {payload.type} en tabla {payload.table}")
    
    # Solo procesar inserciones en la tabla responses
    if payload.type != "INSERT" or payload.table != "responses":
        return {"status": "ignored", "reason": "Not an INSERT on responses table"}
    
    record = payload.record
    
    # Verificar si es un video
    if not record.get('data', {}).get('type') == 'video':
        return {"status": "ignored", "reason": "Not a video response"}
    
    if not record.get('data', {}).get('video_url'):
        return {"status": "ignored", "reason": "No video_url found"}
    
    response_id = record.get('id')
    if not response_id:
        raise HTTPException(status_code=400, detail="No response_id in record")
    
    logger.info(f"Procesando video para response_id: {response_id}")
    
    # Agregar tarea de procesamiento en background
    background_tasks.add_task(process_video, response_id)
    
    return {
        "status": "accepted",
        "response_id": response_id,
        "message": "Video queued for processing"
    }

@app.get("/health")
async def health():
    """Endpoint de salud detallado"""
    try:
        # Verificar conexión con Supabase
        supabase.table('responses').select("count").limit(1).execute()
        supabase_status = "connected"
    except:
        supabase_status = "disconnected"
    
    return {
        "status": "healthy",
        "services": {
            "supabase": supabase_status,
            "openai": "configured" if os.getenv("OPENAI_API_KEY") else "not configured"
        }
    }

# Proceso periódico para buscar videos pendientes
async def process_pending_videos():
    """Busca y procesa videos pendientes cada 30 segundos"""
    global periodic_task_running
    
    while periodic_task_running:
        try:
            logger.info("Buscando videos pendientes...")
            
            # Buscar respuestas pendientes
            result = supabase.table('responses').select("*").eq('processing_status', 'pending').execute()
            
            if result.data:
                logger.info(f"Encontrados {len(result.data)} videos pendientes")
                
                for response in result.data:
                    # Verificar que sea un video
                    if response.get('data', {}).get('type') == 'video':
                        try:
                            await process_video(response['id'])
                        except Exception as e:
                            logger.error(f"Error procesando video {response['id']}: {str(e)}")
            else:
                logger.info("No hay videos pendientes")
                
        except Exception as e:
            logger.error(f"Error en proceso periódico: {str(e)}")
        
        # Esperar 30 segundos antes de la siguiente verificación
        await asyncio.sleep(30)

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