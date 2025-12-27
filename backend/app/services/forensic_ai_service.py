"""
Serviço de Análise Forense com IA v5.10
=======================================
CORREÇÕES v5.10:
- Distinção clara entre M e N
- CORRIGIDO: Usa apenas campos que existem na tabela
- Mantém estrutura original do _save_analysis
"""

import base64
import re
import json
import httpx
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from app.core.logger import logger
from app.core.config import settings


class ForensicAIService:
    """Análise forense v5.10 - Correção M/N + Campos DB"""
    
    LASER_TRANSITION_YEAR = 2010
    
    # Números que fraudadores mais erram
    HIGH_RISK_CHARS = ['0', '1', '3', '4', '9']
    
    KNOWN_PREFIXES = {
        'JC9RE': ('CG 160', 160), 'JC96E': ('CG 160', 160),
        'ND09E1': ('XRE 300', 300), 'ND11E1': ('XRE 300', 300),
        'NC51E': ('CB 500F/X/R', 500), 'NC49E': ('CB 500', 500),
        'NC61E': ('CB 650', 650), 'NC61E0': ('CB 650R', 650),
        'MC27E': ('CG 160', 160), 'MC41E': ('CG 150', 150),
        'MC44E': ('CG 150', 150), 'MC44E1': ('CG 150', 150),
        'MD41E': ('NXR 160 Bros', 160), 'MD41E0': ('NXR 160 Bros', 160),
        'JC30E': ('CG 125i', 125), 'JC30E1': ('CG 125i', 125),
        'JC41E': ('CG 150', 150), 'JC41E1': ('CG 150', 150),
        'KC16E': ('CG 125 Titan', 125), 'KC16E5': ('CG 125', 125),
        'KC22E': ('CG 125', 125), 'KC22E1': ('CG 125', 125),
        'KC15E': ('CG 125 Titan', 125), 'KC08E': ('CG 125 Titan', 125),
        'KD03E': ('XLR 125', 125), 'KD05E': ('XLR 125', 125),
        'KD08E': ('XLR 125', 125), 'KD03E3': ('XLR 125', 125),
    }
    
    # ========================================
    # DIFERENÇAS CRÍTICAS: HONDA vs FAKE
    # ========================================
    HONDA_VS_FAKE = {
        '0': {
            'honda': {
                'formato': 'OVAL ALONGADO verticalmente',
                'proporcao': 'Altura aproximadamente 1.6x a largura',
                'extremidades': 'Superior e inferior LEVEMENTE ABERTAS',
                'lados': 'Paralelos e RETOS'
            },
            'fake': {
                'formato': 'CIRCULAR/REDONDO',
                'proporcao': 'Altura igual ou próxima da largura',
                'extremidades': 'Totalmente fechadas',
                'lados': 'Curvos'
            },
            'como_identificar': 'Se o 0 parecer uma BOLA/CÍRCULO = FAKE'
        },
        '1': {
            'honda': {
                'formato': 'Haste vertical com SERIFA ANGULAR no topo esquerdo',
                'serifa': 'Inclinada ~45 graus',
                'haste': 'FINA e perfeitamente vertical'
            },
            'fake': {
                'formato': 'Apenas haste vertical RETA',
                'serifa': 'SEM serifa',
                'haste': 'Mais GROSSA'
            },
            'como_identificar': 'Se o 1 for um PALITO RETO sem serifa = FAKE'
        },
        '3': {
            'honda': {
                'formato': 'Duas curvas em C empilhadas, ABERTAS à esquerda',
                'ponto_central': 'Bem definido',
                'curvas': 'PROPORCIONAIS'
            },
            'fake': {
                'formato': 'Curvas ASSIMÉTRICAS',
                'ponto_central': 'Indefinido',
                'curvas': 'Desproporcionais'
            },
            'como_identificar': 'Se o 3 tiver curvas assimétricas = FAKE'
        },
        '4': {
            'honda': {
                'formato': 'Ângulo com GAP característico',
                'gap': 'Linha VERTICAL NÃO TOCA a horizontal',
                'angulo': 'Bem definido ~90 graus'
            },
            'fake': {
                'formato': 'Linhas CONECTADAS',
                'gap': 'SEM gap - linhas se tocam',
                'angulo': 'Pode ser diferente'
            },
            'como_identificar': 'Se as linhas do 4 estiverem CONECTADAS = FAKE'
        },
        '9': {
            'honda': {
                'formato': 'Círculo superior FECHADO + cauda curva',
                'circulo': 'Bem fechado no topo',
                'cauda': 'Curva suave'
            },
            'fake': {
                'formato': 'Círculo mal formado ou cauda reta',
                'circulo': 'Aberto ou muito redondo',
                'cauda': 'Reta demais'
            },
            'como_identificar': 'Se o círculo do 9 estiver aberto = FAKE'
        },
        '7': {
            'honda': {
                'formato': 'Barra horizontal curta + diagonal',
                'traco_meio': 'NÃO TEM traço no meio'
            },
            'fake': {
                'formato': 'Pode ter traço no meio',
                'traco_meio': 'Traço horizontal no meio (europeu)'
            },
            'como_identificar': 'Se o 7 tiver TRAÇO NO MEIO = FAKE'
        },
        '8': {
            'honda': {
                'formato': 'Dois círculos empilhados',
                'proporcao': 'Superior MENOR que inferior'
            },
            'fake': {
                'formato': 'Círculos do mesmo tamanho',
                'proporcao': 'Superior igual ou maior'
            },
            'como_identificar': 'Se os dois círculos do 8 forem IGUAIS = FAKE'
        }
    }
    
    # ========================================
    # LETRAS - ESPECIALMENTE M vs N
    # ========================================
    LETTER_DESCRIPTIONS = {
        'M': {
            'formato': 'DUAS hastes verticais + DUAS diagonais formando V invertido no MEIO',
            'caracteristica_chave': 'TEM 4 TRAÇOS: | \\ / | (duas hastes + duas diagonais)',
            'diagonais': 'DUAS diagonais que se encontram no centro formando ponta para BAIXO',
            'confusao_comum': 'NÃO confundir com N que tem apenas UMA diagonal'
        },
        'N': {
            'formato': 'DUAS hastes verticais + UMA ÚNICA diagonal',
            'caracteristica_chave': 'TEM 3 TRAÇOS: | \\ | (duas hastes + uma diagonal)',
            'diagonais': 'APENAS UMA diagonal do topo-esquerdo ao base-direito',
            'confusao_comum': 'NÃO confundir com M que tem DUAS diagonais'
        },
        'C': {'formato': 'Curva aberta à direita'},
        'D': {'formato': 'Haste vertical + curva fechada à direita'},
        'E': {'formato': 'Haste vertical + TRÊS barras horizontais'},
        'F': {'formato': 'Haste vertical + DUAS barras horizontais (topo e meio)'},
        'H': {'formato': 'DUAS hastes verticais + barra horizontal no MEIO'},
        'J': {'formato': 'Haste vertical com curva na BASE'},
        'K': {'formato': 'Haste vertical + duas diagonais saindo do meio'},
        'L': {'formato': 'Haste vertical + barra horizontal na BASE'},
        'R': {'formato': 'Como P + perna diagonal'},
        'X': {'formato': 'Duas diagonais que se CRUZAM no centro'}
    }
    
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.enabled = bool(self.api_key)
        self.supabase = None
        self.supabase_url = settings.SUPABASE_URL
        self.supabase_key = settings.SUPABASE_KEY
        self.font_urls = {}
        
        self._init_supabase()
        self._load_honda_fonts()
        
        if self.enabled:
            logger.info(f"✓ Serviço de IA Forense v5.10")
            logger.info(f"  Fontes visuais: {len(self.font_urls)}")
            logger.info(f"  Supabase: {'Conectado' if self.supabase else 'Não configurado'}")
    
    def _init_supabase(self):
        try:
            if self.supabase_url and self.supabase_key:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                logger.info("✓ Supabase conectado")
        except Exception as e:
            logger.warning(f"Supabase não conectado: {e}")
            self.supabase = None
    
    def _load_honda_fonts(self):
        """Carrega fontes Honda disponíveis."""
        if not self.supabase_url or not self.supabase_key:
            self._load_local_fonts()
            return
        
        try:
            base = self.supabase_url.rstrip('/')
            resp = httpx.post(
                f"{base}/storage/v1/object/list/honda-fonts",
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}"
                },
                json={"prefix": "", "limit": 100},
                timeout=10.0
            )
            
            if resp.status_code == 200:
                for item in resp.json():
                    name = item.get('name', '')
                    if name.lower().endswith('.png'):
                        char = name.replace('.png', '').replace('.PNG', '').upper()
                        if len(char) == 1:
                            self.font_urls[char] = f"{base}/storage/v1/object/public/honda-fonts/{name}"
                
                if self.font_urls:
                    logger.info(f"✓ Fontes Supabase: {len(self.font_urls)}")
                    return
        except Exception as e:
            logger.warning(f"Erro fontes Supabase: {e}")
        
        self._load_local_fonts()
    
    def _load_local_fonts(self):
        try:
            fonts_dir = settings.FONTS_DIR
            if fonts_dir.exists():
                for f in fonts_dir.glob("*.png"):
                    char = f.stem.upper()
                    if len(char) == 1:
                        self.font_urls[char] = str(f)
                if self.font_urls:
                    logger.info(f"✓ Fontes locais: {len(self.font_urls)}")
        except Exception as e:
            logger.warning(f"Erro fontes locais: {e}")
    
    def _download_font_as_base64(self, char: str) -> Optional[str]:
        url = self.font_urls.get(char.upper())
        if not url:
            return None
        try:
            if url.startswith('http'):
                response = httpx.get(url, timeout=10.0)
                if response.status_code == 200:
                    return base64.b64encode(response.content).decode()
            else:
                with open(url, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
        except:
            pass
        return None
    
    def analyze(self, image_bytes: bytes, year: int, model: str = None) -> Dict[str, Any]:
        """Análise forense principal."""
        
        start_time = time.time()
        
        result = {
            'success': False,
            'analysis_id': None,
            'read_code': '',
            'prefix': None,
            'serial': None,
            'expected_model': None,
            'detected_type': 'DESCONHECIDO',
            'expected_type': self.get_expected_type(year),
            'type_match': True,
            'has_mixed_types': False,
            'font_is_honda': True,
            'risk_score': 0,
            'risk_factors': [],
            'font_analysis': {},
            'surface_analysis': {},
            'repeated_chars_analysis': [],
            'recommendations': [],
            'references_used': {'originals': 0, 'frauds': 0, 'fonts': 0}
        }
        
        if not self.enabled:
            result['risk_factors'].append("⚠️ IA não configurada")
            result['risk_score'] = 50
            return result
        
        try:
            expected_type = self.get_expected_type(year)
            logger.info(f"🤖 Análise v5.10 | Ano: {year} | Tipo esperado: {expected_type}")
            
            image_url = self._upload_analysis_image(image_bytes)
            
            result['references_used'] = {
                'originals': len(self._get_original_patterns()),
                'frauds': len(self._get_fraud_patterns()),
                'fonts': len(self.font_urls)
            }
            
            # Análise com IA
            ai_response = self._analyze_with_ai(image_bytes, year)
            
            logger.info(f"🔍 Resposta AI: {json.dumps(ai_response, ensure_ascii=False)[:300]}...")
            
            if not ai_response.get('success'):
                result['risk_factors'].append(f"Erro IA: {ai_response.get('error')}")
                result['risk_score'] = 50
                return result
            
            result['success'] = True
            self._process_response(result, ai_response, year)
            result['risk_score'] = self._calculate_risk_score(result, ai_response)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Salva análise - MÉTODO ORIGINAL QUE FUNCIONAVA
            analysis_id = self._save_analysis(
                image_url=image_url,
                year=year,
                model=model,
                result=result,
                ai_response=ai_response,
                processing_time=processing_time
            )
            
            result['analysis_id'] = analysis_id
            
            logger.info(f"✓ Código: {result['read_code']}")
            logger.info(f"  Fonte Honda: {'SIM' if result.get('font_is_honda') else 'NÃO'}")
            logger.info(f"  Score: {result['risk_score']}")
            logger.info(f"  ID: {analysis_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro análise: {e}", exc_info=True)
            result['risk_factors'].append(f"Erro: {str(e)}")
            result['risk_score'] = 50
            return result
    
    def _analyze_with_ai(self, image_bytes: bytes, year: int) -> Dict:
        """Análise com IA focada em fonte fake e distinção M/N."""
        try:
            b64_main = base64.b64encode(image_bytes).decode()
            expected_type = self.get_expected_type(year)
            
            content = []
            
            # ==========================================
            # SEÇÃO 1: GUIA DE NÚMEROS
            # ==========================================
            guide = """# 🚨 GUIA DE DETECÇÃO: FONTE HONDA vs FAKE

## NÚMEROS CRÍTICOS (0, 1, 3, 4, 9):

"""
            for char in ['0', '1', '3', '4', '9', '7', '8']:
                if char in self.HONDA_VS_FAKE:
                    info = self.HONDA_VS_FAKE[char]
                    guide += f"### NÚMERO {char}:\n"
                    guide += f"✅ HONDA: {info['honda'].get('formato', '')}\n"
                    guide += f"❌ FAKE: {info['fake'].get('formato', '')}\n"
                    guide += f"🔍 {info['como_identificar']}\n\n"
            
            content.append({"type": "text", "text": guide})
            
            # ==========================================
            # SEÇÃO 2: LETRAS - ESPECIALMENTE M vs N
            # ==========================================
            letters_guide = """
# 🔤 GUIA DE LETRAS - ATENÇÃO ESPECIAL M vs N!

## ⚠️ M vs N - DIFERENÇA CRÍTICA:

### LETRA M:
- **ESTRUTURA**: | \\ / | (4 traços)
- **DIAGONAIS**: DUAS diagonais formando V invertido (ponta para BAIXO)
- **CARACTERÍSTICA**: As duas diagonais SE ENCONTRAM no centro

### LETRA N:
- **ESTRUTURA**: | \\ | (3 traços)  
- **DIAGONAIS**: APENAS UMA diagonal (do topo-esquerdo para base-direita)
- **CARACTERÍSTICA**: Diagonal vai de canto a canto

### COMO DIFERENCIAR:
- Conte as diagonais no meio: 2 diagonais = M, 1 diagonal = N
- M tem ponta para baixo no centro, N tem linha reta diagonal

"""
            content.append({"type": "text", "text": letters_guide})
            
            # ==========================================
            # SEÇÃO 3: IMAGENS DE REFERÊNCIA
            # ==========================================
            content.append({
                "type": "text",
                "text": "\n# 📚 REFERÊNCIAS VISUAIS:\n"
            })
            
            # Prioriza M e N
            priority_chars = ['M', 'N', '0', '1', '3', '4', '9', '7', '8', '2', '5', '6']
            for char in priority_chars:
                if char in self.font_urls:
                    b64_font = self._download_font_as_base64(char)
                    if b64_font:
                        extra = ""
                        if char == 'M':
                            extra = " - DUAS diagonais (V invertido)"
                        elif char == 'N':
                            extra = " - UMA diagonal apenas"
                        elif char in self.HIGH_RISK_CHARS:
                            extra = " ⚠️ CRÍTICO"
                        content.append({"type": "text", "text": f"\n### '{char}'{extra}"})
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                        })
            
            # Outras letras
            for char in sorted(self.font_urls.keys()):
                if char.isalpha() and char not in priority_chars:
                    b64_font = self._download_font_as_base64(char)
                    if b64_font:
                        content.append({"type": "text", "text": f"\n### '{char}'"})
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                        })
            
            # ==========================================
            # SEÇÃO 4: MOTOR PARA ANÁLISE
            # ==========================================
            content.append({
                "type": "text",
                "text": f"""

# 🔍 MOTOR PARA ANÁLISE

**Ano:** {year} | **Tipo esperado:** {expected_type}

## INSTRUÇÕES:

1. **LEIA** cada caractere com cuidado
2. **PARA LETRAS**: Verifique especialmente M vs N (conte as diagonais!)
3. **PARA NÚMEROS**: Compare com padrão Honda
4. **VERIFIQUE**: Consistência, espaçamento, profundidade

"""
            })
            
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_main}
            })
            
            # ==========================================
            # SEÇÃO 5: FORMATO DE RESPOSTA
            # ==========================================
            content.append({
                "type": "text",
                "text": """

# RESPONDA EM JSON:

```json
{
  "leitura": {
    "linha1": "PREFIXO",
    "linha2": "SERIAL",
    "codigo_completo": "PREFIXO-SERIAL",
    "confianca": 0-100,
    "notas_leitura": "observações sobre caracteres"
  },
  
  "analise_fonte": {
    "fonte_e_honda": true/false,
    "confianca_fonte": 0-100,
    
    "numeros_criticos": {
      "0": {"encontrado": true/false, "e_honda": true/false, "problema": ""},
      "1": {"encontrado": true/false, "e_honda": true/false, "tem_serifa_angular": true/false, "problema": ""},
      "3": {"encontrado": true/false, "e_honda": true/false, "problema": ""},
      "4": {"encontrado": true/false, "e_honda": true/false, "tem_gap": true/false, "problema": ""},
      "9": {"encontrado": true/false, "e_honda": true/false, "problema": ""}
    },
    
    "letras_verificadas": {
      "M_ou_N": {
        "letra_identificada": "M ou N",
        "diagonais_contadas": 1 ou 2,
        "certeza": 0-100
      }
    },
    
    "consistencia": {
      "espessura_uniforme": true/false,
      "espacamento_uniforme": true/false,
      "profundidade_uniforme": true/false,
      "alinhamento_correto": true/false
    },
    
    "caracteres_problematicos": ["lista"],
    "observacoes": "detalhes"
  },
  
  "analise_fraude": {
    "tipo_gravacao": {
      "linha1": "LASER ou ESTAMPAGEM",
      "linha2": "LASER ou ESTAMPAGEM",
      "mistura": true/false
    },
    "superficie": {
      "area_lixada": true/false,
      "numeros_fantasma": true/false,
      "rebarbas": true/false
    },
    "evidencias": ["lista"]
  },
  
  "conclusao": {
    "veredicto": "ORIGINAL ou SUSPEITO ou ADULTERADO",
    "certeza": 0-100,
    "motivo_principal": "razão",
    "fonte_autentica": true/false
  }
}
```

## REGRAS DE DECISÃO:
1. Número crítico com fonte errada = ADULTERADO
2. Quatro SEM GAP = ADULTERADO
3. Mistura de tipos = ADULTERADO
4. M/N confundido não é fraude, mas impacta leitura

SEJA RIGOROSO!
"""
            })
            
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": content}]
                },
                timeout=180.0
            )
            
            if response.status_code == 200:
                text = response.json()['content'][0]['text']
                parsed = self._parse_json(text)
                parsed['success'] = True
                return parsed
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Erro análise IA: {e}")
            return {'success': False, 'error': str(e)}
    
    def _parse_json(self, text: str) -> Dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.warning(f"Erro parse JSON: {e}")
        return {}
    
    def _process_response(self, result: Dict, ai: Dict, year: int):
        """Processa resposta da IA."""
        
        # LEITURA
        leitura = ai.get('leitura', {})
        l1 = leitura.get('linha1', '')
        l2 = leitura.get('linha2', '')
        code = leitura.get('codigo_completo', '')
        
        if not code and l1 and l2:
            code = f"{l1}-{l2}"
        
        if code:
            code = re.sub(r'[^A-Z0-9\-]', '', code.upper())
            result['read_code'] = code
            parts = code.split('-')
            if parts:
                result['prefix'] = parts[0]
                result['serial'] = parts[1] if len(parts) > 1 else ''
                for p in [parts[0], parts[0][:-1], parts[0][:-2]]:
                    if p in self.KNOWN_PREFIXES:
                        result['expected_model'] = self.KNOWN_PREFIXES[p][0]
                        break
        
        result['ocr_confidence'] = {'overall': leitura.get('confianca', 0)}
        
        # Notas de leitura
        notas = leitura.get('notas_leitura', '')
        if notas:
            result['recommendations'].append(f"Leitura: {notas}")
        
        # ANÁLISE DE FONTE
        fonte = ai.get('analise_fonte', {})
        result['font_analysis'] = fonte
        
        fonte_honda = fonte.get('fonte_e_honda', True)
        result['font_is_honda'] = fonte_honda
        
        if not fonte_honda:
            result['risk_factors'].insert(0, 
                "🚨🚨🚨 FRAUDE: FONTE NÃO É HONDA!"
            )
        
        # Números críticos
        numeros_criticos = fonte.get('numeros_criticos', {})
        for num in ['0', '1', '3', '4', '9']:
            info = numeros_criticos.get(num, {})
            if info.get('encontrado') and not info.get('e_honda', True):
                problema = info.get('problema', 'não corresponde ao padrão')
                result['risk_factors'].insert(0, 
                    f"🚨🚨 FONTE FAKE: Número '{num}' - {problema}"
                )
        
        # Verificações específicas
        info_4 = numeros_criticos.get('4', {})
        if info_4.get('encontrado') and not info_4.get('tem_gap', True):
            result['risk_factors'].insert(0, 
                "🚨🚨 FONTE FAKE: Número '4' SEM GAP!"
            )
        
        info_1 = numeros_criticos.get('1', {})
        if info_1.get('encontrado') and not info_1.get('tem_serifa_angular', True):
            result['risk_factors'].insert(0, 
                "🚨🚨 FONTE FAKE: Número '1' SEM SERIFA ANGULAR!"
            )
        
        # Letras verificadas (M/N)
        letras = fonte.get('letras_verificadas', {})
        mn_info = letras.get('M_ou_N', {})
        if mn_info:
            letra = mn_info.get('letra_identificada', '')
            diagonais = mn_info.get('diagonais_contadas', 0)
            certeza = mn_info.get('certeza', 0)
            if letra and certeza < 90:
                result['recommendations'].append(
                    f"Verificar letra {letra}: {diagonais} diagonal(is), {certeza}% certeza"
                )
        
        # Consistência
        consistencia = fonte.get('consistencia', {})
        if not consistencia.get('espessura_uniforme', True):
            result['risk_factors'].append("🚨 Espessura NÃO UNIFORME")
        if not consistencia.get('espacamento_uniforme', True):
            result['risk_factors'].append("🚨 Espaçamento IRREGULAR")
        if not consistencia.get('profundidade_uniforme', True):
            result['risk_factors'].append("🚨 Profundidade VARIÁVEL")
        if not consistencia.get('alinhamento_correto', True):
            result['risk_factors'].append("🚨 Alinhamento INCORRETO")
        
        # Caracteres problemáticos
        chars_prob = fonte.get('caracteres_problematicos', [])
        if chars_prob:
            result['risk_factors'].append(f"⚠️ Caracteres problemáticos: {', '.join(chars_prob)}")
        
        # ANÁLISE DE FRAUDE
        fraude = ai.get('analise_fraude', {})
        
        tipo = fraude.get('tipo_gravacao', {})
        tipo_l1 = tipo.get('linha1', '').upper()
        tipo_l2 = tipo.get('linha2', '').upper()
        
        if tipo_l1 and tipo_l2:
            if tipo_l1 == tipo_l2:
                result['detected_type'] = tipo_l1
            else:
                result['detected_type'] = 'MISTURA'
        
        if tipo.get('mistura') or (tipo_l1 and tipo_l2 and tipo_l1 != tipo_l2):
            result['has_mixed_types'] = True
            result['risk_factors'].insert(0, "🚨🚨🚨 FRAUDE: MISTURA DE TIPOS!")
        
        # Tipo vs ano
        expected = self.get_expected_type(year)
        detected = result.get('detected_type', '')
        if detected and detected not in ['DESCONHECIDO', 'MISTURA'] and detected != expected:
            result['type_match'] = False
            result['risk_factors'].append(f"🚨 INCOMPATÍVEL: {detected} em {year}")
        
        # Superfície
        superficie = fraude.get('superficie', {})
        result['surface_analysis'] = superficie
        
        if superficie.get('numeros_fantasma'):
            result['risk_factors'].insert(0, "🚨🚨🚨 FRAUDE: NÚMEROS FANTASMA!")
        if superficie.get('area_lixada'):
            result['risk_factors'].insert(0, "🚨🚨🚨 FRAUDE: ÁREA LIXADA!")
        if superficie.get('rebarbas'):
            result['risk_factors'].append("🚨 Rebarbas detectadas")
        
        # Evidências
        for ev in fraude.get('evidencias', []):
            if ev and ev not in str(result['risk_factors']):
                result['risk_factors'].append(f"⚠️ {ev}")
        
        # CONCLUSÃO
        conclusao = ai.get('conclusao', {})
        veredicto = conclusao.get('veredicto', '').upper()
        certeza = conclusao.get('certeza', 0)
        motivo = conclusao.get('motivo_principal', '')
        fonte_autentica = conclusao.get('fonte_autentica', True)
        
        if not fonte_autentica:
            result['font_is_honda'] = False
        
        if veredicto == 'ADULTERADO':
            result['risk_factors'].insert(0, f"🚨🚨 IA: ADULTERADO ({certeza}%)")
        elif veredicto == 'SUSPEITO':
            result['risk_factors'].append(f"⚠️ IA: SUSPEITO ({certeza}%)")
        
        if motivo:
            result['recommendations'].insert(0, f"Motivo: {motivo}")
    
    def _calculate_risk_score(self, result: Dict, ai: Dict) -> int:
        """Calcula score de risco."""
        score = 0
        
        fonte = ai.get('analise_fonte', {})
        
        # Fonte não Honda
        if not fonte.get('fonte_e_honda', True):
            score += 80
        
        # Números críticos
        numeros_criticos = fonte.get('numeros_criticos', {})
        for num in ['0', '1', '3', '4', '9']:
            info = numeros_criticos.get(num, {})
            if info.get('encontrado') and not info.get('e_honda', True):
                score += 25
        
        # 4 sem gap
        info_4 = numeros_criticos.get('4', {})
        if info_4.get('encontrado') and not info_4.get('tem_gap', True):
            score += 30
        
        # 1 sem serifa
        info_1 = numeros_criticos.get('1', {})
        if info_1.get('encontrado') and not info_1.get('tem_serifa_angular', True):
            score += 20
        
        # Consistência
        consistencia = fonte.get('consistencia', {})
        if not consistencia.get('espessura_uniforme', True):
            score += 20
        if not consistencia.get('espacamento_uniforme', True):
            score += 15
        if not consistencia.get('profundidade_uniforme', True):
            score += 25
        if not consistencia.get('alinhamento_correto', True):
            score += 15
        
        # Mistura de tipos
        if result.get('has_mixed_types'):
            score += 85
        
        # Superfície
        superficie = result.get('surface_analysis', {})
        if superficie.get('numeros_fantasma'):
            score += 90
        if superficie.get('area_lixada'):
            score += 85
        if superficie.get('rebarbas'):
            score += 15
        
        # Tipo incompatível
        if not result.get('type_match', True):
            score += 25
        
        # Veredicto IA
        conclusao = ai.get('conclusao', {})
        veredicto = conclusao.get('veredicto', '').upper()
        certeza = conclusao.get('certeza', 0)
        
        if veredicto == 'ADULTERADO':
            score += int(certeza * 0.2)
        elif veredicto == 'SUSPEITO':
            score += int(certeza * 0.1)
        
        return min(score, 100)
    
    # ========================================
    # MÉTODOS DE PERSISTÊNCIA - ORIGINAIS
    # ========================================
    
    def _get_original_patterns(self) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            response = self.supabase.table('motors_original').select('*').limit(3).execute()
            return response.data or []
        except:
            return []
    
    def _get_fraud_patterns(self) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            response = self.supabase.table('motors_fraud').select('*').limit(3).execute()
            return response.data or []
        except:
            return []
    
    def _upload_analysis_image(self, image_bytes: bytes) -> Optional[str]:
        if not self.supabase:
            return None
        try:
            filename = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            self.supabase.storage.from_('analysis-images').upload(
                filename, image_bytes, {"content-type": "image/jpeg"}
            )
            return self.supabase.storage.from_('analysis-images').get_public_url(filename)
        except Exception as e:
            logger.warning(f"Erro upload imagem: {e}")
            return None
    
    def _save_analysis(self, image_url: str, year: int, model: str,
                       result: Dict, ai_response: Dict, processing_time: int) -> Optional[str]:
        """Salva análise no Supabase - MÉTODO ORIGINAL."""
        if not self.supabase:
            return None
        try:
            # APENAS campos que existem na tabela!
            data = {
                'image_url': image_url,
                'year_informed': year,
                'model_informed': model,
                'read_code': result.get('read_code'),
                'prefix': result.get('prefix'),
                'serial': result.get('serial'),
                'detected_type': result.get('detected_type'),
                'expected_type': result.get('expected_type'),
                'risk_score': result.get('risk_score'),
                'verdict': self.get_verdict(result.get('risk_score', 0)),
                'has_mixed_types': result.get('has_mixed_types', False),
                'risk_factors': result.get('risk_factors', []),
                'ai_response': ai_response,
                'refs_originals_used': result.get('references_used', {}).get('originals', 0),
                'refs_frauds_used': result.get('references_used', {}).get('frauds', 0),
                'processing_time_ms': processing_time
            }
            response = self.supabase.table('analysis_history').insert(data).execute()
            if response.data:
                return response.data[0].get('id')
        except Exception as e:
            logger.error(f"Erro salvando análise: {e}")
        return None
    
    def get_expected_type(self, year: int) -> str:
        return 'ESTAMPAGEM' if year < self.LASER_TRANSITION_YEAR else 'LASER'
    
    def get_verdict(self, score: int) -> str:
        if score >= 80: return "FRAUDE CONFIRMADA"
        elif score >= 60: return "ALTA SUSPEITA"
        elif score >= 40: return "SUSPEITO"
        elif score >= 20: return "ATENÇÃO"
        elif score >= 10: return "VERIFICAR"
        return "REGULAR"
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas."""
        originals = frauds = 0
        if self.supabase:
            try:
                originals = len(self.supabase.table('motors_original').select('id').execute().data or [])
                frauds = len(self.supabase.table('motors_fraud').select('id').execute().data or [])
            except:
                pass
        
        fonts_count = len(self.font_urls)
        
        return {
            'originals': originals,
            'frauds': frauds,
            'fonts_loaded': fonts_count,
            'fonts_visual': fonts_count,
            'fonts_available': sorted(self.font_urls.keys()),
            **self.get_accuracy_stats()
        }
    
    def get_accuracy_stats(self) -> Dict:
        if not self.supabase:
            return {'accuracy_rate': 'N/A'}
        try:
            evaluated = self.supabase.table('analysis_history').select('id').eq('evaluated', True).execute().data or []
            correct = self.supabase.table('analysis_history').select('id').eq('evaluated', True).eq('evaluation_correct', True).execute().data or []
            pending = self.supabase.table('analysis_history').select('id').eq('evaluated', False).execute().data or []
            
            total_evaluated = len(evaluated)
            total_correct = len(correct)
            
            accuracy = round((total_correct / total_evaluated) * 100, 1) if total_evaluated > 0 else 'N/A'
            
            return {
                'accuracy_rate': accuracy,
                'total_evaluated': total_evaluated,
                'total_correct': total_correct,
                'pending_evaluation': len(pending)
            }
        except:
            return {'accuracy_rate': 'N/A'}
    
    def evaluate_analysis(self, analysis_id: str, correct: bool, 
                          correct_code: str = None, correct_verdict: str = None,
                          is_fraud: bool = None, notes: str = None,
                          evaluator: str = None) -> Tuple[bool, str]:
        """Avalia uma análise."""
        if not self.supabase:
            return False, "Supabase não configurado"
        
        try:
            response = self.supabase.table('analysis_history').select('*').eq('id', analysis_id).single().execute()
            
            if not response.data:
                return False, "ID da análise não encontrado"
            
            update_data = {
                'evaluated': True,
                'evaluation_correct': correct,
                'correct_code': correct_code or response.data.get('read_code'),
                'correct_verdict': correct_verdict,
                'is_fraud_confirmed': is_fraud,
                'evaluation_notes': notes,
                'evaluated_at': datetime.now().isoformat(),
                'evaluated_by': evaluator
            }
            
            self.supabase.table('analysis_history').update(update_data).eq('id', analysis_id).execute()
            return True, "Avaliação salva"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    def get_analysis_detail(self, analysis_id: str) -> Optional[Dict]:
        """Busca detalhes de uma análise."""
        if not self.supabase:
            return None
        try:
            response = self.supabase.table('analysis_history').select('*').eq('id', analysis_id).single().execute()
            return response.data
        except:
            return None
    
    def promote_to_reference(self, analysis_id: str) -> Tuple[bool, str]:
        """Promove análise para referência."""
        if not self.supabase:
            return False, "Supabase não configurado"
        
        try:
            response = self.supabase.table('analysis_history').select('*').eq('id', analysis_id).single().execute()
            if not response.data:
                return False, "Análise não encontrada"
            
            analysis = response.data
            if not analysis.get('evaluated'):
                return False, "Análise não foi avaliada"
            if not analysis.get('evaluation_correct'):
                return False, "Só análises corretas podem ser promovidas"
            
            code = analysis.get('correct_code') or analysis.get('read_code')
            prefix = analysis.get('prefix')
            year = analysis.get('year_informed')
            detected_type = analysis.get('detected_type', '').lower()
            is_fraud = analysis.get('is_fraud_confirmed', False)
            image_url = analysis.get('image_url')
            
            if is_fraud:
                self.supabase.table('motors_fraud').insert({
                    'fraud_code': code, 'prefix': prefix, 'year_claimed': year,
                    'fraud_type': 'confirmado_prf',
                    'description': analysis.get('evaluation_notes') or 'Fraude confirmada',
                    'indicators': analysis.get('risk_factors', []),
                    'image_url': image_url
                }).execute()
                ref_type = 'fraud'
            else:
                self.supabase.table('motors_original').insert({
                    'code': code, 'prefix': prefix, 'year': year,
                    'engraving_type': detected_type if detected_type in ['laser', 'estampagem'] else 'laser',
                    'description': analysis.get('evaluation_notes') or 'Verificado',
                    'image_url': image_url, 'verified': True
                }).execute()
                ref_type = 'original'
            
            self.supabase.table('analysis_history').update({
                'promoted_to_reference': True,
                'promoted_at': datetime.now().isoformat(),
                'reference_type': ref_type
            }).eq('id', analysis_id).execute()
            
            return True, f"Promovido como {ref_type}"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    def get_analysis_history(self, limit: int = 50, only_pending: bool = False) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            query = self.supabase.table('analysis_history').select('*').order('created_at', desc=True).limit(limit)
            if only_pending:
                query = query.eq('evaluated', False)
            return query.execute().data or []
        except:
            return []
    
    def add_original(self, code: str, year: int, engraving_type: str, 
                     image_bytes: bytes, model: str = None, description: str = None) -> Tuple[bool, str]:
        if not self.supabase:
            return False, "Supabase não configurado"
        try:
            code = code.upper().strip()
            prefix = code.split('-')[0] if '-' in code else code[:6]
            filename = f"original_{code.replace('-', '_')}.jpg"
            
            self.supabase.storage.from_('motors-original').upload(filename, image_bytes, {"content-type": "image/jpeg"})
            url = self.supabase.storage.from_('motors-original').get_public_url(filename)
            
            self.supabase.table('motors_original').insert({
                'code': code, 'prefix': prefix, 'year': year,
                'engraving_type': engraving_type.lower(), 'model': model,
                'description': description, 'image_url': url, 'verified': True
            }).execute()
            
            return True, f"Motor {code} cadastrado"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    def add_fraud(self, fraud_code: str, fraud_type: str, description: str,
                  image_bytes: bytes, original_code: str = None, 
                  indicators: List[str] = None, year_claimed: int = None) -> Tuple[bool, str]:
        if not self.supabase:
            return False, "Supabase não configurado"
        try:
            fraud_code = fraud_code.upper().strip()
            prefix = fraud_code.split('-')[0] if '-' in fraud_code else fraud_code[:6]
            filename = f"fraud_{fraud_code.replace('-', '_')}.jpg"
            
            self.supabase.storage.from_('motors-fraud').upload(filename, image_bytes, {"content-type": "image/jpeg"})
            url = self.supabase.storage.from_('motors-fraud').get_public_url(filename)
            
            self.supabase.table('motors_fraud').insert({
                'fraud_code': fraud_code, 'prefix': prefix, 'year_claimed': year_claimed,
                'fraud_type': fraud_type, 'description': description,
                'indicators': indicators or [], 'image_url': url
            }).execute()
            
            return True, f"Fraude {fraud_code} cadastrada"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    def list_originals(self) -> List[Dict]:
        if not self.supabase: return []
        try: return self.supabase.table('motors_original').select('*').execute().data or []
        except: return []
    
    def list_frauds(self) -> List[Dict]:
        if not self.supabase: return []
        try: return self.supabase.table('motors_fraud').select('*').execute().data or []
        except: return []
