import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from app.services.ocr import OCREngine
from app.services.conformity_service import ConformityService
from app.services.anomaly_service import AnomalyService
from app.services.visual_matcher import VisualMatcher
from app.services.reference_loader import ReferenceLoader
from app.database.honda_specs import HondaSpecs
from app.domain.schemas import FinalResponse
from app.core.logger import logger

app = FastAPI(title="PRF Honda Inspector v1.0")

# Inicialização dos Serviços (Padrão Singleton)
ocr_engine = OCREngine()
conformity_svc = ConformityService()
anomaly_svc = AnomalyService()
visual_svc = VisualMatcher()

@app.post("/analyze/vin", response_model=FinalResponse)
async def analyze_component(
    photo: UploadFile = File(...),
    year: int = Form(...),
    model: str = Form(...), # Ex: CG 160 (usado para buscar pasta)
    component: str = Form(...) # 'chassi' ou 'motor'
):
    try:
        logger.info(f"Iniciando análise: Honda {model} {year} - {component}")
        
        # 1. OCR e Leitura
        content = await photo.read()
        raw_text, ocr_details = ocr_engine.process_image(content)
        
        # Limpeza (apenas alfanuméricos)
        clean_code = re.sub(r'[^A-Z0-9]', '', raw_text)

        # 2. Análise de Conformidade (Regras)
        conf_res = conformity_svc.analyze(clean_code, year)

        # 3. Análise de Anomalia (Matemática/Forense)
        expected_type = HondaSpecs.get_expected_marking_type(year)
        forensic_res = anomaly_svc.analyze(content, ocr_details, expected_type)

        # 4. Análise Visual (Comparação com Banco de Dados)
        ref_path = ReferenceLoader.get_image_path("HONDA", year, component)
        visual_res = visual_svc.compare(content, ref_path)

        # 5. Cálculo do Veredito
        score = 0
        reasons = []

        # Penalidades Conformidade
        if conf_res['status'] == 'FALHA': 
            score += 40
            reasons.extend(conf_res['details'])
        
        # Penalidades Forenses
        if forensic_res['status'] == 'SUSPEITO':
            score += 30
            for out in forensic_res['outliers']:
                reasons.append(f"Anomalia no caractere '{out['char']}' (Pos {out['position']}): {out['reason']}")
            
            if forensic_res['detected_type'] != expected_type:
                reasons.append(f"Tipo de marcação divergente: Detectado {forensic_res['detected_type']} vs Esperado {expected_type}")

        # Penalidades Visuais
        if visual_res['status'] == 'DIVERGENTE':
            score += 30
            reasons.append("Fonte/Estilo visual diverge do banco de referência (SSIM baixo).")
        elif visual_res['status'] == 'ALERTA':
            # Apenas informativo se não tiver imagem no banco
            reasons.append(f"Nota: {visual_res['details']}")

        verdict = "REGULAR"
        if score > 30: verdict = "ATENÇÃO"
        if score > 70: verdict = "ALTA SUSPEITA DE FRAUDE"

        return {
            "verdict": verdict,
            "risk_score": min(score, 100),
            "read_code": clean_code,
            "components": {
                "conformity": conf_res,
                "forensic": forensic_res,
                "visual": visual_res
            },
            "explanation": reasons
        }

    except Exception as e:
        logger.error(f"Erro Crítico: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)