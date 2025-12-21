"""
PRF Honda Inspector - API de Análise de Motor
=============================================

Sistema forense para identificação de fraudes em números de motor
de motocicletas Honda.

Foco: Apenas análise de MOTOR (não chassi)
"""

import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.services.ocr import OCREngine
from app.services.anomaly_service import AnomalyService
from app.services.visual_matcher import VisualMatcher
from app.services.reference_loader import ReferenceLoader
from app.services.font_analyzer import FontAnalyzer
from app.database.honda_motor_specs import HondaMotorSpecs
from app.domain.schemas import FinalResponse
from app.core.logger import logger
from app.core.config import settings

# Inicializa FastAPI
app = FastAPI(
    title="PRF Honda Inspector - Motor",
    version="2.0.0",
    description="Sistema Forense de Identificação de Fraudes em Motores Honda"
)

# CORS para acesso do app mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicialização dos Serviços (Singleton)
logger.info("Inicializando serviços...")
ocr_engine = OCREngine()
anomaly_svc = AnomalyService()
visual_svc = VisualMatcher()
font_analyzer = FontAnalyzer()

# Garante estrutura de diretórios
ReferenceLoader.ensure_directories()
logger.info("API pronta para receber requisições")


@app.get("/")
async def root():
    """Endpoint raiz."""
    return {
        "name": "PRF Honda Inspector - Motor",
        "version": "2.0.0",
        "status": "online"
    }


