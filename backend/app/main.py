"""
PRF Honda Inspector - API v5.16
===============================
REFATORAÇÃO COMPLETA

CORREÇÕES DE SEGURANÇA:
1. Validação de input em todos os endpoints
2. Rate limiting básico
3. Sanitização de dados
4. Headers de segurança

CORREÇÕES DE BUGS:
1. Tratamento de erros mais robusto
2. Validação de tipos
3. Memory management melhorado

MELHORIAS:
1. Documentação OpenAPI expandida
2. Logs estruturados
3. Health check detalhado
"""

import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import time
from collections import defaultdict

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.forensic_ai_service import ForensicAIService
from app.domain.schemas import FinalResponse
from app.core.logger import logger
from app.core.config import settings


# ========================================
# MIDDLEWARE DE SEGURANÇA
# ========================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adiciona headers de segurança às respostas."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting básico por IP."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Limpa requests antigos (mais de 1 minuto)
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if now - req_time < 60
        ]
        
        # Verifica limite
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit excedido. Tente novamente em 1 minuto."}
            )
        
        self.requests[client_ip].append(now)
        return await call_next(request)


# ========================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ========================================

app = FastAPI(
    title="PRF Honda Inspector",
    version="5.16.0",
    description="""
    Sistema de análise forense de números de motor Honda.
    
    ## Funcionalidades
    
    - **Leitura OCR**: Extração automática do número do motor
    - **Análise de Fonte**: Comparação com padrão Honda oficial
    - **Detecção de Fraude**: Identificação de adulterações
    - **Histórico**: Armazenamento de análises anteriores
    
    ## Tipos de Gravação
    
    - **ESTAMPAGEM**: Motores antes de 2010
    - **LASER**: Motores a partir de 2010
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=int(getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60))
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, 'CORS_ORIGINS', ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialização
logger.info("=" * 60)
logger.info("PRF Honda Inspector v5.16.0")
logger.info("=" * 60)

forensic_ai = ForensicAIService()

stats = forensic_ai.get_stats()
logger.info(f"IA: {'✓' if forensic_ai.enabled else '✗'}")
logger.info(f"Supabase: {'✓' if forensic_ai.supabase else '✗'}")
logger.info(f"Fontes Honda: {stats.get('fonts_loaded', 0)}")
logger.info(f"Refs: {stats.get('originals', 0)} originais, {stats.get('frauds', 0)} fraudes")
logger.info("=" * 60)


# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def convert_numpy(obj: Any) -> Any:
    """Converte tipos numpy para tipos Python nativos."""
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def validate_year(year: int) -> int:
    """Valida e sanitiza o ano informado."""
    if not isinstance(year, int):
        try:
            year = int(year)
        except (ValueError, TypeError):
            raise HTTPException(400, "Ano deve ser um número inteiro")
    
    if year < 1970:
        raise HTTPException(400, "Ano deve ser maior que 1970")
    if year > datetime.now().year + 2:
        raise HTTPException(400, f"Ano não pode ser maior que {datetime.now().year + 2}")
    
    return year


def validate_file(file: UploadFile) -> None:
    """Valida o arquivo de upload."""
    if not file:
        raise HTTPException(400, "Arquivo não enviado")
    
    # Verifica tipo MIME
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    content_type = file.content_type or ''
    
    if content_type not in allowed_types:
        raise HTTPException(
            400,
            f"Tipo de arquivo inválido: {content_type}. Use: {', '.join(allowed_types)}"
        )
    
    # Verifica tamanho (10MB max)
    max_size = 10 * 1024 * 1024
    # Nota: file.size pode não estar disponível em todas as versões


def sanitize_string(s: Optional[str], max_length: int = 100) -> Optional[str]:
    """Sanitiza string de input."""
    if s is None:
        return None
    
    # Remove caracteres perigosos
    s = s.strip()
    s = s.replace('\x00', '')  # Remove null bytes
    
    # Limita tamanho
    if len(s) > max_length:
        s = s[:max_length]
    
    return s


# ========================================
# FRONTEND (se existir)
# ========================================

frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    @app.get("/app", include_in_schema=False)
    async def serve_app():
        """Serve a aplicação frontend."""
        return FileResponse(str(frontend_path / "index.html"))


# ========================================
# ENDPOINTS PRINCIPAIS
# ========================================

@app.get("/")
async def root():
    """
    Informações do sistema.
    
    Retorna status do serviço e estatísticas básicas.
    """
    stats = forensic_ai.get_stats()
    return {
        "name": "PRF Honda Inspector",
        "version": "5.16.0",
        "mode": "Análise Forense com IA",
        "ai_enabled": forensic_ai.enabled,
        "supabase": forensic_ai.supabase is not None,
        "fonts_loaded": stats.get('fonts_loaded', 0),
        "stats": stats,
        "frontend": "/app" if frontend_path.exists() else "Não instalado"
    }


@app.get("/health")
async def health_check():
    """
    Health check detalhado.
    
    Verifica status de todos os componentes do sistema.
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": "ok",
            "forensic_ai": "ok" if forensic_ai.enabled else "degraded",
            "supabase": "ok" if forensic_ai.supabase else "unavailable"
        }
    }
    
    # Define status geral
    if not forensic_ai.enabled:
        health["status"] = "degraded"
    
    return health


