"""
Serviço de Análise Forense com IA v5.3
======================================
APRENDIZADO DE PADRÕES VISUAIS:
- IA aprende COMO são motores originais (padrão de qualidade)
- IA aprende COMO fraudadores fazem (padrões de erro)
- Compara VISUALMENTE os padrões, não códigos específicos
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
    """Análise forense com aprendizado de padrões v5.3"""
    
    LASER_TRANSITION_YEAR = 2010
    
    KNOWN_PREFIXES = {
        'JC9RE': ('CG 160', 160), 'JC96E': ('CG 160', 160),
        'JC96E1': ('CG 160', 160), 'JC91E': ('CG 160', 160),
        'ND09E1': ('XRE 300', 300), 'ND09E': ('XRE 300', 300),
        'NC51E': ('CB 500F/X/R', 500), 'NC56E': ('CB 650F', 650),
        'MC27E': ('CG 160', 160), 'MC41E': ('CG 150', 150),
        'MC38E': ('CG 125 Fan', 125), 'MC52E': ('CB 300R', 300),
        'MD09E1': ('XRE 300', 300), 'MD09E': ('XRE 300', 300),
        'MD37E': ('NXR 160 Bros', 160), 'MD38E': ('XRE 190', 190),
        'JC30E': ('CG 125i', 125), 'JC75E': ('CG 160', 160),
        'JC79E': ('CG 160 Fan', 160),
        'JF77E': ('BIZ 110i', 110), 'JF83E': ('BIZ 125', 125),
        'PC40E': ('PCX 150', 150), 'PC44E': ('PCX 160', 160),
        'KC16E': ('CG 125 Titan', 125), 'KC16E1': ('CG 125', 125),
        'KC16E6': ('CG 125 Titan', 125),
        'KC08E': ('CG 125 Titan', 125), 'KC08E2': ('CG 125 Titan', 125),
        'KC08E5': ('CG 125 Titan', 125),
        'KD08E': ('XLR 125', 125), 'KD08E2': ('XLR 125', 125),
        'KYJ': ('BIZ 125', 125),
    }
    
    CRITICAL_CHARS = ['0', '1', '3', '4', '5', '6', '8', '9']
    
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
            logger.info(f"✓ Serviço de IA Forense v5.3 (Aprendizado de Padrões)")
            logger.info(f"  Fontes Honda: {len(self.font_urls)}")
    
    def _init_supabase(self):
        try:
            if self.supabase_url and self.supabase_key:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                logger.info("✓ Supabase conectado")
        except Exception as e:
            logger.warning(f"Supabase: {e}")
    
    def _load_honda_fonts(self):
        """Carrega URLs das fontes Honda."""
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
                        self.font_urls[char] = f"{base}/storage/v1/object/public/honda-fonts/{name}"
                
                if self.font_urls:
                    logger.info(f"✓ Fontes Supabase: {len(self.font_urls)}")
                    return
        except Exception as e:
            logger.warning(f"Erro fontes: {e}")
        
        self._load_local_fonts()
    
    def _load_local_fonts(self):
        try:
            fonts_dir = settings.FONTS_DIR
            if fonts_dir.exists():
                for f in fonts_dir.glob("*.png"):
                    self.font_urls[f.stem.upper()] = str(f)
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
    
    # ========================================
    # BUSCA DE PADRÕES (NÃO POR CÓDIGO!)
    # ========================================
    
    def _get_original_patterns(self, expected_type: str) -> List[Dict]:
        """
        Busca exemplos de motores ORIGINAIS para a IA aprender o PADRÃO.
        Prioriza mesmo tipo de gravação (LASER ou ESTAMPAGEM).
        """
        if not self.supabase:
            return []
        
        patterns = []
        
        try:
            # Primeiro: busca do mesmo tipo de gravação
            response = self.supabase.table('motors_original').select('*').eq(
                'engraving_type', expected_type.lower()
            ).limit(3).execute()
            
            if response.data:
                patterns.extend(response.data)
                logger.info(f"  ✓ {len(response.data)} originais tipo {expected_type}")
            
            # Se não tiver suficiente, busca qualquer um
            if len(patterns) < 2:
                response2 = self.supabase.table('motors_original').select('*').limit(5).execute()
                if response2.data:
                    for item in response2.data:
                        if item not in patterns:
                            patterns.append(item)
                            if len(patterns) >= 4:
                                break
            
            logger.info(f"  Total padrões originais: {len(patterns)}")
            
        except Exception as e:
            logger.warning(f"Erro buscando padrões originais: {e}")
        
        return patterns[:4]
    
    def _get_fraud_patterns(self) -> List[Dict]:
        """
        Busca exemplos de FRAUDES para a IA aprender os PADRÕES de adulteração.
        Não filtra por código - queremos QUALQUER exemplo de fraude.
        """
        if not self.supabase:
            return []
        
        patterns = []
        
        try:
            # Busca todas as fraudes cadastradas (variadas)
            response = self.supabase.table('motors_fraud').select('*').limit(5).execute()
            
            if response.data:
                patterns.extend(response.data)
                logger.info(f"  ✓ {len(response.data)} padrões de fraude carregados")
            
        except Exception as e:
            logger.warning(f"Erro buscando padrões de fraude: {e}")
        
        return patterns[:4]
    
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
    
    # ========================================
    # ANÁLISE PRINCIPAL
    # ========================================
    
    def analyze(self, image_bytes: bytes, year: int, model: str = None) -> Dict[str, Any]:
        """Análise com aprendizado de padrões visuais."""
        
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
            'font_comparison': [],
            'alignment_analysis': {},
            'font_consistency': {},
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
            logger.info(f"🤖 Análise v5.3 | Ano: {year} | Tipo esperado: {expected_type}")
            
            # Upload da imagem
            image_url = self._upload_analysis_image(image_bytes)
            
            # Busca PADRÕES (não códigos específicos!)
            original_patterns = self._get_original_patterns(expected_type)
            fraud_patterns = self._get_fraud_patterns()
            
            result['references_used'] = {
                'originals': len(original_patterns),
                'frauds': len(fraud_patterns),
                'fonts': len(self.font_urls)
            }
            
            # Análise com IA
            ai_response = self._analyze_with_pattern_learning(
                image_bytes, year, original_patterns, fraud_patterns
            )
            
            if not ai_response.get('success'):
                result['risk_factors'].append(f"Erro: {ai_response.get('error')}")
                result['risk_score'] = 50
                return result
            
            result['success'] = True
            self._process_response(result, ai_response, year)
            result['risk_score'] = self._calculate_risk_score(result)
            
            # Tempo de processamento
            processing_time = int((time.time() - start_time) * 1000)
            
            # Salva no histórico
            analysis_id = self._save_analysis(
                image_url=image_url,
                year=year,
                model=model,
                result=result,
                ai_response=ai_response,
                processing_time=processing_time
            )
            
            result['analysis_id'] = analysis_id
            
            logger.info(f"✓ {result['read_code']} | Score: {result['risk_score']} | ID: {analysis_id}")
            return result
            
        except Exception as e:
            logger.error(f"Erro: {e}", exc_info=True)
            result['risk_factors'].append(f"Erro: {str(e)}")
            result['risk_score'] = 50
            return result
    
    def _analyze_with_pattern_learning(self, image_bytes: bytes, year: int,
                                        original_patterns: List[Dict], 
                                        fraud_patterns: List[Dict]) -> Dict:
        """
        Análise com APRENDIZADO DE PADRÕES.
        A IA recebe exemplos de originais e fraudes para APRENDER como cada um se parece.
        """
        try:
            b64_main = base64.b64encode(image_bytes).decode()
            expected_type = self.get_expected_type(year)
            
            content = []
            
            # ==========================================
            # SEÇÃO 1: FONTES OFICIAIS HONDA
            # ==========================================
            content.append({
                "type": "text",
                "text": """# 📚 MATERIAL DE TREINAMENTO - FONTES OFICIAIS HONDA

