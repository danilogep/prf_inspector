"""
PRF Honda Motor Inspector - Especificações de Motor Honda
=========================================================
VERSÃO REFATORADA v5.16

CORREÇÕES:
1. Prefixos expandidos com base nas imagens de referência fornecidas
2. Regex corrigido para capturar todos os formatos válidos
3. Adicionada validação mais robusta
4. Corrigido bug off-by-one na extração do serial
5. Melhorada documentação e tipagem

NOVOS PREFIXOS IDENTIFICADOS NAS IMAGENS:
- KD03E3, KD08E1, KD08E2
- KC08E1, KC22E1, KF34E1
- JC30E7, JC96E
- MD41E0, ND11E1
- NC49E1F
"""

import re
from typing import Optional, Dict, Tuple, List, Set
from dataclasses import dataclass
from enum import Enum


class EngravingType(Enum):
    """Tipos de gravação de motor Honda."""
    ESTAMPAGEM = "ESTAMPAGEM"  # Antes de 2010
    LASER = "LASER"            # A partir de 2010
    DESCONHECIDO = "DESCONHECIDO"


@dataclass(frozen=True)
class MotorInfo:
    """Informações de um modelo de motor."""
    modelo: str
    cilindrada: int
    anos_producao: Optional[Tuple[int, int]] = None  # (inicio, fim) ou None se ainda em produção