@app.post("/analyze/motor", response_model=FinalResponse)
async def analyze_motor(
    photo: UploadFile = File(..., description="Foto do número de motor (JPEG/PNG)"),
    year: int = Form(..., ge=1970, le=2100, description="Ano do veículo"),
    model: Optional[str] = Form(None, max_length=100, description="Modelo da moto (opcional)")
):
    """
    Analisa número de motor Honda.
    
    ## Processo de Análise
    
    1. **OCR**: Leitura do número gravado
    2. **Validação**: Verifica formato Honda
    3. **Análise de Fonte**: Compara com padrão Honda
    4. **Detecção de Fraude**: Identifica adulterações
    
    ## Retorno
    
    - `verdict`: Classificação (REGULAR, ATENÇÃO, SUSPEITO, FRAUDE)
    - `risk_score`: Score de risco (0-100)
    - `read_code`: Código lido
    - `analysis_id`: ID para feedback posterior
    
    ## Exemplos de Códigos Honda
    
    - CG 160: MC27E-1009153
    - XRE 300: MD09E1-B215797
    - CB 500: NC51E-A123456
    """
    try:
        # Validações
        validate_file(photo)
        year = validate_year(year)
        model = sanitize_string(model, 100)
        
        logger.info("=" * 50)
        logger.info(f"ANÁLISE v5.16 | Ano: {year} | Modelo: {model or 'N/I'}")
        logger.info("=" * 50)
        
        # Lê conteúdo do arquivo
        content = await photo.read()
        
        if len(content) == 0:
            raise HTTPException(400, "Arquivo vazio")
        
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(400, "Arquivo muito grande (máximo 10MB)")
        
        # Executa análise
        result = forensic_ai.analyze(content, year, model)
        verdict = forensic_ai.get_verdict(result['risk_score'])
        
        logger.info(f"CÓDIGO: {result['read_code']}")
        logger.info(f"SCORE: {result['risk_score']} -> {verdict}")
        logger.info(f"ID: {result.get('analysis_id')}")
        
        # Monta explicações
        explanations = result.get('risk_factors', []).copy()
        explanations.extend(result.get('recommendations', []))
        
        return FinalResponse(
            verdict=verdict,
            risk_score=result['risk_score'],
            read_code=result['read_code'],
            prefix=result['prefix'],
            serial=result['serial'],
            expected_model=result['expected_model'],
            components=convert_numpy({
                "analysis_id": result.get('analysis_id'),
                "ai_analysis": {
                    "success": result['success'],
                    "detected_type": result['detected_type'],
                    "expected_type": result['expected_type'],
                    "type_match": result['type_match'],
                    "has_mixed_types": result.get('has_mixed_types', False),
                    "font_is_honda": result.get('font_is_honda', True),
                    "font_analysis": result.get('font_analysis', {}),
                    "surface_analysis": result.get('surface_analysis', {})
                },
                "references_used": result.get('references_used', {}),
                "year": year
            }),
            explanation=explanations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na análise: {e}", exc_info=True)
        raise HTTPException(500, f"Erro interno: {str(e)}")


# ========================================
# ENDPOINTS DE FEEDBACK
# ========================================

@app.post("/evaluate/{analysis_id}")
async def evaluate_analysis(
    analysis_id: str,
    correct: bool = Form(..., description="A análise estava correta?"),
    correct_code: Optional[str] = Form(None, description="Código correto (se diferente)"),
    correct_verdict: Optional[str] = Form(None, description="Veredicto correto"),
    is_fraud: Optional[bool] = Form(None, description="É fraude confirmada?"),
    notes: Optional[str] = Form(None, max_length=1000, description="Observações do perito")
):
    """
    Registra avaliação de uma análise.
    
    Usado para feedback e melhoria contínua do sistema.
    """
    try:
        # Sanitização
        analysis_id = sanitize_string(analysis_id, 50)
        correct_code = sanitize_string(correct_code, 50)
        correct_verdict = sanitize_string(correct_verdict, 50)
        notes = sanitize_string(notes, 1000)
        
        if not analysis_id:
            raise HTTPException(400, "ID de análise inválido")
        
        if not forensic_ai.supabase:
            raise HTTPException(503, "Banco de dados não disponível")
        
        # Atualiza registro
        update_data = {
            'feedback_correct': correct,
            'feedback_code': correct_code,
            'feedback_verdict': correct_verdict,
            'feedback_is_fraud': is_fraud,
            'feedback_notes': notes,
            'feedback_at': datetime.utcnow().isoformat()
        }
        
        response = forensic_ai.supabase.table('analysis_history').update(
            update_data
        ).eq('id', analysis_id).execute()
        
        if response.data:
            logger.info(f"Feedback registrado: {analysis_id} - {'CORRETO' if correct else 'INCORRETO'}")
            return {"status": "ok", "message": "Feedback registrado com sucesso"}
        else:
            raise HTTPException(404, "Análise não encontrada")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no feedback: {e}")
        raise HTTPException(500, str(e))


# ========================================
# ENDPOINTS DE INFORMAÇÃO
# ========================================

@app.get("/prefixes")
async def list_prefixes():
    """
    Lista prefixos de motor conhecidos.
    
    Retorna todos os prefixos Honda cadastrados com informações do modelo.
    """
    from app.database.honda_motor_specs import HondaMotorSpecs
    
    prefixes = []
    for prefix, info in sorted(HondaMotorSpecs.ENGINE_PREFIXES.items()):
        prefixes.append({
            "prefix": prefix,
            "model": info[0],
            "cc": info[1]
        })
    
    return {
        "total": len(prefixes),
        "prefixes": prefixes
    }


@app.get("/stats")
async def get_stats():
    """
    Estatísticas do sistema.
    
    Retorna métricas de uso e performance.
    """
    return forensic_ai.get_stats()


# ========================================
# ERROR HANDLERS
# ========================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handler personalizado para HTTPException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler para exceções não tratadas."""
    logger.error(f"Erro não tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "Erro interno do servidor",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
