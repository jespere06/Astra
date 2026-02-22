class AstraIngestError(Exception):
    """Excepción base para el módulo de ingesta."""
    pass

class DocxFormatError(AstraIngestError):
    """El archivo no es un ZIP válido o está corrupto."""
    pass

class OOXMLError(AstraIngestError):
    """El archivo es un ZIP pero no cumple la estructura interna OOXML esperada."""
    pass