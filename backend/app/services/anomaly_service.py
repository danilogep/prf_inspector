import cv2
import numpy as np
from typing import Dict, List, Optional
from app.services.font_analyzer import FontAnalyzer
from app.core.config import settings
from app.core.logger import logger
from app.database.honda_motor_specs import HondaMotorSpecs


class AnomalyService:
    """
    Serviço de detecção de anomalias forenses em gravações de motor.
    
    Análises realizadas:
    1. Densidade de pontos (micropunção vs estampagem)
    2. Alinhamento vertical dos caracteres
    3. Conformidade tipográfica (comparação com fonte Honda)
    4. Detecção de vazamentos/gaps característicos
    5. Análise especial de caracteres de alto risco (0,1,3,4,9)
    """
    
    def __init__(self):
        self.font_analyzer = FontAnalyzer()
    
    def analyze(
        self, 
        image_bytes: bytes,
        ocr_metrics: List[dict],
        expected_type: str,
        char_images: Optional[List] = None
    ) -> Dict:
        """
        Realiza análise forense completa da gravação do motor.
        
        Args:
            image_bytes: Bytes da imagem original
            ocr_metrics: Métricas do OCR (caracteres, posições, etc)
            expected_type: 'MICROPOINT' ou 'STAMPED'
            char_images: Lista de (imagem, caractere, posição)
        """
        result = {
            'status': 'OK',
            'detected_type': 'UNKNOWN',
            'avg_dots': 0.0,
            'alignment_ok': True,
            'characters': [],
            'gap_analysis': [],
            'high_risk_alerts': [],
            'outliers': []
        }
        
        try:
            if not ocr_metrics:
                result['status'] = 'INCONCLUSIVO'
                result['outliers'].append({
                    'char': '-',
                    'position': 0,
                    'reason': 'Nenhum caractere detectado pelo OCR'
                })
                return result
            
            # 1. Análise de tipo de gravação (micropunção vs estampagem)
            dot_analysis = self._analyze_marking_type(ocr_metrics)
            result['detected_type'] = dot_analysis['type']
            result['avg_dots'] = dot_analysis['avg_dots']
            
            # Se tipo detectado diferente do esperado, já é suspeito
            if result['detected_type'] != expected_type and result['detected_type'] != 'UNKNOWN':
                result['outliers'].append({
                    'char': '*',
                    'position': 0,
                    'reason': f"Tipo de gravação: detectado {result['detected_type']}, esperado {expected_type}"
                })
            
            # 2. Análise de alinhamento
            alignment_issues = self._analyze_alignment(ocr_metrics)
            if alignment_issues:
                result['alignment_ok'] = False
                result['outliers'].extend(alignment_issues)
            
            # 3. Análise de densidade por caractere
            density_issues = self._analyze_density_outliers(ocr_metrics, dot_analysis['median_dots'])
            result['outliers'].extend(density_issues)
            
            # 4. Análise tipográfica com detecção de vazamentos
            if char_images and len(self.font_analyzer.get_available_templates()) > 0:
                font_result = self.font_analyzer.analyze_all_characters(char_images)
                result['characters'] = font_result.get('characters', [])
                result['gap_analysis'] = [
                    c.get('gap_analysis', {}) 
                    for c in font_result.get('characters', [])
                    if c.get('gap_analysis')
                ]
                result['high_risk_alerts'].extend(font_result.get('alerts', []))
                
                # Adiciona caracteres suspeitos da análise tipográfica
                for char_analysis in font_result.get('characters', []):
                    if char_analysis.get('is_suspicious'):
                        issues = char_analysis.get('issues', [])
                        for issue in issues:
                            result['outliers'].append({
                                'char': char_analysis['char'],
                                'position': char_analysis.get('position', 0),
                                'reason': issue
                            })
            else:
                # Se não tem templates, faz análise básica de caracteres de alto risco
                result['high_risk_alerts'] = self._analyze_high_risk_basic(ocr_metrics)
            
            # 5. Remove duplicatas e determina status final
            result['outliers'] = self._deduplicate_outliers(result['outliers'])
            result['status'] = self._determine_status(result, expected_type)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na análise forense: {e}")
            result['status'] = 'ERRO'
            result['outliers'].append({
                'char': '-',
                'position': 0,
                'reason': f"Erro interno: {str(e)}"
            })
            return result
    
    def _analyze_marking_type(self, metrics: List[dict]) -> Dict:
        """Analisa tipo de marcação baseado na densidade de pontos."""
        if not metrics:
            return {'type': 'UNKNOWN', 'avg_dots': 0, 'median_dots': 0}
        
        dots = [m.get('dot_count', 0) for m in metrics]
        avg_dots = np.mean(dots) if dots else 0
        median_dots = np.median(dots) if dots else 0
        
        # Se média de pontos > threshold, é micropunção
        if avg_dots > settings.MICROPOINT_DOT_THRESHOLD:
            detected_type = 'MICROPOINT'
        elif avg_dots < 1.5:
            detected_type = 'STAMPED'
        else:
            detected_type = 'UNKNOWN'
        
        return {
            'type': detected_type,
            'avg_dots': round(avg_dots, 2),
            'median_dots': median_dots
        }
    
    def _analyze_alignment(self, metrics: List[dict]) -> List[Dict]:
        """Detecta caracteres desalinhados verticalmente."""
        issues = []
        
        if len(metrics) < 3:
            return issues
        
        # Usa mediana como referência
        heights = [m.get('height', 0) for m in metrics if m.get('height', 0) > 0]
        centers = [m.get('center_y', 0) for m in metrics if m.get('center_y', 0) > 0]
        
        if not heights or not centers:
            return issues
        
        median_height = np.median(heights)
        median_center = np.median(centers)
        tolerance = median_height * settings.ALIGNMENT_TOLERANCE
        
        for m in metrics:
            center_y = m.get('center_y', 0)
            if center_y == 0:
                continue
            
            deviation = abs(center_y - median_center)
            if deviation > tolerance:
                issues.append({
                    'char': m.get('char', '?'),
                    'position': m.get('index', 0) + 1,
                    'reason': f"Desalinhamento vertical: {deviation:.1f}px da linha base"
                })
        
        return issues
    
    def _analyze_density_outliers(self, metrics: List[dict], median_dots: float) -> List[Dict]:
        """Detecta caracteres com densidade de pontos anômala."""
        issues = []
        
        # Só analisa se for micropunção
        if median_dots < settings.MICROPOINT_DOT_THRESHOLD:
            return issues
        
        tolerance = median_dots * settings.DENSITY_TOLERANCE
        
        for m in metrics:
            dots = m.get('dot_count', 0)
            deviation = abs(dots - median_dots)
            
            if deviation > tolerance and median_dots > 0:
                direction = "acima" if dots > median_dots else "abaixo"
                issues.append({
                    'char': m.get('char', '?'),
                    'position': m.get('index', 0) + 1,
                    'reason': f"Densidade anômala: {dots} pontos ({direction} da média {median_dots:.0f})"
                })
        
        return issues
    
    def _analyze_high_risk_basic(self, metrics: List[dict]) -> List[str]:
        """Análise básica de caracteres de alto risco quando não há templates."""
        alerts = []
        
        for m in metrics:
            char = m.get('char', '')
            if not char:
                continue
            
            for c in char:
                if HondaMotorSpecs.is_high_risk_char(c):
                    possible = HondaMotorSpecs.get_possible_forgeries(c)
                    if possible:
                        alerts.append(
                            f"Caractere '{c}' (alto risco) - pode ser adulteração de: {', '.join(possible)}"
                        )
        
        return alerts
    
    def _deduplicate_outliers(self, outliers: List[Dict]) -> List[Dict]:
        """Remove outliers duplicados."""
        seen = {}
        
        for outlier in outliers:
            key = (outlier.get('char', ''), outlier.get('position', 0))
            
            if key not in seen:
                seen[key] = outlier
            else:
                # Concatena razões
                existing = seen[key]
                existing['reason'] = f"{existing['reason']}; {outlier['reason']}"
        
        return list(seen.values())
    
    def _determine_status(self, result: Dict, expected_type: str) -> str:
        """Determina status final baseado em todas as análises."""
        score = 0
        
        # Conta outliers
        score += len(result.get('outliers', [])) * 10
        
        # Penaliza divergência de tipo
        if result.get('detected_type') != expected_type and result.get('detected_type') != 'UNKNOWN':
            score += 20
        
        # Penaliza problemas de alinhamento
        if not result.get('alignment_ok', True):
            score += 10
        
        # Penaliza alertas de alto risco
        high_risk_count = len(result.get('high_risk_alerts', []))
        score += high_risk_count * 15
        
        # Penaliza problemas nos vazamentos
        gap_issues = sum(
            1 for gap in result.get('gap_analysis', [])
            if not gap.get('gaps_match', True)
        )
        score += gap_issues * 20
        
        if score == 0:
            return 'OK'
        elif score <= 20:
            return 'ATENÇÃO'
        else:
            return 'SUSPEITO'
