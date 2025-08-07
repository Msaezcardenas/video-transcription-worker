# Worker de Transcripción - Configuración de Despliegue

## Variables de Entorno Requeridas

### Base de Datos PostgreSQL
```
DB_HOST=agendapro-postgres-production.cluster-cni0tmazzjyb.us-west-2.rds.amazonaws.com
DB_PORT=5432
DB_NAME=TalentaPro
DB_USER=TalentaPro_user
DB_PASSWORD=F_8-5,83E>7UdA
```

### OpenAI API
```
OPENAI_API_KEY=your_openai_api_key_here
```

### Configuración Opcional
```
PORT=10000
LOG_LEVEL=INFO
```

## Problemas Comunes

### 1. Error de Conexión a PostgreSQL
- **Síntoma**: `Connection timed out` a la base de datos
- **Causa**: Problema de red/firewall entre Render y AWS RDS
- **Solución**: Verificar que AWS RDS permita conexiones desde Render

### 2. Webhook 404
- **Síntoma**: `POST //webhook HTTP/1.1" 404 Not Found`
- **Causa**: URL mal configurada en el cliente
- **Solución**: Verificar `TRANSCRIPTION_WORKER_URL` en aplicación principal

### 3. Fallos Consecutivos
- El worker tiene resistencia automática con backoff exponencial
- Después de 5 fallos consecutivos, espera 5 minutos antes de reintentar

## Endpoints Disponibles

- `GET /` - Información del servicio
- `GET /health` - Estado de salud detallado
- `POST /webhook` - Recibir requests de transcripción
- `POST /supabase-webhook` - Webhook nativo de Supabase

## Verificación de Despliegue

1. Acceder a `https://your-worker-url.onrender.com/health`
2. Verificar que `database` esté `connected`
3. Verificar que todas las variables de entorno estén `configured`