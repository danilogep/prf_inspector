from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict


class CharacterAnalysis(BaseModel):
    """Análise detalhada de um caractere individual."""
    char: str = Field(..., description="Caractere analisado")
    position: int = Field(..., description="Posição no código (1-indexed)")
    confidence: float = Field(..., description="Confiança do OCR (0-100)")
    is_high_risk: bool = Field(default=False, description="Se é caractere de alto risco (0,1,3,4,9)")
    similarity_score: float = Field(default=0.0, description="Similaridade com template Honda")
    has_expected_gaps: bool = Field(default=True, description="Se possui os vazamentos esperados da fonte")
    dot_count: int = Field(default=0, description="Contagem de pontos (micropunção)")
    issues: List[str] = Field(default=[], description="Problemas detectados")


class GapAnalysis(BaseModel):
    """Análise dos vazamentos/gaps característicos da fonte Honda."""
    char: str
    expected_gaps: List[str] = Field(default=[], description="Gaps esperados na fonte Honda")
    gaps_detected: bool = Field(default=True, description="Se os gaps foram detectados corretamente")
    gap_score: float = Field(default=100.0, description="Score de conformidade dos gaps (0-100)")
    notes: List[str] = Field(default=[])


class ForensicReport(BaseModel):
    """Relatório de análise forense do motor."""
    status: str = Field(..., description="OK, ATENÇÃO ou SUSPEITO")
    detected_type: str = Field(..., description="MICROPOINT ou STAMPED")
    avg_dots: float = Field(default=0.0, description="Média de pontos por caractere")
    alignment_ok: bool = Field(default=True, description="Se caracteres estão alinhados")
    characters: List[CharacterAnalysis] = Field(default=[])
    gap_analysis: List[GapAnalysis] = Field(default=[], description="Análise de vazamentos da fonte")
    high_risk_alerts: List[str] = Field(default=[], description="Alertas sobre caracteres de alto risco")
    outliers: List[Dict] = Field(default=[])


class EngineValidation(BaseModel):
    """Validação do formato do número de motor."""
    valid: bool = Field(..., description="Se o formato é válido")
    original: str = Field(..., description="Número original recebido")
    cleaned: str = Field(..., description="Número limpo/normalizado")
    prefix: Optional[str] = Field(None, description="Prefixo do motor (ex: MC27E)")
    serial: Optional[str] = Field(None, description="Número serial")
    model_info: Optional[tuple] = Field(None, description="(modelo, cilindrada)")
    issues: List[str] = Field(default=[])


class VisualReport(BaseModel):
    """Relatório de comparação visual com referência."""
    status: str = Field(..., description="COMPATÍVEL, DIVERGENTE ou SEM_REFERÊNCIA")
    similarity: float = Field(default=0.0, description="Percentual de similaridade")
    reference_used: Optional[str] = Field(None, description="Arquivo de referência usado")
    details: str = Field(default="")


class FinalResponse(BaseModel):
    """Resposta final da análise de motor."""
    verdict: str = Field(
        ..., 
        description="REGULAR, ATENÇÃO, SUSPEITO ou ALTA SUSPEITA DE FRAUDE"
    )
    risk_score: int = Field(
        ..., 
        ge=0, 
        le=100, 
        description="Score de risco (0-100)"
    )
    read_code: str = Field(..., description="Código lido pelo OCR")
    prefix: Optional[str] = Field(None, description="Prefixo identificado")
    serial: Optional[str] = Field(None, description="Serial identificado")
    expected_model: Optional[str] = Field(None, description="Modelo esperado pelo prefixo")
    components: Dict[str, Any] = Field(
        ..., 
        description="Detalhes de cada análise realizada"
    )
    explanation: List[str] = Field(
        ..., 
        description="Lista de observações e alertas"
    )
