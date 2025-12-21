# PRF Honda Inspector - Análise de Motor

Sistema forense para identificação de fraudes em números de motor de motocicletas Honda.

## Características

### Análises Realizadas

1. **OCR**: Leitura do número gravado no motor
2. **Validação de Formato**: Verifica padrão Honda (prefixo + serial)
3. **Análise Forense**:
   - Tipo de gravação (micropunção vs estampagem)
   - Alinhamento dos caracteres
   - Densidade de pontos
4. **Análise Tipográfica**:
   - Comparação com fonte Honda oficial
   - **Detecção de vazamentos (gaps)** - característica crucial
5. **Comparação Visual**: Com banco de referências

### Caracteres de Alto Risco

Os números mais falsificados são: **0, 1, 3, 4, 9**

Estes recebem análise mais rigorosa, especialmente na detecção de vazamentos:
- **4**: Tem gap característico onde linha vertical não toca horizontal
- **0**: Deve ser oval fechada sem gaps internos
- **9**: Tem cauda curva específica
- **1**: Deve ser estreito com serifas específicas
- **3**: Tem aberturas à esquerda

### Tipos de Gravação

- **Antes de 2010**: Estampagem (caracteres sólidos)
- **A partir de 2010**: Laser/Micropunção (formado por pontos)

---

## Instalação

### 1. Backend (Servidor)

```bash
cd backend

# Cria ambiente virtual
python -m venv venv

# Ativa ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instala dependências
pip install -r requirements.txt
```

### 2. Configurar Templates de Fonte

**IMPORTANTE**: Para a análise tipográfica funcionar, você precisa adicionar os templates da fonte Honda.

```bash
# Copia a imagem da fonte para o backend
cp /caminho/para/imagem_fonte.jpg backend/

# Extrai os templates
cd backend
python extract_font_templates.py imagem_fonte.jpg
```

Ou manualmente:
1. Recorte cada número (0-9) da imagem de referência
2. Salve como PNG em `backend/data/fonts/` (0.png, 1.png, etc.)

### 3. Iniciar Servidor

```bash
cd backend

# Descubra seu IP
# Windows: ipconfig
# Linux: ip addr

# Inicia o servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Testar API

- Health check: http://localhost:8000/health
- Fontes carregadas: http://localhost:8000/fonts
- Prefixos conhecidos: http://localhost:8000/prefixes
- Documentação: http://localhost:8000/docs

---

## Uso da API

### Endpoint Principal

```
POST /analyze/motor
```

**Parâmetros (form-data):**
- `photo`: Foto do número de motor (JPEG/PNG)
- `year`: Ano do modelo (ex: 2020)
- `model`: Modelo da moto (opcional, ex: "CG 160")

**Resposta:**
```json
{
  "verdict": "REGULAR | ATENÇÃO | SUSPEITO | ALTA SUSPEITA DE FRAUDE",
  "risk_score": 0-100,
  "read_code": "MC27E-1009153",
  "prefix": "MC27E",
  "serial": "1009153",
  "expected_model": "CG 160 Titan/Fan/Start",
  "components": {
    "engine_validation": {...},
    "forensic": {...},
    "visual": {...}
  },
  "explanation": ["lista de observações"]
}
```

---

## Prefixos de Motor Conhecidos

| Prefixo | Modelo | Cilindrada |
|---------|--------|------------|
| MC27E | CG 160 Titan/Fan/Start | 160cc |
| MC41E | CG 150 Titan/Fan | 150cc |
| MD09E / MD09E1 | XRE 300 | 300cc |
| MC52E | CB 300R Twister | 300cc |
| NC51E | CB 500F/X/R | 500cc |
| KYJ | BIZ 125 | 125cc |
| PC40E | PCX 150 | 150cc |

---

## Estrutura do Projeto

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py      # Configurações
│   │   └── logger.py      # Logging
│   ├── database/
│   │   └── honda_motor_specs.py  # Especificações Honda
│   ├── domain/
│   │   └── schemas.py     # Modelos de dados
│   ├── services/
│   │   ├── ocr.py              # Motor de OCR
│   │   ├── font_analyzer.py    # Análise tipográfica + vazamentos
│   │   ├── anomaly_service.py  # Detecção de anomalias
│   │   ├── visual_matcher.py   # Comparação visual
│   │   └── reference_loader.py # Carregador de referências
│   └── main.py            # API FastAPI
├── data/
│   ├── fonts/             # Templates da fonte Honda
│   └── references/        # Imagens de referência
│       └── HONDA/
│           └── MOTOR/
│               └── {ANO}/
├── requirements.txt
└── extract_font_templates.py
```

---

## Adicionando Referências de Motor

```
backend/data/references/HONDA/MOTOR/
├── 2020/
│   └── MC27E.jpg    # Referência para CG 160
├── 2021/
│   └── MD09E1.jpg   # Referência para XRE 300
└── default/
    └── motor.jpg    # Fallback genérico
```

---

## Troubleshooting

### "Nenhum template carregado"

Verifique se os arquivos de fonte estão em `backend/data/fonts/`:
```bash
ls backend/data/fonts/
# Deve mostrar: 0.png 1.png 2.png ... 9.png
```

### "Network Error" no app mobile

1. Verifique se o IP está correto no App.tsx
2. Confirme que o firewall permite conexões na porta 8000
3. Teste: `curl http://SEU_IP:8000/health`

### OCR não detecta nada

1. Foto deve estar nítida e na horizontal
2. Iluminação adequada (evite sombras fortes)
3. O número deve ocupar boa parte da imagem

---

## Notas Técnicas

### Detecção de Vazamentos (Gaps)

A fonte Honda possui "vazamentos" característicos - pontos onde as linhas não se conectam totalmente. Por exemplo:
- O número **4** tem um gap onde a linha vertical não encosta na horizontal
- O número **9** tem uma cauda específica

Falsificadores frequentemente erram esses detalhes, tornando a detecção de gaps uma das análises mais importantes.

### Score de Risco

| Score | Veredito |
|-------|----------|
| 0-10 | REGULAR |
| 11-30 | ATENÇÃO |
| 31-60 | SUSPEITO |
| 61-100 | ALTA SUSPEITA DE FRAUDE |

---

## Licença

Uso restrito para fins de fiscalização pela PRF.
