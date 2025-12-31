# 🚀 PLANO DE AÇÃO - PRF Honda Inspector

## Roadmap Completo: Do Teste à Produção

---

## 📋 FASE 1: TESTES (1-2 semanas)

### 1.1 Testes Automatizados

Crie o arquivo `backend/tests/test_analysis.py`:

```python
"""
Testes automatizados para PRF Honda Inspector
Execute: pytest tests/ -v
"""

import pytest
import httpx
from pathlib import Path
from app.database.honda_motor_specs import HondaMotorSpecs
from app.services.forensic_ai_service import ForensicAIService

# ========================================
# TESTES DE PREFIXOS
# ========================================

class TestHondaMotorSpecs:
    
    def test_prefixos_conhecidos(self):
        """Testa se prefixos das imagens são reconhecidos."""
        prefixos_esperados = [
            'KC08E1', 'KC08E2', 'KC22E1',  # Série KC
            'KD08E1', 'KD08E2', 'KF34E1',  # Série KD/KF
            'MD41E0', 'ND11E1',             # Bros/XRE
            'NC49E1F', 'JC30E7',            # CB/CG
        ]
        
        for prefixo in prefixos_esperados:
            info = HondaMotorSpecs.get_prefix_info(prefixo)
            assert info is not None, f"Prefixo {prefixo} não reconhecido!"
    
    def test_validacao_formato_valido(self):
        """Testa formatos válidos de motor."""
        codigos_validos = [
            "MD09E1-B215797",
            "MC27E-1009153",
            "KC08E2-S029466",
            "NC49E1F-105588",
            "KD08E2S029466",  # Sem hífen
        ]
        
        for codigo in codigos_validos:
            result = HondaMotorSpecs.validate_engine_format(codigo)
            assert result['valid'], f"Código {codigo} deveria ser válido!"
            assert result['prefix'] is not None
            assert result['serial'] is not None
    
    def test_validacao_formato_invalido(self):
        """Testa formatos inválidos."""
        codigos_invalidos = [
            "",
            "ABC",
            "12345",
            "XXXXXXXXXXXXXXXXXX",
        ]
        
        for codigo in codigos_invalidos:
            result = HondaMotorSpecs.validate_engine_format(codigo)
            assert not result['valid'] or len(result['issues']) > 0
    
    def test_tipo_gravacao_por_ano(self):
        """Testa determinação do tipo de gravação."""
        assert HondaMotorSpecs.get_expected_type(2005) == "ESTAMPAGEM"
        assert HondaMotorSpecs.get_expected_type(2009) == "ESTAMPAGEM"
        assert HondaMotorSpecs.get_expected_type(2010) == "LASER"
        assert HondaMotorSpecs.get_expected_type(2024) == "LASER"
    
    def test_caracteres_alto_risco(self):
        """Testa identificação de caracteres de alto risco."""
        alto_risco = ['0', '1', '3', '4', '5', '6', '8', '9']
        baixo_risco = ['2', '7', 'A', 'B', 'C']
        
        for char in alto_risco:
            assert HondaMotorSpecs.is_high_risk_char(char)
        
        for char in baixo_risco:
            assert not HondaMotorSpecs.is_high_risk_char(char)


# ========================================
# TESTES DE INTEGRAÇÃO COM API
# ========================================

class TestAPIIntegration:
    
    BASE_URL = "http://localhost:8000"
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=self.BASE_URL, timeout=30.0)
    
    def test_health_check(self, client):
        """Testa endpoint de health."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
    
    def test_list_prefixes(self, client):
        """Testa listagem de prefixos."""
        response = client.get("/prefixes")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 30  # Deve ter pelo menos 30 prefixos
    
    def test_analyze_without_file(self, client):
        """Testa análise sem arquivo (deve falhar)."""
        response = client.post("/analyze/motor", data={"year": 2020})
        assert response.status_code == 422  # Validation error
    
    def test_analyze_with_invalid_year(self, client):
        """Testa análise com ano inválido."""
        # Cria imagem fake mínima
        fake_image = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        
        response = client.post(
            "/analyze/motor",
            data={"year": 1800},  # Ano inválido
            files={"photo": ("test.jpg", fake_image, "image/jpeg")}
        )
        assert response.status_code == 400


# ========================================
# TESTES COM IMAGENS REAIS
# ========================================

class TestWithRealImages:
    """
    Testes com imagens reais de motores.
    Coloque as imagens em tests/images/
    """
    
    BASE_URL = "http://localhost:8000"
    IMAGES_DIR = Path(__file__).parent / "images"
    
    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=self.BASE_URL, timeout=120.0)
    
    @pytest.mark.skipif(
        not Path("tests/images").exists(),
        reason="Diretório de imagens não existe"
    )
    def test_imagens_originais(self, client):
        """Testa imagens de motores originais (devem ter score baixo)."""
        originais_dir = self.IMAGES_DIR / "originais"
        
        if not originais_dir.exists():
            pytest.skip("Diretório de originais não existe")
        
        for img_path in originais_dir.glob("*.jpg"):
            with open(img_path, "rb") as f:
                response = client.post(
                    "/analyze/motor",
                    data={"year": 2020},
                    files={"photo": (img_path.name, f, "image/jpeg")}
                )
            
            assert response.status_code == 200
            data = response.json()
            
            # Originais devem ter score < 50
            assert data["risk_score"] < 50, \
                f"Original {img_path.name} teve score alto: {data['risk_score']}"
    
    @pytest.mark.skipif(
        not Path("tests/images").exists(),
        reason="Diretório de imagens não existe"
    )
    def test_imagens_adulteradas(self, client):
        """Testa imagens de motores adulterados (devem ter score alto)."""
        adulterados_dir = self.IMAGES_DIR / "adulterados"
        
        if not adulterados_dir.exists():
            pytest.skip("Diretório de adulterados não existe")
        
        for img_path in adulterados_dir.glob("*.jpg"):
            with open(img_path, "rb") as f:
                response = client.post(
                    "/analyze/motor",
                    data={"year": 2020},
                    files={"photo": (img_path.name, f, "image/jpeg")}
                )
            
            assert response.status_code == 200
            data = response.json()
            
            # Adulterados devem ter score >= 50
            assert data["risk_score"] >= 50, \
                f"Adulterado {img_path.name} teve score baixo: {data['risk_score']}"


# ========================================
# PARA EXECUTAR
# ========================================
# 
# 1. Instale pytest: pip install pytest pytest-asyncio httpx
# 
# 2. Inicie o servidor: uvicorn app.main:app --reload
# 
# 3. Execute os testes: pytest tests/ -v
# 
# 4. Para testes com imagens reais:
#    - Crie pasta tests/images/originais/
#    - Crie pasta tests/images/adulterados/
#    - Coloque as imagens correspondentes
#    - Execute: pytest tests/ -v -k "RealImages"
```

