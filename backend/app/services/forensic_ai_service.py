"""
Serviço de Análise Forense com IA v5.33
=======================================
CORREÇÃO CRÍTICA - ULTRA CONSERVADOR

PROBLEMA CORRIGIDO (v5.33):
- IA estava gerando FALSOS POSITIVOS em massa (97% de erro)
- Causas:
  1. IA classificando variações normais de caracteres como "erro"
  2. IA confundindo textura normal de motor usado com "marcas de lixa"
  3. Score calculado baseado em análise detalhada de caracteres

SOLUÇÃO (v5.33):
- Prompt ultra-simplificado: ignora formato de caracteres
- Cálculo de score ignora "marcas de lixa" (IA erra muito)
- ÚNICAS evidências que aumentam score:
  * Números fantasma (vestígios de numeração anterior)
  * Mistura laser/estampagem na mesma numeração
- Tudo mais = ASSUME ORIGINAL

TAXA ESPERADA: ~95% acertos em ORIGINAIS

CORREÇÕES DE BUGS (v5.16):
1. Race condition no upload de imagem (adicionado lock)
2. Memory leak no OpenCV (adicionado cleanup explícito)
3. JSON parsing mais robusto
4. Timeout handling melhorado
5. Validação de input em todos os métodos públicos

LÓGICA DE SCORE v5.33 (ULTRA CONSERVADOR):
- Base: 15 (assume ORIGINAL)
- Números fantasma detectados = 95
- Mistura laser/estampagem = 90
- Veredicto ADULTERADO com evidência física = 85
- Veredicto ADULTERADO sem evidência física = 35 (IGNORADO)
- Marcas de lixa = IGNORADO (IA erra muito)
- Diferenças de caracteres = IGNORADO
"""

import base64
import re
import json
import httpx
import time
import io
import threading
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

from app.core.logger import logger
from app.core.config import settings

# =====================================================
# MARCADOR v5.33 - ESTE PRINT CONFIRMA ARQUIVO CORRETO
# =====================================================
print("=" * 60)
print("🔷 FORENSIC_AI_SERVICE v5.33 ULTRA CONSERVADOR CARREGADO!")
print("🔷 Se você está vendo isto, o arquivo foi substituído!")
print("=" * 60)

# OpenCV para filtro forense
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
    logger.info("✓ OpenCV disponível para análise forense")
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None
    np = None
    logger.warning("⚠️ OpenCV não instalado - pip install opencv-python")


