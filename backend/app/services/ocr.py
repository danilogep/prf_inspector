import easyocr
from app.core.logger import logger

class OCREngine:
    def __init__(self):
        logger.info("Carregando modelo de OCR na memória...")
        # gpu=False para rodar no seu PC sem CUDA configurado. Mude para True se tiver NVIDIA.
        self.reader = easyocr.Reader(['en'], gpu=False) 

    def process_image(self, image_bytes: bytes):
        try:
            # EasyOCR lê direto de bytes
            result = self.reader.readtext(image_bytes, detail=1)
            
            # Concatena texto e filtra confiança > 30%
            full_text = "".join([r[1] for r in result if r[2] > 0.3]).replace(" ", "").upper()
            return full_text, result
        except Exception as e:
            logger.error(f"Erro OCR: {str(e)}")
            raise e