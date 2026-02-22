import hashlib
import json
import logging
from typing import Iterator, List, Dict, Any
from .constants import MERKLE_CHUNK_SIZE

logger = logging.getLogger(__name__)

class MerkleEngine:
    """
    Implementación de Merkle Tree usando SHA-256.
    Diseñado para procesar streams infinitos sin cargar todo en memoria.
    """

    @staticmethod
    def _hash_node(data: bytes) -> str:
        """Calcula SHA-256 de un bloque de bytes."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _chunk_stream_generator(iterator: Iterator[bytes], chunk_size: int) -> Iterator[bytes]:
        """
        Convierte un iterador de fragmentos pequeños/variables en un iterador
        de bloques de tamaño fijo (excepto el último).
        """
        buffer = bytearray()
        
        for fragment in iterator:
            buffer.extend(fragment)
            
            while len(buffer) >= chunk_size:
                yield bytes(buffer[:chunk_size])
                # Slice eficiente (memoryview sería mejor para ultra-high performance, 
                # pero bytearray es suficiente aquí)
                del buffer[:chunk_size]
        
        # Emitir remanente
        if buffer:
            yield bytes(buffer)

    def calculate_root(self, stream_iterator: Iterator[bytes]) -> Dict[str, Any]:
        """
        Construye el árbol Merkle desde un stream.
        Retorna el Root Hash y el Manifiesto (lista de hojas).
        
        Args:
            stream_iterator: Generador que emite bytes del contenido normalizado.
        """
        leaves = []
        
        # 1. Generar Hojas (Leaf Nodes)
        chunk_gen = self._chunk_stream_generator(stream_iterator, MERKLE_CHUNK_SIZE)
        
        for chunk in chunk_gen:
            leaf_hash = self._hash_node(chunk)
            leaves.append(leaf_hash)
            
        if not leaves:
            # Caso archivo vacío o sin contenido semántico
            empty_hash = self._hash_node(b"")
            return {
                "root_hash": empty_hash,
                "leaves": [],
                "levels": 1
            }

        # 2. Construir Árbol hacia arriba
        current_level = leaves
        tree_structure = [leaves] # Guardamos niveles para auditoría (Merkle Path)

        while len(current_level) > 1:
            next_level = []
            
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                
                # Si hay impar, duplicamos el último nodo (Estándar Bitcoin/Git)
                if i + 1 < len(current_level):
                    right = current_level[i+1]
                else:
                    right = left
                
                # Hash del padre = Hash(Left + Right)
                # Concatenamos los strings hex para simplicidad de depuración visual,
                # o bytes para eficiencia. Usamos encoding ASCII de los hexes.
                combined = (left + right).encode('ascii')
                parent_hash = self._hash_node(combined)
                next_level.append(parent_hash)
            
            current_level = next_level
            tree_structure.append(current_level)

        root_hash = current_level[0]
        
        logger.info(f"Merkle Tree construido. Hojas: {len(leaves)}, Root: {root_hash[:10]}...")

        return {
            "root_hash": root_hash,
            "leaf_count": len(leaves),
            "tree_structure": tree_structure # En producción esto iría a S3/DB si es gigante
        }
