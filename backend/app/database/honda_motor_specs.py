import re
from typing import Optional, Dict, Tuple, List

class HondaMotorSpecs:
    """
    Regras de Negócio para Números de MOTOR Honda.
    
    Formato do Número de Motor Honda:
    - Prefixo: Código do modelo do motor (ex: MC27E, MD09E1)
    - Separador: Hífen (-) - pode ou não estar presente na gravação
    - Sequencial: Número de série (6-8 dígitos)
    
    Exemplos reais:
    - MC27E-1009153 (CG 160)
    - MD09E1-B215797 (XRE 300)
    """
    
    # Prefixos de Motor Honda válidos conhecidos
    # Formato: prefixo -> (modelo_moto, cilindrada)
    ENGINE_PREFIXES: Dict[str, Tuple[str, int]] = {
        # CG Series
        'MC27E': ('CG 160 Titan/Fan/Start', 160),
        'MC41E': ('CG 150 Titan/Fan', 150),
        'MC38E': ('CG 125 Fan', 125),
        'JC30E': ('CG 125i Fan', 125),
        'JC75E': ('CG 160 Titan', 160),
        'JC79E': ('CG 160 Fan', 160),
        
        # XRE Series
        'MD09E': ('XRE 300', 300),
        'MD09E1': ('XRE 300', 300),
        'MD44E': ('XRE 190', 190),
        
        # CB Series
        'NC51E': ('CB 500F/X/R', 500),
        'NC56E': ('CB 650F', 650),
        'MC52E': ('CB 300R Twister', 300),
        'MC65E': ('CB 250F Twister', 250),
        
        # Bros
        'MD37E': ('NXR 160 Bros', 160),
        'MD38E': ('XRE 190 Bros', 190),
        
        # Biz
        'KYJ': ('BIZ 125', 125),
        'JF77E': ('BIZ 110i', 110),
        'JF83E': ('BIZ 125', 125),
        
        # Pop
        'JC75E': ('POP 110i', 110),
        
        # PCX / Scooters
        'PC40E': ('PCX 150', 150),
        'PC44E': ('PCX 160', 160),
        'JF81E': ('Elite 125', 125),
        'JK12E': ('ADV 150', 150),
        
        # Outras
        'NC70E': ('Africa Twin CRF1000', 1000),
        'NC75E': ('Africa Twin CRF1100', 1100),
    }
    
    # Regex para validar formato do número de motor Honda
    # Grupos: (prefixo)(hífen opcional)(serial)
    ENGINE_NUMBER_PATTERN = re.compile(
        r'^([A-Z]{2,4}\d{0,2}[A-Z]?\d?)-?([A-Z]?\d{6,8})$',
        re.IGNORECASE
    )
    
    # Caracteres proibidos (confundem com números)
    FORBIDDEN_CHARS = {'I', 'O', 'Q'}
    
    # Caracteres de alto risco para falsificação
    HIGH_RISK_CHARS = ['0', '1', '3', '4', '9']
    
    # Características dos "vazamentos" (gaps) na fonte Honda
    # Baseado na análise da imagem de referência
    # Formato: char -> lista de descrições dos gaps esperados
    FONT_GAPS = {
        '0': ['oval fechada sem gaps internos', 'proporção altura/largura ~1.5'],
        '1': ['base reta', 'topo com serifa pequena à esquerda'],
        '2': ['curva superior fechada', 'base horizontal'],
        '3': ['duas curvas abertas à esquerda', 'ponto central proeminente'],
        '4': ['gap aberto no encontro das linhas', 'linha vertical não toca horizontal'],
        '5': ['topo horizontal', 'curva inferior aberta à esquerda'],
        '6': ['curva superior aberta', 'círculo inferior fechado'],
        '7': ['linha horizontal no topo', 'diagonal sem serifa'],
        '8': ['dois círculos empilhados', 'proporção superior menor'],
        '9': ['círculo superior fechado', 'cauda curva característica'],
    }

    @staticmethod
    def get_expected_marking_type(year: int) -> str:
        """
        Determina o tipo de marcação esperado baseado no ano.
        - Antes de 2010: Estampagem (STAMPED) - caracteres sólidos
        - A partir de 2010: Laser/Micropunção (MICROPOINT) - formado por pontos
        """
        return "MICROPOINT" if year >= 2010 else "STAMPED"

    @staticmethod
    def validate_engine_format(engine_number: str) -> Dict:
        """
        Valida o formato do número de motor Honda.
        
        Args:
            engine_number: Número do motor (ex: MC27E-1009153)
            
        Returns:
            Dict com status de validação e detalhes extraídos
        """
        # Remove espaços e normaliza
        clean_number = engine_number.strip().upper().replace(' ', '')
        
        result = {
            'valid': False,
            'original': engine_number,
            'cleaned': clean_number,
            'prefix': None,
            'serial': None,
            'model_info': None,
            'issues': []
        }
        
        if not clean_number:
            result['issues'].append("Número de motor vazio")
            return result
        
        # Verifica caracteres proibidos
        for char in HondaMotorSpecs.FORBIDDEN_CHARS:
            if char in clean_number:
                result['issues'].append(
                    f"Caractere proibido '{char}' encontrado (confunde com número)"
                )
        
        # Tenta fazer match com o padrão
        match = HondaMotorSpecs.ENGINE_NUMBER_PATTERN.match(clean_number)
        
        if not match:
            result['issues'].append(
                f"Formato '{clean_number}' não reconhecido como padrão Honda"
            )
            # Tenta extrair prefixo mesmo assim
            for known_prefix in HondaMotorSpecs.ENGINE_PREFIXES.keys():
                if clean_number.startswith(known_prefix):
                    result['prefix'] = known_prefix
                    result['serial'] = clean_number[len(known_prefix):].lstrip('-')
                    result['model_info'] = HondaMotorSpecs.ENGINE_PREFIXES[known_prefix]
                    break
            return result
        
        prefix = match.group(1).upper()
        serial = match.group(2).upper()
        
        result['prefix'] = prefix
        result['serial'] = serial
        
        # Verifica se o prefixo é conhecido
        if prefix in HondaMotorSpecs.ENGINE_PREFIXES:
            result['model_info'] = HondaMotorSpecs.ENGINE_PREFIXES[prefix]
            result['valid'] = True
        else:
            # Tenta match parcial (variações de prefixo)
            for known_prefix, info in HondaMotorSpecs.ENGINE_PREFIXES.items():
                if prefix.startswith(known_prefix[:3]) or known_prefix.startswith(prefix[:3]):
                    result['model_info'] = info
                    result['issues'].append(
                        f"Prefixo '{prefix}' similar a '{known_prefix}' - verificar manualmente"
                    )
                    result['valid'] = True
                    break
            
            if result['model_info'] is None:
                result['issues'].append(
                    f"Prefixo '{prefix}' não cadastrado no banco de dados"
                )
        
        # Valida tamanho do serial
        serial_digits_only = ''.join(c for c in serial if c.isdigit())
        if len(serial_digits_only) < 6:
            result['issues'].append(
                f"Serial muito curto: {len(serial_digits_only)} dígitos (mínimo: 6)"
            )
            result['valid'] = False
        
        return result

    @staticmethod
    def is_high_risk_char(char: str) -> bool:
        """Verifica se o caractere está na lista de alto risco de falsificação."""
        return char in HondaMotorSpecs.HIGH_RISK_CHARS

    @staticmethod
    def get_font_gap_info(char: str) -> List[str]:
        """Retorna informações sobre os gaps esperados na fonte Honda para o caractere."""
        return HondaMotorSpecs.FONT_GAPS.get(char, [])

    @staticmethod
    def get_possible_forgeries(char: str) -> List[str]:
        """
        Retorna caracteres que podem ter sido adulterados para parecer o caractere informado.
        Baseado na imagem de referência de FAKES.
        """
        forgery_map = {
            '0': ['6', '8', '9'],      # 0 pode vir de 6, 8 ou 9 adulterado
            '1': ['7', '4'],            # 1 pode vir de 7 ou 4
            '3': ['8'],                 # 3 pode vir de 8
            '4': ['9', '1'],            # 4 pode vir de 9 ou 1
            '9': ['8', '0', '4'],       # 9 pode vir de 8, 0 ou 4
            '6': ['0', '8'],            # 6 pode vir de 0 ou 8
            '8': ['0', '3', '6', '9'],  # 8 pode vir de vários
        }
        return forgery_map.get(char, [])
