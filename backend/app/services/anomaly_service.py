"""
Serviço de Detecção de Anomalias Forenses v3.0
==============================================
Com integração Claude Vision AI para análise de tipo de gravação.

DETECÇÃO AUTOMÁTICA + IA:
1. Análise computacional (OpenCV) - rápida, gratuita
2. Se confiança < 70% ou inconsistência → Claude Vision AI
3. IA analisa características visuais da gravação

REGRA CRÍTICA:
- Antes de 2010: ESTAMPAGEM (caracteres em relevo)
- 2010 em diante: LASER (micropuntos)

Custo estimado: ~R$0.05-0.10 por análise com IA
"""

import cv2
import numpy as np
import base64
import os
import re
from typing import Dict, List, Optional
from app.services.font_analyzer import FontAnalyzer
from app.core.logger import logger


class AnomalyService:
    
    # Ano de transição
    LASER_TRANSITION_YEAR = 2010
    
    # Thresholds
    CONFIDENCE_THRESHOLD = 0.70  # Abaixo disso, usa IA
    
    def __init__(self):
        self.font_analyzer = FontAnalyzer()
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY', '')
        self.use_claude = bool(self.claude_api_key)
        
        if self.use_claude:
            logger.info("✓ Claude Vision AI habilitada para análise forense")
        else:
            logger.warning("⚠ Claude Vision não configurada - usando apenas análise computacional")
    
    def analyze(
        self, 
        image_bytes: bytes,
        ocr_metrics: List[dict],
        expected_type: str,
        char_images: Optional[List] = None,
        year: int = None
    ) -> Dict:
        """
        Análise forense completa com IA.
        """
        result = {
            'status': 'OK',
            'detected_type': 'DESCONHECIDO',
            'expected_type': expected_type,
            'type_match': True,
            'year_consistency': True,
            'avg_dots': 0.0,
            'alignment_ok': True,
            'characters': [],
            'gap_analysis': [],
            'high_risk_alerts': [],
            'outliers': [],
            'ai_analysis': None
        }
        
        try:
            # 1. DETECÇÃO COMPUTACIONAL (rápida)
            cv_analysis = self._detect_type_opencv(image_bytes)
            result['detected_type'] = cv_analysis['type']
            result['avg_dots'] = cv_analysis['avg_dots']
            result['detection_confidence'] = cv_analysis['confidence']
            result['cv_details'] = cv_analysis['details']
            
            logger.info(f"OpenCV: {cv_analysis['type']} (confiança: {cv_analysis['confidence']:.0%})")
            
            # 2. DECISÃO: Usar IA?
            use_ai = False
            ai_reason = None
            
            # Confiança baixa
            if cv_analysis['confidence'] < self.CONFIDENCE_THRESHOLD:
                use_ai = True
                ai_reason = f"Confiança baixa ({cv_analysis['confidence']:.0%})"
            
            # Inconsistência com ano (situação crítica)
            if cv_analysis['type'] != 'DESCONHECIDO' and cv_analysis['type'] != expected_type:
                use_ai = True
                ai_reason = f"Inconsistência detectada: {cv_analysis['type']} vs esperado {expected_type}"
            
            # 3. ANÁLISE COM IA (se necessário)
            if use_ai and self.use_claude:
                logger.info(f"🤖 Acionando Claude Vision: {ai_reason}")
                ai_result = self._analyze_with_claude(image_bytes, year, expected_type)
                result['ai_analysis'] = ai_result
                
                if ai_result.get('success'):
                    # IA tem prioridade sobre análise computacional
                    result['detected_type'] = ai_result['detected_type']
                    result['detection_confidence'] = ai_result['confidence']
                    result['ai_reasoning'] = ai_result.get('reasoning', '')
                    logger.info(f"Claude Vision: {ai_result['detected_type']} ({ai_result['confidence']:.0%})")
            
            # 4. VALIDAÇÃO: Tipo vs Ano
            if result['detected_type'] != 'DESCONHECIDO':
                if result['detected_type'] != expected_type:
                    result['type_match'] = False
                    result['outliers'].append({
                        'char': '*',
                        'position': 0,
                        'severity': 'CRÍTICO',
                        'reason': f"⚠️ INCONSISTÊNCIA: Gravação {result['detected_type']} detectada, esperado {expected_type} para ano {year}"
                    })
                    result['high_risk_alerts'].append(
                        f"🚨 ALERTA CRÍTICO: Tipo de gravação incompatível com ano informado!"
                    )
            
            # 5. Análise de alinhamento
            if ocr_metrics:
                alignment_issues = self._analyze_alignment(ocr_metrics)
                if alignment_issues:
                    result['alignment_ok'] = False
                    result['outliers'].extend(alignment_issues)
            
            # 6. Análise tipográfica
            if char_images and len(self.font_analyzer.get_available_templates()) > 0:
                font_result = self.font_analyzer.analyze_all_characters(char_images)
                result['characters'] = font_result.get('characters', [])
                result['high_risk_alerts'].extend(font_result.get('alerts', []))
            
            # 7. Status final
            result['status'] = self._determine_status(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro análise forense: {e}")
            result['status'] = 'ERRO'
            return result
    
    def _detect_type_opencv(self, image_bytes: bytes) -> Dict:
        """
        Detecção computacional com OpenCV.
        
        LASER:
        - Linhas finas e precisas
        - Alta densidade de pequenos contornos (micropuntos)
        - Contraste uniforme
        - Sem sombras de relevo
        
        ESTAMPAGEM:
        - Linhas mais grossas
        - Menos contornos pequenos
        - Sombras características do relevo
        - Maior variação de intensidade
        """
        result = {
            'type': 'DESCONHECIDO',
            'confidence': 0.0,
            'avg_dots': 0,
            'details': {}
        }
        
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return result
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # === Métricas ===
            
            # 1. Bordas
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # 2. Espessura de linha
            kernel = np.ones((3, 3), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=1)
            eroded = cv2.erode(edges, kernel, iterations=1)
            thickness_ratio = np.sum(dilated > 0) / (np.sum(eroded > 0) + 1)
            
            # 3. Textura (variância local)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            variance = np.var(gray.astype(float) - blur.astype(float))
            
            # 4. Gradiente (sombras)
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient = np.sqrt(sobelx**2 + sobely**2)
            gradient_std = np.std(gradient) / (np.mean(gradient) + 1)
            
            # 5. Micropuntos (contornos pequenos)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            small_contours = len([c for c in contours if 5 < cv2.contourArea(c) < 100])
            
            result['details'] = {
                'edge_density': round(edge_density, 4),
                'thickness_ratio': round(thickness_ratio, 2),
                'texture_variance': round(variance, 2),
                'gradient_std': round(gradient_std, 2),
                'small_contours': small_contours
            }
            result['avg_dots'] = small_contours
            
            # === Pontuação LASER ===
            laser_score = 0
            max_score = 100
            
            # Bordas finas (LASER tem mais)
            if edge_density > 0.08:
                laser_score += 25
            elif edge_density > 0.05:
                laser_score += 15
            
            # Linhas finas
            if thickness_ratio < 2.0:
                laser_score += 25
            elif thickness_ratio < 2.5:
                laser_score += 15
            
            # Textura uniforme
            if variance < 300:
                laser_score += 20
            elif variance < 500:
                laser_score += 10
            
            # Sem sombras (gradiente uniforme)
            if gradient_std < 1.2:
                laser_score += 15
            elif gradient_std < 1.5:
                laser_score += 8
            
            # Micropuntos
            if small_contours > 100:
                laser_score += 15
            elif small_contours > 50:
                laser_score += 8
            
            # === Decisão ===
            if laser_score >= 65:
                result['type'] = 'LASER'
                result['confidence'] = min(laser_score / max_score, 0.95)
            elif laser_score <= 35:
                result['type'] = 'ESTAMPAGEM'
                result['confidence'] = min((max_score - laser_score) / max_score, 0.95)
            else:
                result['type'] = 'DESCONHECIDO'
                result['confidence'] = 0.5
            
            result['details']['laser_score'] = laser_score
            
            return result
            
        except Exception as e:
            logger.error(f"Erro OpenCV: {e}")
            return result
    
    def _analyze_with_claude(self, image_bytes: bytes, year: int, expected_type: str) -> Dict:
        """
        Análise com Claude Vision AI.
        
        A IA analisa visualmente e determina:
        1. Tipo de gravação (LASER ou ESTAMPAGEM)
        2. Confiança na análise
        3. Razões para a conclusão
        """
        result = {
            'success': False,
            'detected_type': 'DESCONHECIDO',
            'confidence': 0.0,
            'reasoning': ''
        }
        
        try:
            import httpx
            
            b64 = base64.b64encode(image_bytes).decode()
            media_type = "image/png" if image_bytes[:4] == b'\x89PNG' else "image/jpeg"
            
            prompt = f"""Você é um especialista forense em identificação veicular da PRF (Polícia Rodoviária Federal).

Analise esta imagem de número de motor Honda e determine o TIPO DE GRAVAÇÃO:

**ESTAMPAGEM (pré-2010):**
- Caracteres em RELEVO (afundados no metal)
- Bordas mais GROSSAS e irregulares
- Presença de SOMBRAS devido ao relevo
- Aparência mais "pesada" e profunda

**LASER (pós-2010):**
- Caracteres formados por MICROPUNTOS
- Linhas FINAS e precisas
- SEM relevo, gravação superficial
- Aparência mais "limpa" e uniforme

**CONTEXTO:**
- Ano informado do veículo: {year}
- Tipo esperado para este ano: {expected_type}

**RESPONDA EXATAMENTE NESTE FORMATO:**
TIPO: [LASER ou ESTAMPAGEM]
CONFIANÇA: [0-100]%
RAZÃO: [explicação breve das características observadas]

Seja objetivo e técnico na análise."""

            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.claude_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 300,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }]
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                content = response.json()['content'][0]['text']
                result = self._parse_claude_response(content)
                result['success'] = True
                result['raw_response'] = content
                logger.debug(f"Claude response: {content}")
            else:
                logger.error(f"Claude API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erro Claude Vision: {e}")
        
        return result
    
    def _parse_claude_response(self, text: str) -> Dict:
        """Parseia resposta do Claude."""
        result = {
            'detected_type': 'DESCONHECIDO',
            'confidence': 0.5,
            'reasoning': ''
        }
        
        try:
            lines = text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                # TIPO
                if line.upper().startswith('TIPO:'):
                    tipo = line.split(':', 1)[1].strip().upper()
                    if 'LASER' in tipo:
                        result['detected_type'] = 'LASER'
                    elif 'ESTAMPAGEM' in tipo or 'ESTAMPA' in tipo:
                        result['detected_type'] = 'ESTAMPAGEM'
                
                # CONFIANÇA
                elif line.upper().startswith('CONFIANÇA:') or line.upper().startswith('CONFIANCA:'):
                    conf_text = line.split(':', 1)[1].strip()
                    # Extrai número
                    numbers = re.findall(r'(\d+)', conf_text)
                    if numbers:
                        result['confidence'] = int(numbers[0]) / 100.0
                
                # RAZÃO
                elif line.upper().startswith('RAZÃO:') or line.upper().startswith('RAZAO:'):
                    result['reasoning'] = line.split(':', 1)[1].strip()
            
        except Exception as e:
            logger.error(f"Erro parsing: {e}")
        
        return result
    
    def _analyze_alignment(self, metrics: List[dict]) -> List[Dict]:
        """Detecta desalinhamento."""
        issues = []
        
        if len(metrics) < 3:
            return issues
        
        centers = [m.get('center_y', 0) for m in metrics if m.get('center_y', 0) > 0]
        heights = [m.get('height', 0) for m in metrics if m.get('height', 0) > 0]
        
        if not centers or not heights:
            return issues
        
        median_center = np.median(centers)
        median_height = np.median(heights)
        tolerance = median_height * 0.15
        
        for m in metrics:
            center_y = m.get('center_y', 0)
            if center_y == 0:
                continue
            
            deviation = abs(center_y - median_center)
            if deviation > tolerance:
                issues.append({
                    'char': m.get('char', '?'),
                    'position': m.get('index', 0) + 1,
                    'severity': 'MÉDIO',
                    'reason': f"Desalinhamento: {deviation:.1f}px"
                })
        
        return issues
    
    def _determine_status(self, result: Dict) -> str:
        """Status final."""
        if not result.get('type_match', True):
            return 'SUSPEITO'
        
        outliers = len(result.get('outliers', []))
        alerts = len(result.get('high_risk_alerts', []))
        critical = sum(1 for o in result.get('outliers', []) if o.get('severity') == 'CRÍTICO')
        
        if critical > 0:
            return 'SUSPEITO'
        elif outliers > 3 or alerts > 2:
            return 'SUSPEITO'
        elif outliers > 0 or alerts > 0:
            return 'VERIFICAR'
        elif not result.get('alignment_ok', True):
            return 'ATENÇÃO'
        
        return 'OK'
    
    def get_expected_type_for_year(self, year: int) -> str:
        """Retorna tipo esperado para o ano."""
        if year < self.LASER_TRANSITION_YEAR:
            return 'ESTAMPAGEM'
        return 'LASER'
