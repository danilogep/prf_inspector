from app.database.honda_specs import HondaSpecs

class ConformityService:
    def analyze(self, vin: str, year: int) -> dict:
        issues = []
        
        # 1. WMI (3 primeiros dígitos)
        wmi_ok = HondaSpecs.validate_wmi(vin)
        if not wmi_ok: 
            issues.append(f"WMI '{vin[:3]}' inválido para Honda Brasil (Esperado: 9C2).")

        # 2. Ano (10º Dígito)
        year_ok = True
        if len(vin) == 17:
            char_year = vin[9]
            expected = HondaSpecs.get_year_char(year)
            
            # Verifica correlação input vs chassi
            if expected and char_year != expected:
                year_ok = False
                issues.append(f"Ano divergente: Chassi '{char_year}' vs Input '{year}'")
            
            # Verifica caracteres proibidos na posição 10
            if char_year in ['U', 'Z', '0']:
                issues.append("Caractere proibido na posição do ano (NBR 6.066).")

        return {
            "status": "FALHA" if issues else "OK",
            "wmi_valid": wmi_ok,
            "year_valid": year_ok,
            "details": issues
        }