class ForensicAIService:
    """
    Análise forense v5.33 - Versão refatorada com correções de bugs e melhorias.
    
    Thread-safe, com cache e validação robusta.
    """
    
    LASER_TRANSITION_YEAR: int = 2010
    API_TIMEOUT: int = 180  # segundos
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB
    CACHE_TTL: int = 3600  # 1 hora
    
    # Números críticos que fraudadores mais erram
    HIGH_RISK_CHARS: frozenset = frozenset(['0', '1', '3', '4', '5', '6', '8', '9'])
    
    # Prefixos conhecidos - EXPANDIDO
    KNOWN_PREFIXES: Dict[str, Tuple[str, int]] = {
        # CG Series
        'JC9RE': ('CG 160', 160), 'JC96E': ('CG 160', 160),
        'JC30E': ('CG 125i', 125), 'JC30E7': ('CG 125i', 125),
        'MC27E': ('CG 160', 160), 'MC41E': ('CG 150', 150),
        'MC44E': ('CG 150', 150), 'MC44E1': ('CG 150', 150),
        
        # XRE Series
        'ND09E1': ('XRE 300', 300), 'ND11E1': ('XRE 300', 300),
        'MD09E': ('XRE 300', 300), 'MD09E1': ('XRE 300', 300),
        
        # CB Series
        'NC51E': ('CB 500F/X/R', 500), 'NC49E': ('CB 500', 500),
        'NC49E1': ('CB 500', 500), 'NC49E1F': ('CB 500F', 500),
        'NC61E': ('CB 650', 650), 'NC61E0': ('CB 650R', 650),
        
        # Bros
        'MD41E': ('NXR 160 Bros', 160), 'MD41E0': ('NXR 160 Bros', 160),
        
        # Série KC/KD (antigos/exportação)
        'KC08E1': ('CG 125', 125), 'KC08E2': ('CG 125', 125),
        'KC22E1': ('CG 125', 125),
        'KD03E3': ('Motor Genérico', 0),
        'KD08E1': ('Sahara/XLR 125', 125), 'KD08E2': ('Sahara/XLR 125', 125),
        'KF34E1': ('Titan 150', 150),
    }
    
    def __init__(self):
        """Inicializa o serviço com configurações e validações."""
        self._lock = threading.Lock()
        self._cache: Dict[str, Tuple[Dict, float]] = {}
        
        # Configuração da API
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        self.enabled = bool(self.api_key and len(self.api_key) > 20)
        
        # Supabase
        self.supabase = self._init_supabase()
        
        # URLs de fontes para referência
        self.font_urls = self._load_font_urls()
        
        # Cache de imagens em base64 (carrega uma vez)
        self.font_cache_b64 = self._preload_font_cache()
        
        if self.enabled:
            logger.info(f"✓ ForensicAIService v5.33 inicializado")
            logger.info(f"  API Key: {self.api_key[:20]}..." if self.api_key else "  API Key: Não configurada")
        else:
            logger.warning("⚠️ ForensicAIService desabilitado - ANTHROPIC_API_KEY não configurada")
    
    def _init_supabase(self) -> Optional[Any]:
        """Inicializa conexão com Supabase de forma segura."""
        try:
            supabase_url = getattr(settings, 'SUPABASE_URL', None)
            supabase_key = getattr(settings, 'SUPABASE_KEY', None)
            
            if supabase_url and supabase_key:
                from supabase import create_client
                client = create_client(supabase_url, supabase_key)
                logger.info("✓ Supabase conectado")
                return client
        except ImportError:
            logger.warning("⚠️ Biblioteca supabase não instalada")
        except Exception as e:
            logger.error(f"Erro ao conectar Supabase: {e}")
        
        return None
    
    def _load_font_urls(self) -> Dict[str, str]:
        """
        Carrega URLs das fontes de referência Honda.
        
        SIMPLIFICADO v5.33: Usa APENAS fontes genéricas de alta qualidade.
        Formato: "A.png", "0.png", "1.png", etc.
        
        Retorna:
        {
            '0': 'path/to/0.png',
            '1': 'path/to/1.png',
            'A': 'path/to/A.png',
            ...
        }
        """
        font_data = {}
        
        def parse_filename(filename: str) -> Optional[str]:
            """
            Parse nome do arquivo.
            Aceita APENAS formato genérico: "A.png", "0.png"
            Ignora arquivos com _LASER ou _ESTAMPAGEM.
            """
            stem = filename.replace('.png', '').replace('.PNG', '')
            
            # Ignorar arquivos com sufixo _LASER ou _ESTAMPAGEM
            if '_' in stem:
                return None
            
            # Aceitar apenas caracteres únicos
            char = stem.upper()
            if len(char) == 1 and char.isalnum():
                return char
            
            return None
        
        # Tenta carregar do Supabase Storage
        supabase_url = getattr(settings, 'SUPABASE_URL', None)
        supabase_key = getattr(settings, 'SUPABASE_KEY', None)
        
        if supabase_url and supabase_key:
            try:
                base = supabase_url.rstrip('/')
                resp = httpx.post(
                    f"{base}/storage/v1/object/list/honda-fonts",
                    headers={
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}"
                    },
                    json={"prefix": "", "limit": 100},
                    timeout=15.0
                )
                
                if resp.status_code == 200:
                    for item in resp.json():
                        name = item.get('name', '')
                        if name.lower().endswith('.png'):
                            char = parse_filename(name)
                            if char:
                                font_data[char] = f"{base}/storage/v1/object/public/honda-fonts/{name}"
                    
                    if font_data:
                        logger.info(f"✓ Fontes Supabase: {len(font_data)} caracteres")
                        return font_data
            except Exception as e:
                logger.warning(f"Erro fontes Supabase: {e}")
        
        # Fallback: carregar fontes locais
        try:
            fonts_dir = getattr(settings, 'FONTS_DIR', None)
            
            # Se não configurado, tenta caminhos padrão
            if not fonts_dir or not Path(fonts_dir).exists():
                possible_paths = [
                    Path(__file__).parent.parent / 'data' / 'honda_fonts',
                    Path(__file__).parent / 'data' / 'honda_fonts',
                    Path('data/honda_fonts'),
                    Path('backend/data/honda_fonts'),
                ]
                for p in possible_paths:
                    if p.exists():
                        fonts_dir = str(p)
                        break
            
            if fonts_dir and Path(fonts_dir).exists():
                for f in Path(fonts_dir).glob("*.png"):
                    char = parse_filename(f.name)
                    if char:
                        font_data[char] = str(f)
                
                if font_data:
                    logger.info(f"✓ Fontes locais: {len(font_data)} caracteres")
        except Exception as e:
            logger.warning(f"Erro fontes locais: {e}")
        
        return font_data
    
    def _preload_font_cache(self) -> Dict[str, str]:
        """
        Pré-carrega todas as fontes em base64 durante inicialização.
        Isso evita carregar a cada análise, economizando tempo.
        """
        cache = {}
        
        # Carregar apenas NÚMEROS (0-9) - são os mais críticos para fraude
        # Letras raramente são alteradas
        numeros = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        
        for char in numeros:
            if char in self.font_urls:
                b64 = self._load_font_image_base64(self.font_urls[char])
                if b64:
                    cache[char] = b64
        
        if cache:
            logger.info(f"  📦 Cache de fontes: {list(cache.keys())}")
        
        return cache
    
    def _load_font_image_base64(self, path_or_url: str) -> Optional[str]:
        """Carrega uma imagem de fonte e retorna em base64."""
        try:
            if path_or_url.startswith('http'):
                resp = httpx.get(path_or_url, timeout=10.0)
                if resp.status_code == 200:
                    return base64.b64encode(resp.content).decode('utf-8')
            else:
                path = Path(path_or_url)
                if path.exists():
                    return base64.b64encode(path.read_bytes()).decode('utf-8')
        except Exception as e:
            logger.warning(f"Erro carregando fonte {path_or_url}: {e}")
        return None
    
    def _get_reference_fonts_for_code(self, code: str) -> Dict[str, str]:
        """
        Obtém as fontes de referência para os caracteres presentes no código.
        
        SIMPLIFICADO v5.33: Usa apenas fontes genéricas de alta qualidade.
        
        Args:
            code: Código do motor (ex: "MC27E1-A123456")
            
        Returns:
            Dict mapeando caractere -> base64 da imagem de referência
        """
        # Extrair caracteres únicos do código
        chars_unicos = set()
        for c in code.upper():
            if c.isalnum():
                chars_unicos.add(c)
        
        # Carregar imagens de referência
        referencias = {}
        for char in chars_unicos:
            if char in self.font_urls:
                path_or_url = self.font_urls[char]
                b64 = self._load_font_image_base64(path_or_url)
                if b64:
                    referencias[char] = b64
        
        return referencias
    
    @contextmanager
    def _image_buffer(self, image_bytes: bytes):
        """
        Context manager para processamento seguro de imagem.
        Garante cleanup de memória do OpenCV.
        """
        np_arr = None
        img = None
        try:
            if OPENCV_AVAILABLE and np is not None:
                np_arr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            yield img
        finally:
            # Cleanup explícito
            if img is not None:
                del img
            if np_arr is not None:
                del np_arr
    
    def _validate_image(self, image_bytes: bytes) -> Tuple[bool, str]:
        """
        Valida a imagem de entrada.
        
        Returns:
            Tupla (válido, mensagem_erro)
        """
        if not image_bytes:
            return False, "Imagem vazia"
        
        if len(image_bytes) > self.MAX_IMAGE_SIZE:
            return False, f"Imagem muito grande: {len(image_bytes)} bytes (máx: {self.MAX_IMAGE_SIZE})"
        
        # Verifica magic bytes
        if image_bytes[:2] == b'\xff\xd8':
            return True, "JPEG"
        elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            return True, "PNG"
        elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
            return True, "WEBP"
        else:
            return False, "Formato de imagem não suportado (use JPEG, PNG ou WEBP)"
    
    def _get_cache_key(self, image_bytes: bytes, year: int) -> str:
        """Gera chave de cache baseada no hash da imagem."""
        image_hash = hashlib.md5(image_bytes).hexdigest()
        return f"{image_hash}_{year}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Retorna resultado em cache se válido."""
        with self._lock:
            if cache_key in self._cache:
                result, timestamp = self._cache[cache_key]
                if time.time() - timestamp < self.CACHE_TTL:
                    logger.info(f"  Cache hit: {cache_key[:16]}...")
                    return result.copy()
                else:
                    del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, result: Dict):
        """Armazena resultado em cache."""
        with self._lock:
            # Limita tamanho do cache
            if len(self._cache) > 100:
                # Remove entradas mais antigas
                oldest_keys = sorted(
                    self._cache.keys(),
                    key=lambda k: self._cache[k][1]
                )[:20]
                for key in oldest_keys:
                    del self._cache[key]
            
            self._cache[cache_key] = (result.copy(), time.time())
    
    def get_expected_type(self, year: int) -> str:
        """Retorna tipo de gravação esperado para o ano."""
        if not isinstance(year, int) or year < 1970 or year > 2100:
            return "DESCONHECIDO"
        return 'LASER' if year >= self.LASER_TRANSITION_YEAR else 'ESTAMPAGEM'
    
    def get_verdict(self, score: int) -> str:
        """
        Converte score de risco em veredicto textual.
        
        RECALIBRADO v5.16:
        - Limites ajustados para reduzir falsos positivos
        """
        if not isinstance(score, (int, float)):
            return "ERRO"
        
        score = int(score)
        
        if score >= 85:
            return "FRAUDE CONFIRMADA"
        elif score >= 70:
            return "ALTA SUSPEITA"
        elif score >= 50:
            return "SUSPEITO"
        elif score >= 30:
            return "ATENÇÃO"
        elif score >= 15:
            return "VERIFICAR"
        return "REGULAR"
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do serviço."""
        stats = {
            'enabled': self.enabled,
            'supabase_connected': self.supabase is not None,
            'fonts_loaded': len(self.font_urls),
            'cache_size': len(self._cache),
            'originals': 0,
            'frauds': 0,
            'accuracy_rate': 'N/A'
        }
        
        if self.supabase:
            try:
                response = self.supabase.table('motors_original').select('id', count='exact').execute()
                stats['originals'] = response.count or 0
                
                response = self.supabase.table('motors_fraud').select('id', count='exact').execute()
                stats['frauds'] = response.count or 0
            except Exception as e:
                logger.warning(f"Erro ao obter estatísticas: {e}")
        
        return stats
    
    def analyze(self, image_bytes: bytes, year: int, model: Optional[str] = None) -> Dict:
        """
        Método principal de análise.
        
        Args:
            image_bytes: Imagem do motor em bytes
            year: Ano do veículo
            model: Modelo opcional para validação cruzada
            
        Returns:
            Dict com resultado completo da análise
        """
        start_time = time.time()
        
        # Estrutura de resultado padrão
        result = self._create_empty_result(year)
        
        # Validação de input
        valid, msg = self._validate_image(image_bytes)
        if not valid:
            result['risk_factors'].append(f"⚠️ {msg}")
            result['risk_score'] = 50
            return result
        
        if not isinstance(year, int) or year < 1970 or year > 2100:
            result['risk_factors'].append(f"⚠️ Ano inválido: {year}")
            result['risk_score'] = 50
            return result
        
        # Verifica cache
        cache_key = self._get_cache_key(image_bytes, year)
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached
        
        # Verifica se serviço está habilitado
        if not self.enabled:
            result['risk_factors'].append("⚠️ IA não configurada - análise limitada")
            result['risk_score'] = 50
            return result
        
        try:
            logger.info(f"🤖 Análise v5.33 | Ano: {year} | Tipo esperado: {result['expected_type']}")
            
            # Aplica filtro forense CLAHE
            enhanced_bytes = self._apply_forensic_filter(image_bytes)
            if enhanced_bytes:
                logger.info("  ✓ Filtro CLAHE aplicado")
            
            # Upload da imagem para análise posterior
            image_url = self._upload_analysis_image(image_bytes)
            
            # Conta referências de fontes disponíveis
            result['references_used'] = {
                'fonts': len(self.font_urls)
            }
            
            # Análise com IA
            ai_response = self._analyze_with_ai_forensic(
                image_bytes,
                enhanced_bytes,
                year
            )
            
            if ai_response:
                logger.info(f"🔍 Resposta AI recebida")
            
            if not ai_response or not ai_response.get('success'):
                error_msg = ai_response.get('error', 'Erro desconhecido') if ai_response else 'Sem resposta'
                result['risk_factors'].append(f"Erro IA: {error_msg}")
                result['risk_score'] = 50
                return result
            
            result['success'] = True
            
            # Processa resposta da IA
            self._process_response(result, ai_response, year)
            
            # Calcula score de risco
            result['risk_score'] = self._calculate_risk_score(result, ai_response)
            
            # Tempo de processamento
            processing_time = int((time.time() - start_time) * 1000)
            
            # Salva análise no banco
            analysis_id = self._save_analysis(
                image_url=image_url,
                year=year,
                model=model,
                result=result,
                ai_response=ai_response,
                processing_time=processing_time
            )
            
            result['analysis_id'] = analysis_id
            
            # Log do resultado
            logger.info(f"✓ Código: {result['read_code']}")
            logger.info(f"  Fonte Honda: {'SIM' if result.get('font_is_honda') else 'NÃO - SUSPEITO!'}")
            logger.info(f"  Score: {result['risk_score']}")
            logger.info(f"  ID: {analysis_id}")
            
            # Armazena em cache
            self._set_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Erro análise: {e}", exc_info=True)
            result['risk_factors'].append(f"Erro: {str(e)}")
            result['risk_score'] = 50
            return result
    
    def _create_empty_result(self, year: int) -> Dict:
        """Cria estrutura de resultado vazia."""
        return {
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
            'forensic_enhanced': OPENCV_AVAILABLE,
            'repeated_chars_analysis': [],
            'recommendations': [],
            'references_used': {'fonts': 0}
        }
    # ========================================
    # MÉTODOS DE PROCESSAMENTO DE IMAGEM
    # ========================================
    
    def _apply_forensic_filter(self, image_bytes: bytes) -> Optional[bytes]:
        """
        Aplica filtro forense CLAHE para realçar detalhes.
        
        CORREÇÃO v5.16: Adicionado cleanup de memória explícito.
        """
        if not OPENCV_AVAILABLE:
            return None
        
        try:
            with self._image_buffer(image_bytes) as img:
                if img is None:
                    return None
                
                # Converte para LAB
                lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                
                # Aplica CLAHE no canal L
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                l_enhanced = clahe.apply(l)
                
                # Reconstrói imagem
                lab_enhanced = cv2.merge([l_enhanced, a, b])
                enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
                
                # Codifica como JPEG
                _, buffer = cv2.imencode('.jpg', enhanced, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                return buffer.tobytes()
                
        except Exception as e:
            logger.warning(f"Erro no filtro CLAHE: {e}")
            return None
    
    def _upload_analysis_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Faz upload da imagem para storage.
        
        CORREÇÃO v5.16: Thread-safe com lock.
        """
        if not self.supabase:
            return None
        
        try:
            with self._lock:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"analysis_{timestamp}_{hashlib.md5(image_bytes).hexdigest()[:8]}.jpg"
                
                # Upload para storage
                response = self.supabase.storage.from_('motor-images').upload(
                    filename,
                    image_bytes,
                    {'content-type': 'image/jpeg'}
                )
                
                if response:
                    # Retorna URL pública
                    return self.supabase.storage.from_('motor-images').get_public_url(filename)
                    
        except Exception as e:
            logger.warning(f"Erro no upload: {e}")
        
        return None
    
    # ========================================
    # MÉTODOS DE ANÁLISE COM IA
    # ========================================
    
    def _analyze_with_ai_forensic(
        self,
        image_bytes: bytes,
        enhanced_bytes: Optional[bytes],
        year: int
    ) -> Dict:
        """
        Análise com IA no modo PERITO FORENSE.
        
        SIMPLIFICADO v5.33: Uma única chamada com referências dos números críticos.
        """
        try:
            b64_original = base64.b64encode(image_bytes).decode()
            b64_enhanced = base64.b64encode(enhanced_bytes).decode() if enhanced_bytes else None
            expected_type = self.get_expected_type(year)
            
            # Construir prompt com referências dos números críticos (0-9)
            content = self._build_prompt_unico(b64_original, b64_enhanced, expected_type, year)
            
            # Chamada única à API
            response = self._call_api_with_retry(content)
            
            if response and response.get('success'):
                return response
            
            return {'success': False, 'error': response.get('error', 'Erro desconhecido')}
            
        except Exception as e:
            logger.error(f"Erro análise IA: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_prompt_unico(
        self,
        b64_original: str,
        b64_enhanced: Optional[str],
        expected_type: str,
        year: int
    ) -> List[Dict]:
        """
        Prompt ÚNICO otimizado para análise PERICIAL.
        
        v5.33: Análise como perito forense - detecta evidências e justifica.
        Score gradual de 0-100 baseado nas evidências encontradas.
        """
        content = []
        
        system_prompt = self._get_system_prompt()
        
        content.append({
            "type": "text",
            "text": f"""{system_prompt}

# VEÍCULO: Ano {year} | Gravação esperada: {expected_type}

---

# 🔍 REFERÊNCIAS - NÚMEROS HONDA ORIGINAL (0-9)

Você é um PERITO FORENSE. Analise cada número comparando com as referências.
Documente TODAS as evidências encontradas, mesmo sutis.

**ESCALA DE SCORE:**
- 0-30: Original - características consistentes com Honda
- 30-50: Baixo risco - pequenas variações aceitáveis  
- 50-70: Suspeito - evidências que merecem atenção
- 70-85: Alto risco - múltiplas evidências de adulteração
- 85-100: Fraude confirmada - evidências incontestáveis

## Referências:
"""
        })
        
        # Usar cache de fontes (apenas números, pré-carregados)
        numeros = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        referencias_enviadas = []
        
        for num in numeros:
            if num in self.font_cache_b64:
                desc = self._get_char_description(num)
                content.append({
                    "type": "text",
                    "text": f"\n**{num}** ({desc}):"
                })
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": self.font_cache_b64[num]}
                })
                referencias_enviadas.append(num)
        
        if referencias_enviadas:
            logger.info(f"  📚 {len(referencias_enviadas)} referências (cache): {referencias_enviadas}")
        
        # Imagem do motor
        content.append({
            "type": "text",
            "text": """

---

# 📷 MOTOR PARA ANÁLISE

**PROCEDIMENTO PERICIAL:**

1. **LEITURA:** Identifique cada caractere do código
2. **COMPARAÇÃO:** Compare cada número com a referência Honda
3. **EVIDÊNCIAS:** Documente diferenças encontradas (formato, proporção, estilo)
4. **SUPERFÍCIE:** Verifique marcas de lixa, números fantasma, irregularidades
5. **CONCLUSÃO:** Score baseado na quantidade e gravidade das evidências

**INDICADORES DE ADULTERAÇÃO:**
- Formato diferente da referência Honda
- "1" com altura menor (moral baixa)
- "0" circular fechado (sem aberturas características)
- "4" sem gap entre linhas
- "3" com topo reto (possível origem do 8)
- "9" similar ao "6" invertido
- Marcas de lixa (riscos paralelos)
- Números fantasma (gravação anterior visível)
- Inconsistência de estilo entre caracteres

## Imagem:
"""
        })
        
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_original}
        })
        
        # Enhanced
        if b64_enhanced:
            content.append({
                "type": "text",
                "text": "\n## Enhanced (para detectar lixa/fantasmas):"
            })
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_enhanced}
            })
        
        # Instruções de resposta
        content.append({
            "type": "text",
            "text": self._get_response_instructions()
        })
        
        return content
    
    def _get_char_description(self, char: str) -> str:
        """Retorna descrição do que verificar em cada caractere."""
        descricoes = {
            '0': "deve ser OVAL com aberturas, NÃO círculo fechado",
            '1': "deve ter ALTURA IGUAL aos outros e serifa no topo",
            '2': "verificar formato do laço inferior",
            '3': "deve ter topo CURVO, não reto",
            '4': "deve ter GAP entre haste e linha horizontal",
            '5': "barriga deve ter abertura à esquerda",
            '6': "círculo pode ter leve abertura",
            '7': "NÃO deve ter traço no meio",
            '8': "círculo superior deve ser MENOR que inferior",
            '9': "deve ter cauda CURVA, não parecer com 6 invertido",
            'A': "verificar formato do triângulo",
            'B': "verificar formato das barrigas",
            'C': "verificar abertura",
            'D': "verificar curva",
            'E': "verificar linhas horizontais",
            'F': "verificar linhas horizontais",
            'G': "verificar formato",
            'H': "verificar linhas verticais e horizontal",
            'J': "verificar gancho inferior",
            'K': "verificar diagonais",
            'L': "verificar ângulo",
            'M': "DUAS diagonais formando V",
            'N': "UMA diagonal do topo-esq para base-dir",
            'P': "verificar barriga superior",
            'X': "verificar cruzamento das diagonais"
        }
        return descricoes.get(char, "verificar formato")
    
    def _get_system_prompt(self) -> str:
        """Retorna o system prompt EQUILIBRADO para análise forense."""
        return """# ANÁLISE DE MOTOR HONDA - v5.33

## SUA ÚNICA TAREFA:
1. Ler o código gravado (prefixo + serial)
2. Verificar se há EVIDÊNCIAS FÍSICAS GRAVES de adulteração

## ⚠️ REGRA FUNDAMENTAL:
**ASSUMA QUE O MOTOR É ORIGINAL.** A maioria dos motores analisados são originais.

## SOBRE MARCAS NA SUPERFÍCIE:
- Motores usados TÊM marcas, riscos e texturas - isso é NORMAL
- Sujeira, óleo, oxidação criam padrões que parecem "irregulares" - isso é NORMAL  
- Reflexos de luz podem parecer "riscos paralelos" - isso é NORMAL
- **VERDADEIRAS marcas de lixa** são: profundas, uniformes, concentradas APENAS na área dos números
- Se a "marca" está em todo o motor, é DESGASTE NORMAL, não adulteração

## CLASSIFICAÇÃO:

**ORIGINAL** (use na maioria dos casos):
- Gravação presente e legível
- Sem números fantasma visíveis
- Sem mistura óbvia de laser/estampagem
- Marcas na superfície = provavelmente uso normal

**SUSPEITO** (use raramente):
- Qualidade de imagem muito ruim para análise
- Área dos números visivelmente mais polida que o resto

**ADULTERADO** (use APENAS com certeza absoluta):
- NÚMEROS FANTASMA claramente visíveis (vestígios de numeração anterior)
- OU mistura ÓBVIA de LASER e ESTAMPAGEM na mesma numeração

## ⚠️ NÃO USE "ADULTERADO" BASEADO EM:
- Formato dos números (0, 1, 4, 6, 8, 9 variam muito)
- "Círculos fechados" - variação normal
- "Marcas de lixa" - quase sempre é desgaste normal
- Textura irregular - motores usados são assim
- Diferenças de fonte - variação de fabricação"""

    def _get_response_instructions(self) -> str:
        """Retorna instruções de formato de resposta - ULTRA SIMPLIFICADA v5.33."""
        return """

# RESPONDA APENAS EM JSON:

```json
{
  "leitura": {
    "linha1": "PREFIXO",
    "linha2": "SERIAL",
    "codigo_completo": "PREFIXO-SERIAL",
    "confianca": 85
  },
  
  "analise_superficie": {
    "numeros_fantasma": false,
    "descricao": "Superfície com desgaste normal de uso"
  },
  
  "analise_gravacao": {
    "tipo_linha1": "LASER",
    "tipo_linha2": "LASER",
    "mistura_tipos": false
  },
  
  "veredicto": {
    "classificacao": "ORIGINAL",
    "certeza": 85,
    "motivo_principal": "Gravação legível, sem números fantasma ou mistura de tipos"
  }
}
```

## REGRAS DO VEREDICTO:

- **ORIGINAL** (padrão): Sem números fantasma, sem mistura laser/estampagem
- **SUSPEITO**: Qualidade de imagem impede análise conclusiva  
- **ADULTERADO**: SOMENTE se encontrar NÚMEROS FANTASMA ou MISTURA LASER/ESTAMPAGEM

## ⚠️ CRÍTICO:
- NÃO classifique como ADULTERADO por causa de "marcas de lixa" - motores usados têm marcas
- NÃO classifique como ADULTERADO por causa de formato dos números
- NA DÚVIDA, sempre use ORIGINAL"""

    def _call_api_with_retry(self, content: List[Dict], max_retries: int = 2) -> Dict:
        """
        Chama API com retry e backoff exponencial.
        
        NOVO v5.16: Implementação robusta com retry.
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
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
                    timeout=self.API_TIMEOUT
                )
                
                if response.status_code == 200:
                    text = response.json()['content'][0]['text']
                    parsed = self._parse_json_response(text)
                    parsed['success'] = True
                    return parsed
                elif response.status_code == 429:  # Rate limit
                    wait_time = (2 ** attempt) * 5
                    logger.warning(f"Rate limit, aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    
            except httpx.TimeoutException:
                last_error = "Timeout na API"
                logger.warning(f"Timeout na tentativa {attempt + 1}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Erro na tentativa {attempt + 1}: {e}")
            
            # Backoff exponencial
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        
        return {'success': False, 'error': last_error}
    
    def _parse_json_response(self, text: str) -> Dict:
        """
        Parse robusto da resposta JSON.
        
        CORREÇÃO v5.16: Tratamento de múltiplos formatos.
        """
        try:
            # Remove marcadores de código markdown
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            
            # Tenta encontrar JSON válido
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                json_str = match.group()
                
                # Tenta parse direto
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Tenta corrigir problemas comuns
                    json_str = re.sub(r',\s*}', '}', json_str)  # Remove vírgulas finais
                    json_str = re.sub(r',\s*]', ']', json_str)
                    return json.loads(json_str)
                    
        except Exception as e:
            logger.warning(f"Erro parse JSON: {e}")
        
        return {}
    # ========================================
    # PROCESSAMENTO DE RESPOSTA
    # ========================================
    
    def _process_response(self, result: Dict, ai: Dict, year: int):
        """
        Processa resposta da IA e atualiza resultado.
        
        CORREÇÃO v5.16: Lógica de extração melhorada.
        """
        # LEITURA
        leitura = ai.get('leitura', {})
        l1 = leitura.get('linha1', '').strip()
        l2 = leitura.get('linha2', '').strip()
        code = leitura.get('codigo_completo', '').strip()
        
        # Monta código se não veio completo
        if not code and l1 and l2:
            code = f"{l1}-{l2}"
        
        if code:
            # Normaliza código
            code = re.sub(r'[^A-Z0-9\-]', '', code.upper())
            result['read_code'] = code
            
            # Extrai prefixo e serial
            parts = code.split('-')
            if parts:
                result['prefix'] = parts[0]
                result['serial'] = parts[1] if len(parts) > 1 else ''
                
                # Busca modelo esperado
                for prefix_candidate in [parts[0], parts[0][:-1], parts[0][:-2]]:
                    if prefix_candidate in self.KNOWN_PREFIXES:
                        result['expected_model'] = self.KNOWN_PREFIXES[prefix_candidate][0]
                        break
        
        result['ocr_confidence'] = {'overall': leitura.get('confianca', 0)}
        
        # ANÁLISE DE FONTE
        checklist = ai.get('checklist_fonte', {})
        result['font_analysis'] = checklist
        result['font_is_honda'] = checklist.get('fonte_geral_compativel_honda', True)
        
        # ANÁLISE DE GRAVAÇÃO
        gravacao = ai.get('analise_gravacao', {})
        tipo_l1 = gravacao.get('tipo_linha1', '').upper()
        tipo_l2 = gravacao.get('tipo_linha2', '').upper()
        
        if tipo_l1 and tipo_l2:
            if tipo_l1 == tipo_l2:
                result['detected_type'] = tipo_l1
            else:
                result['detected_type'] = 'MISTURA'
                result['has_mixed_types'] = True
        
        if gravacao.get('mistura_tipos'):
            result['has_mixed_types'] = True
            result['risk_factors'].append("🚨 Mistura de gravação (LASER + ESTAMPAGEM)")
        
        if not gravacao.get('compativel_com_ano', True):
            result['type_match'] = False
            result['risk_factors'].append(f"⚠️ Tipo incompatível com ano {year}")
        
        # ANÁLISE DE SUPERFÍCIE
        superficie = ai.get('analise_superficie', {})
        result['surface_analysis'] = superficie
        
        # v5.33: Só adiciona risk_factor para números fantasma (evidência definitiva)
        # Marcas de lixa e textura irregular são ignoradas (IA erra muito)
        if superficie.get('numeros_fantasma'):
            result['risk_factors'].append("🚨 Números fantasma detectados")
        
        # VEREDICTO DA IA
        veredicto = ai.get('veredicto', {})
        classificacao = veredicto.get('classificacao', '').upper()
        certeza = veredicto.get('certeza', 0)
        motivo = veredicto.get('motivo_principal', '')
        motivos = veredicto.get('motivos', [])
        
        # Adiciona motivos às recomendações (para referência, não como risk_factor)
        for m in motivos[:5]:
            if m:
                result['recommendations'].append(m)
        
        # v5.33: NÃO adiciona risk_factors aqui - isso é feito em _calculate_risk_score
        # de forma filtrada para evitar falsos positivos
    
    # ========================================
    # CÁLCULO DE SCORE - ULTRA CONSERVADOR v5.33
    # ========================================
    
    def _calculate_risk_score(self, result: Dict, ai: Dict) -> int:
        """
        Calcula score de risco baseado APENAS em evidências físicas GRAVES.
        
        v5.33: Ultra conservador.
        - IGNORA análise de caracteres completamente
        - IGNORA "marcas de lixa" (IA erra muito nisso)
        - Só aumenta score com: números fantasma ou mistura laser/estampagem
        """
        
        # =====================================================
        # MARCADOR v5.33 - SE VOCÊ VER ESTE LOG, ESTÁ CORRETO!
        # =====================================================
        logger.info("=" * 60)
        logger.info("🔷 v5.33 ULTRA CONSERVADOR - _calculate_risk_score ATIVO")
        logger.info("=" * 60)
        
        score = 15  # Base baixa - assume original
        
        veredicto = ai.get('veredicto', {})
        classificacao = veredicto.get('classificacao', '').upper()
        certeza = veredicto.get('certeza', 0)
        motivo = veredicto.get('motivo_principal', '')
        
        logger.info(f"  📋 Veredicto IA: {classificacao} ({certeza}%)")
        
        # ==========================================
        # ÚNICAS EVIDÊNCIAS QUE IMPORTAM
        # ==========================================
        
        superficie = ai.get('analise_superficie', {})
        gravacao = ai.get('analise_gravacao', {})
        
        # Números fantasma = ÚNICA evidência definitiva de adulteração
        if superficie.get('numeros_fantasma'):
            score = 95
            result['risk_factors'].append("🚨 NÚMEROS FANTASMA detectados - evidência de regravação")
            logger.info("  🚨 Score 95: NÚMEROS FANTASMA!")
            return score
        
        # Mistura LASER + ESTAMPAGEM = evidência forte
        if gravacao.get('mistura_tipos'):
            score = 90
            result['risk_factors'].append("🚨 MISTURA de gravação (LASER + ESTAMPAGEM)")
            logger.info("  🚨 Score 90: MISTURA LASER/ESTAMPAGEM!")
            return score
        
        # ==========================================
        # IGNORAR marcas de lixa - IA erra muito
        # ==========================================
        # Comentado porque a IA confunde textura normal com lixa
        # if superficie.get('marcas_lixa') and superficie.get('marcas_paralelas'):
        #     score = 70
        #     result['risk_factors'].append("⚠️ Marcas de lixa paralelas")
        
        # ==========================================
        # VEREDICTO DA IA (muito conservador)
        # ==========================================
        
        if classificacao == 'ORIGINAL':
            score = 15
            result['risk_factors'].append(f"✓ IA: ORIGINAL ({certeza}%)")
            
        elif classificacao == 'SUSPEITO':
            score = 35
            result['risk_factors'].append(f"⚠️ IA: SUSPEITO ({certeza}%)")
            if motivo:
                result['risk_factors'].append(f"  - {motivo}")
            
        elif classificacao == 'ADULTERADO':
            # Só aceita veredicto ADULTERADO se baseado em evidências físicas graves
            motivo_lower = motivo.lower() if motivo else ''
            
            # Veredicto baseado em números fantasma ou mistura = aceitar
            if 'fantasma' in motivo_lower or 'mistura' in motivo_lower:
                score = 85
                result['risk_factors'].append(f"🚨 IA: ADULTERADO ({certeza}%) - {motivo}")
            else:
                # Qualquer outro motivo (caracteres, lixa, fonte) = IGNORAR
                score = 35
                result['risk_factors'].append(f"⚠️ IA mencionou adulteração mas sem evidência física grave")
                logger.info(f"  ℹ️ Veredicto ADULTERADO ignorado - motivo: {motivo}")
        
        logger.info(f"  📊 Score final: {score}")
        
        return min(score, 100)
    
    def _check_specific_chars(self, checklist: Dict, score: int, fonte_ok: bool) -> Tuple[int, bool]:
        """
        Verifica caracteres específicos com critérios de PERITO FORENSE.
        
        Cada indicador contribui para o score de forma independente.
        Múltiplos indicadores se acumulam.
        """
        
        # '4' conectado = forte indicador
        if checklist.get('4_presente'):
            tem_gap = checklist.get('4_tem_gap_visivel', True)
            prob_4 = checklist.get('4_problema', 'nenhum')
            if not tem_gap or prob_4 == 'claramente_conectado':
                score = max(score, 85)
                fonte_ok = False
                logger.info("  🚨 Score 85: '4' CONECTADO (sem gap)")
        
        # '1' com MORAL BAIXA ou sem barra
        if checklist.get('1_presente'):
            altura_ok = checklist.get('1_altura_normal', True)
            tem_barra = checklist.get('1_tem_barra_topo', True)
            moral_baixa = checklist.get('1_moral_baixa', False)
            prob_1 = checklist.get('1_problema', 'nenhum')
            
            if moral_baixa or not altura_ok or prob_1 in ['altura_baixa', 'moral_baixa']:
                score = max(score, 80)
                fonte_ok = False
                logger.info("  🚨 Score 80: '1' com MORAL BAIXA")
            
            if not tem_barra or prob_1 == 'sem_barra':
                score = max(score, 75)
                fonte_ok = False
                logger.info("  ⚠️ Score 75: '1' SEM BARRA/SERIFA")
        
        # '0' fechado circular (sem aberturas)
        if checklist.get('0_presente'):
            tem_aberturas = checklist.get('0_tem_aberturas', True)
            prob_0 = checklist.get('0_problema', 'nenhum')
            
            if not tem_aberturas or prob_0 == 'fechado_circular':
                score = max(score, 85)
                fonte_ok = False
                logger.info("  🚨 Score 85: '0' FECHADO (sem aberturas)")
        
        # '3' com TOPO RETO (provavelmente veio do 8)
        if checklist.get('3_presente'):
            topo_curvo = checklist.get('3_topo_curvo', True)
            topo_reto = checklist.get('3_topo_reto', False)
            prob_3 = checklist.get('3_problema', 'nenhum')
            
            if topo_reto or not topo_curvo or prob_3 in ['topo_reto', 'veio_do_8']:
                score = max(score, 85)
                fonte_ok = False
                logger.info("  🚨 Score 85: '3' com TOPO RETO")
        
        # '9' parece '6' invertido
        if checklist.get('9_presente'):
            cauda_curva = checklist.get('9_cauda_curva', True)
            parece_6 = checklist.get('9_parece_6_invertido', False)
            prob_9 = checklist.get('9_problema', 'nenhum')
            
            if parece_6 or prob_9 in ['parece_6', 'cauda_reta', 'circulo_fechado']:
                score = max(score, 85)
                fonte_ok = False
                logger.info(f"  🚨 Score 85: '9' {prob_9 or 'parece 6'}")
            elif not cauda_curva:
                score = max(score, 70)
                fonte_ok = False
                logger.info("  ⚠️ Score 70: '9' sem cauda curva")
        
        # '7' europeu
        if checklist.get('7_presente'):
            sem_traco = checklist.get('7_sem_traco_meio', True)
            prob_7 = checklist.get('7_problema', 'nenhum')
            if not sem_traco or prob_7 == 'tem_traco_europeu':
                score = max(score, 80)
                fonte_ok = False
                logger.info("  🚨 Score 80: '7' estilo EUROPEU")
        
        # Caracteres secundários
        if checklist.get('5_presente') and not checklist.get('5_barriga_aberta', True):
            score = max(score, 70)
            fonte_ok = False
            logger.info("  ⚠️ Score 70: '5' barriga fechada")
        
        if checklist.get('6_presente') and not checklist.get('6_circulo_aberto', True):
            score = max(score, 70)
            fonte_ok = False
            logger.info("  ⚠️ Score 70: '6' círculo fechado")
        
        if checklist.get('8_presente') and not checklist.get('8_superior_menor', True):
            score = max(score, 65)
            fonte_ok = False
            logger.info("  ⚠️ Score 65: '8' círculos iguais")
        
        return score, fonte_ok
    
    def _check_computer_font_pattern(self, checklist: Dict, score: int, fonte_ok: bool) -> Tuple[int, bool]:
        """Detecta padrão de fonte de computador."""
        
        padrao_computador = checklist.get('padrao_fonte_computador', False)
        multiplos_fechados = checklist.get('multiplos_circulos_fechados', False)
        
        # Conta círculos fechados
        circulos_fechados = 0
        if checklist.get('0_problema') == 'fechado_circular':
            circulos_fechados += 1
        if checklist.get('6_problema') == 'circulo_fechado':
            circulos_fechados += 1
        if checklist.get('9_problema') == 'circulo_fechado':
            circulos_fechados += 1
        
        # Múltiplos círculos fechados = fonte de computador
        if padrao_computador or multiplos_fechados or circulos_fechados >= 2:
            score = max(score, 92)
            fonte_ok = False
            logger.info(f"  🚨 Score 92: PADRÃO FONTE DE COMPUTADOR ({circulos_fechados} círculos fechados)")
        
        return score, fonte_ok
        
        return score, fonte_ok
    
    def _count_total_errors(self, checklist: Dict, qtd_erros: int, chars_problema: List) -> int:
        """Conta total de erros encontrados."""
        
        total = max(qtd_erros, len(chars_problema))
        
        if total == 0:
            # Conta manualmente verificando problemas específicos
            problem_keys = ['0_problema', '1_problema', '3_problema', '4_problema', 
                           '5_problema', '6_problema', '7_problema', '8_problema', '9_problema']
            for key in problem_keys:
                prob = checklist.get(key, 'nenhum')
                if prob not in ['nenhum', '', None]:
                    total += 1
            
            # Verifica também campos booleanos de problemas
            if checklist.get('1_moral_baixa', False):
                total += 1
            if checklist.get('3_topo_reto', False):
                total += 1
            if checklist.get('9_parece_6_invertido', False):
                total += 1
        
        return total
    
    def _check_consistency_and_engraving(
        self,
        ai: Dict,
        checklist: Dict,
        score: int,
        fonte_ok: bool
    ) -> int:
        """
        Verifica consistência entre linhas, tipo de gravação, superfície e alinhamento.
        
        Critérios de PERITO FORENSE:
        - Mistura de tipos = FRAUDE CONFIRMADA
        - Números fantasma = FRAUDE CONFIRMADA
        - Marcas de lixa paralelas = FORTE SUSPEITA
        - Desalinhamento severo = SUSPEITA
        - Espaçamento irregular = SUSPEITA
        """
        
        gravacao = ai.get('analise_gravacao', {})
        consistencia = checklist.get('consistencia_linha1_linha2', True)
        estilo_consistente = gravacao.get('estilo_fonte_consistente', True)
        
        # Inconsistência entre linhas = SUSPEITO
        if not consistencia or not estilo_consistente:
            score = max(score, 85)
            logger.info("  🚨 Score 85: INCONSISTÊNCIA entre linha 1 e linha 2")
        
        # MISTURA DE TIPOS = FRAUDE CONFIRMADA
        if gravacao.get('mistura_tipos'):
            score = max(score, 98)
            qual_parte = gravacao.get('qual_parte_diferente', '')
            logger.info(f"  🚨 Score 98: MISTURA LASER + ESTAMPAGEM {qual_parte}")
        
        # NÚMEROS FANTASMA = FRAUDE CONFIRMADA
        superficie = ai.get('analise_superficie', {})
        checklist_sup = ai.get('checklist_superficie', {})
        
        tem_fantasma = (
            superficie.get('numeros_fantasma', False) or
            checklist_sup.get('numeros_fantasma_visiveis', False)
        )
        if tem_fantasma:
            score = max(score, 98)
            descricao = checklist_sup.get('descricao_fantasma', superficie.get('descricao_detalhada', ''))
            logger.info(f"  🚨 Score 98: NÚMEROS FANTASMA {descricao}")
        
        # MARCAS DE LIXA = FORTE SUSPEITA
        tem_lixa = (
            superficie.get('marcas_lixa', False) or
            superficie.get('marcas_paralelas', False) or
            checklist_sup.get('tipo_marcas') == 'lixamento_suspeito' or
            checklist_sup.get('marcas_paralelas_uniformes', False)
        )
        if tem_lixa:
            score = max(score, 75)
            logger.info("  🚨 Score 75: MARCAS DE LIXA detectadas")
            
            # Se marcas estão concentradas nos números = mais suspeito
            if checklist_sup.get('marcas_concentradas_nos_numeros', False):
                score = max(score, 85)
                logger.info("  🚨 Score 85: Lixa concentrada nos números!")
        
        # DESALINHAMENTO
        checklist_alin = ai.get('checklist_alinhamento', {})
        
        # Desalinhamento severo ou punção manual = FORTE SUSPEITA
        if checklist_alin.get('desalinhamento_severo', False) or checklist_alin.get('indica_puncao_manual', False):
            score = max(score, 80)
            qual = checklist_alin.get('qual_caractere_desalinhado', '')
            logger.info(f"  🚨 Score 80: DESALINHAMENTO SEVERO / PUNÇÃO MANUAL {qual}")
        elif not checklist.get('numeros_alinhados', True) or not checklist_alin.get('todos_na_mesma_linha_base', True):
            score = max(score, 70)
            logger.info("  ⚠️ Score 70: Desalinhamento detectado")
        
        # ESPAÇAMENTO IRREGULAR = SUSPEITA
        espacamento_irregular = (
            checklist_alin.get('espacamento_irregular', False) or
            not checklist.get('espaçamento_uniforme', True)
        )
        if espacamento_irregular:
            score = max(score, 75)
            qual = checklist_alin.get('qual_espacamento_irregular', '')
            logger.info(f"  ⚠️ Score 75: ESPAÇAMENTO IRREGULAR {qual}")
        
        return score
    
    def _apply_ai_verdict(
        self,
        ai: Dict,
        checklist: Dict,
        score: int,
        fonte_ok: bool,
        qtd_erros: int,
        chars_problema: List
    ) -> int:
        """
        DUPLA CHECAGEM: Aplica veredicto da IA comparando com análise estruturada.
        
        Esta é a segunda camada de verificação. O veredicto da IA serve para:
        1. Confirmar problemas detectados no checklist
        2. Detectar problemas que o checklist não capturou
        3. Identificar inconsistências que requerem atenção
        """
        
        veredicto = ai.get('veredicto', {})
        classificacao = veredicto.get('classificacao', '').upper()
        certeza = veredicto.get('certeza', 0)
        motivos = veredicto.get('motivos', [])
        
        if classificacao == 'ADULTERADO':
            # IA detectou adulteração
            if not fonte_ok or qtd_erros > 0 or len(chars_problema) > 0:
                # CONFIRMADO: Checklist também indica problemas
                score = max(score, int(certeza * 0.95))
                logger.info(f"  ✓ DUPLA CONFIRMAÇÃO: IA e Checklist concordam - ADULTERADO ({certeza}%)")
            else:
                # IA viu algo que o checklist não capturou
                # Confia na IA mas com peso menor
                score = max(score, int(certeza * 0.7))
                logger.info(f"  ℹ️ IA detectou adulteração não capturada no checklist: {motivos}")
                
        elif classificacao == 'SUSPEITO':
            # IA tem dúvidas
            if score < 50:
                # Checklist não encontrou nada mas IA está em dúvida
                score = max(score, int(certeza * 0.5))
                logger.info(f"  ℹ️ IA está em dúvida ({certeza}%): {motivos}")
            else:
                # Checklist já indicou problemas, IA confirma suspeita
                score = max(score, int(certeza * 0.7))
                logger.info(f"  ⚠️ IA confirma suspeita do checklist ({certeza}%)")
            
        elif classificacao == 'ORIGINAL':
            # IA diz que é original
            
            # VERIFICAÇÃO EXTRA: Checar indicadores de superfície
            checklist_sup = ai.get('checklist_superficie', {})
            superficie = ai.get('analise_superficie', {})
            checklist_alin = ai.get('checklist_alinhamento', {})
            
            # Indicadores graves que a IA pode ter subestimado
            tem_fantasma = (
                checklist_sup.get('numeros_fantasma_visiveis', False) or
                superficie.get('numeros_fantasma', False)
            )
            tem_lixa = (
                checklist_sup.get('tipo_marcas') == 'lixamento_suspeito' or
                superficie.get('marcas_lixa', False)
            )
            desalinhamento_severo = checklist_alin.get('desalinhamento_severo', False)
            puncao_manual = checklist_alin.get('indica_puncao_manual', False)
            
            # Se há indicadores graves, NÃO aceitar o veredicto ORIGINAL
            if tem_fantasma:
                score = max(score, 90)
                logger.info("  🚨 OVERRIDE: Números fantasma detectados - ignorando veredicto ORIGINAL")
            elif tem_lixa:
                score = max(score, 75)
                logger.info("  ⚠️ OVERRIDE: Marcas de lixa - ignorando veredicto ORIGINAL")
            elif desalinhamento_severo or puncao_manual:
                score = max(score, 80)
                logger.info("  ⚠️ OVERRIDE: Desalinhamento severo - ignorando veredicto ORIGINAL")
            elif score >= 70:
                # Checklist já indicou score alto, manter
                logger.info(f"  ⚠️ Checklist indica score {score}, IA diz ORIGINAL - mantendo score do checklist")
            elif score >= 50:
                # Score médio - reduzir levemente mas manter suspeita
                score = int(score * 0.9)
                logger.info(f"  ℹ️ IA diz ORIGINAL mas há suspeitas - score ajustado para {score}")
            else:
                # Checklist OK e IA OK = provavelmente original
                logger.info("  ✓ DUPLA CONFIRMAÇÃO: IA e Checklist concordam - ORIGINAL")
        
        return score
        
        return score
    
    # ========================================
    # MÉTODOS DE PERSISTÊNCIA
    # ========================================
    
    def _save_analysis(
        self,
        image_url: Optional[str],
        year: int,
        model: Optional[str],
        result: Dict,
        ai_response: Dict,
        processing_time: int
    ) -> Optional[str]:
        """Salva análise no banco de dados."""
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
                'processing_time_ms': processing_time,
                'created_at': datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table('analysis_history').insert(data).execute()
            
            if response.data:
                return response.data[0].get('id')
                
        except Exception as e:
            logger.error(f"Erro salvando análise: {e}")
        
        return None