@app.get("/health")
async def health_check():
    """Verificação de saúde do serviço."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "templates_loaded": len(font_analyzer.get_available_templates()),
        "high_risk_chars": settings.HIGH_RISK_CHARS
    }


@app.get("/references")
async def list_references():
    """Lista referências de motor disponíveis."""
    return ReferenceLoader.list_available_references()


@app.get("/fonts")
async def list_fonts():
    """Lista templates de fonte carregados."""
    templates = font_analyzer.get_available_templates()
    return {
        "total": len(templates),
        "characters": sorted(templates),
        "high_risk": settings.HIGH_RISK_CHARS
    }


@app.get("/prefixes")
async def list_prefixes():
    """Lista prefixos de motor Honda conhecidos."""
    prefixes = []
    for prefix, (model, cc) in HondaMotorSpecs.ENGINE_PREFIXES.items():
        prefixes.append({
            "prefix": prefix,
            "model": model,
            "cc": cc
        })
    return {"total": len(prefixes), "prefixes": prefixes}


@app.post("/analyze/motor", response_model=FinalResponse)
async def analyze_motor(
    photo: UploadFile = File(..., description="Foto do número de motor"),
    year: int = Form(..., description="Ano do modelo (ex: 2020)"),
    model: Optional[str] = Form(None, description="Modelo da moto (ex: CG 160) - opcional"),
):
    """
    Analisa número de motor de motocicleta Honda.
    
    Análises realizadas:
    - OCR: Leitura do número gravado
    - Formato: Validação do padrão Honda (prefixo + serial)
    - Forense: Micropunção, alinhamento, densidade de pontos
    - Tipográfica: Comparação com fonte Honda, detecção de vazamentos
    - Visual: Comparação com banco de referências
    
    Caracteres de alto risco (mais falsificados): 0, 1, 3, 4, 9
    """
    try:
        logger.info(f"=== Iniciando análise de motor: Honda {model or 'N/I'} {year} ===")
        
        # 1. Leitura OCR
        content = await photo.read()
        raw_text, ocr_details, char_images = ocr_engine.process_image(content)
        
        # Limpeza do texto (mantém hífen para separar prefixo do serial)
        clean_code = re.sub(r'[^A-Z0-9-]', '', raw_text.upper())
        logger.info(f"Código lido: {clean_code}")
        
        # 2. Validação de formato do motor Honda
        engine_validation = HondaMotorSpecs.validate_engine_format(clean_code)
        logger.info(f"Validação: {engine_validation}")
        
        # 3. Obtém métricas detalhadas dos caracteres
        ocr_metrics = ocr_engine.get_character_metrics(content)
        
        # 4. Análise Forense (anomalias, vazamentos, etc)
        expected_type = HondaMotorSpecs.get_expected_marking_type(year)
        forensic_result = anomaly_svc.analyze(
            content, 
            ocr_metrics, 
            expected_type,
            char_images
        )
        logger.info(f"Forense: status={forensic_result['status']}, tipo={forensic_result['detected_type']}")
        
        # 5. Comparação visual (se houver referência)
        ref_path = ReferenceLoader.get_motor_reference(
            year, 
            engine_validation.get('prefix')
        )
        visual_result = visual_svc.compare(content, ref_path)
        
        # 6. Calcula score de risco e monta resposta
        score, reasons = _calculate_risk_score(
            engine_validation,
            forensic_result,
            visual_result,
            expected_type
        )
        
        verdict = _determine_verdict(score)
        logger.info(f"=== Resultado: {verdict} (score: {score}) ===")
        
        # Monta resposta
        return FinalResponse(
            verdict=verdict,
            risk_score=min(score, 100),
            read_code=clean_code,
            prefix=engine_validation.get('prefix'),
            serial=engine_validation.get('serial'),
            expected_model=engine_validation.get('model_info', [None])[0] if engine_validation.get('model_info') else None,
            components={
                "engine_validation": engine_validation,
                "forensic": forensic_result,
                "visual": visual_result
            },
            explanation=reasons
        )
        
    except Exception as e:
        logger.error(f"Erro na análise: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


# Endpoint legado para compatibilidade com app existente
@app.post("/analyze/vin", response_model=FinalResponse)
async def analyze_vin_legacy(
    photo: UploadFile = File(...),
    year: int = Form(...),
    model: str = Form(...),
    component: str = Form(...)
):
    """
    Endpoint legado para compatibilidade.
    Redireciona para análise de motor.
    """
    return await analyze_motor(photo, year, model)


def _calculate_risk_score(
    validation: dict,
    forensic: dict,
    visual: dict,
    expected_type: str
) -> tuple:
    """
    Calcula score de risco (0-100) e lista de razões.
    
    Pesos:
    - Validação de formato: até 25 pontos
    - Análise forense: até 45 pontos
    - Comparação visual: até 30 pontos
    """
    score = 0
    reasons = []
    
    # 1. Validação de formato (0-25 pontos)
    if not validation.get('valid', False):
        issues = validation.get('issues', [])
        score += min(len(issues) * 8, 25)
        reasons.extend(issues)
    
    # 2. Análise forense (0-45 pontos)
    forensic_status = forensic.get('status', 'OK')
    
    if forensic_status == 'SUSPEITO':
        score += 20
    elif forensic_status == 'ATENÇÃO':
        score += 10
    
    # Outliers (anomalias detectadas)
    outliers = forensic.get('outliers', [])
    score += min(len(outliers) * 5, 15)
    
    for outlier in outliers:
        reasons.append(
            f"'{outlier.get('char', '?')}' (pos {outlier.get('position', '?')}): {outlier.get('reason', 'anomalia')}"
        )
    
    # Divergência de tipo de gravação
    detected_type = forensic.get('detected_type', 'UNKNOWN')
    if detected_type != expected_type and detected_type != 'UNKNOWN':
        score += 10
        reasons.append(
            f"Tipo de gravação: detectado {detected_type}, esperado {expected_type}"
        )
    
    # Alertas de alto risco (vazamentos, etc)
    high_risk_alerts = forensic.get('high_risk_alerts', [])
    for alert in high_risk_alerts:
        if '⚠️' in alert:  # Alertas críticos
            score += 8
        else:
            score += 3
        reasons.append(alert)
    
    # 3. Comparação visual (0-30 pontos)
    visual_status = visual.get('status', 'SEM_REFERÊNCIA')
    
    if visual_status == 'DIVERGENTE':
        score += 30
        reasons.append(
            f"Padrão visual divergente (similaridade: {visual.get('similarity', 0)}%)"
        )
    elif visual_status == 'SEM_REFERÊNCIA':
        reasons.append("Nota: Sem imagem de referência para comparação visual")
    
    return score, reasons


def _determine_verdict(score: int) -> str:
    """Determina veredito baseado no score."""
    if score <= 10:
        return "REGULAR"
    elif score <= 30:
        return "ATENÇÃO"
    elif score <= 60:
        return "SUSPEITO"
    else:
        return "ALTA SUSPEITA DE FRAUDE"


# Inicialização direta
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
