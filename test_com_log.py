#!/usr/bin/env python3
"""
PRF Honda Inspector - Script de Teste COM LOG v5.33
Params: photo, year
"""

import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime

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
                return {'ok': True, 'data': r.json(), 'tempo': t}
            return {'ok': False, 'erro': f"HTTP {r.status_code}: {r.text[:200]}", 'tempo': t}
    except requests.exceptions.Timeout:
        return {'ok': False, 'erro': f'Timeout {TIMEOUT}s', 'tempo': TIMEOUT}
    except Exception as e:
        return {'ok': False, 'erro': str(e), 'tempo': 0}

def tipo(nome):
    n = nome.upper()
    if 'ORIGINAL' in n: return 'ORIGINAL'
    if 'ADULTER' in n or 'FRAUD' in n: return 'ADULTERADO'
    return 'DESCONHECIDO'

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_com_log.py <pasta>")
        sys.exit(1)
    
    pasta = Path(sys.argv[1])
    if not pasta.exists():
        print(f"Pasta não encontrada: {pasta}")
        sys.exit(1)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = Path(f"teste_log_{timestamp}.json")
    
    print("=" * 70)
    print("PRF HONDA INSPECTOR - TESTE COM LOG v5.33")
    print(f"Log: {log_file}")
    print("=" * 70)
    
    try:
        r = requests.get(f"{API_URL}/health", timeout=10)
        if r.status_code != 200:
            print("API offline")
            sys.exit(1)
    except:
        print("API offline")
        sys.exit(1)
    
    print("API OK\n")
    
    imgs = [f for f in pasta.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}]
    por_tipo = {'ORIGINAL': [], 'ADULTERADO': [], 'DESCONHECIDO': []}
    for img in imgs:
        por_tipo[tipo(img.name)].append(img)
    
    print(f"Originais: {len(por_tipo['ORIGINAL'])} | Adulterados: {len(por_tipo['ADULTERADO'])}\n")
    
    log_data = {
        'timestamp': timestamp,
        'versao': 'v5.33',
        'pasta': str(pasta),
        'resultados': [],
        'resumo': {
            'originais': {'total': 0, 'ok': 0, 'falsos_positivos': []},
            'adulterados': {'total': 0, 'ok': 0, 'falsos_negativos': []},
            'falhas': []
        }
    }
    
    # ORIGINAIS
    for img in sorted(por_tipo['ORIGINAL']):
        print(f"[ORIG] {img.name}", end=" ", flush=True)
        r = analisar(img)
        log_data['resumo']['originais']['total'] += 1
        
        resultado = {'arquivo': img.name, 'tipo_esperado': 'ORIGINAL', 'tempo': r.get('tempo', 0)}
        
        if r['ok']:
            data = r['data']
            score = data.get('risk_score', 0)
            resultado['score'] = score
            resultado['codigo'] = data.get('read_code', '')
            resultado['verdict'] = data.get('verdict', '')
            resultado['risk_factors'] = data.get('risk_factors', [])
            
            if score < 50:
                print(f"✓ score={score} t={r['tempo']:.0f}s")
                resultado['status'] = 'OK'
                log_data['resumo']['originais']['ok'] += 1
            else:
                print(f"✗ score={score} FALSO POSITIVO!")
                resultado['status'] = 'FALSO_POSITIVO'
                log_data['resumo']['originais']['falsos_positivos'].append({
                    'arquivo': img.name, 
                    'score': score, 
                    'motivos': data.get('risk_factors', [])
                })
        else:
            print(f"FALHA: {r['erro']}")
            resultado['status'] = 'FALHA'
            resultado['erro'] = r['erro']
            log_data['resumo']['falhas'].append(img.name)
        
        log_data['resultados'].append(resultado)
    
    # ADULTERADOS
    for img in sorted(por_tipo['ADULTERADO']):
        print(f"[ADULT] {img.name}", end=" ", flush=True)
        r = analisar(img)
        log_data['resumo']['adulterados']['total'] += 1
        
        resultado = {'arquivo': img.name, 'tipo_esperado': 'ADULTERADO', 'tempo': r.get('tempo', 0)}
        
        if r['ok']:
            data = r['data']
            score = data.get('risk_score', 0)
            resultado['score'] = score
            resultado['codigo'] = data.get('read_code', '')
            resultado['verdict'] = data.get('verdict', '')
            resultado['risk_factors'] = data.get('risk_factors', [])
            
            if score >= 50:
                print(f"✓ score={score} t={r['tempo']:.0f}s")
                resultado['status'] = 'OK'
                log_data['resumo']['adulterados']['ok'] += 1
            else:
                print(f"✗ score={score} FALSO NEGATIVO!")
                resultado['status'] = 'FALSO_NEGATIVO'
                log_data['resumo']['adulterados']['falsos_negativos'].append({
                    'arquivo': img.name, 
                    'score': score, 
                    'motivos': data.get('risk_factors', [])
                })
        else:
            print(f"FALHA: {r['erro']}")
            resultado['status'] = 'FALHA'
            resultado['erro'] = r['erro']
            log_data['resumo']['falhas'].append(img.name)
        
        log_data['resultados'].append(resultado)
    
    # Salvar log
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    # Resumo
    print("\n" + "=" * 70)
    orig = log_data['resumo']['originais']
    adult = log_data['resumo']['adulterados']
    total = orig['total'] + adult['total']
    acertos = orig['ok'] + adult['ok']
    
    if total > 0:
        print(f"TAXA: {acertos}/{total} ({acertos/total*100:.1f}%)")
    
    if orig['falsos_positivos']:
        print(f"\n❌ FALSOS POSITIVOS ({len(orig['falsos_positivos'])}):")
        for fp in orig['falsos_positivos'][:5]:
            print(f"   {fp['arquivo']}: score={fp['score']}")
            for m in fp['motivos'][:2]:
                print(f"     • {m}")
    
    if adult['falsos_negativos']:
        print(f"\n❌ FALSOS NEGATIVOS ({len(adult['falsos_negativos'])}):")
        for fn in adult['falsos_negativos'][:5]:
            print(f"   {fn['arquivo']}: score={fn['score']}")
    
    print(f"\n📄 Log: {log_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
