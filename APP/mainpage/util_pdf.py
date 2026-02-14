from collections import Counter
import os
import base64
from django.conf import settings
import asyncio
import pandas as pd
from collections import Counter
from typing import Optional, Iterable, Tuple, List
from mainpage.util import *

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


# Resumen de países con conteo y porcentaje, no traduce el nombre del país
def resumen_paises(excel_data):
    if not excel_data:
        return None

    # Convertir a DataFrame para facilitar el trabajo
    df = pd.DataFrame(excel_data)
    
    # Detectar columna país usando normalización
    columnas_norm = {normalizar(c): c for c in df.columns}
    
    col_pais = None
    for key_norm, col_original in columnas_norm.items():
        if key_norm in ("pais", "country"):
            col_pais = col_original
            break

    if not col_pais:
        return None

    # Filtrar valores válidos
    paises = df[col_pais].dropna()
    paises = paises[paises != ""]
    paises = paises[paises != "nan"]

    if paises.empty:
        return None

    total = len(paises)
    conteo = Counter(paises)

    # Calcular porcentajes
    resumen = []
    for pais, n in conteo.most_common():
        porcentaje = round((n / total) * 100)
        resumen.append(f"{pais} {porcentaje}%")

    return ", ".join(resumen)

# Guardar gráfico desde data URL, se reciben desde ver_imagenes.html
def guardar_grafico(data_url, nombre):
    if not data_url:
        return None

    try:
        header, encoded = data_url.split(",", 1)
        image_data = base64.b64decode(encoded)

        path = os.path.join(settings.MEDIA_ROOT, f"{nombre}.png")

        with open(path, "wb") as f:
            f.write(image_data)

        # Verificación real
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None

        return path

    except Exception as e:
        print(f"Error guardando gráfico {nombre}: {e}")
        return None

def render_many_html_to_png(
    jobs: Iterable[Tuple[str, str]],
    width: int = 1400,
    height: int = 900,
) -> List[Optional[str]]:
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return [None for _ in jobs]

    normalized: List[Tuple[Path, Path]] = []
    for html_path, png_path in jobs:
        hp = Path(html_path).resolve()
        pp = Path(png_path).resolve()
        if not hp.exists():
            normalized.append((hp, pp))
        else:
            normalized.append((hp, pp))

    async def _run() -> List[Optional[str]]:
        out: List[Optional[str]] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                for html_path, png_path in normalized:
                    if not html_path.exists():
                        out.append(None)
                        continue

                    page = await browser.new_page(viewport={"width": width, "height": height})
                    try:
                        await page.goto(f"file://{html_path}", wait_until="networkidle")
                        await page.screenshot(path=str(png_path), full_page=True)
                    finally:
                        await page.close()

                    if png_path.exists() and png_path.stat().st_size > 0:
                        out.append(str(png_path))
                    else:
                        out.append(None)
            finally:
                await browser.close()
        return out

    try:
        return asyncio.run(_run())
    except Exception:
        return [None for _ in jobs]
    

def _normalize_img_id(s: object) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    base = os.path.basename(s)
    root, ext = os.path.splitext(base)
    if ext.lower() in IMG_EXTS:
        base = root
    return normalizar_nombre(base)

def build_geo_stats_tables(excel_data, imagenes, model_results):
    if not excel_data:
        return None, None, 0

    df = pd.DataFrame(excel_data)
    cols = {normalizar(c): c for c in df.columns}

    col_country = None
    col_area = None
    col_id = None

    for k, orig in cols.items():
        if k in ("pais", "country"):
            col_country = orig
        elif k in ("region", "area", "región"):
            col_area = orig
        elif k in ("id", "nombre", "imagen", "image", "filename", "nombreimagen"):
            col_id = orig

    if not col_id:
        return None, None, 0

    keep_cols = [col_id]
    if col_country:
        keep_cols.append(col_country)
    if col_area:
        keep_cols.append(col_area)

    df = df[keep_cols].copy()
    df["img_id"] = df[col_id].map(_normalize_img_id)

    valid_img_ids = []
    for (name, _), res in zip(imagenes, model_results):
        if len(res) > 4 and res[4] == 0:
            valid_img_ids.append(_normalize_img_id(name))

    df = df[df["img_id"].isin(set(valid_img_ids))].copy()

    total = int(df.shape[0])

    country_counter = Counter()
    area_counter = Counter()

    def _clean_series(s: pd.Series) -> pd.Series:
        return s.astype(str).str.strip()

    if col_country:
        c = _clean_series(df[col_country])
        country_counter = Counter([x for x in c.tolist() if x and x.lower() not in ("nan", "none")])

    # ---- key change: areas only when country == Spain/España ----
    if col_area:
        df_area = df
        if col_country:
            c = _clean_series(df[col_country]).str.lower()

            spain_values = {
                "españa", "espana", "spain", "es", "esp", "españa ", "espana ", "spain "
            }
            df_area = df[c.isin(spain_values)].copy()

        a = _clean_series(df_area[col_area])
        area_counter = Counter([x for x in a.tolist() if x and x.lower() not in ("nan", "none")])

    def to_rows(counter: Counter, total_n: int, top_n: int = 20):
        items = counter.most_common(top_n)
        rows = []
        for label, count in items:
            pct = (count / total_n * 100.0) if total_n > 0 else 0.0
            rows.append((label, int(count), pct))
        return rows

    countries_rows = to_rows(country_counter, total, top_n=50)

    # For areas, percentages should be relative to Spain-only total (more meaningful)
    if col_area and col_country:
        spain_total = 0
        c = _clean_series(df[col_country]).str.lower()
        spain_values = {"españa", "espana", "spain", "es", "esp"}
        spain_total = int(df[c.isin(spain_values)].shape[0])
    else:
        spain_total = total

    areas_rows = to_rows(area_counter, spain_total, top_n=50)

    return countries_rows, areas_rows, total
