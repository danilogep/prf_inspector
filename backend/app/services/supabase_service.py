"""
Supabase Service - Banco de dados e Storage de imagens
======================================================

Este serviço gerencia:
1. Banco de dados PostgreSQL (via Supabase)
   - Tabela de análises realizadas
   - Tabela de motores de referência
   - Tabela de casos de adulteração confirmados

2. Storage de imagens
   - Imagens de referência por modelo/ano
   - Imagens de análises realizadas
   - Templates de fonte Honda

Configuração necessária no .env:
    SUPABASE_URL=https://xxxxx.supabase.co
    SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
"""

import httpx
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.core.logger import logger
from app.core.config import settings


class SupabaseService:
    """
    Cliente para Supabase (PostgreSQL + Storage).
    
    Tabelas esperadas:
    - motor_analyses: Histórico de análises
    - motor_references: Imagens de referência
    - fraud_cases: Casos de adulteração confirmados
    """
    
    def __init__(self):
        self.url = getattr(settings, 'SUPABASE_URL', None)
        self.key = getattr(settings, 'SUPABASE_KEY', None)
        self.enabled = bool(self.url and self.key)
        
        if self.enabled:
            self.headers = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json"
            }
            logger.info("Supabase Service inicializado")
        else:
            logger.warning("Supabase Service desabilitado - credenciais não configuradas")
    
    # ============== BANCO DE DADOS ==============
    
    async def save_analysis(
        self,
        image_hash: str,
        read_code: str,
        prefix: Optional[str],
        serial: Optional[str],
        year: int,
        model: Optional[str],
        verdict: str,
        risk_score: int,
        ocr_result: str,
        ai_result: Optional[Dict] = None,
        forensic_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Salva uma análise no banco de dados.
        """
        if not self.enabled:
            return None
        
        data = {
            "image_hash": image_hash,
            "read_code": read_code,
            "prefix": prefix,
            "serial": serial,
            "year": year,
            "model": model,
            "verdict": verdict,
            "risk_score": risk_score,
            "ocr_result": ocr_result,
            "ai_result": json.dumps(ai_result) if ai_result else None,
            "forensic_data": json.dumps(forensic_data) if forensic_data else None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/motor_analyses",
                    headers=self.headers,
                    json=data
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"Análise salva: {read_code}")
                return data
            else:
                logger.error(f"Erro ao salvar análise: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro no Supabase: {e}")
            return None
    
    async def get_reference_by_prefix(
        self, 
        prefix: str, 
        year: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Busca imagem de referência por prefixo e ano.
        """
        if not self.enabled:
            return None
        
        try:
            query = f"{self.url}/rest/v1/motor_references?prefix=eq.{prefix}"
            if year:
                query += f"&year=eq.{year}"
            query += "&limit=1"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(query, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    return data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar referência: {e}")
            return None
    
    async def check_fraud_database(self, serial: str) -> Optional[Dict]:
        """
        Verifica se o serial está no banco de fraudes conhecidas.
        """
        if not self.enabled or not serial:
            return None
        
        try:
            query = f"{self.url}/rest/v1/fraud_cases?serial=eq.{serial}&limit=1"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(query, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    logger.warning(f"⚠️ Serial {serial} encontrado no banco de fraudes!")
                    return data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao verificar fraudes: {e}")
            return None
    
    async def add_fraud_case(
        self,
        serial: str,
        prefix: str,
        description: str,
        reported_by: str,
        image_url: Optional[str] = None
    ) -> bool:
        """
        Adiciona um caso de fraude ao banco.
        """
        if not self.enabled:
            return False
        
        data = {
            "serial": serial,
            "prefix": prefix,
            "description": description,
            "reported_by": reported_by,
            "image_url": image_url,
            "confirmed": False,  # Precisa confirmação
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/fraud_cases",
                    headers=self.headers,
                    json=data
                )
            
            return response.status_code in [200, 201]
            
        except Exception as e:
            logger.error(f"Erro ao adicionar fraude: {e}")
            return False
    
    async def get_analysis_stats(self) -> Dict:
        """
        Retorna estatísticas das análises.
        """
        if not self.enabled:
            return {"enabled": False}
        
        try:
            # Total de análises
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/motor_analyses?select=count",
                    headers={**self.headers, "Prefer": "count=exact"}
                )
            
            total = int(response.headers.get("content-range", "0-0/0").split("/")[1])
            
            # Por veredito
            verdicts = {}
            for verdict in ["REGULAR", "VERIFICAR", "ATENÇÃO", "SUSPEITO", "ALTA SUSPEITA DE FRAUDE"]:
                response = await client.get(
                    f"{self.url}/rest/v1/motor_analyses?verdict=eq.{verdict}&select=count",
                    headers={**self.headers, "Prefer": "count=exact"}
                )
                count = int(response.headers.get("content-range", "0-0/0").split("/")[1])
                verdicts[verdict] = count
            
            return {
                "enabled": True,
                "total_analyses": total,
                "by_verdict": verdicts
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {"enabled": True, "error": str(e)}
    
    # ============== STORAGE ==============
    
    async def upload_image(
        self,
        bucket: str,
        path: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg"
    ) -> Optional[str]:
        """
        Faz upload de imagem para o Storage.
        
        Args:
            bucket: Nome do bucket (ex: "references", "analyses")
            path: Caminho no bucket (ex: "2020/MD09E1/ref001.jpg")
            image_bytes: Conteúdo da imagem
            content_type: Tipo MIME
            
        Returns:
            URL pública da imagem ou None
        """
        if not self.enabled:
            return None
        
        try:
            upload_headers = {
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": content_type
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/storage/v1/object/{bucket}/{path}",
                    headers=upload_headers,
                    content=image_bytes
                )
            
            if response.status_code in [200, 201]:
                # Retorna URL pública
                public_url = f"{self.url}/storage/v1/object/public/{bucket}/{path}"
                logger.info(f"Imagem uploaded: {public_url}")
                return public_url
            else:
                logger.error(f"Erro no upload: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro no upload: {e}")
            return None
    
    async def download_image(self, bucket: str, path: str) -> Optional[bytes]:
        """
        Baixa imagem do Storage.
        """
        if not self.enabled:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/storage/v1/object/public/{bucket}/{path}"
                )
            
            if response.status_code == 200:
                return response.content
            return None
            
        except Exception as e:
            logger.error(f"Erro no download: {e}")
            return None
    
    async def list_references(self, prefix: Optional[str] = None) -> List[Dict]:
        """
        Lista imagens de referência disponíveis.
        """
        if not self.enabled:
            return []
        
        try:
            query = f"{self.url}/rest/v1/motor_references?select=*"
            if prefix:
                query += f"&prefix=eq.{prefix}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(query, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            return []
            
        except Exception as e:
            logger.error(f"Erro ao listar referências: {e}")
            return []


# Singleton
_supabase_service: Optional[SupabaseService] = None


def get_supabase_service() -> SupabaseService:
    """Retorna instância singleton do serviço."""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service


# ============== SQL PARA CRIAR TABELAS ==============
"""
Execute este SQL no Supabase Dashboard para criar as tabelas:

-- Tabela de análises
CREATE TABLE motor_analyses (
    id BIGSERIAL PRIMARY KEY,
    image_hash TEXT NOT NULL,
    read_code TEXT NOT NULL,
    prefix TEXT,
    serial TEXT,
    year INTEGER,
    model TEXT,
    verdict TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    ocr_result TEXT,
    ai_result JSONB,
    forensic_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_analyses_prefix ON motor_analyses(prefix);
CREATE INDEX idx_analyses_serial ON motor_analyses(serial);
CREATE INDEX idx_analyses_verdict ON motor_analyses(verdict);

-- Tabela de referências
CREATE TABLE motor_references (
    id BIGSERIAL PRIMARY KEY,
    prefix TEXT NOT NULL,
    year INTEGER,
    model TEXT,
    image_url TEXT NOT NULL,
    description TEXT,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_references_prefix ON motor_references(prefix);

-- Tabela de fraudes conhecidas
CREATE TABLE fraud_cases (
    id BIGSERIAL PRIMARY KEY,
    serial TEXT NOT NULL UNIQUE,
    prefix TEXT,
    description TEXT,
    reported_by TEXT,
    image_url TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fraud_serial ON fraud_cases(serial);

-- Habilitar RLS (Row Level Security)
ALTER TABLE motor_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE motor_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_cases ENABLE ROW LEVEL SECURITY;

-- Políticas de acesso (ajuste conforme necessidade)
CREATE POLICY "Allow all for authenticated" ON motor_analyses FOR ALL USING (true);
CREATE POLICY "Allow all for authenticated" ON motor_references FOR ALL USING (true);
CREATE POLICY "Allow all for authenticated" ON fraud_cases FOR ALL USING (true);
"""
