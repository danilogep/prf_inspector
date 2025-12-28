"""
Serviço de Análise Forense com IA v5.15
=======================================
MELHORIAS v5.15:
- Verificação dos números 5 e 6 (barriga/círculo fechado = fraude)
- Detecção de PADRÃO FONTE DE COMPUTADOR (múltiplos círculos fechados)
- Verificação de CONSISTÊNCIA entre linha 1 e linha 2
- Escala de score por QUANTIDADE de erros (3+ erros = 98)
- Tipos de problema específicos: fechado_circular, barriga_fechada, circulo_fechado

MANTIDO de v5.14b:
- Diferenciação M vs N com contagem de diagonais
- Comparação obrigatória com referências Honda antes de criticar
- 1 caractere claramente alterado = FRAUDE
- Diferenciação entre marcas de uso e lixamento
- Filtro Forense CLAHE

LÓGICA DE SCORE:
- 1 erro claro = 85
- 2 erros = 92
- 3+ erros = 98
- Múltiplos círculos fechados = 95 (fonte de computador)
- Números fantasma = 98
- Inconsistência entre linhas = 90
"""

import base64
import re
import json
import httpx
import time
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from app.core.logger import logger
from app.core.config import settings

# OpenCV para filtro forense
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
    logger.info("✓ OpenCV disponível para análise forense")
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("⚠️ OpenCV não instalado - pip install opencv-python")


