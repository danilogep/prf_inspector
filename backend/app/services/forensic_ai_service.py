"""
Serviço de Análise Forense com IA v5.0.1
========================================
- Melhor tratamento de erros
- Logs detalhados para debug
"""

import base64
import re
import json
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from app.core.logger import logger
from app.core.config import settings


class ForensicAIService:
    """Análise forense com referências visuais v5.0.1"""
    
    LASER_TRANSITION_YEAR = 2010
    
    KNOWN_PREFIXES = {
        'ND09E1': ('XRE 300', 300), 'ND09E': ('XRE 300', 300),
        'NC51E': ('CB 500F/X/R', 500), 'NC56E': ('CB 650F', 650),
        'MC27E': ('CG 160', 160), 'MC41E': ('CG 150', 150),
        'MC38E': ('CG 125 Fan', 125), 'MC52E': ('CB 300R', 300),
        'MD09E1': ('XRE 300', 300), 'MD09E': ('XRE 300', 300),
        'MD37E': ('NXR 160 Bros', 160), 'MD38E': ('XRE 190', 190),
        'JC30E': ('CG 125i', 125), 'JC75E': ('CG 160', 160),
        'JC79E': ('CG 160 Fan', 160), 'JC96E': ('CG 160', 160),
        'JC96E1': ('CG 160', 160), 'JC91E': ('CG 160', 160),
        'JF77E': ('BIZ 110i', 110), 'JF83E': ('BIZ 125', 125),
        'PC40E': ('PCX 150', 150), 'PC44E': ('PCX 160', 160),
        'KC16E': ('CG 125 Titan', 125), 'KC16E1': ('CG 125', 125),
        'KC16E6': ('CG 125 Titan', 125),
        'KC08E': ('CG 125 Titan', 125), 'KC08E2': ('CG 125 Titan', 125),
        'KC08E5': ('CG 125 Titan', 125),
        'KD08E': ('XLR 125', 125), 'KD08E2': ('XLR 125', 125),
        'KYJ': ('BIZ 125', 125),
    }
    
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.enabled = bool(self.api_key)
        self.supabase = None
        self.supabase_url = settings.SUPABASE_URL
        self.supabase_key = settings.SUPABASE_KEY
        
        self._init_supabase()
        
        if self.enabled:
            logger.info("✓ Serviço de IA Forense v5.0.1")
    
    def _init_supabase(self):
        try:
            if self.supabase_url and self.supabase_key:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                logger.info("✓ Supabase conectado")
        except Exception as e:
            logger.warning(f"Supabase: {e}")
    
    def _get_reference_originals(self, prefix: str, year: int, engraving_type: str) -> List[Dict]:
        """Busca motores ORIGINAIS similares."""
        if not self.supabase:
            return []
        
        try:
            prefix_base = prefix[:4] if len(prefix) > 4 else prefix
            
            response = self.supabase.table('motors_original').select('*').or_(
                f"prefix.ilike.{prefix_base}%,engraving_type.eq.{engraving_type}"
            ).limit(3).execute()
            
            return response.data or []
        except Exception as e:
            logger.warning(f"Erro buscando originais: {e}")
            return []
    
    def _get_reference_frauds(self, prefix: str) -> List[Dict]:
        """Busca motores ADULTERADOS similares."""
        if not self.supabase:
            return []
        
        try:
            prefix_base = prefix[:4] if len(prefix) > 4 else prefix
            
            response = self.supabase.table('motors_fraud').select('*').ilike(
                'prefix', f'{prefix_base}%'
            ).limit(3).execute()
            
            return response.data or []
        except Exception as e:
            logger.warning(f"Erro buscando fraudes: {e}")
            return []
    
    def _download_image_as_base64(self, url: str) -> Optional[str]:
        """Baixa imagem e converte para base64."""
        try:
            response = httpx.get(url, timeout=10.0)
            if response.status_code == 200:
                return base64.b64encode(response.content).decode()
        except Exception as e:
            logger.warning(f"Erro baixando imagem: {e}")
        return None
    
    def analyze(self, image_bytes: bytes, year: int, model: str = None) -> Dict[str, Any]:
        """Análise com referências visuais."""
        
        result = {
            'success': False,
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
            'characters_analysis': [],
            'alignment_analysis': {},
            'font_consistency': {},
            'repeated_chars_analysis': [],
            'recommendations': [],
            'references_used': {'originals': 0, 'frauds': 0}
        }
        
        if not self.enabled:
            result['risk_factors'].append("⚠️ IA não configurada")
            result['risk_score'] = 50
            return result
        
        try:
            logger.info(f"🤖 Análise v5.0.1 | Ano: {year}")
            
            prefix_guess = self._quick_read_prefix(image_bytes)
            expected_type = self.get_expected_type(year)
            
            ref_originals = self._get_reference_originals(prefix_guess or 'KC', year, expected_type)
            ref_frauds = self._get_reference_frauds(prefix_guess or 'KC')
            
            logger.info(f"  Refs: {len(ref_originals)} originais, {len(ref_frauds)} fraudes")
            
            result['references_used'] = {
                'originals': len(ref_originals),
                'frauds': len(ref_frauds)
            }
            
            ai_response = self._analyze_with_references(
                image_bytes, year, ref_originals, ref_frauds
            )
            
            if not ai_response.get('success'):
                result['risk_factors'].append(f"Erro: {ai_response.get('error')}")
                result['risk_score'] = 50
                return result
            
            result['success'] = True
            self._process_response(result, ai_response, year)
            result['risk_score'] = self._calculate_risk_score(result)
            
            logger.info(f"✓ {result['read_code']} | Score: {result['risk_score']}")
            return result
            
        except Exception as e:
            logger.error(f"Erro: {e}", exc_info=True)
            result['risk_factors'].append(f"Erro: {str(e)}")
            result['risk_score'] = 50
            return result
    
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
                            {"type": "text", "text": "Leia apenas o PREFIXO (primeira linha) deste código de motor Honda. Responda APENAS com o prefixo, nada mais. Ex: KC16E6"}
                        ]
                    }]
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                text = response.json()['content'][0]['text'].strip()
                prefix = re.sub(r'[^A-Z0-9]', '', text.upper())[:7]
                return prefix if prefix else None
        except:
            pass
        return None
    
    def _analyze_with_references(self, image_bytes: bytes, year: int, 
                                  ref_originals: List[Dict], ref_frauds: List[Dict]) -> Dict:
        """Análise com imagens de referência."""
        try:
            b64_main = base64.b64encode(image_bytes).decode()
            
            content = []
            
            content.append({
                "type": "text", 
                "text": "## IMAGEM A ANALISAR (Motor sob investigação):"
            })
            content.append({
                "type": "image", 
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_main}
            })
            
            if ref_originals:
                content.append({
                    "type": "text",
                    "text": "\n## REFERÊNCIAS DE MOTORES ORIGINAIS:"
                })
                
                for i, ref in enumerate(ref_originals, 1):
                    b64_ref = self._download_image_as_base64(ref.get('image_url', ''))
                    if b64_ref:
                        content.append({
                            "type": "text",
                            "text": f"\n### Original #{i}: {ref.get('code', 'N/A')} | Ano: {ref.get('year', 'N/A')} | Tipo: {ref.get('engraving_type', 'N/A').upper()}"
                        })
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_ref}
                        })
            
            if ref_frauds:
                content.append({
                    "type": "text",
                    "text": "\n## REFERÊNCIAS DE MOTORES ADULTERADOS:"
                })
                
                for i, ref in enumerate(ref_frauds, 1):
                    b64_ref = self._download_image_as_base64(ref.get('image_url', ''))
                    if b64_ref:
                        indicators = ref.get('indicators', [])
                        indicators_str = ', '.join(indicators) if indicators else 'N/A'
                        content.append({
                            "type": "text",
                            "text": f"\n### Fraude #{i}: {ref.get('fraud_code', 'N/A')}\n"
                                   f"Tipo: {ref.get('fraud_type', 'N/A')}\n"
                                   f"Indicadores: {indicators_str}\n"
                                   f"Descrição: {ref.get('description', 'N/A')}"
                        })
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_ref}
                        })
            
            prompt = self._build_analysis_prompt(year, len(ref_originals), len(ref_frauds))
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
                    "max_tokens": 5000,
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
    
    def _build_analysis_prompt(self, year: int, num_originals: int, num_frauds: int) -> str:
        """Constrói prompt de análise."""
        
        ref_instructions = ""
        if num_originals > 0:
            ref_instructions += f"""
## INSTRUÇÕES - COMPARAÇÃO COM ORIGINAIS
Você tem {num_originals} imagem(ns) de motores ORIGINAIS verificados.
- Compare QUALIDADE, ALINHAMENTO, ESPESSURA, ESPAÇAMENTO
- Se diferente dos originais = SUSPEITO
"""
        
        if num_frauds > 0:
            ref_instructions += f"""
## INSTRUÇÕES - COMPARAÇÃO COM FRAUDES
Você tem {num_frauds} imagem(ns) de motores ADULTERADOS conhecidos.
- Verifique padrões SIMILARES às fraudes
- Se encontrar padrões similares = ALTA SUSPEITA
"""
        
        return f"""
{ref_instructions}

## ANÁLISE DO MOTOR

Ano: {year}
Tipo esperado: {'ESTAMPAGEM' if year < 2010 else 'LASER'}

## REGRAS DE FRAUDE

1. MISTURA DE TIPOS = FRAUDE CERTA
2. DESALINHAMENTO severo = SUSPEITO
3. FONTE DIFERENTE = FRAUDE
4. CARACTERES REPETIDOS DIFERENTES = FRAUDE

## TIPOS DE GRAVAÇÃO

ESTAMPAGEM (antes 2010): Metal DEFORMADO, PROFUNDIDADE, SOMBRAS, linhas GROSSAS
LASER (2010+): Superfície PLANA, micropuntos, linhas FINAS

## RESPOSTA JSON

```json
{{
  "codigo_linha1": "PREFIXO",
  "codigo_linha2": "SERIAL",
  "codigo_completo": "PREFIXO-SERIAL",
  
  "comparacao_originais": {{
    "similar": true/false,
    "diferencas": []
  }},
  
  "comparacao_fraudes": {{
    "similar_fraude": true/false,
    "padroes_encontrados": []
  }},
  
  "analise_tipo": {{
    "tipo_detectado": "LASER ou ESTAMPAGEM",
    "tipo_linha1": "LASER ou ESTAMPAGEM",
    "tipo_linha2": "LASER ou ESTAMPAGEM",
    "ha_mistura": true/false,
    "onde_muda": ""
  }},
  
  "analise_alinhamento": {{
    "ok": true/false,
    "problemas": []
  }},
  
  "analise_fonte": {{
    "consistente": true/false,
    "problemas": []
  }},
  
  "caracteres_repetidos": [
    {{"char": "X", "posicoes": [], "identicos": true/false}}
  ],
  
  "sinais_adulteracao": [],
  "conclusao": "ORIGINAL/SUSPEITO/ADULTERADO",
  "certeza": 0-100
}}
```
"""
    
    def _parse_json(self, text: str) -> Dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                return json.loads(match.group())
            return {}
        except:
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
        
        # Comparação com originais
        comp_orig = ai.get('comparacao_originais', {})
        if not comp_orig.get('similar', True):
            diffs = comp_orig.get('diferencas', [])
            result['risk_factors'].append(f"🚨 DIFERENTE dos originais: {diffs}")
        
        # Comparação com fraudes
        comp_fraud = ai.get('comparacao_fraudes', {})
        if comp_fraud.get('similar_fraude'):
            padroes = comp_fraud.get('padroes_encontrados', [])
            result['risk_factors'].insert(0, f"🚨🚨 SIMILAR A FRAUDES! {padroes}")
        
        # Tipo de gravação
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
            result['risk_factors'].insert(0, f"🚨🚨 FRAUDE: L1={tipo_l1}, L2={tipo_l2}!")
        
        # Alinhamento
        alin = ai.get('analise_alinhamento', {})
        result['alignment_analysis'] = alin
        if not alin.get('ok', True):
            probs = alin.get('problemas', [])
            result['risk_factors'].append(f"🚨 DESALINHAMENTO: {probs}")
        
        # Fonte
        fonte = ai.get('analise_fonte', {})
        result['font_consistency'] = fonte
        if not fonte.get('consistente', True):
            probs = fonte.get('problemas', [])
            result['risk_factors'].insert(0, f"🚨🚨 FONTE DIFERENTE: {probs}")
        
        # Caracteres repetidos
        for rep in ai.get('caracteres_repetidos', []):
            result['repeated_chars_analysis'].append(rep)
            if not rep.get('identicos', True):
                result['risk_factors'].insert(0, f"🚨🚨 FRAUDE: '{rep.get('char')}' DIFERENTE!")
        
        # Sinais
        for sinal in ai.get('sinais_adulteracao', []):
            if sinal:
                result['risk_factors'].append(f"🚨 {sinal}")
        
        # Conclusão
        conclusao = ai.get('conclusao', '').upper()
        if conclusao == 'ADULTERADO':
            if "FRAUDE" not in str(result['risk_factors'][:2]):
                result['risk_factors'].insert(0, "🚨🚨 IA: ADULTERADO!")
        elif conclusao == 'SUSPEITO':
            result['risk_factors'].append("⚠️ IA: SUSPEITO")
        
        # Comparação com ano
        detected = result.get('detected_type', 'DESCONHECIDO')
        expected = self.get_expected_type(year)
        result['expected_type'] = expected
        
        if detected != 'DESCONHECIDO' and detected != expected:
            result['type_match'] = False
            result['risk_factors'].insert(0, f"🚨 {detected} em {year}! Esperado: {expected}!")
    
    def _calculate_risk_score(self, result: Dict) -> int:
        score = 0
        
        for f in result.get('risk_factors', []):
            if 'SIMILAR A FRAUDES' in f:
                score += 70
                break
        
        if result.get('has_mixed_types'):
            score += 80
        
        for f in result.get('risk_factors', []):
            if 'DIFERENTE dos originais' in f:
                score += 30
                break
        
        fonte = result.get('font_consistency', {})
        if not fonte.get('consistente', True):
            score += 50
        
        for rep in result.get('repeated_chars_analysis', []):
            if not rep.get('identicos', True):
                score += 40
        
        if not result.get('type_match', True):
            score += 35
        
        alin = result.get('alignment_analysis', {})
        if not alin.get('ok', True):
            score += 25
        
        for f in result.get('risk_factors', []):
            if '🚨🚨' in f:
                score += 15
            elif '🚨' in f:
                score += 8
            elif '⚠️' in f:
                score += 3
        
        return min(score, 100)
    
    def get_expected_type(self, year: int) -> str:
        return 'ESTAMPAGEM' if year < self.LASER_TRANSITION_YEAR else 'LASER'
    
    def get_verdict(self, score: int) -> str:
        if score >= 80:
            return "FRAUDE CONFIRMADA"
        elif score >= 60:
            return "ALTA SUSPEITA"
        elif score >= 40:
            return "SUSPEITO"
        elif score >= 20:
            return "ATENÇÃO"
        elif score >= 10:
            return "VERIFICAR"
        return "REGULAR"
    
    # ========== GERENCIAMENTO ==========
    
    def add_original(self, code: str, year: int, engraving_type: str, 
                     image_bytes: bytes, model: str = None, description: str = None) -> Tuple[bool, str]:
        """Adiciona motor ORIGINAL. Retorna (sucesso, mensagem)."""
        if not self.supabase:
            return False, "Supabase não configurado"
        
        try:
            # Normaliza
            code = code.upper().strip()
            engraving_type = engraving_type.lower().strip()
            
            if engraving_type not in ['laser', 'estampagem']:
                return False, f"engraving_type inválido: {engraving_type}. Use 'laser' ou 'estampagem'"
            
            # Extrai prefixo
            if '-' in code:
                prefix = code.split('-')[0]
            else:
                # Tenta extrair prefixo (geralmente 5-6 chars até o número do serial)
                match = re.match(r'^([A-Z]+\d+E\d?)', code)
                if match:
                    prefix = match.group(1)
                else:
                    prefix = code[:6]
            
            filename = f"original_{code.replace('-', '_').replace(' ', '_')}.jpg"
            
            logger.info(f"Cadastrando original: {code}")
            logger.info(f"  Prefixo: {prefix}")
            logger.info(f"  Ano: {year}")
            logger.info(f"  Tipo: {engraving_type}")
            logger.info(f"  Arquivo: {filename}")
            
            # Remove arquivo existente
            try:
                self.supabase.storage.from_('motors-original').remove([filename])
                logger.info(f"  Arquivo anterior removido")
            except Exception as e:
                logger.info(f"  Sem arquivo anterior: {e}")
            
            # Upload
            try:
                upload_result = self.supabase.storage.from_('motors-original').upload(
                    filename, image_bytes, {"content-type": "image/jpeg"}
                )
                logger.info(f"  Upload OK")
            except Exception as e:
                return False, f"Erro no upload: {str(e)}"
            
            # URL pública
            url = self.supabase.storage.from_('motors-original').get_public_url(filename)
            logger.info(f"  URL: {url}")
            
            # Insere no banco
            try:
                data = {
                    'code': code,
                    'prefix': prefix,
                    'year': year,
                    'engraving_type': engraving_type,
                    'model': model,
                    'description': description,
                    'image_url': url,
                    'verified': True
                }
                self.supabase.table('motors_original').insert(data).execute()
                logger.info(f"  Registro inserido no banco")
            except Exception as e:
                return False, f"Erro ao inserir no banco: {str(e)}"
            
            logger.info(f"✓ Motor original cadastrado: {code}")
            return True, f"Motor {code} cadastrado com sucesso"
            
        except Exception as e:
            logger.error(f"Erro cadastrando original: {e}", exc_info=True)
            return False, f"Erro: {str(e)}"
    
    def add_fraud(self, fraud_code: str, fraud_type: str, description: str,
                  image_bytes: bytes, original_code: str = None, 
                  indicators: List[str] = None, year_claimed: int = None) -> Tuple[bool, str]:
        """Adiciona motor ADULTERADO. Retorna (sucesso, mensagem)."""
        if not self.supabase:
            return False, "Supabase não configurado"
        
        try:
            # Normaliza
            fraud_code = fraud_code.upper().strip()
            
            # Extrai prefixo
            if '-' in fraud_code:
                prefix = fraud_code.split('-')[0]
            else:
                match = re.match(r'^([A-Z]+\d+E\d?)', fraud_code)
                if match:
                    prefix = match.group(1)
                else:
                    prefix = fraud_code[:6]
            
            filename = f"fraud_{fraud_code.replace('-', '_').replace(' ', '_')}.jpg"
            
            logger.info(f"Cadastrando fraude: {fraud_code}")
            logger.info(f"  Prefixo: {prefix}")
            logger.info(f"  Tipo fraude: {fraud_type}")
            logger.info(f"  Arquivo: {filename}")
            
            # Remove arquivo existente
            try:
                self.supabase.storage.from_('motors-fraud').remove([filename])
            except:
                pass
            
            # Upload
            try:
                self.supabase.storage.from_('motors-fraud').upload(
                    filename, image_bytes, {"content-type": "image/jpeg"}
                )
            except Exception as e:
                return False, f"Erro no upload: {str(e)}"
            
            url = self.supabase.storage.from_('motors-fraud').get_public_url(filename)
            
            # Insere no banco
            try:
                data = {
                    'fraud_code': fraud_code,
                    'original_code': original_code.upper() if original_code else None,
                    'prefix': prefix,
                    'year_claimed': year_claimed,
                    'fraud_type': fraud_type,
                    'description': description,
                    'indicators': indicators or [],
                    'image_url': url
                }
                self.supabase.table('motors_fraud').insert(data).execute()
            except Exception as e:
                return False, f"Erro ao inserir no banco: {str(e)}"
            
            logger.info(f"✓ Fraude cadastrada: {fraud_code}")
            return True, f"Fraude {fraud_code} cadastrada com sucesso"
            
        except Exception as e:
            logger.error(f"Erro cadastrando fraude: {e}", exc_info=True)
            return False, f"Erro: {str(e)}"
    
    def list_originals(self) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            response = self.supabase.table('motors_original').select('*').execute()
            return response.data or []
        except:
            return []
    
    def list_frauds(self) -> List[Dict]:
        if not self.supabase:
            return []
        try:
            response = self.supabase.table('motors_fraud').select('*').execute()
            return response.data or []
        except:
            return []
    
    def get_stats(self) -> Dict:
        return {
            'originals': len(self.list_originals()),
            'frauds': len(self.list_frauds())
        }
    
    def debug_supabase(self) -> Dict:
        """Debug do Supabase."""
        result = {
            "connected": self.supabase is not None,
            "url": self.supabase_url[:50] + "..." if self.supabase_url else None
        }
        
        if not self.supabase:
            return result
        
        # Testa buckets
        try:
            buckets = self.supabase.storage.list_buckets()
            result["buckets"] = [b.name for b in buckets]
        except Exception as e:
            result["buckets_error"] = str(e)
        
        # Testa tabelas
        try:
            orig = self.supabase.table('motors_original').select('id').limit(1).execute()
            result["table_motors_original"] = "OK"
        except Exception as e:
            result["table_motors_original_error"] = str(e)
        
        try:
            fraud = self.supabase.table('motors_fraud').select('id').limit(1).execute()
            result["table_motors_fraud"] = "OK"
        except Exception as e:
            result["table_motors_fraud_error"] = str(e)
        
        return result