Estas são as FONTES OFICIAIS usadas pela Honda na gravação de motores.
MEMORIZE cada detalhe: curvas, ângulos, espessuras, proporções.
Qualquer caractere no motor analisado que seja DIFERENTE destas fontes indica ADULTERAÇÃO."""
            })
            
            fonts_added = 0
            for char in self.CRITICAL_CHARS:
                b64_font = self._download_font_as_base64(char)
                if b64_font:
                    content.append({"type": "text", "text": f"\n### Fonte Honda '{char}':"})
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                    })
                    fonts_added += 1
            
            logger.info(f"  Fontes Honda enviadas: {fonts_added}")
            
            # ==========================================
            # SEÇÃO 2: EXEMPLOS DE MOTORES ORIGINAIS
            # ==========================================
            if original_patterns:
                content.append({
                    "type": "text",
                    "text": f"""

# ✅ EXEMPLOS DE MOTORES ORIGINAIS (PADRÃO DE QUALIDADE)

Estes são {len(original_patterns)} exemplos de motores ORIGINAIS verificados.
APRENDA como é a gravação CORRETA:
- Alinhamento PERFEITO entre caracteres
- Espaçamento UNIFORME
- Profundidade CONSISTENTE
- Fonte IDÊNTICA em todos os caracteres
- Qualidade PROFISSIONAL da gravação"""
                })
                
                for i, pattern in enumerate(original_patterns, 1):
                    b64_ref = self._download_image_as_base64(pattern.get('image_url', ''))
                    if b64_ref:
                        content.append({
                            "type": "text",
                            "text": f"\n### ORIGINAL #{i}: {pattern.get('code', 'N/A')}\n"
                                   f"Tipo: {pattern.get('engraving_type', 'N/A').upper()}\n"
                                   f"Ano: {pattern.get('year', 'N/A')}\n"
                                   f"Observe: alinhamento, fonte, qualidade"
                        })
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_ref}
                        })
            
            # ==========================================
            # SEÇÃO 3: EXEMPLOS DE FRAUDES (PADRÕES DE ERRO)
            # ==========================================
            if fraud_patterns:
                content.append({
                    "type": "text",
                    "text": f"""

