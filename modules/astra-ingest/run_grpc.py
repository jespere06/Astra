
import sys
import os

# Asegurar que el directorio raíz está en el path
sys.path.append(os.getcwd())

from src.api.grpc.server import serve

if __name__ == "__main__":
    serve()