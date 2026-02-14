from __future__ import annotations

import math
import os
import shutil
import tempfile
import urllib.parse
import zipfile
from collections import Counter
from datetime import datetime

import pandas as pd
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from mainpage.modelo import model_gpu as model
from mainpage.util import *
from mainpage.util_pdf import *

import uuid
from django.http import JsonResponse, FileResponse, HttpResponse
from django.urls import reverse

IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

def normalizar_id_imagen(s: object) -> str:
    # Normalize image ID from path or filename

    if s is None:
        return ""

    s = str(s).strip()
    base = os.path.basename(s)
    root, ext = os.path.splitext(base)

    if ext.lower() in IMG_EXTS:
        base = root

    return normalizar_nombre(base)


def ver_imagenes(request):
# Build view context: model outputs + charts + optional Excel metadata and maps
    chart_data = {
        "animal": ["Tiburón", "Raya", "Otro"],
        "valuesA": [0, 0, 0],
        "orden": ["Carcharhiniformes", "Squaliformes", "Torpediniformes", "Rajiformes"],
        "valuesO": [0, 0, 0, 0],
        "familia": ["Scyliorhinidae", "Triakidae", "Oxynotidae", "Rajidae", "Torpedinidae"],
        "valuesF": [0, 0, 0, 0, 0],
        "especie": [
            "Galeus melastomus",
            "Galeorhinus galeus",
            "Oxynotus centrina",
            "Mustelus mustelus",
            "Scyliorhinus canicula",
            "Leucoraja naevus",
            "Torpedo marmorata",
        ],
        "valuesE": [0, 0, 0, 0, 0, 0, 0],
    }

    excel_data = request.session.get("excel_data")
    model_results = model.main(request.session.get("temp_dir"))

    imagenes = request.session.get("imagenes", [])
    imagenes_formateadas = [{"nombre": n, "ruta": r} for (n, r) in imagenes]

    animal_map = {"shark": "Tiburón", "stingray": "Raya", "other": "Otro"}
    orden_map = ["carcharhiniformes", "squaliformes", "torpediniformes", "rajiformes"]
    familia_map = ["scyliorhinidae", "triakidae", "oxynotidae", "rajidae", "torpedinidae"]
    especie_map = ["bocanegra", "cazon", "cerdo_marino", "musola", "pintarroja", "santiaguesa", "tembladera"]
    especie_cientifica = {
        "bocanegra": "Galeus melastomus",
        "cazon": "Galeorhinus galeus",
        "cerdo_marino": "Oxynotus centrina",
        "musola": "Mustelus mustelus",
        "pintarroja": "Scyliorhinus canicula",
        "santiaguesa": "Leucoraja naevus",
        "tembladera": "Torpedo marmorata",
    }

    for result in model_results:
        if result[0] == "shark":
            chart_data["valuesA"][0] += 1
            result.append(0)
        elif result[0] == "stingray":
            chart_data["valuesA"][1] += 1
            result.append(0)
        elif result[0] == "other":
            chart_data["valuesA"][2] += 1
            result.append(1)
        else:
            result.append(1)

        result[0] = "Animal: " + animal_map.get(result[0], str(result[0]))

        if result[1] in orden_map:
            chart_data["valuesO"][orden_map.index(result[1])] += 1
        result[1] = "Orden: " + str(result[1])

        if result[2] in familia_map:
            chart_data["valuesF"][familia_map.index(result[2])] += 1
        result[2] = "Familia: " + str(result[2])

        if result[3] in especie_map:
            chart_data["valuesE"][especie_map.index(result[3])] += 1

        if result[3] in especie_cientifica:
            result[3] = "Especie: " + especie_cientifica[result[3]]
        else:
            result[3] = "Especie: " + str(result[3])

    request.session["model_results"] = model_results

    especies = list(zip(chart_data["especie"], chart_data["valuesE"]))
    especies = [e for e in especies if e[1] > 0]
    especies.sort(key=lambda x: x[1], reverse=True)
    chart_data["especie"] = [e[0] for e in especies]
    chart_data["valuesE"] = [e[1] for e in especies]

    request.session["chart_data"] = chart_data

    excel_lookup = {}
    if excel_data:
        df = pd.DataFrame(excel_data)
        columnas_norm = {normalizar(c): c for c in df.columns}

        col_nombre = None
        col_pais = None
        col_region = None
        col_fecha = None

        for key_norm, col_original in columnas_norm.items():
            if key_norm in ("pais", "country"):
                col_pais = col_original
            elif key_norm in ("region", "area", "región"):
                col_region = col_original
            elif key_norm in ("observed_on", "observedon", "fecha", "date"):
                col_fecha = col_original
            elif key_norm in ("id", "nombre", "imagen", "image", "filename", "nombreimagen"):
                col_nombre = col_original

        for row in excel_data:
            nombre = normalizar_id_imagen(row.get(col_nombre, "")) if col_nombre else ""
            if nombre:
                excel_lookup[nombre] = {
                    "pais": row.get(col_pais, "Desconocido") if col_pais else "Desconocido",
                    "region": row.get(col_region, "Desconocida") if col_region else "Desconocida",
                    "fecha": formatear_fecha(row.get(col_fecha)) if col_fecha else None,
                }

    imagenes_con_resultados = []
    imagenes_no_elasmobranquios = []

    for img, res in zip(imagenes_formateadas, model_results):
        nombre_img = normalizar_id_imagen(img["nombre"])
        datos_excel = excel_lookup.get(nombre_img)
        resultados_finales = res[:4]

        if datos_excel:
            if datos_excel.get("pais") not in (None, "", "nan", "Desconocido"):
                resultados_finales.append(f"País: {datos_excel['pais']}")
            if datos_excel.get("region") not in (None, "", "nan", "Desconocida"):
                resultados_finales.append(f"Región: {datos_excel['region']}")
            if datos_excel.get("fecha"):
                resultados_finales.append(f"Fecha: {datos_excel['fecha']}")

        item = {
            "nombre": nombre_img,
            "ruta": img["ruta"],
            "resultados": resultados_finales,
        }

        if len(res) > 4 and res[4] == 0:
            imagenes_con_resultados.append(item)
        else:
            imagenes_no_elasmobranquios.append(item)

    def build_time_charts(excel_data, imagenes, model_results):
    # Create month/species and year/species count series from Excel dates
        if not excel_data:
            return None, None

        df = pd.DataFrame(excel_data)
        cols = {str(c).strip().lower().replace(" ", "").replace("_", ""): c for c in df.columns}

        date_col = None
        for k, orig in cols.items():
            if k in ("observedon", "observed_on", "fecha", "date"):
                date_col = orig
                break

        id_col = None
        for k, orig in cols.items():
            if k in ("id", "nombre", "imagen", "image", "filename", "nombreimagen"):
                id_col = orig
                break

        if not date_col or not id_col:
            return None, None

        df = df[[id_col, date_col]].copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])

        def normalize_id(s):
            s = "" if s is None else str(s).strip()
            base = os.path.basename(s)
            root, ext = os.path.splitext(base)
            if ext.lower() in IMG_EXTS:
                base = root
            return normalizar_nombre(base)

        df["img_id"] = df[id_col].map(normalize_id)
        df["month"] = df[date_col].dt.month
        df["year"] = df[date_col].dt.year.astype(int)

        imagen_a_especie = {}
        for (nombre_img, _), res in zip(imagenes, model_results):
            if len(res) > 4 and res[4] != 0:
                continue
            img_id = normalize_id(nombre_img)
            especie = str(res[3]).replace("Especie: ", "")
            imagen_a_especie[img_id] = especie

        df["species"] = df["img_id"].map(imagen_a_especie)
        df = df.dropna(subset=["species"])

        month_labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

        pivot_m = (
            df.pivot_table(index="month", columns="species", values="img_id", aggfunc="count", fill_value=0)
            .reindex(range(1, 13), fill_value=0)
        )

        species_order = pivot_m.sum(axis=0).sort_values(ascending=False).index.tolist()
        pivot_m = pivot_m[species_order]

        chart_month_species = {
            "labels": month_labels,
            "series": {sp: pivot_m[sp].astype(int).tolist() for sp in pivot_m.columns},
        }

        year_counts = df.groupby("year")["img_id"].count().sort_values(ascending=False).head(6)
        top_years = year_counts.index.tolist()

        pivot_y = (
            df.pivot_table(index="year", columns="species", values="img_id", aggfunc="count", fill_value=0)
            .reindex(top_years, fill_value=0)
        )

        species_order_y = pivot_y.sum(axis=0).sort_values(ascending=False).index.tolist()
        pivot_y = pivot_y[species_order_y]

        chart_years = {
            "labels": [str(y) for y in pivot_y.index.tolist()],
            "series": {sp: pivot_y[sp].astype(int).tolist() for sp in pivot_y.columns},
        }

        return chart_month_species, chart_years

    chart_month_species, chart_years = build_time_charts(
        excel_data=request.session.get("excel_data"),
        imagenes=request.session.get("imagenes", []),
        model_results=model_results,
    )

    request.session["chart_month_species"] = chart_month_species
    request.session["chart_years"] = chart_years
    
    
    mapa_world_url = None

    temp_dir = request.session.get("temp_dir")
    excel_data = request.session.get("excel_data")
    
    excel_elasm = filter_excel_by_elasmobranchs(excel_data, imagenes, model_results)


    if excel_data and temp_dir and os.path.exists(temp_dir):
        mapa_path = os.path.join(temp_dir, "mapa_world.html")
        geojson_path = os.path.join(settings.BASE_DIR, "mainpage/static/mainpage/maps/world-countries.json")
            
        ok = generar_mapa_paises_html_desde_excel(
            excel_data=excel_elasm,
            output_html_path=mapa_path,
            geojson_path=geojson_path,
            )

        if ok:
            mapa_world_url = mapa_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
            
    mapa_ccaa_url = None
    
    if excel_data and temp_dir and os.path.exists(temp_dir):
        mapa_ccaa_path = os.path.join(temp_dir, "mapa_ccaa.html")
        geojson_ccaa_path = os.path.join(settings.BASE_DIR, "mainpage/static/mainpage/maps/spain-communities.geojson")

        ok = generar_mapa_ccaa_html_desde_excel_area(
            excel_data=excel_elasm ,
            output_html_path=mapa_ccaa_path,
            geojson_path=geojson_ccaa_path,
        )

        if ok:
            mapa_ccaa_url = mapa_ccaa_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)

    return render(
    request,
    "mainpage/ver_imagenes.html",
    {
        "imagenes": imagenes_con_resultados,
        "imagenes_no": imagenes_no_elasmobranquios,
        "excel_data": excel_data,
        "chart_data": chart_data,
        "chart_month_species": chart_month_species,
        "chart_years": chart_years,
        "mapa_world_url": mapa_world_url,
        "mapa_ccaa_url": mapa_ccaa_url,
    },
    )