# ❌ EXEMPLOS DE FRAUDES (PADRÕES DE ADULTERAÇÃO)

Estes são {len(fraud_patterns)} exemplos de motores ADULTERADOS.
APRENDA os ERROS que fraudadores cometem:
- Mistura de tipos (LASER + ESTAMPAGEM no mesmo motor)
- Desalinhamento entre caracteres
- Fonte DIFERENTE da Honda oficial
- Caracteres repetidos com formatos diferentes
- Qualidade INFERIOR ou IRREGULAR
- Espaçamento inconsistente"""
                })
                
                for i, pattern in enumerate(fraud_patterns, 1):
                    b64_ref = self._download_image_as_base64(pattern.get('image_url', ''))
                    if b64_ref:
                        indicators = pattern.get('indicators', [])
                        content.append({
                            "type": "text",
                            "text": f"\n### FRAUDE #{i}: {pattern.get('fraud_code', 'N/A')}\n"
                                   f"Tipo de fraude: {pattern.get('fraud_type', 'N/A')}\n"
                                   f"Descrição: {pattern.get('description', 'N/A')}\n"
                                   f"Indicadores: {indicators if indicators else 'N/A'}"
                        })
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_ref}
                        })
            
            # ==========================================
            # SEÇÃO 4: MOTOR A SER ANALISADO
            # ==========================================
            content.append({
                "type": "text",
                "text": f"""

# 🔍 MOTOR PARA ANÁLISE

Ano informado: {year}
Tipo de gravação esperado: {expected_type}

Agora analise este motor usando TODO o conhecimento acima:
1. Compare CADA caractere com as fontes Honda oficiais
2. Compare a QUALIDADE com os exemplos de originais
3. Procure PADRÕES similares aos exemplos de fraude
4. Verifique se há MISTURA de tipos de gravação"""
            })
            
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_main}
            })
            
            # ==========================================
            # SEÇÃO 5: PROMPT DE ANÁLISE
            # ==========================================
            prompt = self._build_pattern_analysis_prompt(year, expected_type, 
                                                          len(original_patterns), 
                                                          len(fraud_patterns),
                                                          fonts_added)
            content.append({"type": "text", "text": prompt})
            
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 6000,
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
            return {'success': False, 'error': str(e)}
    
    def _build_pattern_analysis_prompt(self, year: int, expected_type: str,
                                        num_originals: int, num_frauds: int,
                                        num_fonts: int) -> str:
        """Prompt focado em comparação de PADRÕES."""
        return f"""

# INSTRUÇÕES DE ANÁLISE FORENSE

## Você recebeu:
- {num_fonts} imagens de FONTES OFICIAIS HONDA
- {num_originals} exemplos de MOTORES ORIGINAIS (padrão de qualidade)
- {num_frauds} exemplos de FRAUDES (padrões de erro dos fraudadores)

## TAREFA: Analise o motor e determine se é ORIGINAL ou ADULTERADO

