# 🔧 CORREÇÃO v4 - PRF Honda Motor Inspector

## Novidades desta Versão

### 1. OCR com Dupla Verificação
- **EasyOCR** (primário): Rápido, gratuito, offline
- **Claude Vision API** (secundário): Mais preciso, acionado automaticamente quando:
  - Confiança do EasyOCR < 70%
  - Prefixo não reconhecido
  - Caracteres suspeitos (O em vez de 0)

### 2. Correção do Problema MD09E1
O OCR agora detecta corretamente:
- `MD09EB...` → `MD09E1B...` (adiciona o "1" perdido)
- `MDO9E...` → `MD09E1...` (corrige O→0 e adiciona "1")

### 3. Integração Supabase
- Banco de imagens de referência
- Histórico de análises
- Base de fraudes confirmadas
- Sistema de feedback de peritos

---

## Configuração

### 1. Variáveis de Ambiente (.env)

```env
# Claude Vision API (opcional mas recomendado)
ANTHROPIC_API_KEY=sk-ant-api...

# Supabase (opcional)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=eyJ...
```

### 2. Instalar Dependências

```bash
pip install httpx supabase
```

### 3. Criar Tabelas no Supabase (SQL)

```sql
-- Referências de motores
CREATE TABLE motor_references (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    prefix TEXT NOT NULL,
    year INT NOT NULL,
    model TEXT NOT NULL,
    image_url TEXT,
    hash TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Histórico de análises
CREATE TABLE analysis_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    image_hash TEXT,
    read_code TEXT,
    verdict TEXT,
    risk_score INT,
    details JSONB,
    feedback TEXT,
    feedback_notes TEXT,
    feedback_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Fraudes confirmadas
CREATE TABLE fraud_cases (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    original_code TEXT,
    fake_code TEXT,
    image_url TEXT,
    image_hash TEXT,
    description TEXT,
    confirmed_by TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Storage bucket
-- Criar bucket "motor-images" no Supabase Storage (público)
```

---

## Arquivos para Substituir

```
CORRECAO_v4/
├── main.py                    → backend/app/main.py
├── services/
│   ├── ocr.py                 → backend/app/services/ocr.py
│   ├── supabase_service.py    → backend/app/services/supabase_service.py (NOVO)
│   └── anomaly_service.py     → backend/app/services/anomaly_service.py
└── database/
    └── honda_motor_specs.py   → backend/app/database/honda_motor_specs.py
```

---

## Novos Endpoints

### Análise com forçar Claude
```bash
curl -X POST "http://localhost:8000/analyze/motor" \
  -F "photo=@motor.jpg" \
  -F "year=2020" \
  -F "force_claude=true"
```

### Upload de Referência
```bash
curl -X POST "http://localhost:8000/references/upload" \
  -F "photo=@ref_md09e1.jpg" \
  -F "prefix=MD09E1" \
  -F "year=2020" \
  -F "model=XRE 300"
```

### Registrar Fraude Confirmada
```bash
curl -X POST "http://localhost:8000/fraud/register" \
  -F "photo=@fraude.jpg" \
  -F "original_code=MD09E1-A123456" \
  -F "fake_code=MD09E1-B789012" \
  -F "description=Número regravado com solda" \
  -F "confirmed_by=Perito João Silva"
```

### Feedback do Perito
```bash
curl -X POST "http://localhost:8000/feedback/uuid-da-analise" \
  -F "feedback=CORRETO" \
  -F "notes=Análise precisa"
```

---

## Custo Estimado

### Claude Vision API
- ~$0.01-0.02 por análise com imagem
- Só é acionado quando EasyOCR tem dúvida (~30% das vezes)
- Estimativa: 100 análises/dia = ~$15-30/mês

### Supabase (Gratuito)
- 500MB banco de dados
- 1GB storage
- 50.000 requisições/mês
- Suficiente para ~5.000 análises/mês

---

## Fluxo de Funcionamento

```
┌─────────────┐
│   Imagem    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     Confiança < 70%?     ┌─────────────┐
│  EasyOCR    │────────────────────────▶ │Claude Vision│
│  (rápido)   │     Prefixo errado?      │  (preciso)  │
└──────┬──────┘                          └──────┬──────┘
       │                                        │
       └──────────────┬─────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  Melhor OCR  │
              │  Escolhido   │
              └──────┬───────┘
                     │
                     ▼
       ┌─────────────────────────┐
       │ Verifica Fraude Conhecida│
       │     (Supabase)          │
       └───────────┬─────────────┘
                   │
                   ▼
          ┌────────────────┐
          │Análise Forense │
          └────────┬───────┘
                   │
                   ▼
          ┌────────────────┐
          │   Resultado    │
          │ + Salva Histórico│
          └────────────────┘
```

---

## Resultado Esperado para MD09E1-B215797

```json
{
  "verdict": "REGULAR",
  "risk_score": 5,
  "read_code": "MD09E1B215797",
  "prefix": "MD09E1",
  "serial": "B215797",
  "expected_model": "XRE 300"
}
```
