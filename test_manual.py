#!/usr/bin/env python3
"""
PRF Honda Inspector - Script de Teste Manual
=============================================

Testa todas as imagens de ORIGINAIS e ADULTERADOS
e gera relatório de taxa de acerto.

Uso:
    python test_manual.py [caminho_das_imagens]
    
Exemplo:
    python test_manual.py /mnt/project
    python test_manual.py ./imagens
"""

import httpx
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ========================================
# CONFIGURAÇÃO
# ========================================

API_URL = "http://localhost:8000"
TIMEOUT = 120.0  # segundos

# Anos padrão para teste (ajuste conforme necessário)
DEFAULT_YEAR_ORIGINAL = 2020
DEFAULT_YEAR_ADULTERADO = 2018


def get_api_status(client: httpx.Client) -> Tuple[bool, str]:
    """Verifica status da API."""
    try:
        response = client.get(f"{API_URL}/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            return True, f"API OK - IA: {data.get('components', {}).get('forensic_ai', 'N/A')}"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


def analyze_image(
    client: httpx.Client, 
    image_path: Path, 
    year: int
) -> Optional[Dict]:
    """Envia imagem para análise."""
    try:
        with open(image_path, "rb") as f:
            response = client.post(
                f"{API_URL}/analyze/motor",
                data={"year": str(year)},
                files={"photo": (image_path.name, f, "image/jpeg")},
                timeout=TIMEOUT
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"      ❌ Erro HTTP: {response.status_code}")
            return None
            
    except httpx.TimeoutException:
        print(f"      ⏰ Timeout após {TIMEOUT}s")
        return None
    except Exception as e:
        print(f"      ❌ Erro: {e}")
        return None


def test_single_image(
    client: httpx.Client,
    image_path: Path,
    expected_type: str,
    year: int
) -> Dict:
    """Testa uma única imagem e retorna resultado."""
    
    print(f"\n   📷 {image_path.name}")
    
    result = {
        "image": image_path.name,
        "expected": expected_type,
        "year": year,
        "score": None,
        "verdict": None,
        "code": None,
        "correct": False,
        "error": None
    }
    
    data = analyze_image(client, image_path, year)
    
    if data is None:
        result["error"] = "Falha na análise"
        print(f"      ❌ Falha na análise")
        return result
    
    score = data.get("risk_score", 0)
    verdict = data.get("verdict", "N/A")
    code = data.get("read_code", "N/A")
    
    result["score"] = score
    result["verdict"] = verdict
    result["code"] = code
    
    # Determina se acertou
    if expected_type == "ORIGINAL":
        result["correct"] = score < 50
    else:  # ADULTERADO
        result["correct"] = score >= 50
    
    emoji = "✅" if result["correct"] else "❌"
    print(f"      {emoji} Score: {score:3d} | {verdict}")
    print(f"         Código: {code}")
    
    return result


def find_images(base_dir: Path) -> Tuple[List[Path], List[Path]]:
    """Encontra imagens de originais e adulterados."""
    
    originais = []
    adulterados = []
    
    # Padrão 1: ORIGINAL_N.jpeg e ADULTERADOS_N.jpeg
    for i in range(1, 50):
        orig = base_dir / f"ORIGINAL_{i}.jpeg"
        if orig.exists():
            originais.append(orig)
        
        adult = base_dir / f"ADULTERADOS_{i}.jpeg"
        if adult.exists():
            adulterados.append(adult)
    
    # Padrão 2: Subpastas originais/ e adulterados/
    orig_dir = base_dir / "originais"
    if orig_dir.exists():
        originais.extend(orig_dir.glob("*.jpg"))
        originais.extend(orig_dir.glob("*.jpeg"))
        originais.extend(orig_dir.glob("*.png"))
    
    adult_dir = base_dir / "adulterados"
    if adult_dir.exists():
        adulterados.extend(adult_dir.glob("*.jpg"))
        adulterados.extend(adult_dir.glob("*.jpeg"))
        adulterados.extend(adult_dir.glob("*.png"))
    
    return sorted(originais), sorted(adulterados)


def print_header():
    """Imprime cabeçalho."""
    print("\n" + "=" * 70)
    print("🔬 PRF HONDA INSPECTOR - TESTE DE IMAGENS")
    print("=" * 70)


def print_summary(results: List[Dict]):
    """Imprime resumo dos resultados."""
    
    print("\n" + "=" * 70)
    print("📊 RELATÓRIO FINAL")
    print("=" * 70)
    
    total = len(results)
    if total == 0:
        print("❌ Nenhuma imagem testada!")
        return
    
    corretos = sum(1 for r in results if r["correct"])
    erros_analise = sum(1 for r in results if r["error"])
    
    originais = [r for r in results if r["expected"] == "ORIGINAL"]
    adulterados = [r for r in results if r["expected"] == "ADULTERADO"]
    
    orig_corretos = sum(1 for r in originais if r["correct"])
    adult_corretos = sum(1 for r in adulterados if r["correct"])
    
    print(f"\n📈 TAXA DE ACERTO GERAL: {corretos}/{total} ({100*corretos/total:.1f}%)")
    
    if originais:
        print(f"\n   🟢 ORIGINAIS:   {orig_corretos}/{len(originais)} ({100*orig_corretos/len(originais):.1f}%)")
        # Detalhes de erros em originais
        erros_orig = [r for r in originais if not r["correct"] and not r["error"]]
        if erros_orig:
            print(f"      Falsos positivos (originais marcados como fraude):")
            for r in erros_orig:
                print(f"         - {r['image']}: score={r['score']}")
    
    if adulterados:
        print(f"\n   🔴 ADULTERADOS: {adult_corretos}/{len(adulterados)} ({100*adult_corretos/len(adulterados):.1f}%)")
        # Detalhes de erros em adulterados
        erros_adult = [r for r in adulterados if not r["correct"] and not r["error"]]
        if erros_adult:
            print(f"      Falsos negativos (fraudes não detectadas):")
            for r in erros_adult:
                print(f"         - {r['image']}: score={r['score']}")
    
    if erros_analise > 0:
        print(f"\n   ⚠️  ERROS DE ANÁLISE: {erros_analise}")
    
    # Estatísticas de score
    scores_orig = [r["score"] for r in originais if r["score"] is not None]
    scores_adult = [r["score"] for r in adulterados if r["score"] is not None]
    
    print(f"\n📉 DISTRIBUIÇÃO DE SCORES:")
    if scores_orig:
        print(f"   Originais:   min={min(scores_orig):3d}  média={sum(scores_orig)/len(scores_orig):5.1f}  max={max(scores_orig):3d}")
    if scores_adult:
        print(f"   Adulterados: min={min(scores_adult):3d}  média={sum(scores_adult)/len(scores_adult):5.1f}  max={max(scores_adult):3d}")


def save_report(results: List[Dict], output_path: Path):
    """Salva relatório em arquivo."""
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("PRF HONDA INSPECTOR - RELATÓRIO DE TESTE\n")
        f.write("=" * 70 + "\n")
        f.write(f"Data: {timestamp}\n")
        f.write(f"Total de imagens: {len(results)}\n")
        
        corretos = sum(1 for r in results if r["correct"])
        f.write(f"Taxa de acerto: {100*corretos/len(results):.1f}%\n")
        f.write("\n")
        
        f.write("-" * 70 + "\n")
        f.write("DETALHES\n")
        f.write("-" * 70 + "\n")
        
        for r in results:
            status = "✓" if r["correct"] else "✗"
            error_info = f" [ERRO: {r['error']}]" if r["error"] else ""
            f.write(f"{status} {r['image']:30s} | esperado: {r['expected']:10s} | score: {r['score'] or 'N/A':>3} | {r['verdict'] or 'N/A'}{error_info}\n")
        
        f.write("\n")
        f.write("-" * 70 + "\n")
        f.write("ERROS (requerem atenção)\n")
        f.write("-" * 70 + "\n")
        
        erros = [r for r in results if not r["correct"]]
        if erros:
            for r in erros:
                f.write(f"- {r['image']}: esperado {r['expected']}, obteve score={r['score']}\n")
        else:
            f.write("Nenhum erro! 🎉\n")
    
    # Também salva JSON para processamento posterior
    json_path = output_path.with_suffix('.json')
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "results": results,
            "summary": {
                "total": len(results),
                "correct": sum(1 for r in results if r["correct"]),
                "accuracy": 100 * sum(1 for r in results if r["correct"]) / len(results) if results else 0
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Relatório salvo em: {output_path}")
    print(f"📄 JSON salvo em: {json_path}")


def main():
    """Função principal."""
    
    print_header()
    
    # Determina diretório de imagens
    if len(sys.argv) > 1:
        images_dir = Path(sys.argv[1])
    else:
        # Tenta locais comuns
        candidates = [
            Path("/mnt/project"),
            Path("./imagens"),
            Path("../imagens"),
            Path("."),
        ]
        images_dir = None
        for c in candidates:
            if c.exists() and (list(c.glob("ORIGINAL_*.jpeg")) or list(c.glob("ADULTERADOS_*.jpeg"))):
                images_dir = c
                break
        
        if images_dir is None:
            print("❌ Diretório de imagens não encontrado!")
            print("   Uso: python test_manual.py /caminho/para/imagens")
            sys.exit(1)
    
    print(f"\n📁 Diretório de imagens: {images_dir.absolute()}")
    
    # Encontra imagens
    originais, adulterados = find_images(images_dir)
    
    print(f"   Originais encontrados: {len(originais)}")
    print(f"   Adulterados encontrados: {len(adulterados)}")
    
    if not originais and not adulterados:
        print("\n❌ Nenhuma imagem encontrada!")
        print("   Certifique-se de que os arquivos seguem o padrão:")
        print("   - ORIGINAL_1.jpeg, ORIGINAL_2.jpeg, ...")
        print("   - ADULTERADOS_1.jpeg, ADULTERADOS_2.jpeg, ...")
        sys.exit(1)
    
    # Verifica conexão com API
    print(f"\n🔌 Conectando à API: {API_URL}")
    
    with httpx.Client() as client:
        connected, status = get_api_status(client)
        
        if not connected:
            print(f"❌ Falha na conexão: {status}")
            print(f"   Certifique-se que o servidor está rodando:")
            print(f"   uvicorn app.main:app --host 0.0.0.0 --port 8000")
            sys.exit(1)
        
        print(f"✅ {status}")
        
        results = []
        
        # Testa ORIGINAIS
        if originais:
            print("\n" + "=" * 70)
            print("📂 TESTANDO IMAGENS ORIGINAIS")
            print("   (Esperado: score < 50)")
            print("=" * 70)
            
            for img_path in originais:
                result = test_single_image(
                    client, img_path, "ORIGINAL", DEFAULT_YEAR_ORIGINAL
                )
                results.append(result)
        
        # Testa ADULTERADOS
        if adulterados:
            print("\n" + "=" * 70)
            print("📂 TESTANDO IMAGENS ADULTERADAS")
            print("   (Esperado: score >= 50)")
            print("=" * 70)
            
            for img_path in adulterados:
                result = test_single_image(
                    client, img_path, "ADULTERADO", DEFAULT_YEAR_ADULTERADO
                )
                results.append(result)
    
    # Imprime resumo
    print_summary(results)
    
    # Salva relatório
    report_name = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    save_report(results, Path(report_name))
    
    # Retorna código de saída baseado na taxa de acerto
    corretos = sum(1 for r in results if r["correct"])
    taxa = corretos / len(results) if results else 0
    
    if taxa >= 0.9:
        print("\n🎉 Excelente! Taxa de acerto >= 90%")
        sys.exit(0)
    elif taxa >= 0.7:
        print("\n⚠️ Bom, mas pode melhorar. Taxa de acerto >= 70%")
        sys.exit(0)
    else:
        print("\n❌ Taxa de acerto abaixo de 70% - revisar modelo")
        sys.exit(1)


if __name__ == "__main__":
    main()
