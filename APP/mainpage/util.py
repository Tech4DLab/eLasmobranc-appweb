from datetime import datetime
import unicodedata
import csv
import io
import os
import pandas as pd
import json
from pathlib import Path
import folium
import pycountry

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


# Normalización de nombres de archivo, eliminando ruta, extensión y acentos
def normalizar_nombre(nombre):
    base = os.path.basename(str(nombre)).strip().lower()
    nombre_sin_ext, _ = os.path.splitext(base)
    nombre_sin_ext = unicodedata.normalize("NFKD", nombre_sin_ext)
    nombre_sin_ext = "".join(c for c in nombre_sin_ext if not unicodedata.combining(c))
    return nombre_sin_ext

# Normalización de texto genérico, eliminando acentos y espacios
def normalizar(texto):
    if not texto:
        return ""
    texto = str(texto)
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower().replace(" ", "")

# Cargar datos tabulares desde CSV o Excel
def cargar_datos_tabulares(file):
    nombre = file.name.lower()

    # ── CSV ─────────────────────────────
    if nombre.endswith(".csv"):
        try:
            # Leer todo el archivo como bytes primero
            raw_bytes = file.read()
            
            # Intentar diferentes encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252']
            raw = None
            
            for encoding in encodings:
                try:
                    raw = raw_bytes.decode(encoding)
                    break
                except:
                    continue
            
            if raw is None:
                raw = raw_bytes.decode('utf-8', errors='replace')
            
            # Limpiar caracteres problemáticos (BOM, etc)
            raw = raw.replace('\ufeff', '')  # Eliminar BOM
            raw = raw.replace('\r\n', '\n')  # Normalizar saltos de línea
            raw = raw.replace('\r', '\n')
            
            # Usar StringIO para simular un archivo
            text_stream = io.StringIO(raw)
            
            # Parsear con csv.reader
            reader = csv.reader(text_stream, delimiter=',', quotechar='"')
            
            # Convertir a lista
            data = list(reader)
            
            print(f"Total de líneas: {len(data)}")
            if len(data) > 1:
                print(f"Columnas header: {len(data[0])}")
                print(f"Columnas fila 1: {len(data[1])}")
                print(f"Fila 1 completa: {data[1]}")
            
            # Verificar que hay datos
            if len(data) < 2:
                return pd.DataFrame()
            
            # Separar header y filas
            columns = data[0]
            rows = data[1:]
            
            # Filtrar filas vacías y verificar consistencia
            valid_rows = []
            for i, row in enumerate(rows):
                if row and len(row) == len(columns):
                    valid_rows.append(row)
                elif row and len(row) == 1 and ',' in row[0]:
                    # La fila está mal parseada, intentar separarla manualmente
                    print(f"Fila {i+1} mal parseada, reintentando...")
                    manual_row = list(csv.reader([row[0]], delimiter=',', quotechar='"'))[0]
                    if len(manual_row) == len(columns):
                        valid_rows.append(manual_row)
                    else:
                        print(f"Fila {i+1} descartada: {len(manual_row)} columnas en lugar de {len(columns)}")
            
            # Crear DataFrame
            df = pd.DataFrame(valid_rows, columns=columns)
            
            return df
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    # ── Excel ────────────────────────────
    return pd.read_excel(file)

# Formatear fechas a DD/MM/YYYY
def formatear_fecha(valor):
    """
    Convierte una fecha en formato ISO (YYYY-MM-DD) o timestamp
    a DD/MM/YYYY. Maneja también NaT o valores vacíos.
    """
    if not valor or valor in ["NaT", "nan", ""]:
        return None

    try:
        # Si ya es string ISO con T (timestamp completo)
        if isinstance(valor, str) and 'T' in valor:
            fecha = datetime.fromisoformat(valor.split('T')[0])
            return fecha.strftime("%d/%m/%Y")
        
        # Intenta parsear formato ISO normal
        fecha = datetime.fromisoformat(str(valor))
        return fecha.strftime("%d/%m/%Y")
    except:
        # Si falla, intenta con pandas
        try:
            fecha = pd.to_datetime(valor)
            return fecha.strftime("%d/%m/%Y")
        except:
            return str(valor)

def _iso_a3(country: object) -> str | None:
    if country is None:
        return None
    c = str(country).strip()
    if not c:
        return None
    try:
        return pycountry.countries.lookup(c).alpha_3
    except Exception:
        return None

