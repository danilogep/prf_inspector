"""
PRF Honda Inspector - API v5.0.1
================================
Melhor tratamento de erros
"""

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List

from app.services.forensic_ai_service import ForensicAIService
from app.domain.schemas import FinalResponse
from app.core.logger import logger

app = FastAPI(
    title="PRF Honda Inspector",
    version="5.0.1",
    description="Análise comparativa com banco de referências"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("=" * 60)
logger.info("PRF Honda Inspector v5.0.1")
logger.info("=" * 60)

forensic_ai = ForensicAIService()

stats = forensic_ai.get_stats()
logger.info(f"IA: {'✓' if forensic_ai.enabled else '✗'}")
logger.info(f"Supabase: {'✓' if forensic_ai.supabase else '✗'}")
logger.info(f"Refs: {stats['originals']} originais, {stats['frauds']} fraudes")
logger.info("=" * 60)


def convert_numpy(obj):
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


@app.get("/")
async def root():
    stats = forensic_ai.get_stats()
    return {
        "name": "PRF Honda Inspector",
        "version": "5.0.1",
        "ai_enabled": forensic_ai.enabled,
        "supabase": forensic_ai.supabase is not None,
        "references": stats
    }


@app.post("/analyze/motor", response_model=FinalResponse)
async def analyze_motor(
    photo: UploadFile = File(...),
    year: int = Form(...),
    model: Optional[str] = Form(None)
):
    """Analisa motor com referências."""
    try:
        logger.info("=" * 50)
        logger.info(f"ANÁLISE v5.0.1 | Ano: {year}")
        logger.info("=" * 50)
        
        content = await photo.read()
        result = forensic_ai.analyze(content, year, model)
        verdict = forensic_ai.get_verdict(result['risk_score'])
        
        logger.info(f"CÓDIGO: {result['read_code']}")
        logger.info(f"SCORE: {result['risk_score']} -> {verdict}")
        
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
                "ai_analysis": {
                    "success": result['success'],
                    "detected_type": result['detected_type'],
                    "expected_type": result['expected_type'],
                    "type_match": result['type_match'],
                    "has_mixed_types": result.get('has_mixed_types', False),
                    "alignment": result.get('alignment_analysis', {}),
                    "font_consistency": result.get('font_consistency', {}),
                    "repeated_chars": result.get('repeated_chars_analysis', [])
                },
                "references_used": result.get('references_used', {}),
                "year": year
            }),
            explanation=explanations
        )
        
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ========================================
# MOTORES ORIGINAIS
# ========================================

@app.post("/references/originals/add")
async def add_original(
    code: str = Form(..., description="Código: KC08E57083003 ou KC08E5-7083003"),
    year: int = Form(..., description="Ano do veículo"),
    engraving_type: str = Form(..., description="laser ou estampagem"),
    photo: UploadFile = File(...),
    model: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Cadastra motor ORIGINAL.
    
    - code: Código completo (com ou sem hífen)
    - year: Ano do veículo
    - engraving_type: 'laser' ou 'estampagem' (minúsculo)
    - photo: Imagem JPG
    """
    if not forensic_ai.supabase:
        raise HTTPException(503, "Supabase não configurado")
    
    # Normaliza engraving_type para minúsculo
    engraving_type = engraving_type.lower().strip()
    
    if engraving_type not in ['laser', 'estampagem']:
        raise HTTPException(400, f"engraving_type deve ser 'laser' ou 'estampagem', recebido: '{engraving_type}'")
    
    content = await photo.read()
    
    success, message = forensic_ai.add_original(
        code, year, engraving_type, content, model, description
    )
    
    if success:
        return {
            "status": "success",
            "message": message,
            "code": code.upper(),
            "year": year,
            "type": engraving_type
        }
    
    raise HTTPException(500, message)


@app.get("/references/originals/list")
async def list_originals():
    """Lista motores originais."""
    originals = forensic_ai.list_originals()
    return {"total": len(originals), "originals": originals}


# ========================================
# MOTORES ADULTERADOS
# ========================================

@app.post("/references/frauds/add")
async def add_fraud(
    fraud_code: str = Form(..., description="Código visível"),
    fraud_type: str = Form(..., description="mistura_tipos, regravacao_parcial, etc"),
    description: str = Form(..., description="Descrição da fraude"),
    photo: UploadFile = File(...),
    original_code: Optional[str] = Form(None),
    indicators: Optional[str] = Form(None, description="Indicadores separados por vírgula"),
    year_claimed: Optional[int] = Form(None)
):
    """
    Cadastra motor ADULTERADO.
    
    Tipos de fraude:
    - mistura_tipos
    - regravacao_total
    - regravacao_parcial
    - desalinhamento
    - fonte_diferente
    - lixamento
    """
    if not forensic_ai.supabase:
        raise HTTPException(503, "Supabase não configurado")
    
    content = await photo.read()
    indicators_list = [i.strip() for i in indicators.split(',')] if indicators else []
    
    success, message = forensic_ai.add_fraud(
        fraud_code, fraud_type, description, content,
        original_code, indicators_list, year_claimed
    )
    
    if success:
        return {
            "status": "success",
            "message": message,
            "fraud_code": fraud_code.upper(),
            "fraud_type": fraud_type
        }
    
    raise HTTPException(500, message)


@app.get("/references/frauds/list")
async def list_frauds():
    """Lista fraudes."""
    frauds = forensic_ai.list_frauds()
    return {"total": len(frauds), "frauds": frauds}


# ========================================
# DEBUG E STATS
# ========================================

@app.get("/references/stats")
async def get_stats():
    """Estatísticas."""
    return forensic_ai.get_stats()


@app.get("/debug/supabase")
async def debug_supabase():
    """Debug Supabase."""
    return forensic_ai.debug_supabase()


@app.get("/health")
async def health():
    stats = forensic_ai.get_stats()
    return {"status": "healthy", "version": "5.0.1", "references": stats}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
