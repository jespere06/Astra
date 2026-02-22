import random
import re
import string
from typing import List

class NoiseInjector:
    """
    Injects ASR-like noise into clean text to simulate transcription errors.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.fillers = ['eh', 'este', 'mmm', 'pues', 'o sea', 'bueno', 'digamos']
        
        # Simple Number to Word Mapping (0-9)
        # For full implementation, we'd need num2words library, but we can start with basic digits.
        self.num_map = {
            '0': 'cero', '1': 'uno', '2': 'dos', '3': 'tres', '4': 'cuatro',
            '5': 'cinco', '6': 'seis', '7': 'siete', '8': 'ocho', '9': 'nueve'
        }

    def corrupt(self, text: str) -> str:
        """
        Applies a random chain of corruptions.
        """
        # Pipeline: Expand -> Strip -> Stutter -> Fillers
        dirty = self.expand_numbers(text)
        dirty = self.strip_formatting(dirty)
        
        # Randomly apply more intense corruptions
        if self.rng.random() < 0.3:
            dirty = self.simulate_stutter(dirty)
            
        dirty = self.inject_fillers(dirty, rate=0.1)
        
        return dirty

    def strip_formatting(self, text: str) -> str:
        """
        Lowercases text and removes punctuation.
        """
        text = text.lower()
        # Remove punctuation but keep spaces
        # Using translation table is faster
        translator = str.maketrans('', '', string.punctuation)
        return text.translate(translator)

    def inject_fillers(self, text: str, rate: float = 0.1) -> str:
        """
        Injects filler words at random positions.
        """
        words = text.split()
        if not words:
            return text
            
        new_words = []
        for word in words:
            new_words.append(word)
            if self.rng.random() < rate:
                new_words.append(self.rng.choice(self.fillers))
                
        return " ".join(new_words)

    def simulate_stutter(self, text: str, rate: float = 0.05) -> str:
        """
        Duplicates short words or syllables.
        """
        words = text.split()
        if not words:
            return text
            
        new_words = []
        for word in words:
            # Stutter on short words (len <= 3)
            if len(word) <= 3 and self.rng.random() < rate:
                new_words.append(word)
                new_words.append(word)
            else:
                new_words.append(word)
                
        return " ".join(new_words)

    def expand_numbers(self, text: str) -> str:
        """
        Converts digits to words.
        """
        def replace(match):
            num_str = match.group(0)
            # Simple digit expansion
            expanded = []
            for digit in num_str:
                if digit in self.num_map:
                    expanded.append(self.num_map[digit])
                else:
                    expanded.append(digit)
            return " ".join(expanded)

        # Find sequence of digits
        return re.sub(r'\d+', replace, text)