class HondaMotorSpecs:
    """
    Regras de Negócio para Números de MOTOR Honda.
    
    Formato do Número de Motor Honda:
    - Prefixo: Código do modelo do motor (ex: MC27E, MD09E1, KD08E2)
    - Separador: Hífen (-) - pode ou não estar presente na gravação
    - Sequencial: Número de série (letra opcional + 6-7 dígitos)
    
    Exemplos reais das imagens analisadas:
    - KD08E2-S029466 (Original)
    - MD41E0-J012382 (Original)
    - NC49E1F-105588 (Original)
    - KD03E3-7008427 (Adulterado - marcas de lixamento)
    
    TIPOS DE GRAVAÇÃO:
    - ESTAMPAGEM: Antes de 2010 - caracteres sólidos, prensados no metal
    - LASER: A partir de 2010 - gravação a laser, linhas finas e precisas
    """
    
    # Ano de transição para gravação a laser
    LASER_TRANSITION_YEAR: int = 2010
    
    # Caracteres de alto risco de falsificação
    HIGH_RISK_CHARS: Set[str] = frozenset({'0', '1', '3', '4', '5', '6', '8', '9'})
    
    # Prefixos de Motor Honda válidos conhecidos
    # EXPANDIDO com base nas imagens fornecidas e padrões observados
    # Formato: prefixo -> MotorInfo(modelo, cilindrada)
    ENGINE_PREFIXES: Dict[str, Tuple[str, int]] = {
        # ========================================
        # CG Series
        # ========================================
        'MC27E': ('CG 160 Titan/Fan/Start', 160),
        'MC41E': ('CG 150 Titan/Fan', 150),
        'MC38E': ('CG 125 Fan', 125),
        'MC44E': ('CG 150', 150),
        'MC44E1': ('CG 150', 150),
        'JC30E': ('CG 125i Fan', 125),
        'JC30E7': ('CG 125i Fan', 125),  # NOVO - visto em imagens
        'JC75E': ('CG 160 Titan', 160),
        'JC79E': ('CG 160 Fan', 160),
        'JC96E': ('CG 160', 160),  # NOVO - visto em imagens
        'JC9RE': ('CG 160', 160),
        
        # ========================================
        # XRE Series
        # ========================================
        'MD09E': ('XRE 300', 300),
        'MD09E1': ('XRE 300', 300),
        'ND09E1': ('XRE 300', 300),  # Variação
        'ND11E1': ('XRE 300', 300),  # NOVO - visto em imagens
        'MD44E': ('XRE 190', 190),
        
        # ========================================
        # CB Series
        # ========================================
        'NC51E': ('CB 500F/X/R', 500),
        'NC49E': ('CB 500', 500),
        'NC49E1': ('CB 500', 500),  # NOVO
        'NC49E1F': ('CB 500F', 500),  # NOVO - visto em imagens
        'NC56E': ('CB 650F', 650),
        'NC61E': ('CB 650', 650),
        'NC61E0': ('CB 650R', 650),
        'MC52E': ('CB 300R Twister', 300),
        'MC65E': ('CB 250F Twister', 250),
        
        # ========================================
        # Bros / NXR Series
        # ========================================
        'MD37E': ('NXR 160 Bros', 160),
        'MD38E': ('XRE 190 Bros', 190),
        'MD41E': ('NXR 160 Bros', 160),
        'MD41E0': ('NXR 160 Bros', 160),  # NOVO - visto em imagens
        
        # ========================================
        # Biz Series
        # ========================================
        'KYJ': ('BIZ 125', 125),
        'JF77E': ('BIZ 110i', 110),
        'JF83E': ('BIZ 125', 125),
        
        # ========================================
        # Pop Series
        # ========================================
        'JC75E': ('POP 110i', 110),
        
        # ========================================
        # PCX / Scooters
        # ========================================
        'PC40E': ('PCX 150', 150),
        'PC44E': ('PCX 160', 160),
        'JF81E': ('Elite 125', 125),
        'JK12E': ('ADV 150', 150),
        
        # ========================================
        # Africa Twin
        # ========================================
        'NC70E': ('Africa Twin CRF1000', 1000),
        'NC75E': ('Africa Twin CRF1100', 1100),
        
        # ========================================
        # NOVOS - Identificados nas imagens fornecidas
        # Séries KC e KD (motores mais antigos/exportação)
        # ========================================
        'KC08E1': ('CG 125', 125),  # NOVO - visto em imagens
        'KC08E2': ('CG 125', 125),  # NOVO - visto em imagens
        'KC22E1': ('CG 125', 125),  # NOVO - visto em imagens
        'KD03E3': ('Motor Genérico', 0),  # NOVO - visto em adulterados
        'KD08E1': ('Sahara/XLR 125', 125),  # NOVO - visto em imagens
        'KD08E2': ('Sahara/XLR 125', 125),  # NOVO - visto em imagens
        'KF34E1': ('Titan 150', 150),  # NOVO - visto em imagens
    }
    
    # Regex CORRIGIDO para validar formato do número de motor Honda
    # MELHORIA: Suporta mais variações de prefixo
    # Grupos: (prefixo: 2-6 letras/números)(hífen opcional)(serial: letra opcional + números)
    ENGINE_NUMBER_PATTERN = re.compile(
        r'^([A-Z]{2,4}\d{0,2}[A-Z]?\d?[A-Z]?)-?([A-Z]?\d{5,8})$',
        re.IGNORECASE
    )
    
    # Regex alternativo mais permissivo para casos especiais
    ENGINE_NUMBER_PATTERN_ALT = re.compile(
        r'^([A-Z]{2}[A-Z0-9]{2,5})-?([A-Z0-9]{5,8})$',
        re.IGNORECASE
    )

    @classmethod
    def get_expected_engraving_type(cls, year: int) -> EngravingType:
        """
        Retorna o tipo de gravação esperado para o ano do veículo.
        
        Args:
            year: Ano do veículo
            
        Returns:
            EngravingType esperado
        """
        if year < 1980 or year > 2100:
            return EngravingType.DESCONHECIDO
        return EngravingType.LASER if year >= cls.LASER_TRANSITION_YEAR else EngravingType.ESTAMPAGEM

    @classmethod
    def get_expected_type(cls, year: int) -> str:
        """
        Retorna o tipo de gravação esperado como string.
        Mantido para compatibilidade com código existente.
        """
        return cls.get_expected_engraving_type(year).value

    @classmethod
    def validate_engine_format(cls, engine_number: str) -> Dict:
        """
        Valida o formato do número de motor Honda.
        
        CORREÇÕES v5.16:
        - Ordenação correta de prefixos por tamanho
        - Tratamento de casos especiais (NC49E1F)
        - Melhor extração de serial
        
        Args:
            engine_number: Número do motor (ex: MD09E1-B215797)
            
        Returns:
            Dict com status de validação e detalhes extraídos
        """
        result = {
            'valid': False,
            'original': engine_number,
            'cleaned': '',
            'prefix': None,
            'serial': None,
            'model_info': None,
            'issues': [],
            'confidence': 0.0  # NOVO: nível de confiança na validação
        }
        
        # Validação de input
        if not engine_number or not isinstance(engine_number, str):
            result['issues'].append("Número de motor vazio ou inválido")
            return result
        
        # Normaliza: remove espaços, converte para maiúsculo
        clean_number = engine_number.strip().upper().replace(' ', '')
        result['cleaned'] = clean_number
        
        # Remove hífen para análise, mas preserva informação
        has_hyphen = '-' in clean_number
        clean_for_analysis = clean_number.replace('-', '')
        
        if len(clean_for_analysis) < 8:
            result['issues'].append(f"Número muito curto: {len(clean_for_analysis)} caracteres (mínimo: 8)")
            return result
        
        if len(clean_for_analysis) > 16:
            result['issues'].append(f"Número muito longo: {len(clean_for_analysis)} caracteres (máximo: 16)")
            return result
        
        # CORREÇÃO: Ordenar prefixos por tamanho (maior primeiro)
        # Isso garante que MD09E1 seja testado antes de MD09E
        sorted_prefixes = sorted(
            cls.ENGINE_PREFIXES.keys(),
            key=lambda x: (-len(x), x)  # Ordena por tamanho decrescente, depois alfabético
        )
        
        matched_prefix = None
        for prefix in sorted_prefixes:
            if clean_for_analysis.startswith(prefix):
                matched_prefix = prefix
                break
        
        if matched_prefix:
            result['prefix'] = matched_prefix
            # CORREÇÃO: Extrair serial corretamente
            result['serial'] = clean_for_analysis[len(matched_prefix):]
            result['model_info'] = cls.ENGINE_PREFIXES[matched_prefix]
            result['valid'] = True
            result['confidence'] = 0.95  # Alta confiança - prefixo conhecido
        else:
            # Tenta match com regex principal
            match = cls.ENGINE_NUMBER_PATTERN.match(clean_for_analysis)
            
            if not match:
                # Tenta regex alternativo
                match = cls.ENGINE_NUMBER_PATTERN_ALT.match(clean_for_analysis)
            
            if match:
                result['prefix'] = match.group(1).upper()
                result['serial'] = match.group(2).upper()
                result['valid'] = True
                result['confidence'] = 0.70  # Média confiança - padrão reconhecido
                result['issues'].append(
                    f"Prefixo '{result['prefix']}' não cadastrado no banco de dados (pode ser válido)"
                )
            else:
                result['issues'].append(
                    f"Formato '{clean_number}' não reconhecido como padrão Honda"
                )
                result['confidence'] = 0.0
        
        # Validações adicionais do serial
        if result['serial']:
            serial = result['serial']
            
            # Extrai apenas dígitos para validação
            serial_digits = ''.join(c for c in serial if c.isdigit())
            
            if len(serial_digits) < 5:
                result['issues'].append(
                    f"Serial muito curto: {len(serial_digits)} dígitos (mínimo: 5)"
                )
                result['valid'] = False
                result['confidence'] *= 0.5
            
            if len(serial_digits) > 8:
                result['issues'].append(
                    f"Serial muito longo: {len(serial_digits)} dígitos (máximo: 8)"
                )
                result['confidence'] *= 0.8
            
            # Verifica caracteres inválidos no serial
            invalid_chars = set(serial) - set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            if invalid_chars:
                result['issues'].append(
                    f"Caracteres inválidos no serial: {invalid_chars}"
                )
                result['confidence'] *= 0.7
        
        return result

    @classmethod
    def is_high_risk_char(cls, char: str) -> bool:
        """
        Verifica se o caractere está na lista de alto risco de falsificação.
        
        Args:
            char: Caractere a verificar
            
        Returns:
            True se for caractere de alto risco
        """
        return char.upper() in cls.HIGH_RISK_CHARS

    @classmethod
    def get_high_risk_chars_in_code(cls, code: str) -> List[Tuple[int, str]]:
        """
        Retorna lista de caracteres de alto risco encontrados no código.
        
        Args:
            code: Código do motor
            
        Returns:
            Lista de tuplas (posição, caractere)
        """
        return [
            (i, char) 
            for i, char in enumerate(code) 
            if cls.is_high_risk_char(char)
        ]

    @classmethod
    def get_prefix_info(cls, prefix: str) -> Optional[Tuple[str, int]]:
        """
        Retorna informações do modelo para um prefixo.
        
        Args:
            prefix: Prefixo do motor
            
        Returns:
            Tupla (modelo, cilindrada) ou None
        """
        # Tenta match exato primeiro
        if prefix in cls.ENGINE_PREFIXES:
            return cls.ENGINE_PREFIXES[prefix]
        
        # Tenta match parcial (para casos como NC49E1F -> NC49E1)
        for known_prefix in sorted(cls.ENGINE_PREFIXES.keys(), key=len, reverse=True):
            if prefix.startswith(known_prefix):
                return cls.ENGINE_PREFIXES[known_prefix]
        
        return None

    @classmethod
    def normalize_ocr_result(cls, ocr_text: str) -> str:
        """
        Normaliza resultado do OCR, corrigindo erros comuns.
        
        CORREÇÕES APLICADAS:
        - O (letra) -> 0 (zero) em contexto numérico
        - I (letra) -> 1 (um) em contexto numérico
        - Remove caracteres inválidos
        
        Args:
            ocr_text: Texto bruto do OCR
            
        Returns:
            Texto normalizado
        """
        if not ocr_text:
            return ""
        
        # Remove espaços e converte para maiúsculo
        text = ocr_text.strip().upper().replace(' ', '')
        
        # Correção contextual de O -> 0
        # Em seriais (após o prefixo), O geralmente é 0
        result = []
        in_serial = False
        
        for i, char in enumerate(text):
            # Detecta início do serial (após letra E seguida de número ou hífen)
            if not in_serial and i > 0:
                if (text[i-1] in 'E0123456789' and char in '-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
                    in_serial = True
            
            if in_serial:
                if char == 'O':
                    result.append('0')  # Corrige O -> 0 no serial
                elif char == 'I':
                    result.append('1')  # Corrige I -> 1 no serial
                else:
                    result.append(char)
            else:
                result.append(char)
        
        return ''.join(result)

    @classmethod
    def calculate_similarity(cls, code1: str, code2: str) -> float:
        """
        Calcula similaridade entre dois códigos de motor.
        Útil para comparação com banco de dados.
        
        Args:
            code1: Primeiro código
            code2: Segundo código
            
        Returns:
            Score de similaridade (0.0 a 1.0)
        """
        if not code1 or not code2:
            return 0.0
        
        # Normaliza ambos
        c1 = code1.upper().replace('-', '').replace(' ', '')
        c2 = code2.upper().replace('-', '').replace(' ', '')
        
        if c1 == c2:
            return 1.0
        
        # Calcula distância de Levenshtein simplificada
        if len(c1) != len(c2):
            # Penaliza diferença de tamanho
            len_penalty = abs(len(c1) - len(c2)) / max(len(c1), len(c2))
        else:
            len_penalty = 0
        
        # Conta caracteres diferentes
        min_len = min(len(c1), len(c2))
        matches = sum(1 for i in range(min_len) if c1[i] == c2[i])
        
        similarity = matches / max(len(c1), len(c2))
        
        return max(0.0, similarity - len_penalty)


# Alias para compatibilidade com código existente
def get_expected_type(year: int) -> str:
    """Função de compatibilidade."""
    return HondaMotorSpecs.get_expected_type(year)


def validate_engine_format(engine_number: str) -> Dict:
    """Função de compatibilidade."""
    return HondaMotorSpecs.validate_engine_format(engine_number)
