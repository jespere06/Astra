import os
import fnmatch
from pathlib import Path

def load_dockerignore():
    ignore_rules = []
    if os.path.exists('.dockerignore'):
        with open('.dockerignore', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_rules.append(line)
    # Siempre ignorar el propio script de análisis
    ignore_rules.append('analyze_context.py')
    return ignore_rules

def is_ignored(path, rules):
    for rule in rules:
        # Manejar reglas que empiezan con **/ (común en tu .dockerignore)
        if rule.startswith('**/'):
            pattern = rule[3:]
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        # Reglas estándar
        if fnmatch.fnmatch(path, rule) or fnmatch.fnmatch(os.path.basename(path), rule):
            return True
        # Manejar carpetas (si la regla es 'venv', debe ignorar 'venv/archivo.py')
        if any(fnmatch.fnmatch(part, rule.rstrip('/')) for part in path.split(os.sep)):
            return True
    return False

def analyze():
    rules = load_dockerignore()
    included_files = []
    total_size = 0
    ignored_count = 0

    print(f"🔍 Analizando contexto de construcción en: {os.getcwd()}")
    print(f"📋 Reglas cargadas: {len(rules)}")
    print("-" * 50)

    for root, dirs, files in os.walk('.'):
        # Filtrar directorios para no entrar en carpetas ignoradas (ahorra tiempo)
        relative_root = os.path.relpath(root, '.')
        if relative_root != '.':
            if is_ignored(relative_root, rules):
                ignored_count += len(files) + len(dirs)
                dirs[:] = [] # No entrar en esta carpeta
                continue

        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, '.')
            
            if is_ignored(relative_path, rules):
                ignored_count += 1
                continue
            
            file_size = os.path.getsize(full_path)
            included_files.append((relative_path, file_size))
            total_size += file_size

    # Ordenar por tamaño para ver los "culpables"
    included_files.sort(key=lambda x: x[1], reverse=True)

    print(f"✅ Archivos que SÍ se envían a Docker (Top 15 más pesados):")
    for path, size in included_files[:15]:
        print(f"  {size / 1024 / 1024:7.2f} MB  | {path}")

    print("-" * 50)
    print(f"📊 RESUMEN:")
    print(f"  Total archivos incluidos: {len(included_files)}")
    print(f"  Total archivos ignorados: {ignored_count}")
    print(f"  PESO TOTAL DEL CONTEXTO: {total_size / 1024 / 1024:.2f} MB")
    print("-" * 50)

    if total_size > 100 * 1024 * 1024:
        print("⚠️ ALERTA: Tu contexto pesa más de 100MB. Esto ralentiza el build.")
        print("Revisa si olvidaste incluir alguna carpeta pesada en el .dockerignore")

if __name__ == "__main__":
    analyze()