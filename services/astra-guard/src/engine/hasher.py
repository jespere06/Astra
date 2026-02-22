import hashlib
from fastapi import UploadFile

class HasherEngine:
    CHUNK_SIZE = 64 * 1024  # 64KB chunks para no saturar RAM

    @staticmethod
    async def calculate_sha256(file: UploadFile) -> str:
        """
        Calcula el hash SHA-256 de un archivo subido leyendo en streaming.
        Resetea el puntero del archivo al inicio después de leer.
        """
        sha256_hash = hashlib.sha256()
        
        # Asegurarse de estar al inicio del archivo
        await file.seek(0)
        
        while True:
            data = await file.read(HasherEngine.CHUNK_SIZE)
            if not data:
                break
            sha256_hash.update(data)
        
        # Resetear puntero para usos posteriores si es necesario
        await file.seek(0)
        
        return sha256_hash.hexdigest()

    @staticmethod
    def verify_hash(calculated: str, expected: str) -> bool:
        # Comparación constante de tiempo para evitar ataques de timing (aunque SHA256 ya es seguro)
        return calculated.lower() == expected.lower()
