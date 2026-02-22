import os
import re
import pandas as pd
from datetime import datetime
from googleapiclient.discovery import build
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

# ================= CONFIGURACIÓN =================
YOUTUBE_API_KEY = 'AIzaSyATYgZZfElQUzujDJ8xRkiLNnckmpkPuuE'  # ⚠️ PON TU CLAVE AQUÍ
CHANNEL_ID = 'UC5lIHGjfdoGqpJoSjemw_4w' 
INPUT_FOLDER = '/Users/jesusandresmezacontreras/projects/astra/minutes-txt'
OUTPUT_CSV = 'match_sesiones_optimizado.csv'
# ================================================

def get_uploads_playlist_id(youtube, channel_id):
    """Obtiene el ID de la playlist de 'Subidas' del canal para ahorrar cuota."""
    res = youtube.channels().list(id=channel_id, part='contentDetails').execute()
    return res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

def get_all_videos_2024(youtube, playlist_id):
    """Descarga TODOS los videos del 2024 de una vez. Mucho más rápido y barato."""
    videos = []
    next_page_token = None
    
    print("📥 Descargando catálogo de videos del canal (esto puede tardar unos segundos)...")
    
    while True:
        res = youtube.playlistItems().list(
            playlistId=playlist_id,
            part='snippet',
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        
        for item in res['items']:
            pub_date = item['snippet']['publishedAt']
            # Filtramos solo 2024 (o 2023 si tienes actas viejas)
            if '2024' in pub_date or '2023' in pub_date: 
                videos.append({
                    'id': item['snippet']['resourceId']['videoId'],
                    'title': item['snippet']['title'],
                    'desc': item['snippet']['description'],
                    'date_str': pub_date,
                    'full_text': item['snippet']['title'] + " " + item['snippet']['description']
                })
        
        next_page_token = res.get('nextPageToken')
        if not next_page_token:
            break
            
        # Si llegamos a videos muy viejos (ej: 2022), paramos para ahorrar tiempo
        last_date = res['items'][-1]['snippet']['publishedAt']
        if '2022' in last_date:
            break
            
    print(f"✅ Se encontraron {len(videos)} videos en el catálogo.")
    return videos

def parse_date_from_filename(filename):
    """
    Extrae fecha del nombre del archivo. 
    Ej: 'ACTA N° 013 DE ENERO 16 DE 2024...' -> datetime(2024, 1, 16)
    """
    months = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    # Regex para capturar: MES (espacio) DIA (espacio) AÑO
    # OJO: Ajustado al formato de tu CSV: "ENERO 16 DE 2024"
    match = re.search(r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(\d{1,2})\s+de\s+(\d{4})', filename, re.IGNORECASE)
    
    if match:
        try:
            m_str, d_str, y_str = match.groups()
            return datetime(int(y_str), months[m_str.lower()], int(d_str))
        except:
            return None
    return None

def extract_topic_from_text(file_path):
    """Extrae el tema principal del contenido del acta."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Buscar el punto 3 (usualmente el tema central)
        topic_pattern = re.compile(r'(?:^|\n)3\.\s+(.+?)(?=\n4\.|\n\n|$)', re.DOTALL)
        match = topic_pattern.search(content)
        if match:
            return match.group(1).strip().replace('\n', ' ')
        
        # Fallback: Primeras líneas si no encuentra el punto 3
        return content[:500].replace('\n', ' ')
    except:
        return ""

def find_video_match(acta_date, acta_topic, all_videos, model):
    """
    Lógica de matcheo en 2 pasos:
    1. Filtro duro por FECHA (buscar día y mes en el título del video).
    2. Si hay varios, desempatar con IA.
    """
    if not acta_date:
        return "No encontrado", "", 0.0

    spanish_months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                      'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    
    day_str = str(acta_date.day)
    month_str = spanish_months[acta_date.month - 1]
    
    # PASO 1: Filtrar videos que contengan "16" y "Enero" en el título
    candidates = []
    for v in all_videos:
        title_lower = v['title'].lower()
        # Buscamos que el título tenga el día y el mes (ej: "Sesión 16 de Enero")
        if day_str in title_lower and month_str in title_lower:
            candidates.append(v)
    
    # Si no hay match exacto en título, buscamos por fecha de publicación (margen de error +- 2 días)
    if not candidates:
        for v in all_videos:
            v_date = datetime.strptime(v['date_str'][:10], '%Y-%m-%d')
            delta = abs((v_date - acta_date).days)
            if delta <= 2:
                candidates.append(v)

    if not candidates:
        return "No encontrado (Sin coincidencia de fecha)", "", 0.0

    # PASO 2: Si hay 1 solo candidato, es ese. Si hay varios, usamos IA.
    if len(candidates) == 1:
        return candidates[0]['title'], f"https://www.youtube.com/watch?v={candidates[0]['id']}", 1.0
    
    # Desempate con IA
    video_texts = [c['full_text'] for c in candidates]
    embeddings_topic = model.encode([acta_topic])
    embeddings_videos = model.encode(video_texts)
    
    similarities = cosine_similarity(embeddings_topic, embeddings_videos)[0]
    best_idx = similarities.argmax()
    best_score = similarities[best_idx]
    
    return candidates[best_idx]['title'], f"https://www.youtube.com/watch?v={candidates[best_idx]['id']}", round(best_score, 2)

def main():
    if YOUTUBE_API_KEY == 'TU_API_KEY_AQUI':
        print("❌ ERROR: Configura tu API Key.")
        return

    # 1. Configurar servicios
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # 2. Obtener inventario de videos (SOLO UNA VEZ)
    uploads_id = get_uploads_playlist_id(youtube, CHANNEL_ID)
    all_videos = get_all_videos_2024(youtube, uploads_id)
    
    # 3. Procesar archivos
    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith('.txt')]
    results = []

    print(f"\n🔄 Procesando {len(files)} actas...")
    
    for filename in tqdm(files):
        # A. Extraer fecha del NOMBRE DEL ARCHIVO (Más fiable)
        acta_date = parse_date_from_filename(filename)
        
        # B. Extraer tema del texto
        file_path = os.path.join(INPUT_FOLDER, filename)
        acta_topic = extract_topic_from_text(file_path)
        
        # C. Buscar Match
        vid_title, vid_link, confidence = find_video_match(acta_date, acta_topic, all_videos, model)
        
        results.append({
            'Archivo': filename,
            'Fecha_Detectada': acta_date.strftime('%Y-%m-%d') if acta_date else "Error formato",
            'Video_Match': vid_title,
            'Link': vid_link,
            'Confianza': confidence
        })

    # 4. Guardar
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Resultados guardados en {OUTPUT_CSV}")

if __name__ == '__main__':
    main()