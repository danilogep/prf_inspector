"""
Serviço de Análise Forense com IA v5.7
======================================
SISTEMA HÍBRIDO DE OCR:
- Caracteres COM fonte: comparação visual com imagem
- Caracteres SEM fonte: descrição textual detalhada
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
    """Análise forense com OCR híbrido v5.7"""
    
    LASER_TRANSITION_YEAR = 2010
    
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
        'KD08E': ('XLR 125', 125),
    }
    
    # Descrições textuais detalhadas para caracteres SEM fonte
    CHAR_DESCRIPTIONS = {
        'F': "Haste vertical com DUAS barras horizontais: uma no topo e uma no meio. NÃO tem barra inferior (diferente de E).",
        'H': "DUAS hastes verticais paralelas conectadas por UMA barra horizontal no MEIO.",
        'L': "Haste vertical com UMA barra horizontal apenas na BASE (canto inferior).",
        'N': "DUAS hastes verticais conectadas por UMA ÚNICA diagonal do canto SUPERIOR ESQUERDO ao INFERIOR DIREITO. DIFERENTE de M que tem DUAS diagonais formando V.",
        'O': "Forma oval/circular FECHADA. Similar ao 0 mas geralmente mais redondo.",
        'P': "Haste vertical com SEMICÍRCULO fechado apenas no TOPO (parte superior).",
        'R': "Como P (haste com semicírculo no topo) MAS com uma PERNA DIAGONAL saindo do meio para baixo-direita.",
        'S': "Curva em forma de serpente/cobra. Curva para DIREITA no topo, curva para ESQUERDA na base.",
        'T': "UMA barra horizontal no TOPO com haste vertical descendo do CENTRO.",
        'U': "Duas hastes verticais conectadas por curva na BASE (forma de U).",
        'V': "Duas linhas diagonais que se encontram em PONTO na BASE (vértice embaixo).",
        'W': "Como dois V lado a lado, ou M invertido. Dois vértices na BASE.",
        'X': "Duas linhas diagonais que se CRUZAM no centro.",
        'Y': "Duas diagonais que se encontram no MEIO, com haste vertical descendo do ponto de encontro.",
        'Z': "Linha horizontal no TOPO, diagonal descendo para esquerda, linha horizontal na BASE.",
    }
    
    # Diferenciações críticas (confusões comuns)
    CRITICAL_DIFFERENCES = """
## ⚠️ DIFERENCIAÇÕES CRÍTICAS - MEMORIZE:

### M vs N (MUITO IMPORTANTE!)
- **M**: Duas hastes verticais + DUAS diagonais formando "V" no meio (∧)
- **N**: Duas hastes verticais + UMA diagonal só (/)
- Se vir duas hastes com V no meio = M
- Se vir duas hastes com uma diagonal = N

### 0 vs O vs D
- **0** (zero): Oval FINO e alongado verticalmente
- **O** (letra): Mais REDONDO que o zero
- **D**: Tem lado ESQUERDO RETO (haste vertical)

### 1 vs I vs L
- **1**: Tem SERIFA HORIZONTAL no topo (como T invertido pequeno)
- **I**: Apenas linha vertical RETA, sem serifa
- **L**: Linha vertical com barra NA BASE

### 5 vs S
- **5**: Topo RETO e ANGULAR, depois curva
- **S**: CURVO em ambas extremidades (serpente)

### 8 vs B
- **8**: Dois CÍRCULOS empilhados (simétrico)
- **B**: Lado ESQUERDO RETO (haste vertical) + dois semicírculos à direita

### 6 vs G
- **6**: Completamente FECHADO, círculo com cauda subindo
- **G**: ABERTO à direita com barra horizontal entrando

