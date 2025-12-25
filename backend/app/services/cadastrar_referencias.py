"""
Script para cadastrar motores de referência em lote
===================================================
Execute: python cadastrar_referencias.py
"""

import os
import sys
import httpx
from pathlib import Path

API_URL = "http://localhost:8000"


def cadastrar_original(code: str, year: int, engraving_type: str, 
                       photo_path: str, model: str = None, description: str = None):
    """Cadastra motor original."""
    
    if not Path(photo_path).exists():
        print(f"❌ Arquivo não encontrado: {photo_path}")
        return False
    
    with open(photo_path, 'rb') as f:
        files = {'photo': (Path(photo_path).name, f, 'image/jpeg')}
        data = {
            'code': code,
            'year': str(year),
            'engraving_type': engraving_type
        }
        if model:
            data['model'] = model
        if description:
            data['description'] = description
        
        try:
            response = httpx.post(
                f"{API_URL}/references/originals/add",
                data=data,
                files=files,
                timeout=30.0
            )
            
            if response.status_code == 200:
                print(f"✅ Original cadastrado: {code}")
                return True
            else:
                print(f"❌ Erro: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
            return False


def cadastrar_fraude(fraud_code: str, fraud_type: str, description: str,
                     photo_path: str, original_code: str = None,
                     indicators: list = None, year_claimed: int = None):
    """Cadastra motor adulterado."""
    
    if not Path(photo_path).exists():
        print(f"❌ Arquivo não encontrado: {photo_path}")
        return False
    
    with open(photo_path, 'rb') as f:
        files = {'photo': (Path(photo_path).name, f, 'image/jpeg')}
        data = {
            'fraud_code': fraud_code,
            'fraud_type': fraud_type,
            'description': description
        }
        if original_code:
            data['original_code'] = original_code
        if indicators:
            data['indicators'] = ','.join(indicators)
        if year_claimed:
            data['year_claimed'] = str(year_claimed)
        
        try:
            response = httpx.post(
                f"{API_URL}/references/frauds/add",
                data=data,
                files=files,
                timeout=30.0
            )
            
            if response.status_code == 200:
                print(f"✅ Fraude cadastrada: {fraud_code}")
                return True
            else:
                print(f"❌ Erro: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
            return False


def main():
    print("=" * 60)
    print("Cadastro de Referências - PRF Honda Inspector")
    print("=" * 60)
    
    # Verifica conexão
    try:
        response = httpx.get(f"{API_URL}/health", timeout=5.0)
        if response.status_code != 200:
            print("❌ API não está respondendo")
            return
        print("✅ API conectada")
    except:
        print("❌ Não foi possível conectar à API")
        print(f"   Verifique se o servidor está rodando em {API_URL}")
        return
    
    # ========================================
    # CADASTRE SEUS MOTORES ORIGINAIS AQUI
    # ========================================
    
    print("\n📋 Cadastrando motores ORIGINAIS...")
    
    # Descomente e ajuste conforme suas imagens:
    
    # cadastrar_original(
    #     code="KC08E2-E3012920",
    #     year=2004,
    #     engraving_type="estampagem",
    #     photo_path="imagens/motor_original_2004.jpg",
    #     model="CG 125 Titan",
    #     description="Motor original verificado, estampagem com profundidade uniforme"
    # )
    
    # cadastrar_original(
    #     code="JC96E1-S001485",
    #     year=2024,
    #     engraving_type="laser",
    #     photo_path="imagens/motor_original_2024.jpg",
    #     model="CG 160",
    #     description="Motor original laser, micropuntos visíveis"
    # )
    
    # ========================================
    # CADASTRE SUAS FRAUDES CONHECIDAS AQUI
    # ========================================
    
    print("\n📋 Cadastrando motores ADULTERADOS...")
    
    # Descomente e ajuste conforme suas imagens:
    
    # cadastrar_fraude(
    #     fraud_code="KC16E6-C553627",
    #     fraud_type="mistura_tipos",
    #     description="Prefixo KC16E6 em LASER original. Serial C553627 em ESTAMPAGEM grosseira adicionada posteriormente. Desalinhamento visível. Espaçamento irregular.",
    #     photo_path="imagens/fraude_mistura.jpg",
    #     indicators=[
    #         "mistura_laser_estampagem",
    #         "desalinhamento_vertical",
    #         "espacamento_irregular",
    #         "fonte_nao_honda"
    #     ],
    #     year_claimed=2008
    # )
    
    # cadastrar_fraude(
    #     fraud_code="KC08E-3012920",
    #     fraud_type="desalinhamento",
    #     description="Serial com desalinhamento severo. Número 5 com fonte diferente (mais grosso). Espaçamento irregular entre caracteres.",
    #     photo_path="imagens/fraude_desalinhado.jpg",
    #     indicators=[
    #         "desalinhamento_vertical",
    #         "fonte_nao_honda",
    #         "espacamento_irregular"
    #     ],
    #     year_claimed=2004
    # )
    
    # ========================================
    # ESTATÍSTICAS
    # ========================================
    
    print("\n📊 Estatísticas:")
    try:
        response = httpx.get(f"{API_URL}/references/stats", timeout=5.0)
        stats = response.json()
        print(f"   Originais: {stats.get('originals', 0)}")
        print(f"   Fraudes: {stats.get('frauds', 0)}")
    except:
        print("   Erro ao obter estatísticas")
    
    print("\n" + "=" * 60)
    print("Pronto! Descomente as chamadas e ajuste os caminhos das imagens.")
    print("=" * 60)


if __name__ == "__main__":
    main()
