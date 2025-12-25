"""
Script para Extrair Templates de Fonte Honda
=============================================
Uso: python extract_font_templates.py --image caminho/imagem.jpg

Este script ajuda a extrair caracteres individuais de uma imagem
de motor Honda para criar o banco de dados de fontes.
"""

import cv2
import numpy as np
import argparse
from pathlib import Path


def extract_characters(image_path: str, output_dir: str, font_type: str = "laser"):
    """
    Extrai caracteres de uma imagem de motor Honda.
    
    Args:
        image_path: Caminho da imagem fonte
        output_dir: Diretório de saída
        font_type: 'laser' ou 'estampagem'
    """
    
    # Carrega imagem
    img = cv2.imread(image_path)
    if img is None:
        print(f"Erro: Não foi possível carregar {image_path}")
        return
    
    print(f"Imagem carregada: {img.shape}")
    
    # Converte para escala de cinza
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Melhora contraste
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Binariza
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Morfologia para limpar
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # Encontra contornos
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filtra contornos por tamanho
    char_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Filtra por tamanho mínimo e proporção
        if w > 15 and h > 25 and h > w * 0.8:
            char_boxes.append((x, y, w, h))
    
    # Ordena da esquerda para direita, depois de cima para baixo
    char_boxes.sort(key=lambda b: (b[1] // 50, b[0]))  # Agrupa por linha
    
    print(f"\nEncontrados {len(char_boxes)} possíveis caracteres")
    
    # Cria diretório de saída
    output_path = Path(output_dir) / f"honda_{font_type}"
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Mostra imagem com contornos
    img_contours = img.copy()
    for i, (x, y, w, h) in enumerate(char_boxes):
        cv2.rectangle(img_contours, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(img_contours, str(i+1), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    # Redimensiona para visualização
    scale = min(1200 / img_contours.shape[1], 800 / img_contours.shape[0])
    if scale < 1:
        img_display = cv2.resize(img_contours, None, fx=scale, fy=scale)
    else:
        img_display = img_contours
    
    cv2.imshow("Caracteres Detectados (pressione qualquer tecla)", img_display)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    print("\n" + "="*50)
    print("INSTRUÇÕES:")
    print("="*50)
    print("Para cada caractere mostrado:")
    print("  - Digite o valor (ex: N, D, 0, 9, E, 1, B)")
    print("  - Digite 'skip' para pular")
    print("  - Digite 'quit' para sair")
    print("  - Digite 'redo' para refazer o anterior")
    print("="*50 + "\n")
    
    saved_chars = []
    i = 0
    
    while i < len(char_boxes):
        x, y, w, h = char_boxes[i]
        
        # Extrai ROI com margem
        margin = 8
        y1 = max(0, y - margin)
        y2 = min(gray.shape[0], y + h + margin)
        x1 = max(0, x - margin)
        x2 = min(gray.shape[1], x + w + margin)
        
        roi = gray[y1:y2, x1:x2]
        
        # Mostra caractere ampliado
        roi_display = cv2.resize(roi, (200, 250), interpolation=cv2.INTER_NEAREST)
        
        # Adiciona borda para visualização
        roi_display = cv2.copyMakeBorder(roi_display, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=128)
        
        cv2.imshow(f"Caractere {i+1}/{len(char_boxes)}", roi_display)
        cv2.waitKey(100)
        
        # Pede input
        char_name = input(f"Caractere {i+1}/{len(char_boxes)}: ").strip().upper()
        
        if char_name == 'QUIT':
            break
        elif char_name == 'SKIP' or not char_name:
            i += 1
            continue
        elif char_name == 'REDO' and saved_chars:
            # Remove último salvo
            last = saved_chars.pop()
            last_file = output_path / f"{last}.png"
            if last_file.exists():
                last_file.unlink()
            print(f"  Removido: {last}")
            i -= 1
            continue
        
        # Normaliza para tamanho padrão 64x80
        # Mantém proporção e centraliza
        target_w, target_h = 64, 80
        
        h_roi, w_roi = roi.shape
        scale = min((target_w - 10) / w_roi, (target_h - 10) / h_roi)
        new_w = int(w_roi * scale)
        new_h = int(h_roi * scale)
        
        resized = cv2.resize(roi, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Cria canvas branco e centraliza
        canvas = np.ones((target_h, target_w), dtype=np.uint8) * 255
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        # Salva
        output_file = output_path / f"{char_name}.png"
        
        # Se já existe, pergunta se quer substituir
        if output_file.exists():
            replace = input(f"  '{char_name}.png' já existe. Substituir? (s/n): ").strip().lower()
            if replace != 's':
                i += 1
                continue
        
        cv2.imwrite(str(output_file), canvas)
        saved_chars.append(char_name)
        print(f"  ✓ Salvo: {output_file}")
        
        i += 1
    
    cv2.destroyAllWindows()
    
    print("\n" + "="*50)
    print("RESUMO")
    print("="*50)
    print(f"Templates salvos em: {output_path}")
    print(f"Total de caracteres: {len(saved_chars)}")
    print(f"Caracteres: {', '.join(saved_chars)}")
    print("="*50)
    
    # Cria metadata.json básico
    create_metadata(output_path, saved_chars, font_type)


def create_metadata(output_path: Path, chars: list, font_type: str):
    """Cria arquivo metadata.json básico."""
    import json
    
    metadata = {
        "version": "1.0",
        "font_type": font_type,
        "year_range": [2010, 2099] if font_type == "laser" else [1900, 2009],
        "characters": {}
    }
    
    high_risk = ['0', '1', '3', '4', '9']
    
    for char in chars:
        metadata["characters"][char] = {
            "file": f"{char}.png",
            "high_risk": char in high_risk
        }
    
    metadata_file = output_path.parent / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\nMetadata salvo em: {metadata_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Extrai templates de fonte de uma imagem de motor Honda"
    )
    parser.add_argument(
        "--image", "-i",
        required=True,
        help="Caminho da imagem de origem"
    )
    parser.add_argument(
        "--output", "-o",
        default="data/fonts",
        help="Diretório de saída (padrão: data/fonts)"
    )
    parser.add_argument(
        "--type", "-t",
        choices=["laser", "estampagem"],
        default="laser",
        help="Tipo de gravação (padrão: laser)"
    )
    
    args = parser.parse_args()
    
    extract_characters(args.image, args.output, args.type)


if __name__ == "__main__":
    main()