### 1.2 Script de Teste Manual com Suas Imagens

Crie `backend/test_manual.py`:

```python
#!/usr/bin/env python3
"""
Script de teste manual com as imagens fornecidas.
Testa todas as imagens de ORIGINAIS e ADULTERADOS.

Uso: python test_manual.py
"""

import httpx
import sys
from pathlib import Path
from datetime import datetime

# Configuração
API_URL = "http://localhost:8000"
TIMEOUT = 120.0

# Diretório das imagens (ajuste conforme necessário)
PROJECT_DIR = Path("/mnt/project")  # Ou caminho local

def test_image(client: httpx.Client, image_path: Path, expected_type: str, year: int = 2020):
    """Testa uma imagem e retorna resultado."""
    
    print(f"\n{'='*60}")
    print(f"📷 Testando: {image_path.name}")
    print(f"   Esperado: {expected_type}")
    
    try:
        with open(image_path, "rb") as f:
            response = client.post(
                f"{API_URL}/analyze/motor",
                data={"year": year},
                files={"photo": (image_path.name, f, "image/jpeg")},
                timeout=TIMEOUT
            )
        
        if response.status_code != 200:
            print(f"   ❌ Erro HTTP: {response.status_code}")
            return None
        
        data = response.json()
        
        score = data.get("risk_score", 0)
        verdict = data.get("verdict", "N/A")
        code = data.get("read_code", "N/A")
        
        # Determina se acertou
        if expected_type == "ORIGINAL":
            acertou = score < 50
            emoji = "✅" if acertou else "❌"
        else:  # ADULTERADO
            acertou = score >= 50
            emoji = "✅" if acertou else "❌"
        
        print(f"   {emoji} Score: {score}")
        print(f"   📝 Veredicto: {verdict}")
        print(f"   🔢 Código: {code}")
        
        return {
            "image": image_path.name,
            "expected": expected_type,
            "score": score,
            "verdict": verdict,
            "code": code,
            "correct": acertou
        }
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return None


def main():
    print("=" * 60)
    print("🔬 PRF Honda Inspector - Teste de Imagens")
    print("=" * 60)
    
    # Verifica conexão
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5.0)
        if response.status_code != 200:
            print("❌ API não está respondendo")
            sys.exit(1)
        print("✅ API conectada")
    except Exception as e:
        print(f"❌ Não foi possível conectar: {e}")
        print(f"   Certifique-se que o servidor está rodando em {API_URL}")
        sys.exit(1)
    
    results = []
    
    with httpx.Client() as client:
        
        # Testa ORIGINAIS
        print("\n" + "=" * 60)
        print("📂 TESTANDO IMAGENS ORIGINAIS")
        print("=" * 60)
        
        for i in range(1, 21):
            img_path = PROJECT_DIR / f"ORIGINAL_{i}.jpeg"
            if img_path.exists():
                result = test_image(client, img_path, "ORIGINAL")
                if result:
                    results.append(result)
        
        # Testa ADULTERADOS
        print("\n" + "=" * 60)
        print("📂 TESTANDO IMAGENS ADULTERADAS")
        print("=" * 60)
        
        for i in range(1, 18):
            img_path = PROJECT_DIR / f"ADULTERADOS_{i}.jpeg"
            if img_path.exists():
                result = test_image(client, img_path, "ADULTERADO")
                if result:
                    results.append(result)
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL")
    print("=" * 60)
    
    total = len(results)
    corretos = sum(1 for r in results if r["correct"])
    
    originais = [r for r in results if r["expected"] == "ORIGINAL"]
    adulterados = [r for r in results if r["expected"] == "ADULTERADO"]
    
    originais_corretos = sum(1 for r in originais if r["correct"])
    adulterados_corretos = sum(1 for r in adulterados if r["correct"])
    
    print(f"\n📈 TAXA DE ACERTO GERAL: {corretos}/{total} ({100*corretos/total:.1f}%)")
    print(f"\n   ORIGINAIS:   {originais_corretos}/{len(originais)} ({100*originais_corretos/len(originais):.1f}%)")
    print(f"   ADULTERADOS: {adulterados_corretos}/{len(adulterados)} ({100*adulterados_corretos/len(adulterados):.1f}%)")
    
    # Erros
    erros = [r for r in results if not r["correct"]]
    if erros:
        print(f"\n⚠️ ERROS ({len(erros)}):")
        for r in erros:
            print(f"   - {r['image']}: esperado {r['expected']}, score={r['score']}")
    
    # Salva relatório
    report_path = Path(f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_path, "w") as f:
        f.write(f"PRF Honda Inspector - Relatório de Teste\n")
        f.write(f"Data: {datetime.now().isoformat()}\n")
        f.write(f"Taxa de acerto: {100*corretos/total:.1f}%\n\n")
        for r in results:
            status = "✓" if r["correct"] else "✗"
            f.write(f"{status} {r['image']}: {r['expected']} -> score={r['score']}\n")
    
    print(f"\n📄 Relatório salvo em: {report_path}")


if __name__ == "__main__":
    main()
```