### CRITÉRIOS DE ANÁLISE:

1. **COMPARAÇÃO DE FONTES** (MAIS IMPORTANTE!)
   - Compare CADA dígito do motor com as fontes Honda fornecidas
   - Qualquer caractere com formato diferente = ADULTERAÇÃO
   - Fraudadores frequentemente erram: curvas, ângulos, proporções

2. **COMPARAÇÃO COM ORIGINAIS**
   - A qualidade da gravação é similar aos exemplos originais?
   - O alinhamento está perfeito como nos originais?
   - O espaçamento é uniforme como nos originais?

3. **COMPARAÇÃO COM FRAUDES**
   - Há padrões similares aos exemplos de fraude?
   - Há mistura de tipos (LASER + ESTAMPAGEM)?
   - Há sinais de regravação, lixamento, ou adição de metal?

4. **VERIFICAÇÃO DE TIPO**
   - Ano: {year}
   - Tipo esperado: {expected_type}
   - Se o tipo detectado for diferente do esperado = SUSPEITO

## RESPOSTA JSON OBRIGATÓRIA:

```json
{{
  "codigo_linha1": "PREFIXO",
  "codigo_linha2": "SERIAL",
  "codigo_completo": "PREFIXO-SERIAL",
  
  "comparacao_fontes": {{
    "todos_caracteres_corretos": true/false,
    "caracteres_suspeitos": [
      {{"char": "5", "posicao": 7, "problema": "curva inferior diferente da fonte Honda"}}
    ],
    "confianca_fonte": 0-100
  }},
  
  "comparacao_com_originais": {{
    "qualidade_similar": true/false,
    "alinhamento_similar": true/false,
    "espacamento_similar": true/false,
    "diferencas": []
  }},
  
  "comparacao_com_fraudes": {{
    "padroes_similares_encontrados": true/false,
    "padroes": [],
    "tipo_fraude_provavel": ""
  }},
  
  "analise_tipo": {{
    "tipo_detectado": "LASER ou ESTAMPAGEM",
    "tipo_linha1": "LASER ou ESTAMPAGEM",
    "tipo_linha2": "LASER ou ESTAMPAGEM",
    "ha_mistura": true/false,
    "onde_muda": ""
  }},
  
  "analise_alinhamento": {{
    "perfeito": true/false,
    "problemas": []
  }},
  
  "caracteres_repetidos": [
    {{"char": "X", "posicoes": [], "identicos": true/false, "diferenca": ""}}
  ],
  
  "sinais_adulteracao": [],
  
  "conclusao": "ORIGINAL/SUSPEITO/ADULTERADO",
  "certeza": 0-100,
  "justificativa": "explicação detalhada baseada nas comparações acima"
}}
```

