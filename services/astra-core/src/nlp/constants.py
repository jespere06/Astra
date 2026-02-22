# Diccionario de contracciones coloquiales (Español LATAM/Colombia)
# Formato: "coloquial": "formal"
CONTRACTIONS = {
    "pa": "para",
    "pal": "para el",
    "na": "nada",
    "to": "todo",
    "ta": "está",
    "tas": "estás",
    "toy": "estoy",
    "tons": "entonces",
    "noma": "nada más",
    "nomás": "nada más",
    "porfa": "por favor",
    "compa": "compañero",
    "dr": "doctor",
    "dra": "doctora",
    "sr": "señor",
    "sra": "señora",
    "pte": "presidente",
    "sec": "secretario"
}

# Lista de muletillas y rellenos del habla para eliminar
# Se usarán con word boundaries (\b) para evitar falsos positivos
FILLERS = [
    "eh",
    "ehm",
    "em",
    "umm",
    "mmm",
    "uh",
    "uuh",
    "este...",
    "bueno pues",
    "o sea",
    "digamos",
    "mira",
    "viste",
    "ajá",
    "mjm"
]

# Caracteres a eliminar explícitamente (ruido ASR)
BAD_CHARS = [
    "\x00", # Null byte
    "\r",   # Carriage return (dejamos \n si es necesario, pero cleaner normaliza a espacio)
    "\t",   # Tab
    "\ufeff" # BOM
]