### 1.3 Como Executar os Testes

```bash
# 1. Instalar dependências de teste
pip install pytest pytest-asyncio httpx

# 2. Iniciar servidor em um terminal
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Em outro terminal, executar testes
cd backend

# Testes automatizados
pytest tests/ -v

# Teste manual com suas imagens
python test_manual.py
```

---

## 📋 FASE 2: HOSPEDAGEM (1 semana)

### 2.1 Opções de Hospedagem

| Plataforma | Custo | Prós | Contras |
|------------|-------|------|---------|
| **Railway** | $5/mês | Fácil deploy, SSL grátis | Limite de recursos |
| **Render** | Grátis* | Grátis para começar | Dorme após 15min inativo |
| **DigitalOcean** | $6/mês | Controle total | Requer config manual |
| **Oracle Cloud** | Grátis | ARM poderoso grátis | Setup complexo |
| **Fly.io** | Grátis* | Rápido, edge deploy | Limite de uso |

**Recomendação:** **Railway** ou **Render** para começar rápido.

### 2.2 Deploy no Railway (Recomendado)

```bash
# 1. Instale Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Crie projeto
cd backend
railway init

# 4. Configure variáveis de ambiente
railway variables set ANTHROPIC_API_KEY=sk-ant-xxx
railway variables set SUPABASE_URL=https://xxx.supabase.co
railway variables set SUPABASE_KEY=eyJ...

# 5. Deploy
railway up

# Você receberá uma URL tipo: https://prf-inspector.up.railway.app
```

