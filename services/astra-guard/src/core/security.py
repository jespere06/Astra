from jose import jwt, JWTError
from fastapi import HTTPException, status
from src.config import settings

class SecurityUtils:
    @staticmethod
    def validate_token(token: str) -> dict:
        """
        Valida la firma y estructura del JWT.
        En un entorno real, validaría contra JWKS (Auth0/Cognito).
        Aquí usamos una llave secreta compartida para el MVP.
        """
        try:
            # Algoritmo HS256 para MVP (Simétrico)
            # En producción usar RS256 con llave pública
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.JWT_ALGORITHM]
            )
            
            tenant_id = payload.get("tenant_id")
            if not tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido: falta 'tenant_id'"
                )
                
            return payload
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas o expiradas"
            )