class ForensicAIService:
    """Análise forense v5.15 - Detecção de Fonte de Computador + Consistência"""
    
    LASER_TRANSITION_YEAR = 2010
    
    # Números críticos que fraudadores mais erram
    # Adicionado 5 e 6 em v5.15
    HIGH_RISK_CHARS = ['0', '1', '3', '4', '5', '6', '8', '9']
    
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
    # ESPECIFICAÇÕES GEOMÉTRICAS HONDA (Baseado em fontes reais)
    # ========================================
    HONDA_GEOMETRY = {
        '0': {
            'forma': 'Oval ABERTO (duas hastes curvas separadas)',
            'caracteristica': 'Extremidades NÃO se tocam no topo e base',
            'fraude': 'Zero fechado/circular = FRAUDE'
        },
        '1': {
            'forma': 'Haste vertical com BARRA HORIZONTAL no topo esquerdo',
            'caracteristica': 'Parece um 7 espelhado - barra sai para ESQUERDA',
            'fraude': 'Sem barra (palito reto) ou muito curto (moral baixa) = FRAUDE'
        },
        '2': {
            'forma': 'Curva superior + base horizontal',
            'caracteristica': 'Curva aberta descendo para base reta',
            'fraude': 'Formato irregular'
        },
        '3': {
            'forma': 'Duas curvas C ABERTAS empilhadas',
            'caracteristica': 'Curvas não fecham, abertas à esquerda',
            'fraude': 'Curvas fechadas ou assimétricas = FRAUDE'
        },
        '4': {
            'forma': 'Parte angular + haste vertical SEPARADAS',
            'caracteristica': 'GAP obrigatório entre as partes',
            'fraude': 'Linhas conectadas/tocando = FRAUDE'
        },
        '5': {
            'forma': 'Barra horizontal topo + curva inferior aberta',
            'caracteristica': 'Círculo inferior não fecha completamente',
            'fraude': 'Círculo fechado = FRAUDE'
        },
        '6': {
            'forma': 'Cauda superior curva + círculo inferior aberto',
            'caracteristica': 'Círculo não fecha, tem abertura',
            'fraude': 'Círculo fechado = FRAUDE'
        },
        '7': {
            'forma': 'Barra horizontal + diagonal descendo',
            'caracteristica': 'SEM traço no meio (não é estilo europeu)',
            'fraude': 'Com traço no meio = FRAUDE'
        },
        '8': {
            'forma': 'Duas curvas ABERTAS (tipo S com pontas próximas)',
            'caracteristica': 'Curvas não fecham completamente',
            'fraude': 'Círculos fechados = FRAUDE'
        },
        '9': {
            'forma': 'Oval superior + cauda diagonal descendo',
            'caracteristica': 'Oval aberto + cauda reta/diagonal',
            'fraude': 'Oval fechado ou cauda muito curva = FRAUDE'
        }
    }
    
    # Especificações das Letras Honda
    LETTER_SPECS = {
        'A': {
            'forma': 'Duas diagonais + barra horizontal no meio',
            'caracteristica': 'Triângulo aberto no topo'
        },
        'B': {
            'forma': 'Haste vertical + duas curvas à direita',
            'caracteristica': 'Curvas ABERTAS (não fecham)'
        },
        'C': {
            'forma': 'Curva aberta à direita',
            'caracteristica': 'Abertura voltada para direita'
        },
        'D': {
            'forma': 'Haste vertical + curva fechando à direita',
            'caracteristica': 'Forma de arco'
        },
        'E': {
            'forma': 'Haste vertical + três barras horizontais',
            'caracteristica': 'Barras no topo, meio e base'
        },
        'F': {
            'forma': 'Haste vertical + duas barras horizontais',
            'caracteristica': 'Barras no topo e meio (sem base)'
        },
        'G': {
            'forma': 'Curva C + barra horizontal entrando',
            'caracteristica': 'Barra entra no meio da curva'
        },
        'H': {
            'forma': 'Duas hastes verticais + barra no meio',
            'caracteristica': 'Hastes paralelas conectadas'
        },
        'I': {
            'forma': 'Haste vertical simples SEM barra',
            'caracteristica': 'Palito reto (diferente do 1 que tem barra horizontal no topo)'
        },
        'J': {
            'forma': 'Curva inferior + haste subindo',
            'caracteristica': 'Gancho na base'
        },
        'K': {
            'forma': 'Haste vertical + duas diagonais',
            'caracteristica': 'V deitado tocando a haste'
        },
        'M': {
            'forma': 'Duas hastes + DUAS diagonais (V invertido)',
            'caracteristica': 'Diagonais se encontram no CENTRO, ponta para BAIXO',
            'confusao': 'N tem apenas UMA diagonal'
        },
        'N': {
            'forma': 'Duas hastes + UMA diagonal',
            'caracteristica': 'Diagonal do topo-esquerdo ao base-direita',
            'confusao': 'M tem DUAS diagonais'
        },
        'P': {
            'forma': 'Haste vertical + curva fechada no topo',
            'caracteristica': 'Curva só no topo'
        },
        'S': {
            'forma': 'Duas curvas abertas em S',
            'caracteristica': 'Curvas opostas empilhadas'
        }
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
            logger.info(f"✓ Serviço de IA Forense v5.15 (Fonte Computador + Consistência)")
            logger.info(f"  Fontes visuais: {len(self.font_urls)}")
            logger.info(f"  OpenCV CLAHE: {'Ativo' if OPENCV_AVAILABLE else 'Inativo'}")
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
    
    # ========================================
    # FILTRO FORENSE - CLAHE (OpenCV)
    # ========================================
    def _apply_forensic_filter(self, image_bytes: bytes) -> Optional[bytes]:
        """
        Aplica filtro CLAHE para realçar:
        - Marcas de lixa
        - Sulcos de metalurgia
        - Irregularidades de superfície
        - Diferenças de profundidade
        """
        if not OPENCV_AVAILABLE:
            return None
        
        try:
            # Converte bytes para numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            # Converte para LAB (melhor para CLAHE em imagens coloridas)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Aplica CLAHE no canal L (luminância)
            # clipLimit alto = mais contraste local (realça texturas)
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
            l_clahe = clahe.apply(l)
            
            # Aplica também um filtro de realce de bordas para sulcos
            # Isso ajuda a ver marcas de ferramentas e lixa
            kernel_sharpen = np.array([[-1, -1, -1],
                                       [-1,  9, -1],
                                       [-1, -1, -1]])
            l_sharp = cv2.filter2D(l_clahe, -1, kernel_sharpen)
            
            # Combina: 70% CLAHE + 30% sharpened
            l_final = cv2.addWeighted(l_clahe, 0.7, l_sharp, 0.3, 0)
            
            # Reconstrói a imagem
            lab_clahe = cv2.merge([l_final, a, b])
            img_enhanced = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
            
            # Adiciona texto indicando que é versão forense
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(img_enhanced, 'FORENSIC ENHANCED', (10, 30), 
                       font, 0.7, (0, 255, 255), 2)
            
            # Converte de volta para bytes
            _, buffer = cv2.imencode('.jpg', img_enhanced, [cv2.IMWRITE_JPEG_QUALITY, 95])
            return buffer.tobytes()
            
        except Exception as e:
            logger.warning(f"Erro filtro CLAHE: {e}")
            return None
    
    def analyze(self, image_bytes: bytes, year: int, model: str = None) -> Dict[str, Any]:
        """Análise forense principal com filtro CLAHE."""
        
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
            'forensic_enhanced': OPENCV_AVAILABLE,
            'repeated_chars_analysis': [],
            'recommendations': [],
            'references_used': {'originals': 0, 'fonts': 0}
        }
        
        if not self.enabled:
            result['risk_factors'].append("⚠️ IA não configurada")
            result['risk_score'] = 50
            return result
        
        try:
            expected_type = self.get_expected_type(year)
            logger.info(f"🤖 Análise v5.11 | Ano: {year} | Tipo esperado: {expected_type}")
            
            # Aplica filtro forense CLAHE
            enhanced_bytes = self._apply_forensic_filter(image_bytes)
            if enhanced_bytes:
                logger.info("  ✓ Filtro CLAHE aplicado")
            
            image_url = self._upload_analysis_image(image_bytes)
            
            result['references_used'] = {
                'originals': len(self._get_original_patterns()),
                'fonts': len(self.font_urls)
            }
            
            # Análise com IA
            ai_response = self._analyze_with_ai_forensic(
                image_bytes, 
                enhanced_bytes, 
                year
            )
            
            logger.info(f"🔍 Resposta AI: {json.dumps(ai_response, ensure_ascii=False)[:300]}...")
            
            if not ai_response.get('success'):
                result['risk_factors'].append(f"Erro IA: {ai_response.get('error')}")
                result['risk_score'] = 50
                return result
            
            result['success'] = True
            self._process_response(result, ai_response, year)
            result['risk_score'] = self._calculate_risk_score_strict(result, ai_response)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Salva análise - MÉTODO ORIGINAL
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
            logger.info(f"  Fonte Honda: {'SIM' if result.get('font_is_honda') else 'NÃO - FRAUDE!'}")
            logger.info(f"  Score: {result['risk_score']}")
            logger.info(f"  ID: {analysis_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro análise: {e}", exc_info=True)
            result['risk_factors'].append(f"Erro: {str(e)}")
            result['risk_score'] = 50
            return result
    
    def _analyze_with_ai_forensic(self, image_bytes: bytes, 
                                   enhanced_bytes: Optional[bytes], 
                                   year: int) -> Dict:
        """
        Análise com IA no modo PERITO FORENSE.
        Envia duas imagens: Original + Forensic Enhanced
        """
        try:
            b64_original = base64.b64encode(image_bytes).decode()
            b64_enhanced = base64.b64encode(enhanced_bytes).decode() if enhanced_bytes else None
            expected_type = self.get_expected_type(year)
            
            content = []
            
            # ==========================================
            # SYSTEM PROMPT: PERITO FORENSE CÉTICO
            # ==========================================
            system_prompt = """# 🔬 PERITO FORENSE - ANÁLISE DE MOTOR HONDA

## ⚠️⚠️⚠️ REGRA MAIS IMPORTANTE ⚠️⚠️⚠️

**ANTES DE DIZER QUE UM CARACTERE ESTÁ ERRADO:**
1. OLHE a imagem de referência Honda desse caractere
2. COMPARE lado a lado com o caractere no motor
3. SÓ critique se for REALMENTE diferente

**A fonte Honda industrial TEM características específicas. NÃO confunda com fontes de computador!**

---

## ⚠️ DIFERENÇA ENTRE M E N (CONTE AS DIAGONAIS!)

## LETRA M:
- TEM **DUAS** diagonais no meio
- As diagonais formam um **V** com ponta para **BAIXO**
```
│╲  ╱│
│ ╲╱ │  ← V para BAIXO (2 diagonais)
│    │
```

## LETRA N:
- TEM **UMA** diagonal só
- A diagonal vai do **TOPO ESQUERDO** para **BASE DIREITA**
```
│╲   │
│ ╲  │  ← UMA diagonal só
│  ╲ │
```

---

# 🔤 CARACTERÍSTICAS DA FONTE HONDA INDUSTRIAL

## IMPORTANTE: A fonte Honda NÃO é uma fonte de computador!
Os caracteres Honda têm acabamento industrial com pequenas imperfeições normais.

## NÚMERO 0 HONDA:
- Forma OVAL (não circular)
- Pode ter pequenas aberturas nos extremos (normal)
- NÃO é um círculo perfeito
**→ ERRO seria: círculo perfeitamente redondo ou muito estreito**

## NÚMERO 1 HONDA:
- Tem BARRA HORIZONTAL no topo saindo para ESQUERDA
- Parece um "7 espelhado"
- Altura proporcional aos outros números
**→ ERRO seria: palito reto sem barra, ou muito curto (moral baixa)**

## NÚMERO 4 HONDA:
- A parte angular e a haste vertical são SEPARADAS
- Existe um pequeno GAP entre elas
- O gap pode ser pequeno mas EXISTE
**→ ERRO seria: linhas claramente conectadas/tocando**

## NÚMERO 5 HONDA:
- Barra horizontal no topo + curva inferior ABERTA
- A "barriga" do 5 NÃO fecha completamente
- Parece um S invertido com abertura
**→ ERRO seria: barriga completamente FECHADA (círculo)**

## NÚMERO 6 HONDA:
- Cauda superior curva + círculo inferior ABERTO
- O círculo tem uma pequena abertura
- NÃO é um círculo perfeito fechado
**→ ERRO seria: círculo completamente FECHADO**

## NÚMERO 7 HONDA:
- Barra horizontal + diagonal
- SEM traço no meio
**→ ERRO seria: traço cortando a diagonal (estilo europeu)**

## NÚMERO 8 HONDA:
- Duas curvas empilhadas
- Forma de "S" ou ampulheta
- Pode ter pequenas aberturas (normal)
**→ ERRO seria: dois círculos perfeitos fechados**

## NÚMERO 9 HONDA:
- Oval no topo + cauda descendo
- O oval pode ter pequena abertura (normal)
**→ ERRO seria: círculo perfeito fechado no topo**

---

# 🔍 QUANDO CLASSIFICAR COMO PROBLEMA DE FONTE:

**SÓ marque como fonte errada se:**
- O caractere for CLARAMENTE diferente da referência Honda
- A diferença for ÓBVIA, não sutil
- Múltiplos caracteres estiverem errados

**NÃO marque como fonte errada se:**
- O caractere parecer com a referência Honda (mesmo com pequenas variações)
- A diferença for apenas de desgaste/uso
- Apenas um caractere tiver variação mínima

---

# 🔍 SINAIS DE ADULTERAÇÃO REAL:

## 1. NÚMEROS FANTASMA (CRÍTICO!)
Sombras de números ANTERIORES visíveis sob os atuais.
**→ FRAUDE CONFIRMADA**

## 2. PADRÃO "FONTE DE COMPUTADOR" (CRÍTICO!)
Se MÚLTIPLOS números aparecem como CÍRCULOS FECHADOS (0, 5, 6, 8, 9):
- 0 circular fechado + 8 círculos fechados = fonte de computador
- 5 com barriga fechada + 6 fechado = fonte de computador
**→ Múltiplos círculos fechados = FRAUDE (fonte não é Honda)**

## 3. FONTE COMPLETAMENTE DIFERENTE
Todos ou maioria dos caracteres são de fonte diferente (computador, punção manual).
**→ FRAUDE**

## 4. INCONSISTÊNCIA ENTRE LINHAS
Se a linha 1 (prefixo) tem estilo diferente da linha 2 (serial):
- Uma linha mais profunda que outra
- Estilos de fonte visivelmente diferentes
**→ Indica regravação parcial = FRAUDE**

## 5. DESALINHAMENTO SEVERO
Números claramente "dançando", alturas muito diferentes.
**→ Punção manual = FRAUDE**

## 6. LIXAMENTO EVIDENTE + REGRAVAÇÃO
Área claramente lixada COM caracteres de fonte diferente.
**→ FRAUDE**

---

# ⚠️ CUIDADO COM FALSOS POSITIVOS:

## Marcas de USO (NÃO são fraude):
- Arranhões aleatórios
- Desgaste uniforme
- Oxidação natural
- Sujeira

## Variações NORMAIS da fonte Honda:
- Pequenas imperfeições no acabamento
- Desgaste nas bordas dos caracteres
- Profundidade variável (normal em estampagem)

---

# ⚡ CRITÉRIOS DE CLASSIFICAÇÃO:

| Situação | Classificação |
|----------|---------------|
| Números fantasma | ADULTERADO |
| 1+ caractere CLARAMENTE diferente (comparado com referência) | ADULTERADO |
| Desalinhamento severo (punção manual) | ADULTERADO |
| Lixamento + caractere adulterado | ADULTERADO |
| Fonte Honda OK + marcas de uso | **ORIGINAL** |
| Dúvida em caractere (não certeza) | SUSPEITO |

## ⚠️ IMPORTANTE:
- **1 caractere adulterado = FRAUDE** (fraudadores às vezes alteram só 1-2 números)
- MAS você precisa ter CERTEZA comparando com a referência Honda
- Se parecer com a referência Honda = NÃO é erro
- A fonte Honda industrial tem pequenas variações normais

"""
            content.append({"type": "text", "text": system_prompt})
            
            # ==========================================
            # REFERÊNCIAS VISUAIS DAS FONTES
            # ==========================================
            content.append({
                "type": "text",
                "text": "\n# 📚 FONTE HONDA - REFERÊNCIAS VISUAIS:\n"
            })
            
            # Números críticos primeiro
            for char in ['0', '1', '4', '3', '9', '7', '8', '2', '5', '6']:
                if char in self.font_urls:
                    b64_font = self._download_font_as_base64(char)
                    if b64_font:
                        specs = self.HONDA_GEOMETRY.get(char, {})
                        extra = f" - {specs.get('forma', '')}" if specs else ""
                        is_critical = "🚨 CRÍTICO" if char in self.HIGH_RISK_CHARS else ""
                        content.append({"type": "text", "text": f"\n### Número '{char}' {is_critical}{extra}"})
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                        })
            
            # Letras M e N (CRÍTICAS - com destaque especial)
            content.append({
                "type": "text",
                "text": "\n## ⚠️⚠️⚠️ LETRAS M e N - CONTE AS DIAGONAIS! ⚠️⚠️⚠️\n"
            })
            
            if 'M' in self.font_urls:
                b64_font = self._download_font_as_base64('M')
                if b64_font:
                    content.append({
                        "type": "text", 
                        "text": "\n### LETRA 'M' = DUAS diagonais (V com ponta para BAIXO)"
                    })
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                    })
            
            if 'N' in self.font_urls:
                b64_font = self._download_font_as_base64('N')
                if b64_font:
                    content.append({
                        "type": "text", 
                        "text": "\n### LETRA 'N' = UMA diagonal só (topo-esquerdo → base-direita)"
                    })
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                    })
            
            content.append({
                "type": "text",
                "text": "\n**⚠️ CONTE AS DIAGONAIS: 2 diagonais = M | 1 diagonal = N**\n"
            })
            
            # Outras letras
            for char in sorted(self.font_urls.keys()):
                if char.isalpha() and char not in ['M', 'N']:
                    b64_font = self._download_font_as_base64(char)
                    if b64_font:
                        content.append({"type": "text", "text": f"\n### Letra '{char}'"})
                        content.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64_font}
                        })
            
            # ==========================================
            # IMAGENS DO MOTOR (Original + Enhanced)
            # ==========================================
            content.append({
                "type": "text",
                "text": f"""

# 🔍 MOTOR PARA ANÁLISE

**Ano declarado:** {year}
**Tipo esperado:** {expected_type}

## ⚠️ INSTRUÇÕES DE LEITURA:

1. **LEIA CARACTERE POR CARACTERE** - Não pule nenhum!
2. **CARACTERES REPETIDOS** - Se houver dois "4" seguidos, escreva "44". Se houver dois "0" seguidos, escreva "00".
3. **CONTE OS CARACTERES** - Verifique se o total está correto.
4. **LINHA 1 (Prefixo)** - Geralmente 5-6 caracteres (ex: MC44E1, JC96E, ND09E1)
5. **LINHA 2 (Serial)** - Geralmente 6-7 caracteres começando com letra

## IMAGEM DO MOTOR:
"""
            })
            
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_original}
            })
            
            # Adiciona imagem enhanced se disponível
            if b64_enhanced:
                content.append({
                    "type": "text",
                    "text": """

## IMAGEM ENHANCED (contraste aumentado):
Procure marcas de lixa e alterações de textura.
"""
                })
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_enhanced}
                })
            
            # ==========================================
            # INSTRUÇÕES DE ANÁLISE
            # ==========================================
            content.append({
                "type": "text",
                "text": """

# RESPONDA EM JSON - SEJA CONSERVADOR NA ANÁLISE DE FONTE:

```json
{
  "leitura": {
    "linha1": "PREFIXO COMPLETO",
    "linha2": "SERIAL COMPLETO",
    "codigo_completo": "PREFIXO-SERIAL",
    "confianca": 0-100
  },
  
  "checklist_fonte": {
    "comparei_com_referencias": true,
    
    "0_presente": true/false,
    "0_similar_referencia_honda": true/false,
    "0_problema": "nenhum / fechado_circular",
    
    "1_presente": true/false,
    "1_tem_barra_topo": true/false,
    "1_altura_normal": true/false,
    "1_similar_referencia_honda": true/false,
    "1_problema": "nenhum / sem_barra / moral_baixa",
    
    "4_presente": true/false,
    "4_tem_gap_visivel": true/false,
    "4_similar_referencia_honda": true/false,
    "4_problema": "nenhum / claramente_conectado",
    
    "5_presente": true/false,
    "5_barriga_aberta": true/false,
    "5_similar_referencia_honda": true/false,
    "5_problema": "nenhum / barriga_fechada",
    
    "6_presente": true/false,
    "6_circulo_aberto": true/false,
    "6_similar_referencia_honda": true/false,
    "6_problema": "nenhum / circulo_fechado",
    
    "7_presente": true/false,
    "7_sem_traco_meio": true/false,
    "7_problema": "nenhum / tem_traco_europeu",
    
    "8_presente": true/false,
    "8_similar_referencia_honda": true/false,
    "8_problema": "nenhum / circulos_fechados",
    
    "9_presente": true/false,
    "9_similar_referencia_honda": true/false,
    "9_problema": "nenhum / circulo_fechado",
    
    "M_ou_N_presente": true/false,
    "M_ou_N_diagonais_contadas": 1 ou 2,
    "M_ou_N_letra_identificada": "M ou N",
    
    "padrao_fonte_computador": true/false,
    "multiplos_circulos_fechados": true/false,
    "consistencia_linha1_linha2": true/false,
    
    "fonte_geral_compativel_honda": true/false,
    "quantos_caracteres_claramente_errados": 0,
    "caracteres_com_problema_claro": []
  },
  
  "checklist_superficie": {
    "numeros_fantasma_visiveis": true/false,
    "descricao_fantasma": "",
    
    "tipo_marcas": "nenhuma / uso_normal / lixamento_suspeito",
    "marcas_paralelas_uniformes": true/false,
    "marcas_concentradas_nos_numeros": true/false,
    "descricao_marcas": ""
  },
  
  "checklist_alinhamento": {
    "numeros_bem_alinhados": true/false,
    "desalinhamento_severo": true/false,
    "indica_puncao_manual": true/false
  },
  
  "analise_gravacao": {
    "tipo_linha1": "LASER ou ESTAMPAGEM",
    "tipo_linha2": "LASER ou ESTAMPAGEM",
    "mistura_tipos": true/false,
    "profundidade_uniforme": true/false,
    "estilo_fonte_consistente": true/false
  },
  
  "veredicto": {
    "classificacao": "ORIGINAL ou SUSPEITO ou ADULTERADO",
    "certeza": 0-100,
    "motivos": [],
    "motivo_principal": ""
  }
}
```

## ⚠️ REGRAS PARA CLASSIFICAR:

**ADULTERADO** - se QUALQUER um:
- Números fantasma visíveis
- 1 ou mais caracteres CLARAMENTE diferentes (0,5,6,8,9 fechados; 4 conectado; 1 sem barra)
- Padrão "fonte de computador" (múltiplos círculos fechados)
- Inconsistência entre linha 1 e linha 2
- Desalinhamento SEVERO (punção manual)
- Mistura de tipos de gravação

**ORIGINAL** - se TODOS:
- Fonte compatível com Honda (comparou e é similar)
- Sem números fantasma
- Alinhamento adequado
- Consistência entre linhas
- Marcas são apenas de uso normal

**SUSPEITO** - se:
- Dúvida em algum caractere (não certeza de erro)
- Alguma irregularidade menor

**CRÍTICO: 
- 1 caractere adulterado = FRAUDE (fraudadores alteram só 1-2 números às vezes)
- Múltiplos círculos fechados (0,5,6,8,9) = fonte de computador = FRAUDE
- Compare CADA caractere com a referência Honda!**
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
        """Processa resposta com CHECKLIST OBRIGATÓRIO."""
        
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
        
        # ==========================================
        # CHECKLIST DE FONTE
        # ==========================================
        checklist_fonte = ai.get('checklist_fonte', {})
        result['font_analysis'] = checklist_fonte
        
        # Fonte é Honda?
        fonte_honda = checklist_fonte.get('fonte_geral_compativel_honda', checklist_fonte.get('fonte_e_honda', True))
        result['font_is_honda'] = fonte_honda
        
        # Quantos caracteres com problema CLARO?
        qtd_erros = checklist_fonte.get('quantos_caracteres_claramente_errados', 0)
        chars_problema = checklist_fonte.get('caracteres_com_problema_claro', checklist_fonte.get('caracteres_com_problema', []))
        
        # Verificar cada número no checklist
        problemas_detalhados = []
        
        # Número 0
        if checklist_fonte.get('0_presente'):
            similar = checklist_fonte.get('0_similar_referencia_honda', checklist_fonte.get('0_aberto_como_honda', True))
            prob = checklist_fonte.get('0_problema', 'nenhum')
            if not similar and prob != 'nenhum':
                problemas_detalhados.append(f"'0' {prob}")
                fonte_honda = False
        
        # Número 1
        if checklist_fonte.get('1_presente'):
            similar = checklist_fonte.get('1_similar_referencia_honda', True)
            if not checklist_fonte.get('1_tem_barra_topo', True) and not similar:
                problemas_detalhados.append("'1' sem barra no topo")
                fonte_honda = False
            if not checklist_fonte.get('1_altura_normal', True):
                problemas_detalhados.append("'1' moral baixa")
                fonte_honda = False
            prob_1 = checklist_fonte.get('1_problema', 'nenhum')
            if prob_1 not in ['nenhum', ''] and f"'1'" not in str(problemas_detalhados):
                problemas_detalhados.append(f"'1' {prob_1}")
                fonte_honda = False
        
        # Número 4
        if checklist_fonte.get('4_presente'):
            tem_gap = checklist_fonte.get('4_tem_gap_visivel', checklist_fonte.get('4_tem_gap', True))
            similar = checklist_fonte.get('4_similar_referencia_honda', True)
            prob = checklist_fonte.get('4_problema', 'nenhum')
            if not tem_gap or prob == 'claramente_conectado':
                problemas_detalhados.insert(0, "'4' conectado (sem gap)")
                fonte_honda = False
        
        # Número 5 (NOVO)
        if checklist_fonte.get('5_presente'):
            barriga_aberta = checklist_fonte.get('5_barriga_aberta', True)
            similar = checklist_fonte.get('5_similar_referencia_honda', True)
            prob = checklist_fonte.get('5_problema', 'nenhum')
            if not barriga_aberta or prob == 'barriga_fechada':
                problemas_detalhados.append("'5' barriga fechada")
                fonte_honda = False
        
        # Número 6 (NOVO)
        if checklist_fonte.get('6_presente'):
            circulo_aberto = checklist_fonte.get('6_circulo_aberto', True)
            similar = checklist_fonte.get('6_similar_referencia_honda', True)
            prob = checklist_fonte.get('6_problema', 'nenhum')
            if not circulo_aberto or prob == 'circulo_fechado':
                problemas_detalhados.append("'6' círculo fechado")
                fonte_honda = False
        
        # Número 7
        if checklist_fonte.get('7_presente'):
            if not checklist_fonte.get('7_sem_traco_meio', True):
                problemas_detalhados.insert(0, "'7' com traço europeu")
                fonte_honda = False
        
        # Número 8
        if checklist_fonte.get('8_presente'):
            similar = checklist_fonte.get('8_similar_referencia_honda', checklist_fonte.get('8_aberto_como_honda', True))
            prob = checklist_fonte.get('8_problema', 'nenhum')
            if not similar and prob != 'nenhum':
                problemas_detalhados.append(f"'8' {prob}")
                fonte_honda = False
        
        # Número 9
        if checklist_fonte.get('9_presente'):
            similar = checklist_fonte.get('9_similar_referencia_honda', checklist_fonte.get('9_aberto_como_honda', True))
            prob = checklist_fonte.get('9_problema', 'nenhum')
            if not similar and prob != 'nenhum':
                problemas_detalhados.append(f"'9' {prob}")
                fonte_honda = False
        
        # Atualizar resultado
        result['font_is_honda'] = fonte_honda
        
        # ==========================================
        # VERIFICAÇÃO M vs N (baseado em diagonais)
        # ==========================================
        if checklist_fonte.get('M_ou_N_presente'):
            diagonais = checklist_fonte.get('M_ou_N_diagonais_contadas', 0)
            letra_id = checklist_fonte.get('M_ou_N_letra_identificada', '')
            
            # Validar consistência
            if diagonais == 1 and 'M' in letra_id.upper():
                result['recommendations'].append(
                    f"⚠️ VERIFICAR: Identificou {letra_id} mas contou {diagonais} diagonal (N tem 1, M tem 2)"
                )
            elif diagonais == 2 and 'N' in letra_id.upper():
                result['recommendations'].append(
                    f"⚠️ VERIFICAR: Identificou {letra_id} mas contou {diagonais} diagonais (M tem 2, N tem 1)"
                )
            
            # Guardar info para possível correção
            result['mn_analysis'] = {
                'diagonais_contadas': diagonais,
                'letra_identificada': letra_id,
                'correta': (diagonais == 2 and 'M' in letra_id.upper()) or (diagonais == 1 and 'N' in letra_id.upper())
            }
        
        # Adicionar alertas de fonte
        if not fonte_honda:
            result['risk_factors'].append("🚨 FONTE NÃO É PADRÃO HONDA")
        
        if problemas_detalhados:
            result['risk_factors'].append(
                f"⚠️ Caracteres irregulares: {', '.join(problemas_detalhados)}"
            )
        
        # ==========================================
        # PADRÃO FONTE DE COMPUTADOR (NOVO)
        # ==========================================
        padrao_computador = checklist_fonte.get('padrao_fonte_computador', False)
        multiplos_fechados = checklist_fonte.get('multiplos_circulos_fechados', False)
        
        # Verificar manualmente se há múltiplos círculos fechados
        circulos_fechados = []
        if checklist_fonte.get('0_problema') == 'fechado_circular':
            circulos_fechados.append('0')
        if checklist_fonte.get('5_problema') == 'barriga_fechada':
            circulos_fechados.append('5')
        if checklist_fonte.get('6_problema') == 'circulo_fechado':
            circulos_fechados.append('6')
        if checklist_fonte.get('8_problema') == 'circulos_fechados':
            circulos_fechados.append('8')
        if checklist_fonte.get('9_problema') == 'circulo_fechado':
            circulos_fechados.append('9')
        
        if padrao_computador or multiplos_fechados or len(circulos_fechados) >= 2:
            result['risk_factors'].insert(0, f"🚨🚨 PADRÃO FONTE DE COMPUTADOR - círculos fechados: {', '.join(circulos_fechados) if circulos_fechados else 'detectado'}")
            fonte_honda = False
            result['font_is_honda'] = False
        
        # ==========================================
        # CONSISTÊNCIA ENTRE LINHAS (NOVO)
        # ==========================================
        gravacao = ai.get('analise_gravacao', {})
        consistencia_linhas = checklist_fonte.get('consistencia_linha1_linha2', True)
        estilo_consistente = gravacao.get('estilo_fonte_consistente', True)
        profundidade_uniforme = gravacao.get('profundidade_uniforme', True)
        
        if not consistencia_linhas or not estilo_consistente:
            result['risk_factors'].append("🚨 Inconsistência entre linha 1 e linha 2 (possível regravação)")
            fonte_honda = False
            result['font_is_honda'] = False
        
        if not profundidade_uniforme:
            result['risk_factors'].append("⚠️ Profundidade de gravação irregular")
        
        # ==========================================
        # CHECKLIST DE SUPERFÍCIE
        # ==========================================
        checklist_sup = ai.get('checklist_superficie', {})
        result['surface_analysis'] = checklist_sup
        
        # Números fantasma - CRÍTICO!
        if checklist_sup.get('numeros_fantasma_visiveis'):
            desc = checklist_sup.get('descricao_fantasma', '')
            alerta = "🚨🚨 NÚMEROS FANTASMA DETECTADOS"
            if desc:
                alerta += f" ({desc})"
            result['risk_factors'].insert(0, alerta)
        
        # Tipo de marcas
        tipo_marcas = checklist_sup.get('tipo_marcas', 'nenhuma')
        marcas_paralelas = checklist_sup.get('marcas_paralelas_uniformes', False)
        marcas_concentradas = checklist_sup.get('marcas_concentradas_nos_numeros', False)
        
        if tipo_marcas == 'lixamento_suspeito' or (marcas_paralelas and marcas_concentradas):
            desc = checklist_sup.get('descricao_marcas', '')
            if not fonte_honda:
                alerta = "🚨 Lixamento suspeito + fonte irregular"
            else:
                alerta = "⚠️ Marcas suspeitas (fonte parece OK)"
            if desc:
                alerta += f" ({desc})"
            result['risk_factors'].append(alerta)
        elif tipo_marcas == 'uso_normal':
            result['recommendations'].append("✓ Superfície com marcas normais de uso")
        
        # ==========================================
        # CHECKLIST DE ALINHAMENTO
        # ==========================================
        checklist_alin = ai.get('checklist_alinhamento', {})
        
        desalinhamento_severo = checklist_alin.get('desalinhamento_severo', False)
        puncao_manual = checklist_alin.get('indica_puncao_manual', False)
        
        if desalinhamento_severo or puncao_manual:
            result['risk_factors'].append("🚨 Desalinhamento severo (punção manual)")
        elif not checklist_alin.get('numeros_bem_alinhados', checklist_alin.get('numeros_alinhados', True)):
            result['risk_factors'].append("⚠️ Alinhamento irregular")
        
        # ==========================================
        # COMPATIBILIDADE COM FORMATOS ANTIGOS
        # ==========================================
        # Se não tiver checklist, tenta formato antigo
        if not checklist_fonte:
            pericia_tipo = ai.get('pericia_tipografica', {})
            if pericia_tipo:
                result['font_is_honda'] = pericia_tipo.get('fonte_e_honda_industrial', True)
                result['font_analysis'] = pericia_tipo
        
        if not checklist_sup:
            pericia_sup = ai.get('pericia_superficie', {})
            if pericia_sup:
                result['surface_analysis'] = pericia_sup
                # Processar formato antigo
                if isinstance(pericia_sup.get('numeros_fantasma'), bool):
                    if pericia_sup.get('numeros_fantasma'):
                        result['risk_factors'].insert(0, "🚨🚨 NÚMEROS FANTASMA DETECTADOS")
                if isinstance(pericia_sup.get('marcas_lixa'), bool):
                    if pericia_sup.get('marcas_lixa'):
                        result['risk_factors'].append("🚨 Marcas de lixa")
        
        # ==========================================
        # GRAVAÇÃO
        # ==========================================
        gravacao = ai.get('analise_gravacao', {})
        
        tipo_l1 = gravacao.get('tipo_linha1', '').upper()
        tipo_l2 = gravacao.get('tipo_linha2', '').upper()
        
        if tipo_l1 and tipo_l2:
            if tipo_l1 == tipo_l2:
                result['detected_type'] = tipo_l1
            else:
                result['detected_type'] = 'MISTURA'
        
        if gravacao.get('mistura_tipos'):
            result['has_mixed_types'] = True
            result['risk_factors'].append("🚨 Mistura de gravação (laser + estampagem)")
        
        if not gravacao.get('compativel_com_ano', True):
            result['type_match'] = False
            result['risk_factors'].append(
                f"⚠️ Tipo incompatível com ano {year}"
            )
        
        # ==========================================
        # VEREDICTO
        # ==========================================
        veredicto = ai.get('veredicto', {})
        classificacao = veredicto.get('classificacao', '').upper()
        certeza = veredicto.get('certeza', 0)
        motivo = veredicto.get('motivo_principal', '')
        motivos = veredicto.get('motivos', [])
        
        # Adicionar motivos como recomendações
        for m in motivos[:5]:
            if m:
                result['recommendations'].append(m)
        
        # Veredicto principal
        if classificacao == 'ADULTERADO':
            alerta = f"🚨 VEREDICTO: ADULTERADO ({certeza}%)"
            if motivo:
                alerta += f" - {motivo}"
            result['risk_factors'].insert(0, alerta)
        elif classificacao == 'SUSPEITO':
            alerta = f"⚠️ VEREDICTO: SUSPEITO ({certeza}%)"
            if motivo:
                alerta += f" - {motivo}"
            result['risk_factors'].insert(0, alerta)
        
        # Score calculado em _calculate_risk_score_strict
    
    def _calculate_risk_score_strict(self, result: Dict, ai: Dict) -> int:
        """
        Calcula score de risco.
        REGRA: 1 caractere CLARAMENTE adulterado = FRAUDE
        MAS a IA precisa ter comparado com referência.
        """
        score = 0
        fonte_ok = True
        
        # ==========================================
        # CHECKLIST DE FONTE
        # ==========================================
        checklist_fonte = ai.get('checklist_fonte', {})
        
        # A IA comparou com referências?
        comparou = checklist_fonte.get('comparei_com_referencias', False)
        
        # Quantos caracteres CLARAMENTE errados?
        qtd_erros = checklist_fonte.get('quantos_caracteres_claramente_errados', 0)
        chars_problema = checklist_fonte.get('caracteres_com_problema_claro', checklist_fonte.get('caracteres_com_problema', []))
        
        # Fonte geral compatível?
        fonte_compativel = checklist_fonte.get('fonte_geral_compativel_honda', checklist_fonte.get('fonte_e_honda', True))
        
        # Se tem caracteres claramente errados = FRAUDE
        if qtd_erros >= 1 or len(chars_problema) >= 1:
            score = max(score, 85)
            fonte_ok = False
            logger.info(f"  ⚠️ Score 85: {qtd_erros} caractere(s) claramente errado(s): {chars_problema}")
        
        # Se IA diz fonte não compatível mas NÃO apontou erros claros
        # = provavelmente erro da IA, ignorar
        if not fonte_compativel and qtd_erros == 0 and len(chars_problema) == 0:
            if comparou:
                # Comparou mas não achou erros claros = suspeito leve
                score = max(score, 40)
                logger.info("  ℹ️ Score 40: IA diz não-Honda mas sem erros específicos")
            else:
                # Nem comparou = ignorar
                logger.info("  ℹ️ IA diz não-Honda mas não comparou com referências - ignorando")
        
        # Verificar caracteres específicos
        
        # '4' claramente conectado = FRAUDE
        prob_4 = checklist_fonte.get('4_problema', 'nenhum')
        if checklist_fonte.get('4_presente'):
            tem_gap = checklist_fonte.get('4_tem_gap_visivel', checklist_fonte.get('4_tem_gap', True))
            if not tem_gap or prob_4 == 'claramente_conectado':
                score = max(score, 90)
                fonte_ok = False
                logger.info("  ⚠️ Score 90: '4' claramente conectado")
        
        # '7' com traço europeu = FRAUDE
        if checklist_fonte.get('7_presente'):
            prob_7 = checklist_fonte.get('7_problema', 'nenhum')
            if not checklist_fonte.get('7_sem_traco_meio', True) or prob_7 == 'tem_traco_europeu':
                score = max(score, 85)
                fonte_ok = False
                logger.info("  ⚠️ Score 85: '7' europeu")
        
        # '1' moral baixa (muito curto) = FRAUDE
        if checklist_fonte.get('1_presente'):
            prob_1 = checklist_fonte.get('1_problema', 'nenhum')
            if not checklist_fonte.get('1_altura_normal', True) or prob_1 == 'moral_baixa':
                score = max(score, 85)
                fonte_ok = False
                logger.info("  ⚠️ Score 85: '1' moral baixa")
            if not checklist_fonte.get('1_tem_barra_topo', True) or prob_1 == 'sem_barra':
                score = max(score, 85)
                fonte_ok = False
                logger.info("  ⚠️ Score 85: '1' sem barra")
        
        # '0' claramente diferente = FRAUDE
        if checklist_fonte.get('0_presente'):
            prob_0 = checklist_fonte.get('0_problema', 'nenhum')
            similar_0 = checklist_fonte.get('0_similar_referencia_honda', True)
            if prob_0 in ['claramente_diferente', 'fechado_circular'] or (not similar_0 and prob_0 != 'nenhum'):
                score = max(score, 85)
                fonte_ok = False
                logger.info(f"  ⚠️ Score 85: '0' {prob_0}")
        
        # '5' barriga fechada = FRAUDE (NOVO)
        if checklist_fonte.get('5_presente'):
            prob_5 = checklist_fonte.get('5_problema', 'nenhum')
            barriga_aberta = checklist_fonte.get('5_barriga_aberta', True)
            similar_5 = checklist_fonte.get('5_similar_referencia_honda', True)
            if prob_5 == 'barriga_fechada' or (not barriga_aberta and not similar_5):
                score = max(score, 85)
                fonte_ok = False
                logger.info("  ⚠️ Score 85: '5' barriga fechada")
        
        # '6' círculo fechado = FRAUDE (NOVO)
        if checklist_fonte.get('6_presente'):
            prob_6 = checklist_fonte.get('6_problema', 'nenhum')
            circulo_aberto = checklist_fonte.get('6_circulo_aberto', True)
            similar_6 = checklist_fonte.get('6_similar_referencia_honda', True)
            if prob_6 == 'circulo_fechado' or (not circulo_aberto and not similar_6):
                score = max(score, 85)
                fonte_ok = False
                logger.info("  ⚠️ Score 85: '6' círculo fechado")
        
        # '8' claramente diferente = FRAUDE
        if checklist_fonte.get('8_presente'):
            prob_8 = checklist_fonte.get('8_problema', 'nenhum')
            similar_8 = checklist_fonte.get('8_similar_referencia_honda', True)
            if prob_8 in ['claramente_diferente', 'circulos_fechados'] or (not similar_8 and prob_8 != 'nenhum'):
                score = max(score, 85)
                fonte_ok = False
                logger.info(f"  ⚠️ Score 85: '8' {prob_8}")
        
        # '9' claramente diferente = FRAUDE
        if checklist_fonte.get('9_presente'):
            prob_9 = checklist_fonte.get('9_problema', 'nenhum')
            similar_9 = checklist_fonte.get('9_similar_referencia_honda', True)
            if prob_9 in ['claramente_diferente', 'circulo_fechado'] or (not similar_9 and prob_9 != 'nenhum'):
                score = max(score, 85)
                fonte_ok = False
                logger.info(f"  ⚠️ Score 85: '9' {prob_9}")
        
        # ==========================================
        # PADRÃO FONTE DE COMPUTADOR (NOVO)
        # ==========================================
        padrao_computador = checklist_fonte.get('padrao_fonte_computador', False)
        multiplos_fechados = checklist_fonte.get('multiplos_circulos_fechados', False)
        
        # Contar quantos caracteres têm círculos fechados
        circulos_fechados_count = 0
        if checklist_fonte.get('0_problema') == 'fechado_circular':
            circulos_fechados_count += 1
        if checklist_fonte.get('5_problema') == 'barriga_fechada':
            circulos_fechados_count += 1
        if checklist_fonte.get('6_problema') == 'circulo_fechado':
            circulos_fechados_count += 1
        if checklist_fonte.get('8_problema') == 'circulos_fechados':
            circulos_fechados_count += 1
        if checklist_fonte.get('9_problema') == 'circulo_fechado':
            circulos_fechados_count += 1
        
        # Múltiplos círculos fechados = fonte de computador = FRAUDE CERTA
        if padrao_computador or multiplos_fechados or circulos_fechados_count >= 2:
            score = max(score, 95)
            fonte_ok = False
            logger.info(f"  🚨 Score 95: PADRÃO FONTE DE COMPUTADOR ({circulos_fechados_count} círculos fechados)")
        
        # ==========================================
        # MÚLTIPLOS ERROS = AUMENTA CERTEZA (NOVO)
        # ==========================================
        total_erros = qtd_erros if qtd_erros > 0 else len(chars_problema)
        if total_erros == 0:
            # Contar manualmente
            if checklist_fonte.get('0_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('1_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('4_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('5_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('6_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('7_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('8_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
            if checklist_fonte.get('9_problema', 'nenhum') not in ['nenhum', '']:
                total_erros += 1
        
        # Aumentar score baseado na quantidade de erros
        if total_erros >= 3:
            score = max(score, 98)
            logger.info(f"  🚨 Score 98: {total_erros}+ caracteres com erro = FRAUDE CERTA")
        elif total_erros == 2:
            score = max(score, 92)
            logger.info(f"  ⚠️ Score 92: 2 caracteres com erro")
        
        # ==========================================
        # CONSISTÊNCIA ENTRE LINHAS (NOVO)
        # ==========================================
        gravacao = ai.get('analise_gravacao', {})
        consistencia_linhas = checklist_fonte.get('consistencia_linha1_linha2', True)
        estilo_consistente = gravacao.get('estilo_fonte_consistente', True)
        
        if not consistencia_linhas or not estilo_consistente:
            score = max(score, 90)
            fonte_ok = False
            logger.info("  ⚠️ Score 90: inconsistência entre linhas")
        
        # ==========================================
        # CHECKLIST DE SUPERFÍCIE
        # ==========================================
        checklist_sup = ai.get('checklist_superficie', {})
        
        # Números fantasma = FRAUDE CONFIRMADA (sempre)
        if checklist_sup.get('numeros_fantasma_visiveis'):
            score = max(score, 98)
            fonte_ok = False
            logger.info("  ⚠️ Score 98: números fantasma")
        
        # Lixamento suspeito
        tipo_marcas = checklist_sup.get('tipo_marcas', 'nenhuma')
        marcas_paralelas = checklist_sup.get('marcas_paralelas_uniformes', False)
        marcas_concentradas = checklist_sup.get('marcas_concentradas_nos_numeros', False)
        
        lixamento_suspeito = (tipo_marcas == 'lixamento_suspeito') or (marcas_paralelas and marcas_concentradas)
        
        if lixamento_suspeito:
            if not fonte_ok:
                # Fonte errada + lixa = aumenta certeza
                score = max(score, 92)
                logger.info("  ⚠️ Score 92: lixamento + fonte errada")
            else:
                # Fonte OK + lixa = suspeito moderado
                score = max(score, 50)
                logger.info("  ℹ️ Score 50: lixamento suspeito mas fonte parece OK")
        
        # ==========================================
        # CHECKLIST DE ALINHAMENTO
        # ==========================================
        checklist_alin = ai.get('checklist_alinhamento', {})
        
        desalinhamento_severo = checklist_alin.get('desalinhamento_severo', False)
        puncao_manual = checklist_alin.get('indica_puncao_manual', False)
        
        if desalinhamento_severo or puncao_manual:
            score = max(score, 90)
            fonte_ok = False
            logger.info("  ⚠️ Score 90: desalinhamento severo / punção manual")
        elif not checklist_alin.get('numeros_bem_alinhados', checklist_alin.get('numeros_alinhados', True)):
            score += 20
        
        # ==========================================
        # GRAVAÇÃO
        # ==========================================
        gravacao = ai.get('analise_gravacao', {})
        
        if gravacao.get('mistura_tipos'):
            score = max(score, 92)
            fonte_ok = False
            logger.info("  ⚠️ Score 92: mistura de tipos")
        
        # ==========================================
        # VEREDICTO DA IA
        # ==========================================
        veredicto = ai.get('veredicto', {})
        classificacao = veredicto.get('classificacao', '').upper()
        certeza = veredicto.get('certeza', 0)
        
        if classificacao == 'ADULTERADO':
            if fonte_ok and qtd_erros == 0:
                # IA diz adulterado mas não apontou erros de fonte = limitar
                score = max(score, min(int(certeza * 0.5), 55))
                logger.info("  ℹ️ IA disse ADULTERADO sem erros de fonte específicos")
            else:
                score = max(score, int(certeza * 0.9))
        elif classificacao == 'SUSPEITO':
            score = max(score, int(certeza * 0.6))
        elif classificacao == 'ORIGINAL':
            # Se IA disse original e não achamos problemas, reduzir score
            if fonte_ok and score < 50:
                score = int(score * 0.5)
                logger.info("  ✓ IA confirmou ORIGINAL")
        
        # ==========================================
        # AJUSTE FINAL: Se fonte OK e score baixo, reduzir
        # ==========================================
        if fonte_ok and score > 0 and score < 50:
            score = int(score * 0.7)
            logger.info(f"  ✓ Fonte parece OK - score ajustado para {score}")
        
        return min(score, 100)
    
    # ========================================
    # MÉTODOS DE PERSISTÊNCIA - ORIGINAIS
    # ========================================
    
    def _get_original_patterns(self) -> List[Dict]:
        """Busca motores originais do BD para referência."""
        if not self.supabase:
            return []
        try:
            response = self.supabase.table('motors_original').select('code,prefix,year,engraving_type,image_url').limit(5).execute()
            return response.data or []
        except:
            return []
    
    def _get_originals_by_prefix(self, prefix: str) -> List[Dict]:
        """Busca originais com mesmo prefixo para comparação."""
        if not self.supabase or not prefix:
            return []
        try:
            response = self.supabase.table('motors_original').select('*').eq('prefix', prefix).limit(3).execute()
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
        """Salva análise no Supabase - CAMPOS ORIGINAIS PRESERVADOS."""
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
        originals = 0
        if self.supabase:
            try:
                originals = len(self.supabase.table('motors_original').select('id').execute().data or [])
            except:
                pass
        
        fonts_count = len(self.font_urls)
        
        return {
            'originals': originals,
            'fonts_loaded': fonts_count,
            'fonts_visual': fonts_count,
            'fonts_available': sorted(self.font_urls.keys()),
            'opencv_available': OPENCV_AVAILABLE,
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
        """Promove análise confirmada como ORIGINAL para o BD de referências."""
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
            if analysis.get('is_fraud_confirmed'):
                return False, "Apenas motores ORIGINAIS podem ser promovidos como referência"
            
            code = analysis.get('correct_code') or analysis.get('read_code')
            prefix = analysis.get('prefix')
            year = analysis.get('year_informed')
            detected_type = analysis.get('detected_type', '').lower()
            image_url = analysis.get('image_url')
            
            # Adiciona ao BD de originais
            self.supabase.table('motors_original').insert({
                'code': code, 
                'prefix': prefix, 
                'year': year,
                'engraving_type': detected_type if detected_type in ['laser', 'estampagem'] else 'laser',
                'description': analysis.get('evaluation_notes') or 'Verificado como original',
                'image_url': image_url, 
                'verified': True
            }).execute()
            
            # Marca como promovido
            self.supabase.table('analysis_history').update({
                'promoted_to_reference': True,
                'promoted_at': datetime.now().isoformat(),
                'reference_type': 'original'
            }).eq('id', analysis_id).execute()
            
            return True, "Promovido como referência original"
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
        """Adiciona motor original verificado ao BD de referências."""
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
            
            return True, f"Motor {code} cadastrado como original"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    def list_originals(self) -> List[Dict]:
        """Lista motores originais cadastrados."""
        if not self.supabase: 
            return []
        try: 
            return self.supabase.table('motors_original').select('*').execute().data or []
        except: 
            return []
