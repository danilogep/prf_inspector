"""
PRF Honda Inspector - API v5.2
==============================
- Comparação visual com fontes Honda
- Sistema de aprendizado contínuo
- Servidor de frontend integrado
"""

import numpy as np
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional

from app.services.forensic_ai_service import ForensicAIService
from app.domain.schemas import FinalResponse
from app.core.logger import logger

app = FastAPI(
    title="PRF Honda Inspector",
    version="5.2.0",
    description="Análise forense com comparação de fontes Honda e aprendizado contínuo"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("=" * 60)
logger.info("PRF Honda Inspector v5.2.0")
logger.info("=" * 60)

forensic_ai = ForensicAIService()

stats = forensic_ai.get_stats()
logger.info(f"IA: {'✓' if forensic_ai.enabled else '✗'}")
logger.info(f"Supabase: {'✓' if forensic_ai.supabase else '✗'}")
logger.info(f"Fontes Honda: {stats.get('fonts_loaded', 0)}")
logger.info(f"Refs: {stats.get('originals', 0)} originais, {stats.get('frauds', 0)} fraudes")
logger.info(f"Acurácia: {stats.get('accuracy_rate', 'N/A')}%")
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


# ========================================
# FRONTEND
# ========================================

# Tenta montar pasta frontend se existir
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    @app.get("/app")
    async def serve_app():
        return FileResponse(str(frontend_path / "index.html"))


@app.get("/")
async def root():
    stats = forensic_ai.get_stats()
    return {
        "name": "PRF Honda Inspector",
        "version": "5.2.0",
        "mode": "Comparação de Fontes + Aprendizado Contínuo",
        "ai_enabled": forensic_ai.enabled,
        "supabase": forensic_ai.supabase is not None,
        "fonts_loaded": stats.get('fonts_loaded', 0),
        "stats": stats,
        "frontend": "/app" if frontend_path.exists() else "Não instalado"
    }


# ========================================
# ANÁLISE
# ========================================

@app.post("/analyze/motor", response_model=FinalResponse)
async def analyze_motor(
    photo: UploadFile = File(...),
    year: int = Form(...),
    model: Optional[str] = Form(None)
):
    """
    Analisa motor Honda com:
    - Comparação visual com fontes Honda oficiais
    - Referências de motores originais e fraudes
    - Sistema de aprendizado contínuo
    
    Retorna `analysis_id` para avaliação posterior.
    """
    try:
        logger.info("=" * 50)
        logger.info(f"ANÁLISE v5.2 | Ano: {year}")
        logger.info("=" * 50)
        
        content = await photo.read()
        result = forensic_ai.analyze(content, year, model)
        verdict = forensic_ai.get_verdict(result['risk_score'])
        
        logger.info(f"CÓDIGO: {result['read_code']}")
        logger.info(f"SCORE: {result['risk_score']} -> {verdict}")
        logger.info(f"ID: {result.get('analysis_id')}")
        
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
                    "font_comparison": result.get('font_comparison', []),
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
# AVALIAÇÃO / FEEDBACK
# ========================================

@app.post("/evaluate/{analysis_id}")
async def evaluate_analysis(
    analysis_id: str,
    correct: bool = Form(...),
    correct_code: Optional[str] = Form(None),
    correct_verdict: Optional[str] = Form(None),
    is_fraud: Optional[bool] = Form(None),
    notes: Optional[str] = Form(None)
):
    """
    Avalia uma análise.
    
    - correct: A IA acertou?
    - is_fraud: É fraude confirmada?
    - correct_code: Código correto se IA errou
    """
    if not forensic_ai.supabase:
        raise HTTPException(503, "Supabase não configurado")
    
    success, message = forensic_ai.evaluate_analysis(
        analysis_id=analysis_id,
        correct=correct,
        correct_code=correct_code,
        correct_verdict=correct_verdict,
        is_fraud=is_fraud,
        notes=notes
    )
    
    if success:
        return {"status": "success", "message": message}
    raise HTTPException(400, message)


@app.post("/promote/{analysis_id}")
async def promote_to_reference(analysis_id: str):
    """Promove análise para banco de referências."""
    if not forensic_ai.supabase:
        raise HTTPException(503, "Supabase não configurado")
    
    success, message = forensic_ai.promote_to_reference(analysis_id)
    
    if success:
        return {"status": "success", "message": message}
    raise HTTPException(400, message)


# ========================================
# HISTÓRICO E ESTATÍSTICAS
# ========================================

@app.get("/history")
async def get_history(limit: int = 50, pending_only: bool = False):
    """Lista histórico de análises."""
    history = forensic_ai.get_analysis_history(limit=limit, only_pending=pending_only)
    return {"total": len(history), "analyses": history}


@app.get("/history/{analysis_id}")
async def get_analysis_detail(analysis_id: str):
    """Detalhes de uma análise."""
    detail = forensic_ai.get_analysis_detail(analysis_id)
    if not detail:
        raise HTTPException(404, "Não encontrada")
    return detail


@app.get("/stats")
async def get_stats():
    """Estatísticas do sistema."""
    return forensic_ai.get_stats()


# ========================================
# REFERÊNCIAS MANUAIS
# ========================================

@app.post("/references/originals/add")
async def add_original(
    code: str = Form(...),
    year: int = Form(...),
    engraving_type: str = Form(...),
    photo: UploadFile = File(...),
    model: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """Cadastra motor original."""
    if not forensic_ai.supabase:
        raise HTTPException(503, "Supabase não configurado")
    
    engraving_type = engraving_type.lower().strip()
    if engraving_type not in ['laser', 'estampagem']:
        raise HTTPException(400, "engraving_type: 'laser' ou 'estampagem'")
    
    content = await photo.read()
    success, message = forensic_ai.add_original(
        code, year, engraving_type, content, model, description
    )
    
    if success:
        return {"status": "success", "message": message}
    raise HTTPException(500, message)


@app.get("/references/originals/list")
async def list_originals():
    """Lista originais."""
    return {"originals": forensic_ai.list_originals()}


@app.post("/references/frauds/add")
async def add_fraud(
    fraud_code: str = Form(...),
    fraud_type: str = Form(...),
    description: str = Form(...),
    photo: UploadFile = File(...),
    original_code: Optional[str] = Form(None),
    indicators: Optional[str] = Form(None),
    year_claimed: Optional[int] = Form(None)
):
    """Cadastra fraude."""
    if not forensic_ai.supabase:
        raise HTTPException(503, "Supabase não configurado")
    
    content = await photo.read()
    indicators_list = [i.strip() for i in indicators.split(',')] if indicators else []
    
    success, message = forensic_ai.add_fraud(
        fraud_code, fraud_type, description, content,
        original_code, indicators_list, year_claimed
    )
    
    if success:
        return {"status": "success", "message": message}
    raise HTTPException(500, message)


@app.get("/references/frauds/list")
async def list_frauds():
    """Lista fraudes."""
    return {"frauds": forensic_ai.list_frauds()}


@app.get("/health")
async def health():
    stats = forensic_ai.get_stats()
    return {
        "status": "healthy",
        "version": "5.2.0",
        "fonts": stats.get('fonts_loaded', 0),
        "accuracy": f"{stats.get('accuracy_rate', 0)}%",
        "pending": stats.get('pending_evaluation', 0)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