## ⚠️ SEJA RIGOROSO!
- Use o conhecimento dos exemplos fornecidos
- Compare VISUALMENTE cada detalhe
- Na dúvida, marque como SUSPEITO
- Um único caractere diferente da fonte Honda = FRAUDE
"""
    
    def _quick_read_prefix(self, image_bytes: bytes) -> Optional[str]:
        """Leitura rápida do prefixo."""
        try:
            b64 = base64.b64encode(image_bytes).decode()
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 100,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                            {"type": "text", "text": "Leia apenas o PREFIXO (primeira linha) deste código de motor Honda. Responda APENAS com o prefixo."}
                        ]
                    }]
                },
                timeout=30.0
            )
            if response.status_code == 200:
                text = response.json()['content'][0]['text'].strip()
                return re.sub(r'[^A-Z0-9]', '', text.upper())[:7]
        except:
            pass
        return None
    
    def _parse_json(self, text: str) -> Dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                return json.loads(match.group())
        except:
            pass
        return {}
    
    def _process_response(self, result: Dict, ai: Dict, year: int):
        """Processa resposta da IA."""
        
        # Código
        code = ai.get('codigo_completo', '')
        if not code:
            l1 = ai.get('codigo_linha1', '')
            l2 = ai.get('codigo_linha2', '')
            if l1 and l2:
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
        
        # Comparação de fontes (NOVO FORMATO)
        comp_fontes = ai.get('comparacao_fontes', {})
        result['font_comparison'] = comp_fontes
        
        if not comp_fontes.get('todos_caracteres_corretos', True):
            chars_suspeitos = comp_fontes.get('caracteres_suspeitos', [])
            for cs in chars_suspeitos:
                result['risk_factors'].insert(0, 
                    f"🚨🚨 FONTE DIFERENTE: '{cs.get('char')}' pos {cs.get('posicao')} - {cs.get('problema')}"
                )
        
        confianca = comp_fontes.get('confianca_fonte', 100)
        if confianca < 70:
            result['risk_factors'].append(f"⚠️ Confiança baixa nas fontes: {confianca}%")
        
        # Comparação com originais
        comp_orig = ai.get('comparacao_com_originais', {})
        if not comp_orig.get('qualidade_similar', True):
            result['risk_factors'].append("🚨 Qualidade DIFERENTE dos originais")
        if not comp_orig.get('alinhamento_similar', True):
            result['risk_factors'].append("🚨 Alinhamento DIFERENTE dos originais")
        if not comp_orig.get('espacamento_similar', True):
            result['risk_factors'].append("🚨 Espaçamento DIFERENTE dos originais")
        
        diffs = comp_orig.get('diferencas', [])
        for d in diffs:
            result['risk_factors'].append(f"⚠️ {d}")
        
        # Comparação com fraudes
        comp_fraud = ai.get('comparacao_com_fraudes', {})
        if comp_fraud.get('padroes_similares_encontrados'):
            padroes = comp_fraud.get('padroes', [])
            tipo_fraude = comp_fraud.get('tipo_fraude_provavel', '')
            result['risk_factors'].insert(0, 
                f"🚨🚨 PADRÃO DE FRAUDE DETECTADO! {tipo_fraude} - {padroes}"
            )
        
        # Tipo
        tipo = ai.get('analise_tipo', {})
        result['detected_type'] = tipo.get('tipo_detectado', 'DESCONHECIDO').upper()
        
        if tipo.get('ha_mistura'):
            result['has_mixed_types'] = True
            onde = tipo.get('onde_muda', '')
            result['risk_factors'].insert(0, f"🚨🚨 FRAUDE: MISTURA DE TIPOS! {onde}")
        
        tipo_l1 = tipo.get('tipo_linha1', '').upper()
        tipo_l2 = tipo.get('tipo_linha2', '').upper()
        if tipo_l1 and tipo_l2 and tipo_l1 != tipo_l2:
            result['has_mixed_types'] = True
            result['risk_factors'].insert(0, f"🚨🚨 FRAUDE: Linha1={tipo_l1}, Linha2={tipo_l2}!")
        
        # Alinhamento
        alin = ai.get('analise_alinhamento', {})
        result['alignment_analysis'] = alin
        if not alin.get('perfeito', True):
            probs = alin.get('problemas', [])
            result['risk_factors'].append(f"🚨 DESALINHAMENTO: {probs}")
        
        # Caracteres repetidos
        for rep in ai.get('caracteres_repetidos', []):
            result['repeated_chars_analysis'].append(rep)
            if not rep.get('identicos', True):
                result['risk_factors'].insert(0, 
                    f"🚨🚨 FRAUDE: '{rep.get('char')}' DIFERENTE! {rep.get('diferenca')}"
                )
        
        # Sinais
        for sinal in ai.get('sinais_adulteracao', []):
            if sinal:
                result['risk_factors'].append(f"🚨 {sinal}")
        
        # Conclusão da IA
        conclusao = ai.get('conclusao', '').upper()
        if conclusao == 'ADULTERADO':
            if "FRAUDE" not in str(result['risk_factors'][:2]):
                result['risk_factors'].insert(0, "🚨🚨 IA CONCLUI: ADULTERADO!")
        elif conclusao == 'SUSPEITO':
            result['risk_factors'].append("⚠️ IA CONCLUI: SUSPEITO")
        
        just = ai.get('justificativa', '')
        if just:
            result['recommendations'].append(f"Análise: {just}")
        
        # Verificação tipo vs ano
        detected = result.get('detected_type', 'DESCONHECIDO')
        expected = self.get_expected_type(year)
        result['expected_type'] = expected
        
        if detected != 'DESCONHECIDO' and detected != expected:
            result['type_match'] = False
            result['risk_factors'].insert(0, f"🚨 {detected} em {year}! Esperado: {expected}!")
    
    def _calculate_risk_score(self, result: Dict) -> int:
        score = 0
        
        # Padrão de fraude detectado
        for f in result.get('risk_factors', []):
            if 'PADRÃO DE FRAUDE' in f:
                score += 70
                break
        
        # Mistura de tipos
        if result.get('has_mixed_types'):
            score += 80
        
        # Fontes diferentes (MUITO IMPORTANTE)
        comp_fontes = result.get('font_comparison', {})
        chars_suspeitos = comp_fontes.get('caracteres_suspeitos', [])
        score += len(chars_suspeitos) * 40
        
        if not comp_fontes.get('todos_caracteres_corretos', True):
            score += 30
        
        # Diferente dos originais
        for f in result.get('risk_factors', []):
            if 'DIFERENTE dos originais' in f:
                score += 20
        
        # Caracteres repetidos diferentes
        for rep in result.get('repeated_chars_analysis', []):
            if not rep.get('identicos', True):
                score += 40
        
        # Tipo incompatível com ano
        if not result.get('type_match', True):
            score += 35
        
        # Desalinhamento
        alin = result.get('alignment_analysis', {})
        if not alin.get('perfeito', True):
            score += 25
        
        # Contagem de fatores
        for f in result.get('risk_factors', []):
            if '🚨🚨' in f:
                score += 10
            elif '🚨' in f:
                score += 5
            elif '⚠️' in f:
                score += 2
        
        return min(score, 100)
    
    # ========================================
    # HISTÓRICO E FEEDBACK
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
            
            if correct:
                return True, f"Avaliação salva! Use /promote/{analysis_id} para adicionar como referência."
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
            if analysis.get('promoted_to_reference'):
                return False, "Já foi promovida"
            
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
                    'description': analysis.get('evaluation_notes') or 'Fraude confirmada pelo PRF',
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
                    'description': analysis.get('evaluation_notes') or 'Verificado pelo PRF',
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
    
    def get_analysis_history(self, limit: int = 50, only_pending: bool = False) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            query = self.supabase.table('analysis_history').select(
                'id, read_code, prefix, year_informed, detected_type, risk_score, verdict, '
                'evaluated, evaluation_correct, is_fraud_confirmed, created_at, image_url'
            ).order('created_at', desc=True).limit(limit)
            
            if only_pending:
                query = query.eq('evaluated', False)
            
            return query.execute().data or []
        except:
            return []
    
    def get_analysis_detail(self, analysis_id: str) -> Optional[Dict]:
        if not self.supabase:
            return None
        try:
            return self.supabase.table('analysis_history').select('*').eq(
                'id', analysis_id
            ).single().execute().data
        except:
            return None
    
    def get_accuracy_stats(self) -> Dict:
        if not self.supabase:
            return {}
        try:
            data = self.supabase.table('analysis_history').select('*').execute().data or []
            total = len(data)
            evaluated = [d for d in data if d.get('evaluated')]
            correct = [d for d in evaluated if d.get('evaluation_correct')]
            accuracy = (len(correct) / len(evaluated) * 100) if evaluated else 0
            
            return {
                'total_analyses': total,
                'total_evaluated': len(evaluated),
                'total_correct': len(correct),
                'accuracy_rate': round(accuracy, 2),
                'pending_evaluation': total - len(evaluated)
            }
        except:
            return {}
    
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
            'fonts_loaded': len(self.font_urls),
            **self.get_accuracy_stats()
        }
    
    # Cadastro manual
    def add_original(self, code: str, year: int, engraving_type: str, 
                     image_bytes: bytes, model: str = None, description: str = None) -> Tuple[bool, str]:
        if not self.supabase:
            return False, "Supabase não configurado"
        try:
            code = code.upper().strip()
            engraving_type = engraving_type.lower().strip()
            if engraving_type not in ['laser', 'estampagem']:
                return False, "engraving_type: laser ou estampagem"
            
            prefix = code.split('-')[0] if '-' in code else code[:6]
            filename = f"original_{code.replace('-', '_')}.jpg"
            
            try:
                self.supabase.storage.from_('motors-original').remove([filename])
            except:
                pass
            
            self.supabase.storage.from_('motors-original').upload(
                filename, image_bytes, {"content-type": "image/jpeg"}
            )
            url = self.supabase.storage.from_('motors-original').get_public_url(filename)
            
            self.supabase.table('motors_original').insert({
                'code': code, 'prefix': prefix, 'year': year,
                'engraving_type': engraving_type, 'model': model,
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
            
            try:
                self.supabase.storage.from_('motors-fraud').remove([filename])
            except:
                pass
            
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
