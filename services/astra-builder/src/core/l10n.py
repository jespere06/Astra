from datetime import datetime
import pytz

class Localizer:
    """
    Transforma timestamps UTC a la hora legal del Tenant.
    """
    def __init__(self, timezone_str: str):
        try:
            self.tz = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            self.tz = pytz.UTC

    def format_timestamp(self, iso_timestamp: str, format_str: str = "%d de %B de %Y, %I:%M %p") -> str:
        """
        Convierte UTC ISO string -> Texto local formateado.
        """
        if not iso_timestamp:
            return ""
        
        try:
            # Asumimos que el input viene en UTC ISO 8601
            dt_utc = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            dt_local = dt_utc.astimezone(self.tz)
            
            # TODO: Implementar locale para meses en español (setlocale no es thread-safe)
            # Por ahora, mapeo simple o uso de librerías como Babel si se requiere
            return dt_local.strftime(format_str)
        except ValueError:
            return iso_timestamp  # Fallback: retornar string original si falla