def generar_mapa_paises_html_desde_excel(
    excel_data: list[dict] | None,
    output_html_path: str,
    geojson_path: str,
) -> bool:
    geojson_path = Path(geojson_path)
    if not geojson_path.exists():
        return False

    with geojson_path.open(encoding="utf-8") as f:
        geojson_data = json.load(f)

    m = folium.Map(location=[20, 0], zoom_start=2)

    country_counts = None

    if excel_data:
        df = pd.DataFrame(excel_data)
        if not df.empty:
            cols_norm = {str(c).strip().lower().replace(" ", "").replace("_", ""): c for c in df.columns}

            country_col = None
            for k, orig in cols_norm.items():
                if k in ("country", "pais"):
                    country_col = orig
                    break

            if country_col:
                df = df.dropna(subset=[country_col]).copy()
                df[country_col] = df[country_col].astype(str).str.strip()
                df = df[df[country_col] != ""]

                if not df.empty:
                    country_counts = df[country_col].value_counts().reset_index()
                    country_counts.columns = ["country", "count"]
                    country_counts["iso_a3"] = country_counts["country"].apply(_iso_a3)
                    country_counts = country_counts.dropna(subset=["iso_a3"])
                    if country_counts.empty:
                        country_counts = None

    if country_counts is not None:
        folium.Choropleth(
            geo_data=geojson_data,
            data=country_counts,
            columns=["iso_a3", "count"],
            key_on="feature.id",
            fill_color="YlOrRd",
            fill_opacity=0.8,
            line_opacity=0.3,
            nan_fill_color="lightgray",
            legend_name="Número de muestras por país",
        ).add_to(m)

    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
    m.save(output_html_path)
    return True

CCAA_NAME_TO_CODE = { "andalusia": "01", 
                     "aragon": "02", 
                     "asturias": "03", 
                     "balearic islands": "04", 
                     "canary islands": "05", 
                     "cantabria": "06", "catalonia": "09", 
                     "valencian community": "10", 
                     "galicia": "12", 
                     "region of murcia": "14", 
                     "autonomous community of the basque country": "16", 
                     "ceuta": "18", 
                     "melilla": "19", }

def _norm(s):
    return " ".join(str(s).strip().lower().replace("_", " ").replace("-", " ").split())


def generar_mapa_ccaa_html_desde_excel_area(
    excel_data: list[dict] | None,
    output_html_path: str,
    geojson_path: str,
    
) -> bool:
    geojson_path = Path(geojson_path)
    if not geojson_path.exists():
        return False

    with geojson_path.open(encoding="utf-8") as f:
        geojson_ccaa = json.load(f)

    m = folium.Map(location=[40, -3], zoom_start=6)

    counts = None

    if excel_data:
        df = pd.DataFrame(excel_data)
        if not df.empty:
            cols = {str(c).strip().lower().replace(" ", "").replace("_", ""): c for c in df.columns}
            country_col = cols.get("country")
            area_col = cols.get("area")

            if country_col and area_col:
                df = df.dropna(subset=[country_col, area_col]).copy()
                df[country_col] = df[country_col].astype(str).str.strip()
                df[area_col] = df[area_col].astype(str).str.strip()

                df = df[df[country_col].isin(["Spain"])]
                if not df.empty:
                    df["cod_ccaa"] = df[area_col].map(lambda x: CCAA_NAME_TO_CODE.get(_norm(x)))
                    df = df.dropna(subset=["cod_ccaa"])
                    if not df.empty:
                        counts = df["cod_ccaa"].value_counts().reset_index()
                        counts.columns = ["cod_ccaa", "count"]

    if counts is not None:
        folium.Choropleth(
            geo_data=geojson_ccaa,
            data=counts,
            columns=["cod_ccaa", "count"],
            key_on="feature.properties.cod_ccaa",
            fill_color="YlOrRd",
            fill_opacity=0.8,
            line_opacity=0.3,
            nan_fill_color="lightgray",
            legend_name="Número de muestras por comunidad",
        ).add_to(m)

    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
    m.save(output_html_path)
    return True

def normalizar_id_imagen(s: object) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    base = os.path.basename(s)
    root, ext = os.path.splitext(base)
    if ext.lower() in IMG_EXTS:
        base = root
    return normalizar_nombre(base)


def _normalize_excel_image_id(value: object) -> str:
    return normalizar_id_imagen(value)


def _find_excel_id_column(excel_data: list[dict]) -> str | None:
    if not excel_data:
        return None
    df = pd.DataFrame(excel_data)
    cols = {normalizar(str(c)): c for c in df.columns}
    for k_norm, orig in cols.items():
        if k_norm in ("id", "nombre", "imagen", "image", "filename", "nombreimagen"):
            return orig
    return None


def filter_to_elasmobranchs(imagenes: list[tuple[str, str]], model_results: list[list]) -> tuple[list[tuple[str, str]], list[list]]:
    im_filtradas = []
    res_filtrados = []
    for im, res in zip(imagenes, model_results):
        if len(res) > 4 and res[4] == 0:
            im_filtradas.append(im)
            res_filtrados.append(res)
    return im_filtradas, res_filtrados


def filter_excel_by_elasmobranchs(excel_data: list[dict] | None, imagenes: list[tuple[str, str]], model_results: list[list]) -> list[dict] | None:
    if not excel_data:
        return excel_data

    id_col = _find_excel_id_column(excel_data)
    if not id_col:
        return excel_data

    elasm_ids = set()
    for (nombre_img, _), res in zip(imagenes, model_results):
        if len(res) > 4 and res[4] == 0:
            elasm_ids.add(_normalize_excel_image_id(nombre_img))

    filtered = []
    for row in excel_data:
        rid = _normalize_excel_image_id(row.get(id_col, ""))
        if rid in elasm_ids:
            filtered.append(row)

    return filtered
