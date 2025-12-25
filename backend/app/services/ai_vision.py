"""
AI Vision Service - Segunda leitura com Claude API ou Google Vision
===================================================================

Este serviço fornece uma segunda opinião usando IA de visão para:
1. Confirmar a leitura do OCR
2. Detectar sinais de adulteração
3. Classificar o tipo de gravação (LASER/ESTAMPAGEM)

Requer configuração de API key no arquivo .env
"""

import base64
import httpx
import json
from typing import Optional, Dict, Any
from app.core.logger import logger
from app.core.config import settings


class AIVisionService:
    """
    Serviço de visão computacional usando Claude API.
    
    Uso:
        service = AIVisionService()
        result = await service.analyze_motor_image(image_bytes)
    """
    
    # Prompt otimizado para análise de motor Honda
    ANALYSIS_PROMPT = """Analise esta imagem de número de motor de motocicleta Honda gravado em metal.

TAREFAS:
1. LEITURA: Leia o número completo gravado. O formato típico é:
   - Primeira linha: Prefixo do motor (ex: MD09E1, MC27E, NC51E)
   - Segunda linha: Serial (ex: B215797, 1009153)
   
2. TIPO DE GRAVAÇÃO: Identifique se é:
   - LASER: Linhas finas e precisas (motos 2010+)
   - ESTAMPAGEM: Caracteres sólidos e prensados (motos antes de 2010)

3. SINAIS DE ADULTERAÇÃO: Procure por:
   - Caracteres desalinhados
   - Diferença de profundidade entre caracteres
   - Sinais de raspagem ou polimento
   - Caracteres com fonte diferente
   - Especialmente nos números 0, 1, 3, 4, 9 (mais falsificados)

RESPONDA APENAS EM JSON válido, sem markdown:
{
    "numero_lido": "PREFIXO-SERIAL",
    "prefixo": "XXXXX",
    "serial": "XXXXXXX",
    "confianca_leitura": 0.0 a 1.0,
    "tipo_gravacao": "LASER" ou "ESTAMPAGEM",
    "sinais_adulteracao": [],
    "adulteracao_detectada": true/false,
    "observacoes": "texto livre"
}"""

    def __init__(self):
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            logger.info("AI Vision Service inicializado com Claude API")
        else:
            logger.warning("AI Vision Service desabilitado - ANTHROPIC_API_KEY não configurada")
    
    async def analyze_motor_image(
        self, 
        image_bytes: bytes,
        ocr_result: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analisa imagem de motor usando Claude API.
        
        Args:
            image_bytes: Imagem em bytes (JPEG/PNG)
            ocr_result: Resultado do OCR local para comparação
            
        Returns:
            Dict com análise da IA
        """
        if not self.enabled:
            return {
                "enabled": False,
                "error": "API key não configurada",
                "numero_lido": ocr_result or "",
                "confianca_leitura": 0.0
            }
        
        try:
            # Codifica imagem em base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Determina tipo de mídia
            media_type = "image/jpeg"
            if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                media_type = "image/png"
            
            # Monta prompt com contexto do OCR se disponível
            prompt = self.ANALYSIS_PROMPT
            if ocr_result:
                prompt += f"\n\nNOTA: O OCR local detectou: '{ocr_result}'. Confirme ou corrija esta leitura."
            
            # Chamada à API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1024,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_base64
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": prompt
                                }
                            ]
                        }]
                    }
                )
            
            if response.status_code != 200:
                logger.error(f"Erro na API Claude: {response.status_code} - {response.text}")
                return {
                    "enabled": True,
                    "error": f"API retornou status {response.status_code}",
                    "numero_lido": ocr_result or "",
                    "confianca_leitura": 0.0
                }
            
            # Processa resposta
            result = response.json()
            content = result.get("content", [{}])[0].get("text", "{}")
            
            # Tenta parsear JSON da resposta
            try:
                # Remove possíveis marcadores de código
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                content = content.strip()
                
                ai_result = json.loads(content)
                ai_result["enabled"] = True
                ai_result["error"] = None
                
                logger.info(f"AI Vision leu: {ai_result.get('numero_lido', 'N/A')}")
                
                return ai_result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Falha ao parsear JSON da IA: {e}")
                return {
                    "enabled": True,
                    "error": "Resposta da IA não é JSON válido",
                    "raw_response": content,
                    "numero_lido": ocr_result or "",
                    "confianca_leitura": 0.0
                }
                
        except httpx.TimeoutException:
            logger.error("Timeout na chamada à API Claude")
            return {
                "enabled": True,
                "error": "Timeout na API",
                "numero_lido": ocr_result or "",
                "confianca_leitura": 0.0
            }
        except Exception as e:
            logger.error(f"Erro no AI Vision Service: {e}")
            return {
                "enabled": True,
                "error": str(e),
                "numero_lido": ocr_result or "",
                "confianca_leitura": 0.0
            }
    
    def compare_readings(
        self, 
        ocr_result: str, 
        ai_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compara leitura do OCR com leitura da IA.
        
        Returns:
            Dict com resultado da comparação e leitura final recomendada
        """
        ai_reading = ai_result.get("numero_lido", "").upper().replace("-", "").replace(" ", "")
        ocr_reading = ocr_result.upper().replace("-", "").replace(" ", "")
        
        # Calcula similaridade
        if not ai_reading or not ocr_reading:
            match_score = 0.0
        else:
            # Conta caracteres iguais na mesma posição
            matches = sum(1 for a, b in zip(ai_reading, ocr_reading) if a == b)
            max_len = max(len(ai_reading), len(ocr_reading))
            match_score = matches / max_len if max_len > 0 else 0.0
        
        # Determina leitura final
        ai_confidence = ai_result.get("confianca_leitura", 0.0)
        
        if match_score >= 0.9:
            # Alta concordância - usa qualquer um
            final_reading = ai_reading if ai_confidence > 0.8 else ocr_reading
            status = "CONFIRMADO"
        elif ai_confidence > 0.85:
            # IA tem alta confiança - prefere IA
            final_reading = ai_reading
            status = "IA_PREFERIDO"
        elif match_score >= 0.7:
            # Concordância moderada
            final_reading = ai_reading if ai_confidence > 0.7 else ocr_reading
            status = "PARCIAL"
        else:
            # Discordância - precisa revisão manual
            final_reading = ocr_reading  # Mantém OCR como padrão
            status = "DIVERGENTE"
        
        return {
            "status": status,
            "match_score": round(match_score, 2),
            "ocr_reading": ocr_reading,
            "ai_reading": ai_reading,
            "ai_confidence": ai_confidence,
            "final_reading": final_reading,
            "adulteracao_detectada": ai_result.get("adulteracao_detectada", False),
            "sinais_adulteracao": ai_result.get("sinais_adulteracao", []),
            "tipo_gravacao_ai": ai_result.get("tipo_gravacao", ""),
            "requer_revisao_manual": status == "DIVERGENTE"
        }


# Singleton para uso global
_ai_vision_service: Optional[AIVisionService] = None


def get_ai_vision_service() -> AIVisionService:
    """Retorna instância singleton do serviço."""
    global _ai_vision_service
    if _ai_vision_service is None:
        _ai_vision_service = AIVisionService()
    return _ai_vision_service