def main_page(request):
    # Handle ZIP+optional Excel upload, store session data, and redirect to results
    error = None

    if request.method == "POST" and request.FILES.get("zipfile"):
        if request.FILES.get("excelfile"):
            try:
                excel_file = request.FILES["excelfile"]
                df = cargar_datos_tabulares(excel_file)
                df = df.map(lambda x: x.isoformat() if isinstance(x, pd.Timestamp) or hasattr(x, "isoformat") else x)
                data = df.to_dict(orient="records")
                request.session["excel_data"] = data
            except Exception as e:
                error = f"Error al procesar el Excel: {e}"
        else:
            request.session["excel_data"] = None

        zip_file = request.FILES["zipfile"]

        nombres = []
        rutas = []

        temp_dir = tempfile.mkdtemp(dir=settings.MEDIA_ROOT)
        request.session["zip_name"] = zip_file.name

        try:
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                for name in zip_ref.namelist():
                    if name.lower().endswith(tuple(IMG_EXTS)):
                        zip_ref.extract(name, temp_dir)
                        ruta_fisica = os.path.join(temp_dir, name)
                        ruta_web = ruta_fisica.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
                        nombres.append(os.path.basename(name))
                        rutas.append(ruta_web)

            if not nombres:
                error = "No se encontraron imágenes dentro del ZIP."
        except zipfile.BadZipFile:
            error = "El archivo subido no es un ZIP válido."
            nombres = []
            rutas = []
        except Exception as e:
            error = f"Error al procesar el ZIP: {e}"
            nombres = []
            rutas = []

        if not error:
            request.session["imagenes"] = list(zip(nombres, rutas))
            request.session["temp_dir"] = temp_dir
            return redirect("mainpage:ver_imagenes")

    return render(request, "mainpage/main_page.html", {"error": error})


