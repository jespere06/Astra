from jose import jwt, JWTError
from src.config import settings
from typing import Dict, Any

class SecurityUtils:
    @staticmethod
    def validate_token(token: str) -> Dict[str, Any]:
        """
        Valida la firma y expiración del JWT.
        Retorna el payload decodificado si es válido.
        Lanza JWTError si falla.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            raise e
