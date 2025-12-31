#!/usr/bin/env python3
"""
PRF Honda Inspector - Script de Teste v5.33
Endpoint: /analyze/motor | Params: photo, year
"""

import sys
import time
import requests
from pathlib import Path

API_URL = "http://localhost:8000"
ENDPOINT = "/analyze/motor"
TIMEOUT = 180
ANO = 2020

def analisar(filepath):
    try:
        with open(filepath, 'rb') as f:
            start = time.time()
            r = requests.post(
                f"{API_URL}{ENDPOINT}",
                files={'photo': (filepath.name, f, 'image/jpeg')},
                data={'year': ANO},
                timeout=TIMEOUT
            )
            t = time.time() - start
            if r.status_code == 200:
                j = r.json()
                return {'ok': True, 'score': j.get('risk_score', 0), 'tempo': t, 'factors': j.get('risk_factors', [])}
            return {'ok': False, 'erro': f"HTTP {r.status_code}", 'tempo': t}
    except requests.exceptions.Timeout:
        return {'ok': False, 'erro': 'Timeout', 'tempo': TIMEOUT}
    except Exception as e:
        return {'ok': False, 'erro': str(e), 'tempo': 0}

def tipo(nome):
    n = nome.upper()
    if 'ORIGINAL' in n: return 'O'
    if 'ADULTER' in n or 'FRAUD' in n: return 'A'
    return '?'

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_manual_flexivel.py <pasta>")
        sys.exit(1)
    
    pasta = Path(sys.argv[1])
    if not pasta.exists():
        print(f"Pasta não encontrada: {pasta}")
        sys.exit(1)
    
    try:
        r = requests.get(f"{API_URL}/health", timeout=10)
        if r.status_code != 200:
            print("API offline")
            sys.exit(1)
    except:
        print("API offline")
        sys.exit(1)
    
    print("=" * 70)
    print("PRF HONDA INSPECTOR - TESTE v5.33 (ULTRA CONSERVADOR)")
    print("=" * 70)
    
    imgs = [f for f in pasta.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}]
    orig = [i for i in imgs if tipo(i.name) == 'O']
    adult = [i for i in imgs if tipo(i.name) == 'A']
    
    print(f"Originais: {len(orig)} | Adulterados: {len(adult)}\n")
    
    res = {'o_ok': 0, 'o_err': 0, 'a_ok': 0, 'a_err': 0, 'falhas': 0}
    
    for img in sorted(orig):
        print(f"[ORIG] {img.name}", end=" ", flush=True)
        r = analisar(img)
        if r['ok']:
            factors = r.get('factors', [])
            if r['score'] < 50:
                print(f"✓ score={r['score']} t={r['tempo']:.0f}s")
                res['o_ok'] += 1
            else:
                print(f"✗ score={r['score']} FALSO POSITIVO!")
                for f in factors[:3]:
                    print(f"     • {f}")
                res['o_err'] += 1
        else:
            print(f"FALHA: {r['erro']}")
            res['falhas'] += 1
    
    for img in sorted(adult):
        print(f"[ADULT] {img.name}", end=" ", flush=True)
        r = analisar(img)
        if r['ok']:
            if r['score'] >= 50:
                print(f"✓ score={r['score']} t={r['tempo']:.0f}s")
                res['a_ok'] += 1
            else:
                print(f"✗ score={r['score']} FALSO NEGATIVO!")
                res['a_err'] += 1
        else:
            print(f"FALHA: {r['erro']}")
            res['falhas'] += 1
    
    print("\n" + "=" * 70)
    total = len(orig) + len(adult)
    acertos = res['o_ok'] + res['a_ok']
    if total > 0:
        print(f"TAXA: {acertos}/{total} ({acertos/total*100:.1f}%)")
    print(f"Originais: {res['o_ok']}/{len(orig)} | FP: {res['o_err']}")
    print(f"Adulterados: {res['a_ok']}/{len(adult)} | FN: {res['a_err']}")
    print(f"Falhas: {res['falhas']}")
    print("=" * 70)

if __name__ == "__main__":
    main()
