#!/usr/bin/env python3
"""
Script para extrair templates de fonte da imagem de referência Honda.

Uso:
    python extract_font_templates.py <caminho_imagem_fonte>
    
Exemplo:
    python extract_font_templates.py honda_numeros.png
    
O script irá:
1. Carregar a imagem com os números 0-9
2. Detectar cada número individualmente
3. Salvar cada número como arquivo separado em data/fonts/
"""

import cv2
import numpy as np
import sys
from pathlib import Path


def extract_characters(image_path: str, output_dir: str = "data/fonts"):
    """
    Extrai caracteres individuais de uma imagem de spritesheet.
    """
    # Carrega imagem
    img = cv2.imread(image_path)
    if img is None:
        print(f"Erro: Não foi possível carregar {image_path}")
        return False
    
    # Converte para escala de cinza
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Binariza (inverte para ter caracteres brancos em fundo preto)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    
    # Encontra contornos
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filtra e ordena contornos
    valid_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Filtra contornos muito pequenos (ruído)
        if w > 15 and h > 20:
            valid_boxes.append((x, y, w, h))
    
    # Ordena da esquerda para direita
    valid_boxes.sort(key=lambda b: b[0])
    
    print(f"Encontrados {len(valid_boxes)} caracteres")
    
    # Cria diretório de saída
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Sequência esperada de caracteres
    chars = "0123456789"
    
    for i, (x, y, w, h) in enumerate(valid_boxes):
        if i >= len(chars):
            print(f"Aviso: Mais contornos ({len(valid_boxes)}) do que caracteres esperados ({len(chars)})")
            break
        
        char = chars[i]
        
        # Adiciona margem
        margin = 5
        y1 = max(0, y - margin)
        y2 = min(gray.shape[0], y + h + margin)
        x1 = max(0, x - margin)
        x2 = min(gray.shape[1], x + w + margin)
        
        # Extrai o caractere (da imagem original em cinza)
        char_img = gray[y1:y2, x1:x2]
        
        # Salva
        output_file = output_path / f"{char}.png"
        cv2.imwrite(str(output_file), char_img)
        print(f"  Salvo: {output_file} ({w}x{h} pixels)")
    
    # Salva também a imagem completa como spritesheet
    sprite_file = output_path / "honda_font.png"
    cv2.imwrite(str(sprite_file), gray)
    print(f"  Spritesheet salvo: {sprite_file}")
    
    return True


def main():
    if len(sys.argv) < 2:
        print("Uso: python extract_font_templates.py <caminho_imagem_fonte>")
        print("")
        print("Exemplo:")
        print("  python extract_font_templates.py WhatsApp_Image_2025-12-20_at_18_28_43.jpeg")
        return
    
    image_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "data/fonts"
    
    print(f"Extraindo caracteres de: {image_path}")
    print(f"Salvando em: {output_dir}")
    print("")
    
    success = extract_characters(image_path, output_dir)
    
    if success:
        print("")
        print("Extração concluída com sucesso!")
        print("")
        print("Próximos passos:")
        print("1. Verifique os arquivos em data/fonts/")
        print("2. Confirme que cada número foi extraído corretamente")
        print("3. Reinicie o servidor para carregar os templates")
    else:
        print("Erro na extração!")


if __name__ == "__main__":
    main()
