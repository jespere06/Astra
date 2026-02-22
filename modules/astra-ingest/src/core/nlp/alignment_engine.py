import difflib
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class Token:
    text: str
    is_variable: bool
    variable_name: str = ""

@dataclass
class TemplateModel:
    tokens: List[Token]
    raw_pattern: str  # Representación string ej: "Se aprueba {VAR_1}"

class SequenceAligner:
    """
    Motor algorítmico para inducir plantillas a partir de variaciones de texto.
    Utiliza heurísticas de distancia de edición para detectar slots dinámicos.
    """

    def __init__(self, threshold: float = 0.3):
        # Umbral: Si un token varía en más del 30% de las muestras, es variable.
        self.threshold = threshold

    def _tokenize(self, text: str) -> List[str]:
        """Tokenización simple preservando puntuación básica."""
        # En producción usar spacy, para MVP split es suficiente pero mejorable
        return text.split()

    def induce_template(self, texts: List[str]) -> TemplateModel:
        """
        Recibe una lista de textos (del mismo cluster) y genera un modelo de plantilla.
        """
        if not texts:
            raise ValueError("La lista de textos no puede estar vacía.")

        if len(texts) == 1:
            # Si solo hay una muestra, todo es estático
            tokens = [Token(t, False) for t in self._tokenize(texts[0])]
            return TemplateModel(tokens, texts[0])

        # 1. Usar la primera cadena como "pivote" o referencia
        reference_tokens = self._tokenize(texts[0])
        n_tokens = len(reference_tokens)
        
        # Mapa de varianza: [False, False, True, False] (True = es variable)
        variance_map = [False] * n_tokens
        
        # 2. Comparar cada texto contra el pivote usando SequenceMatcher
        # Esto es O(N*M) donde N=docs y M=tokens. Aceptable para clusters < 100 items.
        for text in texts[1:]:
            current_tokens = self._tokenize(text)
            matcher = difflib.SequenceMatcher(None, reference_tokens, current_tokens)
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'replace':
                    # Si hubo reemplazo en el rango [i1:i2], marcar como variable
                    for k in range(i1, i2):
                        if k < n_tokens:
                            variance_map[k] = True
                elif tag == 'delete':
                    # Si se borró algo que estaba en la referencia, la referencia en ese punto es inestable
                    for k in range(i1, i2):
                        if k < n_tokens:
                            variance_map[k] = True
                elif tag == 'insert':
                    # Inserciones complejas rompen la alineación posicional simple del pivote.
                    # Estrategia MVP: Ignorar inserciones puras que no reemplazan, 
                    # o marcar el token previo/posterior como variable expansiva.
                    # Para este nivel, asumimos estructura rígida.
                    pass

        # 3. Construir el modelo final
        final_tokens = []
        var_counter = 1
        
        for i, token_text in enumerate(reference_tokens):
            if variance_map[i]:
                # Fusión de variables contiguas
                # Si el anterior ya era variable, no creamos uno nuevo, asumimos slot continuo
                if final_tokens and final_tokens[-1].is_variable:
                    continue
                
                final_tokens.append(Token(
                    text="{VAR}", 
                    is_variable=True, 
                    variable_name=f"VAR_{var_counter}"
                ))
                var_counter += 1
            else:
                final_tokens.append(Token(text=token_text, is_variable=False))

        # Reconstruir patrón string para debugging/hashing
        raw_pattern = " ".join([t.text if not t.is_variable else f"{{{t.variable_name}}}" for t in final_tokens])

        return TemplateModel(tokens=final_tokens, raw_pattern=raw_pattern)