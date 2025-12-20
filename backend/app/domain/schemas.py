from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class SuspiciousChar(BaseModel):
    char: str
    position: int
    reason: str

class ConformityReport(BaseModel):
    status: str
    wmi_valid: bool
    year_valid: bool
    details: List[str]

class ForensicReport(BaseModel):
    status: str
    detected_type: str
    avg_dots: float
    outliers: List[SuspiciousChar]

class VisualReport(BaseModel):
    status: str
    wmi_similarity: float
    style_match: str
    details: str

class FinalResponse(BaseModel):
    verdict: str
    risk_score: int
    read_code: str
    components: Dict[str, Any]
    explanation: List[str]