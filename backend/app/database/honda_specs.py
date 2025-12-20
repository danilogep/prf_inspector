class HondaSpecs:
    """Regras de Negócio baseadas na NBR 6.066 e manuais Honda."""
    
    # Tabela de Anos (10º Dígito) - Conforme Figura 11 da Apostila EFV
    YEAR_CODES = {
        '9': 2009, 'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 
        'E': 2014, 'F': 2015, 'G': 2016, 'H': 2017, 'J': 2018, 
        'K': 2019, 'L': 2020, 'M': 2021, 'N': 2022, 'P': 2023, 
        'R': 2024, 'S': 2025, 'T': 2026, 'V': 2027, 'W': 2028
    }

    @staticmethod
    def get_expected_marking_type(year: int) -> str:
        # Regra heurística: Honda adotou micropunção massivamente pós-2005
        return "MICROPOINT" if year >= 2005 else "SOLID"

    @staticmethod
    def validate_wmi(vin: str) -> bool:
        # 9C2 = Honda Brasil (Manaus)
        return vin.startswith("9C2")

    @staticmethod
    def get_year_char(year: int) -> str:
        for char, y in HondaSpecs.YEAR_CODES.items():
            if y == year: return char
        return None