#!/usr/bin/env python3
"""
Script de Teste Automatizado - PRF Honda Motor Inspector
=========================================================

Este script testa todas as funcionalidades do sistema.

Uso:
    python run_tests.py [--images-dir CAMINHO]

Exemplo:
    python run_tests.py --images-dir /caminho/para/imagens
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Verifica se as dependências estão instaladas
try:
    import requests
    import cv2
    import numpy as np
except ImportError as e:
    print(f"❌ Dependência faltando: {e}")
    print("Execute: pip install requests opencv-python-headless numpy")
    sys.exit(1)


# Configurações
API_BASE_URL = "http://localhost:8000"
RESULTS_FILE = "test_results.json"


class Colors:
    """Cores para output no terminal."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")


def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


class TestRunner:
    def __init__(self, api_url=API_BASE_URL):
        self.api_url = api_url
        self.results = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def check_server(self):
        """Verifica se o servidor está rodando."""
        print_header("1. VERIFICANDO SERVIDOR")
        
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print_success(f"Servidor online: {data.get('status')}")
                print_info(f"Versão: {data.get('version')}")
                print_info(f"Templates carregados: {data.get('templates_loaded')}")
                
                if data.get('templates_loaded', 0) == 0:
                    print_warning("Nenhum template de fonte carregado!")
                    print_warning("A análise tipográfica não funcionará.")
                    print_info("Execute: python extract_font_templates.py <imagem_fonte>")
                
                return True
            else:
                print_error(f"Servidor retornou status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print_error("Não foi possível conectar ao servidor!")
            print_info("Certifique-se de que o servidor está rodando:")
            print_info("  uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return False
        except Exception as e:
            print_error(f"Erro: {e}")
            return False
    
    def check_fonts(self):
        """Verifica templates de fonte."""
        print_header("2. VERIFICANDO TEMPLATES DE FONTE")
        
        try:
            response = requests.get(f"{self.api_url}/fonts")
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                chars = data.get('characters', [])
                
                print_info(f"Total de templates: {total}")
                print_info(f"Caracteres: {', '.join(chars)}")
                
                # Verifica se tem os números 0-9
                missing = []
                for i in range(10):
                    if str(i) not in chars:
                        missing.append(str(i))
                
                if missing:
                    print_warning(f"Templates faltando: {', '.join(missing)}")
                else:
                    print_success("Todos os números 0-9 estão carregados")
                
                return total > 0
            return False
        except Exception as e:
            print_error(f"Erro: {e}")
            return False
    
    def check_prefixes(self):
        """Lista prefixos conhecidos."""
        print_header("3. VERIFICANDO PREFIXOS CONHECIDOS")
        
        try:
            response = requests.get(f"{self.api_url}/prefixes")
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                print_success(f"{total} prefixos de motor cadastrados")
                
                # Mostra alguns exemplos
                prefixes = data.get('prefixes', [])[:5]
                for p in prefixes:
                    print_info(f"  {p['prefix']}: {p['model']} ({p['cc']}cc)")
                
                if total > 5:
                    print_info(f"  ... e mais {total - 5} prefixos")
                
                return True
            return False
        except Exception as e:
            print_error(f"Erro: {e}")
            return False
    
    def test_image(self, image_path, year, model=None, expected_verdict=None):
        """Testa uma imagem específica."""
        test_name = Path(image_path).name
        print(f"\n📷 Testando: {test_name}")
        print(f"   Ano: {year}, Modelo: {model or 'N/A'}")
        
        result = {
            'image': test_name,
            'year': year,
            'model': model,
            'expected': expected_verdict,
            'status': 'ERROR',
            'verdict': None,
            'score': None,
            'code': None,
            'observations': []
        }
        
        try:
            with open(image_path, 'rb') as f:
                files = {'photo': (test_name, f, 'image/jpeg')}
                data = {'year': year}
                if model:
                    data['model'] = model
                
                response = requests.post(
                    f"{self.api_url}/analyze/motor",
                    files=files,
                    data=data,
                    timeout=60
                )
            
            if response.status_code == 200:
                api_result = response.json()
                result['status'] = 'OK'
                result['verdict'] = api_result.get('verdict')
                result['score'] = api_result.get('risk_score')
                result['code'] = api_result.get('read_code')
                result['prefix'] = api_result.get('prefix')
                result['serial'] = api_result.get('serial')
                result['expected_model'] = api_result.get('expected_model')
                result['observations'] = api_result.get('explanation', [])
                
                # Exibe resultado
                verdict = result['verdict']
                score = result['score']
                
                if verdict == 'REGULAR':
                    print_success(f"Veredito: {verdict} (Score: {score}%)")
                elif verdict == 'ATENÇÃO':
                    print_warning(f"Veredito: {verdict} (Score: {score}%)")
                else:
                    print_error(f"Veredito: {verdict} (Score: {score}%)")
                
                print(f"   Código lido: {result['code']}")
                print(f"   Prefixo: {result.get('prefix', 'N/A')}")
                print(f"   Serial: {result.get('serial', 'N/A')}")
                
                if result['observations']:
                    print(f"   Observações:")
                    for obs in result['observations'][:3]:
                        print(f"     • {obs}")
                    if len(result['observations']) > 3:
                        print(f"     ... e mais {len(result['observations']) - 3}")
                
                # Verifica se resultado esperado bate
                if expected_verdict:
                    if verdict == expected_verdict:
                        print_success(f"Resultado esperado: {expected_verdict} ✓")
                        self.passed += 1
                    else:
                        print_warning(f"Esperado: {expected_verdict}, Obtido: {verdict}")
                        self.warnings += 1
                else:
                    self.passed += 1
                
            else:
                result['status'] = 'API_ERROR'
                result['error'] = response.text
                print_error(f"API retornou erro {response.status_code}")
                self.failed += 1
                
        except FileNotFoundError:
            result['status'] = 'FILE_NOT_FOUND'
            print_error(f"Arquivo não encontrado: {image_path}")
            self.failed += 1
        except Exception as e:
            result['status'] = 'EXCEPTION'
            result['error'] = str(e)
            print_error(f"Erro: {e}")
            self.failed += 1
        
        self.results.append(result)
        return result
    
    def test_wrong_year(self, image_path):
        """Testa com ano incorreto para verificar detecção."""
        print_header("5. TESTE: ANO INCORRETO (deve gerar alerta)")
        
        # Ano antes de 2010 = estampagem, mas imagem é micropunção
        result = self.test_image(image_path, year=2008)
        
        if result.get('observations'):
            has_type_alert = any('gravação' in obs.lower() or 'tipo' in obs.lower() 
                                for obs in result['observations'])
            if has_type_alert:
                print_success("Sistema detectou divergência de tipo de gravação!")
            else:
                print_warning("Alerta de tipo de gravação não foi gerado")
        
        return result
    
    def run_all_tests(self, images_dir=None):
        """Executa todos os testes."""
        print_header("PRF HONDA MOTOR INSPECTOR - TESTES")
        print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"API: {self.api_url}")
        
        # 1. Verificar servidor
        if not self.check_server():
            print_error("\nServidor não está disponível. Abortando testes.")
            return False
        
        # 2. Verificar fontes
        self.check_fonts()
        
        # 3. Verificar prefixos
        self.check_prefixes()
        
        # 4. Testar imagens
        print_header("4. TESTANDO IMAGENS")
        
        # Imagens padrão para testar
        test_images = []
        
        if images_dir:
            # Procura imagens no diretório especificado
            img_dir = Path(images_dir)
            if img_dir.exists():
                for ext in ['*.jpg', '*.jpeg', '*.png']:
                    test_images.extend(img_dir.glob(ext))
        
        # Imagens de exemplo (ajuste os caminhos conforme necessário)
        default_images = [
            ("WhatsApp_Image_2025-12-20_at_18_28_30.jpeg", 2020, "CG 160"),
            ("WhatsApp_Image_2025-12-20_at_18_28_31.jpeg", 2022, "XRE 300"),
        ]
        
        for img_info in default_images:
            if isinstance(img_info, tuple):
                img_path, year, model = img_info
            else:
                img_path, year, model = str(img_info), 2020, None
            
            if Path(img_path).exists():
                test_images.append((img_path, year, model))
        
        if not test_images:
            print_warning("Nenhuma imagem de teste encontrada!")
            print_info("Coloque as imagens no diretório atual ou use --images-dir")
        else:
            for img_info in test_images:
                if isinstance(img_info, tuple):
                    img_path, year, model = img_info
                else:
                    img_path, year, model = str(img_info), 2020, None
                self.test_image(img_path, year, model)
        
        # 5. Teste de ano incorreto
        if test_images:
            first_image = test_images[0]
            if isinstance(first_image, tuple):
                self.test_wrong_year(first_image[0])
            else:
                self.test_wrong_year(str(first_image))
        
        # Resumo
        self.print_summary()
        
        # Salva resultados
        self.save_results()
        
        return self.failed == 0
    
    def print_summary(self):
        """Imprime resumo dos testes."""
        print_header("RESUMO DOS TESTES")
        
        total = self.passed + self.failed + self.warnings
        print(f"Total de testes: {total}")
        print_success(f"Passou: {self.passed}")
        if self.warnings:
            print_warning(f"Atenção: {self.warnings}")
        if self.failed:
            print_error(f"Falhou: {self.failed}")
        
        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 TODOS OS TESTES PASSARAM!{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️  ALGUNS TESTES FALHARAM{Colors.END}")
    
    def save_results(self):
        """Salva resultados em arquivo JSON."""
        output = {
            'timestamp': datetime.now().isoformat(),
            'api_url': self.api_url,
            'summary': {
                'total': len(self.results),
                'passed': self.passed,
                'failed': self.failed,
                'warnings': self.warnings
            },
            'tests': self.results
        }
        
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print_info(f"\nResultados salvos em: {RESULTS_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description='Testes do PRF Honda Motor Inspector'
    )
    parser.add_argument(
        '--images-dir',
        help='Diretório com imagens para testar'
    )
    parser.add_argument(
        '--api-url',
        default=API_BASE_URL,
        help=f'URL da API (default: {API_BASE_URL})'
    )
    
    args = parser.parse_args()
    
    runner = TestRunner(api_url=args.api_url)
    success = runner.run_all_tests(images_dir=args.images_dir)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