### E vs F
- **E**: Três barras horizontais (topo, meio, BASE)
- **F**: Apenas DUAS barras (topo e meio, SEM base)
"""
    
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
            logger.info(f"✓ Serviço de IA Forense v5.7 (OCR Híbrido)")
            logger.info(f"  Fontes visuais: {len(self.font_urls)} - {sorted(self.font_urls.keys())}")
            logger.info(f"  Descrições textuais: {len(self.CHAR_DESCRIPTIONS)} caracteres")
    
    def _init_supabase(self):
        try:
            if self.supabase_url and self.supabase_key:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                logger.info("✓ Supabase conectado")
        except Exception as e:
            logger.warning(f"Supabase: {e}")
    
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
        except Exception as e:
            logger.warning(f"Erro fontes Supabase: {e}")
        
        if not self.font_urls:
            self._load_local_fonts()
    
    def _load_local_fonts(self):
        try:
            fonts_dir = settings.FONTS_DIR
            if fonts_dir.exists():
                for f in fonts_dir.glob("*.png"):
                    char = f.stem.upper()
                    if len(char) == 1:
                        self.font_urls[char] = str(f)
        except:
            pass
    
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
    
    def _download_image_as_base64(self, url: str) -> Optional[str]:
        if not url:
            return None
        try:
            response = httpx.get(url, timeout=10.0)
            if response.status_code == 200:
                return base64.b64encode(response.content).decode()
        except:
            pass
        return None
    
    def analyze(self, image_bytes: bytes, year: int, model: str = None) -> Dict[str, Any]:
        """Análise forense com OCR híbrido."""
        
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
            'risk_score': 0,
            'risk_factors': [],
            'ocr_confidence': {},
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
            logger.info(f"🤖 Análise v5.7 | Ano: {year} | Tipo esperado: {expected_type}")
            
            image_url = self._upload_analysis_image(image_bytes)
            
            original_patterns = self._get_original_patterns()
            fraud_patterns = self._get_fraud_patterns()
            
            result['references_used'] = {
                'originals': len(original_patterns),
                'frauds': len(fraud_patterns),
                'fonts': len(self.font_urls)
            }
            
            # Análise com OCR híbrido
            ai_response = self._analyze_hybrid(image_bytes, year)
            
            logger.info(f"🔍 Resposta: {json.dumps(ai_response, ensure_ascii=False)[:500]}...")
            
            if not ai_response.get('success'):
                result['risk_factors'].append(f"Erro: {ai_response.get('error')}")
                result['risk_score'] = 50
                return result
            
            result['success'] = True
            self._process_response(result, ai_response, year)
            result['risk_score'] = self._calculate_risk_score(result, ai_response)
            
            processing_time = int((time.time() - start_time) * 1000)
            
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
            logger.info(f"  Score: {result['risk_score']}")
            for i, f in enumerate(result['risk_factors'][:5]):
                logger.info(f"  [{i+1}] {f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro: {e}", exc_info=True)
            result['risk_factors'].append(f"Erro: {str(e)}")
            result['risk_score'] = 50
            return result
    
    def _analyze_hybrid(self, image_bytes: bytes, year: int) -> Dict:
        """
        ANÁLISE HÍBRIDA:
        - Envia imagens das fontes disponíveis
        - Envia descrições textuais das fontes não disponíveis
        """
        try:
            b64_main = base64.b64encode(image_bytes).decode()
            expected_type = self.get_expected_type(year)
            
            content = []
            
            # ==========================================
            # SEÇÃO 1: FONTES VISUAIS DISPONÍVEIS
            # ==========================================
            fonts_with_images = []
            fonts_text_only = []
            
            content.append({
                "type": "text",
                "text": """# 📚 GUIA DE REFERÊNCIA PARA LEITURA DE CARACTERES HONDA

## PARTE 1: FONTES COM IMAGEM DE REFERÊNCIA
Para estes caracteres, COMPARE VISUALMENTE com a imagem fornecida:"""
            })
            
            # Adiciona fontes visuais
            for char in sorted(self.font_urls.keys()):
                b64_font = self._download_font_as_base64(char)
                if b64_font:
                    fonts_with_images.append(char)
                    
                    # Adiciona dica especial para caracteres críticos
                    hint = ""
                    if char == '1':
                        hint = " ⚠️ Note a SERIFA HORIZONTAL no topo!"
                    elif char == 'M':
                        hint = " ⚠️ Note as DUAS diagonais formando V!"
                    elif char == '0':
                        hint = " ⚠️ Formato OVAL, não redondo!"
                    elif char == '5':
                        hint = " ⚠️ Topo ANGULAR, curva embaixo!"
                    elif char == '8':
                        hint = " ⚠️ Dois círculos, simétrico!"
                    
                    content.append({"type": "text", "text": f"\n### '{char}'{hint}"})
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                    })
            
            logger.info(f"  Fontes visuais: {fonts_with_images}")
            
            # ==========================================
            # SEÇÃO 2: DESCRIÇÕES TEXTUAIS
            # ==========================================
            content.append({
                "type": "text",
                "text": """

