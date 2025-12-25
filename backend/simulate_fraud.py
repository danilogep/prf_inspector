#!/usr/bin/env python3
"""
Simulador de Adulterações - PRF Honda Motor Inspector
======================================================

Este script cria imagens adulteradas para testar a capacidade de detecção
do sistema.

IMPORTANTE: Este script é apenas para TESTES do sistema de detecção.
Não use para fins ilegais.

Uso:
    python simulate_fraud.py <imagem_original>
"""

import cv2
import numpy as np
import sys
from pathlib import Path


def create_test_images(original_path, output_dir="test_fraud_images"):
    """
    Cria várias versões adulteradas de uma imagem para teste.
    """
    # Carrega imagem original
    img = cv2.imread(original_path)
    if img is None:
        print(f"❌ Erro ao carregar: {original_path}")
        return []
    
    # Cria diretório de saída
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    created_files = []
    
    # 1. Cópia original (controle)
    original_file = output_path / "01_original.jpg"
    cv2.imwrite(str(original_file), img)
    created_files.append(("Original (controle)", str(original_file)))
    print(f"✅ Criado: {original_file}")
    
    # 2. Desalinhamento vertical (simula caractere regravado)
    img_misaligned = img.copy()
    h, w = img.shape[:2]
    # Seleciona uma faixa vertical e desloca
    strip_width = w // 15
    strip_x = w // 3
    strip = img_misaligned[:, strip_x:strip_x+strip_width].copy()
    # Desloca para cima
    shift = 5
    img_misaligned[:-shift, strip_x:strip_x+strip_width] = strip[shift:, :]
    
    misaligned_file = output_path / "02_desalinhado.jpg"
    cv2.imwrite(str(misaligned_file), img_misaligned)
    created_files.append(("Desalinhamento vertical", str(misaligned_file)))
    print(f"✅ Criado: {misaligned_file}")
    
    # 3. Alteração de densidade (simula regravação com ferramenta diferente)
    img_density = img.copy()
    # Adiciona ruído em uma área
    roi_x, roi_y = w // 4, h // 4
    roi_w, roi_h = w // 8, h // 2
    roi = img_density[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
    noise = np.random.randint(-30, 30, roi.shape, dtype=np.int16)
    roi_noisy = np.clip(roi.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img_density[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = roi_noisy
    
    density_file = output_path / "03_densidade_alterada.jpg"
    cv2.imwrite(str(density_file), img_density)
    created_files.append(("Densidade alterada (ruído)", str(density_file)))
    print(f"✅ Criado: {density_file}")
    
    # 4. Borramento localizado (simula lixamento/polimento)
    img_blur = img.copy()
    roi_x, roi_y = w // 3, 0
    roi_w, roi_h = w // 6, h
    roi = img_blur[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
    roi_blurred = cv2.GaussianBlur(roi, (15, 15), 0)
    img_blur[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = roi_blurred
    
    blur_file = output_path / "04_borrado_local.jpg"
    cv2.imwrite(str(blur_file), img_blur)
    created_files.append(("Borramento localizado", str(blur_file)))
    print(f"✅ Criado: {blur_file}")
    
    # 5. Contraste alterado (simula foto de gravação raspada/regravada)
    img_contrast = img.copy()
    alpha = 0.7  # Reduz contraste
    beta = 30    # Aumenta brilho
    img_contrast = cv2.convertScaleAbs(img_contrast, alpha=alpha, beta=beta)
    
    contrast_file = output_path / "05_contraste_baixo.jpg"
    cv2.imwrite(str(contrast_file), img_contrast)
    created_files.append(("Contraste reduzido", str(contrast_file)))
    print(f"✅ Criado: {contrast_file}")
    
    # 6. Rotação leve (simula gravação torta)
    center = (w // 2, h // 2)
    angle = 3  # graus
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    img_rotated = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    
    rotated_file = output_path / "06_rotacionado.jpg"
    cv2.imwrite(str(rotated_file), img_rotated)
    created_files.append(("Rotação (3°)", str(rotated_file)))
    print(f"✅ Criado: {rotated_file}")
    
    # 7. Simulação de caractere adicionado (linha extra)
    img_extra = img.copy()
    # Desenha uma linha vertical simulando parte de um caractere
    line_x = w // 2
    cv2.line(img_extra, (line_x, h//4), (line_x, 3*h//4), (50, 50, 50), 2)
    
    extra_file = output_path / "07_linha_extra.jpg"
    cv2.imwrite(str(extra_file), img_extra)
    created_files.append(("Linha extra adicionada", str(extra_file)))
    print(f"✅ Criado: {extra_file}")
    
    # 8. Erosão (simula desgaste/raspagem)
    kernel = np.ones((2, 2), np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    eroded = cv2.erode(gray, kernel, iterations=1)
    img_eroded = cv2.cvtColor(eroded, cv2.COLOR_GRAY2BGR)
    
    eroded_file = output_path / "08_erosao.jpg"
    cv2.imwrite(str(eroded_file), img_eroded)
    created_files.append(("Erosão (desgaste)", str(eroded_file)))
    print(f"✅ Criado: {eroded_file}")
    
    return created_files


def create_batch_test_script(files, output_dir="test_fraud_images"):
    """Cria script para testar todas as imagens geradas."""
    
    script_content = '''#!/usr/bin/env python3
"""
Script para testar imagens adulteradas geradas.
Execute após iniciar o servidor.
"""

import requests
import json

API_URL = "http://localhost:8000/analyze/motor"

test_cases = [
'''
    
    for description, filepath in files:
        script_content += f'    ("{description}", "{filepath}", 2020),\n'
    
    script_content += ''']

def test_all():
    print("="*70)
    print("TESTE DE DETECÇÃO DE ADULTERAÇÕES")
    print("="*70)
    
    results = []
    
    for description, filepath, year in test_cases:
        print(f"\\n📷 {description}")
        print(f"   Arquivo: {filepath}")
        
        try:
            with open(filepath, 'rb') as f:
                response = requests.post(
                    API_URL,
                    files={'photo': f},
                    data={'year': year},
                    timeout=60
                )
            
            if response.status_code == 200:
                result = response.json()
                verdict = result['verdict']
                score = result['risk_score']
                
                if verdict == 'REGULAR':
                    status = '✅'
                elif verdict == 'ATENÇÃO':
                    status = '⚠️'
                else:
                    status = '🚨'
                
                print(f"   {status} Veredito: {verdict} (Score: {score}%)")
                print(f"   Código: {result.get('read_code', 'N/A')}")
                
                if result.get('explanation'):
                    print(f"   Observações:")
                    for obs in result['explanation'][:2]:
                        print(f"     • {obs}")
                
                results.append({
                    'description': description,
                    'verdict': verdict,
                    'score': score
                })
            else:
                print(f"   ❌ Erro: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
    
    # Resumo
    print("\\n" + "="*70)
    print("RESUMO")
    print("="*70)
    
    for r in results:
        status = '✅' if r['verdict'] == 'REGULAR' else ('⚠️' if r['verdict'] == 'ATENÇÃO' else '🚨')
        print(f"{status} {r['description']}: {r['verdict']} ({r['score']}%)")
    
    # Análise
    regulares = sum(1 for r in results if r['verdict'] == 'REGULAR')
    suspeitos = sum(1 for r in results if r['verdict'] not in ['REGULAR'])
    
    print(f"\\nRegulares: {regulares}/{len(results)}")
    print(f"Detectados como suspeitos: {suspeitos}/{len(results)}")
    
    if suspeitos >= len(results) - 1:  # Deve detectar todas menos a original
        print("\\n🎉 Sistema está detectando adulterações corretamente!")
    else:
        print("\\n⚠️ Sistema pode precisar de ajustes nas tolerâncias.")

if __name__ == "__main__":
    test_all()
'''
    
    script_path = Path(output_dir) / "test_fraud_detection.py"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    print(f"\n✅ Script de teste criado: {script_path}")
    return str(script_path)


def main():
    if len(sys.argv) < 2:
        print("Uso: python simulate_fraud.py <imagem_original>")
        print("")
        print("Este script cria imagens adulteradas para testar o sistema de detecção.")
        print("")
        print("Exemplo:")
        print("  python simulate_fraud.py WhatsApp_Image_2025-12-20_at_18_28_30.jpeg")
        return
    
    original_image = sys.argv[1]
    
    if not Path(original_image).exists():
        print(f"❌ Arquivo não encontrado: {original_image}")
        return
    
    print("="*60)
    print("SIMULADOR DE ADULTERAÇÕES - PRF Honda Motor Inspector")
    print("="*60)
    print(f"\nImagem original: {original_image}")
    print("\nCriando imagens de teste...")
    print("")
    
    files = create_test_images(original_image)
    
    if files:
        print(f"\n✅ {len(files)} imagens criadas em 'test_fraud_images/'")
        
        # Cria script de teste
        test_script = create_batch_test_script(files)
        
        print("\n" + "="*60)
        print("PRÓXIMOS PASSOS")
        print("="*60)
        print("""
1. Certifique-se de que o servidor está rodando:
   uvicorn app.main:app --host 0.0.0.0 --port 8000

2. Execute o script de teste:
   python test_fraud_images/test_fraud_detection.py

3. Analise os resultados:
   - A imagem ORIGINAL deve retornar "REGULAR"
   - As imagens ADULTERADAS devem retornar "ATENÇÃO" ou "SUSPEITO"
   
4. Se muitas adulterações passarem como "REGULAR":
   - Ajuste as tolerâncias em app/core/config.py
   - Reduza ALIGNMENT_TOLERANCE e DENSITY_TOLERANCE
""")


if __name__ == "__main__":
    main()