### 2.3 Arquivo de Configuração para Deploy

Crie `backend/railway.json`:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

Crie `backend/Procfile`:
```
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### 2.4 Deploy Alternativo: Render

Crie `backend/render.yaml`:
```yaml
services:
  - type: web
    name: prf-inspector
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
    healthCheckPath: /health
```

---

## 📋 FASE 3: APP MOBILE (1-2 semanas)

### 3.1 Opção A: PWA (Progressive Web App) - MAIS RÁPIDO

O usuário acessa pelo navegador e pode "instalar" como app.

Crie `frontend/manifest.json`:
```json
{
  "name": "PRF Honda Inspector",
  "short_name": "PRF Inspector",
  "description": "Análise forense de motores Honda",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#1a1a2e",
  "theme_color": "#00d4ff",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

Adicione ao `frontend/index.html`:
```html
<head>
  <!-- ... outros tags ... -->
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#00d4ff">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="apple-touch-icon" href="/icons/icon-192.png">
</head>
```

### 3.2 Opção B: APK Android com Capacitor - RECOMENDADO

Permite enviar APK por WhatsApp/Email.

```bash
# 1. Instale Node.js e Capacitor
npm install -g @capacitor/cli

# 2. Crie projeto Capacitor
cd frontend
npm init -y
npm install @capacitor/core @capacitor/android

# 3. Inicialize
npx cap init "PRF Honda Inspector" "br.gov.prf.inspector" --web-dir=.

# 4. Adicione Android
npx cap add android

# 5. Copie os arquivos web
npx cap copy android

# 6. Abra no Android Studio
npx cap open android

# 7. No Android Studio: Build > Build Bundle(s) / APK(s) > Build APK
```

### 3.3 Estrutura do App Android

Crie `frontend/capacitor.config.json`:
```json
{
  "appId": "br.gov.prf.inspector",
  "appName": "PRF Honda Inspector",
  "webDir": ".",
  "bundledWebRuntime": false,
  "server": {
    "url": "https://sua-api.railway.app",
    "cleartext": true
  },
  "plugins": {
    "Camera": {
      "permissions": ["camera"]
    }
  },
  "android": {
    "allowMixedContent": true,
    "captureInput": true,
    "webContentsDebuggingEnabled": false
  }
}
```

### 3.4 Script Automatizado para Gerar APK

Crie `build_apk.sh`:
```bash
#!/bin/bash
# Script para gerar APK do PRF Inspector

echo "🔨 Gerando APK do PRF Honda Inspector..."

# Verifica dependências
if ! command -v npx &> /dev/null; then
    echo "❌ Node.js não instalado"
    exit 1
fi

# Navega para frontend
cd frontend

# Instala dependências se necessário
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependências..."
    npm install
fi

# Copia arquivos web
echo "📋 Copiando arquivos web..."
npx cap copy android

# Sincroniza
echo "🔄 Sincronizando..."
npx cap sync android

# Gera APK via Gradle
echo "🔨 Gerando APK..."
cd android
./gradlew assembleDebug

# Copia APK para pasta acessível
APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK_PATH" ]; then
    cp "$APK_PATH" "../PRF_Inspector.apk"
    echo "✅ APK gerado: frontend/PRF_Inspector.apk"
    echo "📱 Tamanho: $(du -h ../PRF_Inspector.apk | cut -f1)"
else
    echo "❌ Falha ao gerar APK"
    exit 1
fi

echo "
📲 INSTRUÇÕES DE INSTALAÇÃO:
1. Envie o arquivo PRF_Inspector.apk por WhatsApp ou Email
2. No celular Android, abra o arquivo
3. Se pedir, habilite 'Instalar de fontes desconhecidas'
4. Toque em Instalar
"
```

---

## 📋 FASE 4: DISTRIBUIÇÃO PARA BETA TESTERS (1 semana)

### 4.1 Preparação do Material

Crie `INSTRUCOES_INSTALACAO.pdf`:

```markdown
# PRF Honda Inspector - Instruções de Instalação

## Requisitos
- Celular Android 8.0 ou superior
- Conexão com internet
- Câmera funcional

## Instalação

### Passo 1: Receba o arquivo
Você receberá o arquivo `PRF_Inspector.apk` por WhatsApp ou Email.

### Passo 2: Habilite instalação de fontes externas
1. Vá em Configurações > Segurança
2. Ative "Fontes desconhecidas" ou "Instalar apps desconhecidos"
3. Permita para o WhatsApp ou seu app de email

### Passo 3: Instale o app
1. Abra o arquivo APK recebido
2. Toque em "Instalar"
3. Aguarde a instalação

### Passo 4: Primeiro uso
1. Abra o app "PRF Inspector"
2. Permita acesso à câmera quando solicitado
3. Pronto para usar!

## Como Usar

1. **Fotografe o motor**: Aponte a câmera para o número do motor
2. **Informe o ano**: Digite o ano do veículo
3. **Analise**: Toque em "Analisar"
4. **Resultado**: Veja o veredicto e score de risco

## Interpretação dos Resultados

| Veredicto | Score | Significado |
|-----------|-------|-------------|
| REGULAR | 0-14 | Motor aparentemente original |
| VERIFICAR | 15-29 | Verificação manual recomendada |
| ATENÇÃO | 30-49 | Sinais que merecem atenção |
| SUSPEITO | 50-69 | Suspeita de irregularidade |
| ALTA SUSPEITA | 70-84 | Fortes indícios de adulteração |
| FRAUDE CONFIRMADA | 85-100 | Adulteração detectada |

## Suporte
Em caso de dúvidas: [seu-email@prf.gov.br]
```

### 4.2 Modelo de Email para Beta Testers

```text
Assunto: [BETA] PRF Honda Inspector - Convite para Teste

Prezado(a) Policial,

Você foi selecionado para participar do teste beta do sistema 
PRF Honda Inspector, uma ferramenta de análise forense de 
números de motor de motocicletas Honda.

INSTRUÇÕES:
1. Baixe o arquivo APK anexo
2. Siga as instruções do PDF anexo para instalar
3. Teste com casos reais durante suas operações
4. Nos envie feedback pelo formulário: [link]

IMPORTANTE:
- Este é um sistema em TESTE - use como ferramenta auxiliar
- O resultado NÃO substitui a análise técnica oficial
- Relate qualquer problema ou sugestão

Prazo do teste: [data início] a [data fim]

Atenciosamente,
[Seu nome]
Equipe de Tecnologia - PRF
```

### 4.3 Formulário de Feedback (Google Forms)

Crie um Google Forms com estas perguntas:

```
1. Nome e matrícula (opcional)
2. Regional/Unidade
3. Quantas análises você realizou?
4. O app funcionou corretamente? (Sim/Não/Parcialmente)
5. A taxa de acerto pareceu boa? (1-5 estrelas)
6. Houve algum caso que o app errou? (Descreva)
7. O que você melhoraria no app?
8. Você recomendaria para colegas? (Sim/Talvez/Não)
9. Comentários adicionais
```

---

## 📋 FASE 5: MELHORIAS PÓS-BETA (Contínuo)

### 5.1 Métricas para Acompanhar

```python
# Adicione ao main.py um endpoint de métricas
@app.get("/metrics")
async def get_metrics():
    """Métricas de uso do sistema."""
    if not forensic_ai.supabase:
        return {"error": "Supabase não configurado"}
    
    try:
        # Total de análises
        total = forensic_ai.supabase.table('analysis_history')\
            .select('id', count='exact').execute()
        
        # Por veredicto
        verdicts = {}
        for v in ['REGULAR', 'ATENÇÃO', 'SUSPEITO', 'FRAUDE CONFIRMADA']:
            count = forensic_ai.supabase.table('analysis_history')\
                .select('id', count='exact')\
                .eq('verdict', v).execute()
            verdicts[v] = count.count or 0
        
        # Taxa de feedback positivo
        feedback = forensic_ai.supabase.table('analysis_history')\
            .select('feedback_correct')\
            .not_.is_('feedback_correct', 'null').execute()
        
        if feedback.data:
            corretos = sum(1 for f in feedback.data if f['feedback_correct'])
            taxa_acerto = corretos / len(feedback.data) * 100
        else:
            taxa_acerto = None
        
        return {
            "total_analyses": total.count,
            "by_verdict": verdicts,
            "feedback_accuracy": taxa_acerto,
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}
```

### 5.2 Dashboard Simples

Crie `frontend/admin.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>PRF Inspector - Admin</title>
    <style>
        body { font-family: Arial; padding: 20px; background: #1a1a2e; color: white; }
        .card { background: #16213e; padding: 20px; border-radius: 10px; margin: 10px 0; }
        .metric { font-size: 2em; color: #00d4ff; }
    </style>
</head>
<body>
    <h1>📊 PRF Inspector - Dashboard</h1>
    
    <div class="card">
        <h3>Total de Análises</h3>
        <div class="metric" id="total">Carregando...</div>
    </div>
    
    <div class="card">
        <h3>Taxa de Acerto (Feedback)</h3>
        <div class="metric" id="accuracy">Carregando...</div>
    </div>
    
    <div class="card">
        <h3>Por Veredicto</h3>
        <div id="verdicts">Carregando...</div>
    </div>
    
    <script>
        const API = 'https://sua-api.railway.app';
        
        fetch(`${API}/metrics`)
            .then(r => r.json())
            .then(data => {
                document.getElementById('total').textContent = data.total_analyses || 0;
                document.getElementById('accuracy').textContent = 
                    data.feedback_accuracy ? `${data.feedback_accuracy.toFixed(1)}%` : 'N/A';
                
                let verdictHtml = '';
                for (const [v, count] of Object.entries(data.by_verdict || {})) {
                    verdictHtml += `<p>${v}: ${count}</p>`;
                }
                document.getElementById('verdicts').innerHTML = verdictHtml;
            });
    </script>
</body>
</html>
```

---

## ⏱️ CRONOGRAMA SUGERIDO

| Semana | Atividade |
|--------|-----------|
| 1 | Executar testes automatizados e manuais |
| 2 | Corrigir bugs encontrados nos testes |
| 3 | Deploy na nuvem (Railway/Render) |
| 4 | Gerar APK e testar em dispositivos |
| 5 | Distribuir para 5-10 beta testers |
| 6-8 | Coletar feedback e fazer ajustes |
| 9+ | Expandir para mais usuários |

---

## 🔒 CONSIDERAÇÕES DE SEGURANÇA

1. **API Key**: Nunca exponha no código do app
2. **HTTPS**: Sempre use conexão segura
3. **Rate Limiting**: Já implementado no código refatorado
4. **Logs**: Não armazene imagens sensíveis desnecessariamente
5. **Acesso**: Considere autenticação para PRFs (futuro)

---

## 📞 SUPORTE

Para dúvidas sobre implementação:
- Documentação FastAPI: https://fastapi.tiangolo.com
- Capacitor: https://capacitorjs.com
- Railway: https://docs.railway.app