## PARTE 2: FONTES SEM IMAGEM (use descrição textual)
Para estes caracteres, NÃO temos imagem. Use a DESCRIÇÃO para identificar:"""
            })
            
            for char, desc in sorted(self.CHAR_DESCRIPTIONS.items()):
                if char not in fonts_with_images:
                    fonts_text_only.append(char)
                    content.append({
                        "type": "text",
                        "text": f"\n### '{char}': {desc}"
                    })
            
            logger.info(f"  Fontes textuais: {fonts_text_only}")
            
            # ==========================================
            # SEÇÃO 3: DIFERENCIAÇÕES CRÍTICAS
            # ==========================================
            content.append({
                "type": "text",
                "text": self.CRITICAL_DIFFERENCES
            })
            
            # ==========================================
            # SEÇÃO 4: MOTOR PARA ANÁLISE
            # ==========================================
            content.append({
                "type": "text",
                "text": f"""

# 🔍 MOTOR PARA ANÁLISE FORENSE

**Ano:** {year}
**Tipo esperado:** {expected_type}

## INSTRUÇÕES:

### PASSO 1 - LEITURA DO CÓDIGO:
1. Identifique cada caractere da LINHA 1 (prefixo)
2. Identifique cada caractere da LINHA 2 (serial)
3. Para caracteres COM imagem de referência: compare visualmente
4. Para caracteres SEM imagem: use a descrição textual
5. **ATENÇÃO ESPECIAL**: M vs N, 0 vs O, 1 vs I