@csrf_exempt
def borrar_temp(request):
    # Remove temp folder and clear related session keys
    carpeta = request.session.get("temp_dir")

    if carpeta and os.path.exists(carpeta):
        shutil.rmtree(carpeta, ignore_errors=True)

    for k in (
        "temp_dir",
        "imagenes",
        "model_results",
        "chart_data",
        "chart_month_species",
        "chart_years",
        "zip_name",
    ):
        if k in request.session:
            del request.session[k]

    request.session.modified = True
    return JsonResponse({"ok": True})



def generar_pdf(request):
    # Generate a PDF report from session results and POSTed chart images
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    imagenes = request.session.get("imagenes", [])
    model_results = request.session.get("model_results", [])

    zip_name = request.session.get("zip_name", "archivo.zip")
    zip_base = os.path.splitext(zip_name)[0]

    temp_dir = request.session.get("temp_dir")
    if not temp_dir or not os.path.exists(temp_dir):
        return JsonResponse({"ok": False, "error": "Missing temp_dir"}, status=400)

    token = uuid.uuid4().hex
    pdf_path = os.path.join(temp_dir, f"informe_{token}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Resultados eLasmobranch", styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            f"Informe generado a partir de {zip_base}<br/>Fecha de generación: {datetime.now().strftime('%d/%m/%Y')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 25))

    animales = [r[0].replace("Animal: ", "") for r in model_results]
    ordenes = [r[1].replace("Orden: ", "") for r in model_results]
    familias = [r[2].replace("Familia: ", "") for r in model_results]
    especies = [r[3].replace("Especie: ", "") for r in model_results]

    cont_animales = Counter(animales)
    cont_especies = Counter(especies)

    total = sum(cont_especies.values())
    indice_shannon = None
    if total > 0:
        indice_shannon = -sum((c / total) * math.log(c / total) for c in cont_especies.values() if c > 0)

    story.append(Paragraph("Resumen estadístico", styles["Heading1"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"Total de imágenes: <b>{len(model_results)}</b>", styles["Normal"]))
    story.append(Paragraph(f"Tiburones: <b>{cont_animales.get('Tiburón', 0)}</b>", styles["Normal"]))
    story.append(Paragraph(f"Rayas: <b>{cont_animales.get('Raya', 0)}</b>", styles["Normal"]))
    story.append(Paragraph(f"Otros: <b>{cont_animales.get('Otro', 0)}</b>", styles["Normal"]))

    ordenes_validas = {o for o in ordenes if o not in (None, "", "None")}
    familias_validas = {f for f in familias if f not in (None, "", "None")}
    especies_validas = {e for e in especies if e not in (None, "", "None")}

    story.append(Paragraph(f"Órdenes distintos: <b>{len(ordenes_validas)}</b>", styles["Normal"]))
    story.append(Paragraph(f"Familias distintas: <b>{len(familias_validas)}</b>", styles["Normal"]))
    story.append(Paragraph(f"Especies distintas: <b>{len(especies_validas)}</b>", styles["Normal"]))

    cont_especies_validas = Counter(e for e in especies if e not in (None, "", "None"))
    if cont_especies_validas:
        esp, n = cont_especies_validas.most_common(1)[0]
        story.append(Paragraph(f"Especie más frecuente: <b>{esp}</b> ({n} imágenes)", styles["Normal"]))
        if indice_shannon is not None:
            story.append(Paragraph(f"Índice de diversidad (Shannon): <b>{indice_shannon:.3f}</b>", styles["Normal"]))

    excel_data = request.session.get("excel_data")
    if excel_data:
        texto_paises = resumen_paises(excel_data)
        if texto_paises:
            story.append(Paragraph(f"Países de origen: {texto_paises}", styles["Normal"]))

    story.append(Spacer(1, 25))

    chart_animal = request.POST.get("chart_animal")
    chart_orden = request.POST.get("chart_orden")
    chart_familia = request.POST.get("chart_familia")
    chart_especie = request.POST.get("chart_especie")
    chart_month_species = request.POST.get("chart_month_species")
    chart_years = request.POST.get("chart_years")

    graficos_paths = [
        guardar_grafico(chart_animal, "chart_animal"),
        guardar_grafico(chart_orden, "chart_orden"),
        guardar_grafico(chart_familia, "chart_familia"),
    ]
    graficos_paths = [p for p in graficos_paths if p]

    story.append(Paragraph("Gráficos de resultados", styles["Heading1"]))
    story.append(Spacer(1, 15))

    imgs = []
    for path in graficos_paths:
        if path and os.path.exists(path):
            imgs.append(Image(path, width=9.0 * cm, height=9.0 * cm))

    table_rows = []
    if len(imgs) >= 2:
        table_rows.append([imgs[0], imgs[1]])
    elif len(imgs) == 1:
        table_rows.append([imgs[0], ""])

    if len(imgs) >= 3:
        table_rows.append([imgs[2], ""])

    if table_rows:
        t = Table(table_rows, colWidths=[8.5 * cm, 8.5 * cm])
        ts = TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")])
        if len(imgs) >= 3:
            ts.add("SPAN", (0, 1), (1, 1))
            ts.add("ALIGN", (0, 1), (1, 1), "CENTER")
        if len(imgs) == 1:
            ts.add("SPAN", (0, 0), (1, 0))
            ts.add("ALIGN", (0, 0), (1, 0), "CENTER")
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 20))

    img_especie_path = guardar_grafico(chart_especie, "chart_especie") if chart_especie else None
    if img_especie_path and os.path.exists(img_especie_path):
        story.append(Image(img_especie_path, width=18 * cm, height=9 * cm))
        story.append(Spacer(1, 25))

    img_month_path = guardar_grafico(chart_month_species, "chart_month_species") if chart_month_species else None
    img_years_path = guardar_grafico(chart_years, "chart_years") if chart_years else None

    if (img_month_path and os.path.exists(img_month_path)) or (img_years_path and os.path.exists(img_years_path)):
        story.append(PageBreak())
        story.append(Paragraph("Temporalidad", styles["Heading1"]))
        story.append(Spacer(1, 20))

        if img_years_path and os.path.exists(img_years_path):
            story.append(Image(img_years_path, width=13.5 * cm, height=8 * cm, hAlign="CENTER"))
            story.append(Spacer(1, 50))

        if img_month_path and os.path.exists(img_month_path):
            story.append(Image(img_month_path, width=18.0 * cm, height=8.5 * cm, hAlign="CENTER"))
            story.append(Spacer(1, 18))

    world_html = os.path.join(temp_dir, "mapa_world.html") if temp_dir else None
    ccaa_html = os.path.join(temp_dir, "mapa_ccaa.html") if temp_dir else None
    world_png = os.path.join(temp_dir, "mapa_world.png") if temp_dir else None
    ccaa_png = os.path.join(temp_dir, "mapa_ccaa.png") if temp_dir else None

    pdf_html = render_many_html_to_png([(world_html, world_png), (ccaa_html, ccaa_png)], width=1400, height=900)
    world_png_ok, ccaa_png_ok = pdf_html

    imagenes_elasm, model_results_elasm = filter_to_elasmobranchs(imagenes, model_results)
    excel_elasm = filter_excel_by_elasmobranchs(excel_data, imagenes, model_results)

    countries_rows, areas_rows, geo_total = build_geo_stats_tables(
        excel_data=excel_elasm,
        imagenes=imagenes_elasm,
        model_results=model_results_elasm,
    )

    has_any_geo = (world_png_ok and os.path.exists(world_png_ok)) or (ccaa_png_ok and os.path.exists(ccaa_png_ok)) or geo_total > 0

    if has_any_geo:
        story.append(PageBreak())
        if world_png_ok and os.path.exists(world_png_ok):
            story.append(Paragraph("Mapa mundial (casos por país)", styles["Heading2"]))
            story.append(Spacer(1, 10))
            story.append(Image(world_png_ok, width=18.0 * cm, height=10.0 * cm))
            story.append(Spacer(1, 12))

        if countries_rows and geo_total > 0:
            story.append(Paragraph("Países", styles["Heading2"]))
            story.append(Spacer(1, 8))
            data_tbl = [["País", "Casos", "%"]]
            for label, count, pct in countries_rows:
                data_tbl.append([label, str(count), f"{pct:.1f}%"])
            t = Table(data_tbl, repeatRows=1, colWidths=[10 * cm, 3.5 * cm, 3.5 * cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]))
            story.append(t)
            story.append(Spacer(1, 18))

        if ccaa_png_ok and os.path.exists(ccaa_png_ok):
            story.append(PageBreak())
            story.append(Paragraph("España (casos por Comunidad Autónoma)", styles["Heading2"]))
            story.append(Spacer(1, 10))
            story.append(Image(ccaa_png_ok, width=18.0 * cm, height=10.0 * cm))
            story.append(Spacer(1, 12))

        if areas_rows and geo_total > 0:
            story.append(Paragraph("CCAA / Áreas", styles["Heading2"]))
            story.append(Spacer(1, 8))
            data_tbl = [["CCAA / Área", "Casos", "%"]]
            for label, count, pct in areas_rows:
                data_tbl.append([label, str(count), f"{pct:.1f}%"])
            t = Table(data_tbl, repeatRows=1, colWidths=[10 * cm, 3.5 * cm, 3.5 * cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]))
            story.append(t)
            story.append(Spacer(1, 18))

    story.append(PageBreak())
    story.append(Paragraph("Elasmobranquios identificados", styles["Heading1"]))
    story.append(Spacer(1, 12))

    tabla_data = [["Imagen", "Animal", "Orden", "Familia", "Especie"]]
    for (nombre, _), r in zip(imagenes, model_results):
        if len(r) > 4 and r[4] != 0:
            continue
        tabla_data.append([nombre, r[0].replace("Animal: ", ""), r[1].replace("Orden: ", ""), r[2].replace("Familia: ", ""), r[3].replace("Especie: ", "")])

    tabla = Table(tabla_data, repeatRows=1, colWidths=[4 * cm, 3 * cm, 4 * cm, 4 * cm, 5 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 30))

    logo_header1 = os.path.join(settings.BASE_DIR, "mainpage/static/mainpage/images/footer4.png")
    logo_header2 = os.path.join(settings.BASE_DIR, "mainpage/static/mainpage/images/footer5.png")
    logo_footer = os.path.join(settings.BASE_DIR, "mainpage/static/mainpage/images/footer6.2.png")

    def draw_header_footer(canvas, docx):
        # Add header/footer logos and PDF metadata on every page
        canvas.saveState()
        canvas.setAuthor("eLasmobranch")
        canvas.setTitle(f"Informe {zip_base}")
        page_width, page_height = A4
        header_y = page_height - 2.6 * cm

        if os.path.exists(logo_header1):
            canvas.drawImage(logo_header1, x=page_width - 1 * cm - 3.0 * cm, y=header_y + 0.4 * cm, width=3.0 * cm, height=2.0 * cm, preserveAspectRatio=True, mask="auto")
        if os.path.exists(logo_header2):
            canvas.drawImage(logo_header2, x=1.5 * cm, y=header_y + 0.4 * cm, width=3.0 * cm, height=2.0 * cm, preserveAspectRatio=True, mask="auto")
        if os.path.exists(logo_footer):
            footer_width = 18.0 * cm
            canvas.drawImage(logo_footer, x=(page_width - footer_width) / 2, y=0.3 * cm, width=footer_width, preserveAspectRatio=True, mask="auto")

        canvas.restoreState()

    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)

    for p in [img_especie_path, img_month_path, img_years_path, world_png, ccaa_png]:
        if p and os.path.exists(p):
            os.remove(p)
    for p in graficos_paths:
        if p and os.path.exists(p):
            os.remove(p)

    pdf_map = request.session.get("pdf_map", {})
    pdf_map[token] = {"path": pdf_path, "name": f"Informe {zip_base}.pdf"}
    request.session["pdf_map"] = pdf_map
    request.session.modified = True

    return JsonResponse({"ok": True, "download_url": reverse("mainpage:descargar_pdf_token", args=[token])})


def descargar_pdf_token(request, token):
    # Download a generated PDF by token stored in the session
    pdf_map = request.session.get("pdf_map", {})
    item = pdf_map.get(token)
    if not item:
        return HttpResponse("Not found", status=404)

    pdf_path = item.get("path")
    filename = item.get("name") or "informe.pdf"
    if not pdf_path or not os.path.exists(pdf_path):
        return HttpResponse("Not found", status=404)

    quoted_name = urllib.parse.quote(filename)
    resp = FileResponse(open(pdf_path, "rb"), content_type="application/pdf")
    resp["Content-Disposition"] = f"attachment; filename={filename}; filename*=UTF-8''{quoted_name}"
    return resp
