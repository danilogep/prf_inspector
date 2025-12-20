# 🕵️‍♂️ PRF Honda Inspector - Sistema Forense de Identificação Veicular

Sistema composto por uma API em Python (Computer Vision) e um App Mobile (React Native) para auxiliar Policiais Rodoviários Federais na identificação de fraudes em motocicletas Honda, analisando conformidade, textura de micropunção e comparação visual.

## 📋 Pré-requisitos

Para rodar este projeto, você precisa ter instalado:
1.  **Python 3.9+**
2.  **Node.js** (Versão LTS)
3.  **App Expo Go** instalado no seu celular Android/iOS.
4.  Computador e Celular conectados na **mesma rede Wi-Fi**.

---

## 🚀 Como Rodar (Guia Rápido)

### 1. Configuração do Backend (Servidor)

O backend é responsável pela inteligência artificial e OCR.

1. Navegue até a pasta:
   ```bash
   cd backend
   ```

2. Crie e ative o ambiente virtual:
    ```bash
    python -m venv venv
    # Windows:
    venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate
    ```

3. Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

4. **IMPORTANTE**: Descubra o IP do seu computador (ipconfig no Windows ou ifconfig no Linux).

5. Inicie o servidor expondo para a rede:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```

### 2. Configuração do Mobile (App)

1. Navegue até a pasta:
    ```bash
    cd mobile
    ```

2. Instale as dependências:
    ```bash
    npm install
    # ou
    npx expo install
    ```

3. Abra o arquivo App.tsx e edite a variável API_URL com o IP do seu computador:
    ```bash
    const API_URL = 'http://SEU_IP_AQUI:8000/analyze/vin';
// Exemplo: [http://192.168.0.15:8000/analyze/vin](http://192.168.0.15:8000/analyze/vin)
    ```

4. Inicie o projeto Expo:
    ```bash
    npx expo start
    ```

5. Escaneie o QR Code exibido no terminal com o app **Expo Go** no seu celular.

---

## 🗂️ Banco de Dados de Imagens

O sistema compara a foto tirada com imagens originais de fábrica. Você deve alimentar a pasta backend/data/references manualmente.

**Estrutura Obrigatória:**
```bash
backend/data/references/
└── HONDA/
    └── {MODELO}/          (Ex: CG_160, XRE_300 - sem espaços)
        └── {ANO}/
            ├── chassi.jpg  # Foto de referência do chassi
            └── motor.jpg   # Foto de referência do motor
```

---

## ⚠️ Solução de Problemas Comuns

**Erro: "Network Error" ou "Falha de Conexão" no celular:**

1. Verifique se o Firewall do Windows não está bloqueando o Python. Desative temporariamente para testar.
2. Confirme se o IP no App.tsx está correto. IPs mudam se você reiniciar o roteador.
3. Se não funcionar, tente rodar o expo com túnel: npx expo start --tunnel.

**Erro: OCR não detecta nada**

1. A foto precisa estar nítida e na horizontal.
2. O sistema foi otimizado para superfícies metálicas, evite sombras muito fortes.

**Erro: "Module not found" no Python**

1. Verifique se você ativou o ambiente virtual (venv) antes de rodar o comando.