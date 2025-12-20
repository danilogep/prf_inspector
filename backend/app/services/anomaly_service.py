import numpy as np
from app.services.texture_utils import TextureUtils
from app.core.config import settings

class AnomalyService:
    def __init__(self):
        self.tex = TextureUtils()

    def analyze(self, image: bytes, ocr_details: list, expected_type: str) -> dict:
        # Pre-processamento
        _, _, thresh = self.tex.preprocess(image)
        metrics = []

        # 1. Extração de Métricas Individuais
        for i, (bbox, text, _) in enumerate(ocr_details):
            # Limpa caracteres não alfanuméricos
            if not text.isalnum(): continue
            
            roi = self.tex.get_roi(thresh, bbox)
            
            metrics.append({
                "char": text, "idx": i,
                "dots": self.tex.count_dots(roi),
                "height": bbox[2][1] - bbox[0][1],
                "y": (bbox[0][1] + bbox[2][1]) / 2
            })

        if not metrics: 
            return {"status": "INCONCLUSIVO", "detected_type": "UNKNOWN", "avg_dots": 0, "outliers": []}

        # 2. Estatística do Grupo (Mediana é mais robusta que média)
        avg_dots = np.mean([m['dots'] for m in metrics])
        median_dots = np.median([m['dots'] for m in metrics])
        median_h = np.median([m['height'] for m in metrics])
        median_y = np.median([m['y'] for m in metrics])

        # Se tiver mais que 3.5 pontos de média, é micropunção
        detected_type = "MICROPOINT" if avg_dots > 3.5 else "SOLID"
        
        # 3. Detecção de Outliers
        outliers = []
        for m in metrics:
            reasons = []
            
            # Anomalia de Pontos (Se for micropunção)
            if detected_type == "MICROPOINT":
                if abs(m['dots'] - median_dots) > (median_dots * settings.DENSITY_TOLERANCE):
                    reasons.append(f"Densidade anômala ({m['dots']} pts vs média {int(median_dots)})")

            # Anomalia de Alinhamento Vertical
            if abs(m['y'] - median_y) > (median_h * settings.ALIGNMENT_TOLERANCE):
                reasons.append("Desalinhamento vertical")

            if reasons:
                outliers.append({
                    "char": m['char'], 
                    "position": m['idx']+1, 
                    "reason": "; ".join(reasons)
                })

        status = "SUSPEITO" if outliers or (detected_type != expected_type) else "OK"

        return {
            "status": status,
            "detected_type": detected_type,
            "avg_dots": avg_dots,
            "outliers": outliers
        }