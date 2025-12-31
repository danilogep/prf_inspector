#!/usr/bin/env python3
"""
Diagnóstico v5.33 - Mostra resposta COMPLETA da API
"""

import sys
import json
import requests
from pathlib import Path

API_URL = "http://localhost:8000"

def main():
    if len(sys.argv) < 2:
        print("Uso: python diagnostico.py <imagem>")
        sys.exit(1)
    
    img = Path(sys.argv[1])
    if not img.exists():
        print(f"Arquivo não encontrado: {img}")
        sys.exit(1)
    
    print(f"Analisando: {img.name}")
    print("=" * 70)
    
    with open(img, 'rb') as f:
        r = requests.post(
            f"{API_URL}/analyze/motor",
            files={'photo': (img.name, f, 'image/jpeg')},
            data={'year': 2020},
            timeout=300
        )
    
    if r.status_code != 200:
        print(f"ERRO HTTP {r.status_code}")
        print(r.text)
        sys.exit(1)
    
    data = r.json()
    
    print(f"\n📊 SCORE: {data.get('risk_score', '?')}")
    print(f"📝 VERDICT: {data.get('verdict', '?')}")
    print(f"🔤 CÓDIGO: {data.get('read_code', '?')}")
    
    factors = data.get('risk_factors', [])
    print(f"\n⚠️ RISK FACTORS ({len(factors)}):")
    for f in factors:
        print(f"   • {f}")
    
    # Mostra componentes se disponível
    components = data.get('components', {})
    if components:
        ai = components.get('ai_analysis', {})
        
        print("\n" + "=" * 70)
        print("ANÁLISE DA IA:")
        print("=" * 70)
        
        veredicto = ai.get('veredicto', ai.get('font_analysis', {}).get('veredicto', {}))
        if veredicto:
            print(f"  Classificação: {veredicto.get('classificacao', '?')}")
            print(f"  Certeza: {veredicto.get('certeza', '?')}%")
            print(f"  Motivo: {veredicto.get('motivo_principal', '?')}")
        
        superficie = ai.get('surface_analysis', {})
        if superficie:
            print(f"\n  Superfície:")
            print(f"    - Números fantasma: {superficie.get('numeros_fantasma', '?')}")
            print(f"    - Marcas de lixa: {superficie.get('marcas_lixa', '?')}")
            print(f"    - Paralelas: {superficie.get('marcas_paralelas', '?')}")
        
        gravacao = ai.get('analise_gravacao', ai.get('font_analysis', {}).get('analise_gravacao', {}))
        if gravacao:
            print(f"\n  Gravação:")
            print(f"    - Linha 1: {gravacao.get('tipo_linha1', '?')}")
            print(f"    - Linha 2: {gravacao.get('tipo_linha2', '?')}")
            print(f"    - Mistura: {gravacao.get('mistura_tipos', '?')}")
    
    print("\n" + "=" * 70)
    print("JSON COMPLETO:")
    print("=" * 70)
    # Remove campos muito grandes
    clean = {k: v for k, v in data.items() if k not in ['clahe_image']}
    print(json.dumps(clean, indent=2, ensure_ascii=False, default=str)[:3000])

if __name__ == "__main__":
    main()
