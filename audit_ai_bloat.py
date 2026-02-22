import os
import re

# Paquetes que NO deberían estar en un servicio ligero (Orquestador/Dashboard/Guard)
HEAVY_PACKAGES = {
    'torch': 'PyTorch (Motor de tensores, >500MB)',
    'tensorflow': 'TensorFlow (Motor de IA, >400MB)',
    'transformers': 'HuggingFace Transformers (Librería de modelos pesada)',
    'faster-whisper': 'Motor de transcripción local',
    'ctranslate2': 'Motor de inferencia para C++',
    'spacy': 'Librería de NLP (pesada si baja modelos)',
    'scipy': 'Librería científica (pesada de compilar)',
    'nvidia': 'Drivers o herramientas de GPU',
    'bitsandbytes': 'Cuantización de GPU (Solo sirve con NVIDIA)',
    'unsloth': 'Librería de entrenamiento local',
    'xformers': 'Optimizaciones de GPU NVIDIA',
    'sentence-transformers': 'Modelos de embeddings locales',
}

def analyze_requirements(file_path):
    bloat_found = []
    if not os.path.exists(file_path):
        return bloat_found
    
    with open(file_path, 'r') as f:
        content = f.readlines()
        for line in content:
            line = line.strip().lower()
            for pkg, desc in HEAVY_PACKAGES.items():
                if pkg in line and not line.startswith('#'):
                    bloat_found.append((line, desc))
    return bloat_found

def analyze_dockerfile(file_path):
    apt_bloat = []
    if not os.path.exists(file_path):
        return apt_bloat
    
    with open(file_path, 'r') as f:
        content = f.read()
        # Buscar instalaciones de sistema pesadas (X11, Mesa, etc)
        # Veo en tus logs libxcb, libfreetype, etc.
        patterns = ['libgl1', 'mesa', 'libx11', 'build-essential', 'g++', 'gcc']
        for p in patterns:
            if p in content.lower():
                apt_bloat.append(p)
    return apt_bloat

def run_audit():
    print("🕵️  Iniciando auditoría de 'Grasa Innecesaria' en ASTRA...")
    print("="*60)
    
    for root, dirs, files in os.walk('.'):
        if 'venv' in root or 'node_modules' in root:
            continue
            
        for file in files:
            if file == 'requirements.txt':
                path = os.path.join(root, file)
                bloat = analyze_requirements(path)
                if bloat:
                    print(f"⚠️  BLOAT detectado en {path}:")
                    for pkg, desc in bloat:
                        print(f"   - {pkg:25} | {desc}")
                    print("-" * 40)
            
            if file == 'Dockerfile':
                path = os.path.join(root, file)
                bloat = analyze_dockerfile(path)
                if bloat:
                    print(f"📦 APT Bloat detectado en {path}:")
                    print(f"   Instalas herramientas de compilación/gráficas: {bloat}")
                    print("-" * 40)

if __name__ == "__main__":
    run_audit()