### PASSO 2 - ANÁLISE DE FRAUDE:
1. Verifique se há MISTURA de tipos (LASER + ESTAMPAGEM)
2. Compare caracteres REPETIDOS (devem ser idênticos)
3. Procure por NÚMEROS FANTASMA no fundo
4. Procure MARCAS DE LIXA na superfície
5. Verifique se dígitos "1" têm SERIFA HORIZONTAL"""
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
    "confianca_leitura": 0-100,
    "caracteres_dificeis": ["lista de caracteres com dúvida"],
    "metodo_usado": {
      "com_imagem": ["lista de chars identificados por imagem"],
      "por_descricao": ["lista de chars identificados por descrição"]
    }
  },
  
  "analise_fraude": {
    "tipo_gravacao": {
      "linha1": "LASER ou ESTAMPAGEM",
      "linha2": "LASER ou ESTAMPAGEM",
      "mistura_detectada": true/false,
      "onde_mistura": "descrição"
    },
    
    "digito_1": {
      "encontrados": 0,
      "posicoes": [],
      "serifa_correta": true/false,
      "problema": "descrição se houver"
    },
    
    "caracteres_repetidos": [
      {"char": "X", "quantidade": 2, "identicos": true/false, "diferenca": ""}
    ],
    
    "superficie": {
      "marcas_lixa": true/false,
      "area_lixada": true/false,
      "numeros_fantasma": true/false,
      "observacoes": ""
    },
    
    "caracteres_suspeitos": [
      {"char": "X", "posicao": "linha1-pos3", "problema": "descrição"}
    ],
    
    "evidencias_fraude": ["lista de evidências encontradas"]
  },
  
  "conclusao": {
    "veredicto": "ORIGINAL ou SUSPEITO ou ADULTERADO",
    "certeza": 0-100,
    "principal_motivo": "razão principal da conclusão"
  }
}
```

## ⚠️ REGRAS OBRIGATÓRIAS:

1. **NÃO CONFUNDA M com N**: M tem V no meio, N tem diagonal única
2. **VERIFIQUE O "1"**: deve ter serifa HORIZONTAL
3. **SEJA CRÍTICO**: na dúvida, marque como SUSPEITO
4. **MISTURA = FRAUDE**: LASER + ESTAMPAGEM no mesmo motor é fraude certa
5. **CARACTERES DIFERENTES = FRAUDE**: mesmo dígito com formatos diferentes é fraude"""
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
                logger.info(f"  Resposta bruta: {text[:400]}...")
                parsed = self._parse_json(text)
                parsed['success'] = True
                return parsed
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Erro análise: {e}")
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
        """Processa resposta da análise."""
        
        # ==========================================
        # LEITURA
        # ==========================================
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
        
        # Confiança da leitura
        result['ocr_confidence'] = {
            'overall': leitura.get('confianca_leitura', 0),
            'difficult_chars': leitura.get('caracteres_dificeis', []),
            'method': leitura.get('metodo_usado', {})
        }
        
        # Alerta para baixa confiança
        if leitura.get('confianca_leitura', 100) < 80:
            result['risk_factors'].append(
                f"⚠️ Leitura com baixa confiança ({leitura.get('confianca_leitura')}%)"
            )
        
        # ==========================================
        # ANÁLISE DE FRAUDE
        # ==========================================
        fraude = ai.get('analise_fraude', {})
        
        # Tipo de gravação
        tipo = fraude.get('tipo_gravacao', {})
        tipo_l1 = tipo.get('linha1', '').upper()
        tipo_l2 = tipo.get('linha2', '').upper()
        
        if tipo_l1 and tipo_l2:
            if tipo_l1 == tipo_l2:
                result['detected_type'] = tipo_l1
            else:
                result['detected_type'] = 'MISTURA'
        
        if tipo.get('mistura_detectada'):
            result['has_mixed_types'] = True
            onde = tipo.get('onde_mistura', '')
            result['risk_factors'].insert(0, 
                f"🚨🚨 FRAUDE CONFIRMADA: MISTURA DE TIPOS! {onde}"
            )
        elif tipo_l1 and tipo_l2 and tipo_l1 != tipo_l2:
            result['has_mixed_types'] = True
            result['risk_factors'].insert(0, 
                f"🚨🚨 FRAUDE: Linha1={tipo_l1}, Linha2={tipo_l2}!"
            )
        
        # Verificar compatibilidade com ano
        expected = self.get_expected_type(year)
        detected = result.get('detected_type', '')
        if detected and detected not in ['DESCONHECIDO', 'MISTURA'] and detected != expected:
            result['type_match'] = False
            result['risk_factors'].append(
                f"🚨 INCOMPATÍVEL: {detected} em veículo {year} (esperado {expected})"
            )
        
        # Dígito "1"
        digito_1 = fraude.get('digito_1', {})
        if not digito_1.get('serifa_correta', True):
            problema = digito_1.get('problema', '')
            result['risk_factors'].insert(0, 
                f"🚨🚨 FRAUDE: DÍGITO '1' SEM SERIFA CORRETA! {problema}"
            )
        
        # Caracteres repetidos
        for rep in fraude.get('caracteres_repetidos', []):
            result['repeated_chars_analysis'].append(rep)
            if not rep.get('identicos', True):
                diff = rep.get('diferenca', '')
                result['risk_factors'].insert(0, 
                    f"🚨🚨 FRAUDE: '{rep.get('char')}' REPETIDOS DIFERENTES! {diff}"
                )
        
        # Superfície
        superficie = fraude.get('superficie', {})
        result['surface_analysis'] = superficie
        
        if superficie.get('numeros_fantasma'):
            result['risk_factors'].insert(0, "🚨🚨 FRAUDE: NÚMEROS FANTASMA!")
        
        if superficie.get('area_lixada'):
            result['risk_factors'].insert(0, "🚨🚨 FRAUDE: ÁREA LIXADA!")
        
        if superficie.get('marcas_lixa'):
            result['risk_factors'].append("🚨 Marcas de lixa detectadas")
        
        # Caracteres suspeitos
        for char_susp in fraude.get('caracteres_suspeitos', []):
            result['risk_factors'].append(
                f"🚨 SUSPEITO: '{char_susp.get('char')}' em {char_susp.get('posicao')} - {char_susp.get('problema')}"
            )
        
        # Evidências
        for ev in fraude.get('evidencias_fraude', []):
            if ev and ev not in str(result['risk_factors']):
                result['risk_factors'].append(f"⚠️ {ev}")
        
        # ==========================================
        # CONCLUSÃO
        # ==========================================
        conclusao = ai.get('conclusao', {})
        veredicto = conclusao.get('veredicto', '').upper()
        certeza = conclusao.get('certeza', 0)
        motivo = conclusao.get('principal_motivo', '')
        
        if veredicto == 'ADULTERADO':
            if 'FRAUDE CONFIRMADA' not in str(result['risk_factors'][:2]):
                result['risk_factors'].insert(0, f"🚨🚨 IA: ADULTERADO ({certeza}%)")
        elif veredicto == 'SUSPEITO':
            result['risk_factors'].append(f"⚠️ IA: SUSPEITO ({certeza}%)")
        
        if motivo:
            result['recommendations'].append(f"Motivo: {motivo}")
    
    def _calculate_risk_score(self, result: Dict, ai: Dict) -> int:
        """Calcula score de risco."""
        score = 0
        
        # Mistura de tipos
        if result.get('has_mixed_types'):
            score += 85
        
        # Números fantasma
        if result.get('surface_analysis', {}).get('numeros_fantasma'):
            score += 80
        
        # Área lixada
        if result.get('surface_analysis', {}).get('area_lixada'):
            score += 75
        
        # Dígito "1" problemático
        fraude = ai.get('analise_fraude', {})
        if not fraude.get('digito_1', {}).get('serifa_correta', True):
            score += 70
        
        # Caracteres repetidos diferentes
        for rep in result.get('repeated_chars_analysis', []):
            if not rep.get('identicos', True):
                score += 60
        
        # Caracteres suspeitos
        chars_suspeitos = len(fraude.get('caracteres_suspeitos', []))
        score += chars_suspeitos * 25
        
        # Tipo incompatível
        if not result.get('type_match', True):
            score += 35
        
        # Marcas de lixa
        if result.get('surface_analysis', {}).get('marcas_lixa'):
            score += 25
        
        # Baixa confiança na leitura
        confianca = result.get('ocr_confidence', {}).get('overall', 100)
        if confianca < 70:
            score += 15
        
        # Veredicto da IA
        conclusao = ai.get('conclusao', {})
        veredicto = conclusao.get('veredicto', '').upper()
        certeza = conclusao.get('certeza', 0)
        
        if veredicto == 'ADULTERADO':
            score += int(certeza * 0.2)
        elif veredicto == 'SUSPEITO':
            score += int(certeza * 0.1)
        
        # Contagem de alertas
        for f in result.get('risk_factors', []):
            if '🚨🚨' in f:
                score += 5
            elif '🚨' in f:
                score += 3
            elif '⚠️' in f:
                score += 1
        
        return min(score, 100)
    
    # ========================================
    # MÉTODOS DE PERSISTÊNCIA
    # ========================================
    
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
            logger.warning(f"Erro upload: {e}")
            return None
    
    def _save_analysis(self, image_url: str, year: int, model: str,
                       result: Dict, ai_response: Dict, processing_time: int) -> Optional[str]:
        if not self.supabase:
            return None
        try:
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
            logger.error(f"Erro salvando: {e}")
        return None
    
    def evaluate_analysis(self, analysis_id: str, correct: bool, 
                          correct_code: str = None, correct_verdict: str = None,
                          is_fraud: bool = None, notes: str = None,
                          evaluator: str = None) -> Tuple[bool, str]:
        if not self.supabase:
            return False, "Supabase não configurado"
        
        try:
            response = self.supabase.table('analysis_history').select('*').eq(
                'id', analysis_id
            ).single().execute()
            
            if not response.data:
                return False, "Análise não encontrada"
            
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
            
            self.supabase.table('analysis_history').update(update_data).eq(
                'id', analysis_id
            ).execute()
            
            return True, "Avaliação salva"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    def promote_to_reference(self, analysis_id: str) -> Tuple[bool, str]:
        if not self.supabase:
            return False, "Supabase não configurado"
        
        try:
            response = self.supabase.table('analysis_history').select('*').eq(
                'id', analysis_id
            ).single().execute()
            
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
                    'fraud_code': code,
                    'prefix': prefix,
                    'year_claimed': year,
                    'fraud_type': 'confirmado_prf',
                    'description': analysis.get('evaluation_notes') or 'Fraude confirmada',
                    'indicators': analysis.get('risk_factors', []),
                    'image_url': image_url
                }).execute()
                ref_type = 'fraud'
            else:
                self.supabase.table('motors_original').insert({
                    'code': code,
                    'prefix': prefix,
                    'year': year,
                    'engraving_type': detected_type if detected_type in ['laser', 'estampagem'] else 'laser',
                    'description': analysis.get('evaluation_notes') or 'Verificado',
                    'image_url': image_url,
                    'verified': True
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
        originals = frauds = 0
        if self.supabase:
            try:
                originals = len(self.supabase.table('motors_original').select('id').execute().data or [])
                frauds = len(self.supabase.table('motors_fraud').select('id').execute().data or [])
            except:
                pass
        
        return {
            'originals': originals,
            'frauds': frauds,
            'fonts_visual': len(self.font_urls),
            'fonts_text': len(self.CHAR_DESCRIPTIONS),
            'fonts_available': sorted(self.font_urls.keys())
        }
    
    def get_analysis_history(self, limit: int = 50, only_pending: bool = False) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            query = self.supabase.table('analysis_history').select('*').order(
                'created_at', desc=True
            ).limit(limit)
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
            
            self.supabase.storage.from_('motors-original').upload(
                filename, image_bytes, {"content-type": "image/jpeg"}
            )
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
            
            self.supabase.storage.from_('motors-fraud').upload(
                filename, image_bytes, {"content-type": "image/jpeg"}
            )
            url = self.supabase.storage.from_('motors-fraud').get_public_url(filename)
            
            self.supabase.table('motors_fraud').insert({
                'fraud_code': fraud_code, 'prefix': prefix,
                'year_claimed': year_claimed, 'fraud_type': fraud_type,
                'description': description, 'indicators': indicators or [],
                'image_url': url
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
