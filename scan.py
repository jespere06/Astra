import os
import platform
import subprocess

# --- CONFIGURACIÓN ---
# Carpeta fija donde se guardará el resultado
CARPETA_SALIDA = "_EXPORTADO"
# Nombre del archivo final
ARCHIVO_SALIDA = "todo_el_proyecto.txt"

# Extensiones que consideramos "hechas por humanos" (Edita según tus necesidades)
EXTENSIONES_PERMITIDAS = {
    '.py', '.js', '.html', '.css', '.scss', '.json', '.xml', '.yaml', '.yml',
    '.md', '.sql', '.java', '.c', '.cpp', '.h', '.cs', '.php', 
    '.ts', '.tsx', '.jsx', '.rb', '.go', '.rs', '.sh', '.bat', ".txt"
}

# Carpetas a ignorar (archivos generados, librerías, git, etc.)
CARPETAS_IGNORADAS = {
    '.git', '.idea', '.vscode', '__pycache__', 'node_modules', 'transcriptions', 'minutes-txt',
    'venv', '.venv', 'env', 'bin', 'obj', 'build', 'dist', CARPETA_SALIDA, "dataset_final"
}

def revelar_archivo(path):
    """
    Abre el explorador de archivos y selecciona el archivo generado
    según el sistema operativo.
    """
    path = os.path.abspath(path)
    sistema = platform.system()
    
    try:
        if sistema == "Windows":
            # El comando /select permite hacer focus en el archivo
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sistema == "Darwin": # macOS
            subprocess.call(["open", "-R", path])
        else: # Linux
            # En Linux es difícil garantizar la selección, abrimos la carpeta
            subprocess.call(["xdg-open", os.path.dirname(path)])
        print(f"✅ Archivo revelado en: {path}")
    except Exception as e:
        print(f"⚠️ No se pudo abrir el explorador: {e}")

def main():
    # Obtener directorio actual donde está el script
    directorio_base = os.getcwd()
    ruta_carpeta_destino = os.path.join(directorio_base, CARPETA_SALIDA)
    ruta_archivo_final = os.path.join(ruta_carpeta_destino, ARCHIVO_SALIDA)

    # 1. Crear carpeta fija si no existe
    if not os.path.exists(ruta_carpeta_destino):
        os.makedirs(ruta_carpeta_destino)
        print(f"📁 Carpeta creada: {ruta_carpeta_destino}")

    print("⏳ Escaneando archivos y generando reporte...")

    # 2. Abrir archivo en modo 'w' (Write). Esto BORRA automáticamente el contenido anterior.
    with open(ruta_archivo_final, 'w', encoding='utf-8') as outfile:
        
        # Recorrer el árbol de directorios
        for raiz, directorios, archivos in os.walk(directorio_base):
            
            # Modificar la lista 'directorios' in-place para ignorar carpetas no deseadas
            # Esto evita que os.walk entre en .git, node_modules, etc.
            directorios[:] = [d for d in directorios if d not in CARPETAS_IGNORADAS]

            for archivo in archivos:
                nombre, extension = os.path.splitext(archivo)
                
                # Verificar si es un archivo "humano"
                if extension.lower() in EXTENSIONES_PERMITIDAS:
                    ruta_completa = os.path.join(raiz, archivo)
                    
                    # No nos auto-leemos si el script está en las extensiones permitidas
                    if ruta_completa == os.path.abspath(__file__) or ruta_completa == ruta_archivo_final:
                        continue

                    # Escribir cabecera del archivo
                    outfile.write("="*80 + "\n")
                    outfile.write(f"RUTA: {ruta_completa}\n")
                    outfile.write("="*80 + "\n")

                    # Escribir contenido
                    try:
                        with open(ruta_completa, 'r', encoding='utf-8', errors='ignore') as f:
                            contenido = f.read()
                            if not contenido.strip():
                                outfile.write("[ARCHIVO VACÍO]\n")
                            else:
                                outfile.write(contenido + "\n")
                    except Exception as e:
                        outfile.write(f"[ERROR LEYENDO ARCHIVO: {e}]\n")
                    
                    outfile.write("\n\n") # Espacio entre archivos

    print("✅ Proceso completado exitosamente.")
    
    # 3. Hacer reveal del archivo
    revelar_archivo(ruta_archivo_final)

if __name__ == "__main__":
    main()