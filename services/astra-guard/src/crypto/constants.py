"""
Configuración de exclusiones para la normalización canónica de OOXML.
Objetivo: Ignorar metadatos volátiles que cambian al abrir/guardar sin cambios semánticos.
"""

# Prefijos de rutas dentro del ZIP que se ignorarán en el cálculo del hash
VOLATILE_PREFIXES = {
    "docProps/",        # Metadatos de tiempo (creación, modificación, impresión), autor, versión.
    "customXml/",       # Datos inyectados por plugins o el propio ASTRA (que ya están en BD).
    "_rels/.rels"       # Relaciones raíz globales (suelen cambiar IDs arbitrariamente).
}

# Archivos específicos a ignorar si es necesario (ej: configuraciones de impresora)
VOLATILE_FILES = {
    "[Content_Types].xml" # Opcional: A veces Word reordena esto. Para integridad estricta, lo incluimos, pero ordenado.
    # Por ahora NO lo ignoramos, pero el normalizador debe manejar su contenido si cambia.
}

# Tamaño de bloque para el árbol Merkle (4MB)
MERKLE_CHUNK_SIZE = 4 * 1024 * 1024 
