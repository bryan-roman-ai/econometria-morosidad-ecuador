#!/usr/bin/env python3
"""
Descarga reproducible de fuentes públicas oficiales para Ecuador:
1. Superintendencia de Bancos del Ecuador (SB) - Boletín de Series Mensuales Banca Privada
2. Banco Central del Ecuador (BCE) - Información Estadística Mensual (IEM)
3. Banco Mundial (World Bank Open Data API v2) - Indicadores macroeconómicos de Ecuador (ECU)

Registra URL exacta, fecha de descarga (ISO 8601), tamaño y hash SHA-256
en data/raw/fuentes_descarga.json.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import ssl
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/octet-stream, */*",
    "Referer": "https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos-2/",
}

# Contexto SSL estándar con fallback si alguna entidad pública presenta cadena intermedia incompleta
def make_ssl_context(verify: bool = True) -> ssl.SSLContext:
    if verify:
        return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


SOURCES = [
    # 1. Superintendencia de Bancos del Ecuador
    {
        "id": "sb_series_banca_privada_2025",
        "institucion": "Superintendencia de Bancos del Ecuador (SB)",
        "titulo": "Boletín de Series Mensuales - Total Subsistema Banca Privada (Corte Diciembre 2025)",
        "pagina_origen": "https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos-2/",
        "url": (
            "https://www.superbancos.gob.ec/estadisticas/portalestudios/wp-admin/admin-ajax.php"
            "?action=shareonedrive-download&dl=1"
            "&id=01ONK3WL67DUF43B6SYBBJEJJ2KZ7WR2S4"
            "&account_id=341c37a6-daa9-4b83-adad-506b00ccb984"
            "&drive_id=b!Iz-mji9B1EqK1eiAuGWU7x82x3m7uftFja_xK_rSLWY6gLR41EOqTYg222Ho8lwD"
            "&listtoken=cb2dcac486c20e9c7a63b3bc95e58f46"
        ),
        "archivo": "sb_series_banca_privada_dic2025.zip",
        "frecuencia": "Mensual (2003-2025)",
    },
    # 2. Banco Central del Ecuador - IEM (Publicación m2085 - Noviembre 2025)
    {
        "id": "bce_iem_1102_tasas_2015_2021",
        "institucion": "Banco Central del Ecuador (BCE)",
        "titulo": "IEM 1.10.2 Tasas de Interés Activas Efectivas Referenciales por Segmento (Ago 2015 - Abr 2021)",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-1102-e.xlsx",
        "archivo": "bce_IEM-1102-e.xlsx",
        "frecuencia": "Mensual (2015-08 a 2021-04)",
    },
    {
        "id": "bce_iem_1102a_tasas_2021_2025",
        "institucion": "Banco Central del Ecuador (BCE)",
        "titulo": "IEM 1.10.2a Tasas de Interés Activas Efectivas Referenciales por Segmento (Desde May 2021)",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-1102a-e.xlsx",
        "archivo": "bce_IEM-1102a-e.xlsx",
        "frecuencia": "Mensual (2021-05 a 2025-11)",
    },
    {
        "id": "bce_iem_1103_monto_2015_2021",
        "institucion": "Banco Central del Ecuador (BCE)",
        "titulo": "IEM 1.10.3 Monto de Operaciones Activas por Segmento (Sep 2015 - Abr 2021)",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-1103-e.xlsx",
        "archivo": "bce_IEM-1103-e.xlsx",
        "frecuencia": "Mensual (2015-09 a 2021-04)",
    },
    {
        "id": "bce_iem_1103a_monto_2021_2025",
        "institucion": "Banco Central del Ecuador (BCE)",
        "titulo": "IEM 1.10.3a Monto de Operaciones Activas por Segmento (Desde May 2021)",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-1103a-e.xlsx",
        "archivo": "bce_IEM-1103a-e.xlsx",
        "frecuencia": "Mensual (2021-05 a 2025-11)",
    },
    {
        "id": "bce_iem_421_ipc",
        "institucion": "Banco Central del Ecuador (BCE) / INEC",
        "titulo": "IEM 4.2.1 Índice de Precios al Consumidor (IPC) e Inflación Anual/Mensual",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-421-e.xlsx",
        "archivo": "bce_IEM-421-e.xlsx",
        "frecuencia": "Mensual",
    },
    {
        "id": "bce_iem_425_laboral",
        "institucion": "Banco Central del Ecuador (BCE) / INEC",
        "titulo": "IEM 4.2.5 Indicadores del Mercado Laboral Nacional, Urbano y Rural",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-425-e.xlsx",
        "archivo": "bce_IEM-425-e.xlsx",
        "frecuencia": "Mensual",
    },
    {
        "id": "bce_iem_451_confianza",
        "institucion": "Banco Central del Ecuador (BCE)",
        "titulo": "IEM 4.5.1 Índice de Confianza del Consumidor Nacional",
        "pagina_origen": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html",
        "url": "https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-451-e.xlsx",
        "archivo": "bce_IEM-451-e.xlsx",
        "frecuencia": "Mensual",
    },
    # 3. API del Banco Mundial (World Bank Open Data API v2 - Ecuador)
    {
        "id": "wb_pib_crecimiento",
        "institucion": "Banco Mundial (World Bank Open Data API v2)",
        "titulo": "Crecimiento del PIB real anual (%) - NY.GDP.MKTP.KD.ZG",
        "pagina_origen": "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/NY.GDP.MKTP.KD.ZG?format=json&per_page=100",
        "archivo": "wb_ECU_NY.GDP.MKTP.KD.ZG.json",
        "frecuencia": "Anual",
    },
    {
        "id": "wb_desempleo_ilo",
        "institucion": "Banco Mundial / OIT (World Bank Open Data API v2)",
        "titulo": "Desempleo total (% población activa, estimación modelada OIT) - SL.UEM.TOTL.ZS",
        "pagina_origen": "https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/SL.UEM.TOTL.ZS?format=json&per_page=100",
        "archivo": "wb_ECU_SL.UEM.TOTL.ZS.json",
        "frecuencia": "Anual",
    },
    {
        "id": "wb_inflacion_ipc",
        "institucion": "Banco Mundial / FMI (World Bank Open Data API v2)",
        "titulo": "Inflación, precios al consumidor (% anual) - FP.CPI.TOTL.ZG",
        "pagina_origen": "https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/FP.CPI.TOTL.ZG?format=json&per_page=100",
        "archivo": "wb_ECU_FP.CPI.TOTL.ZG.json",
        "frecuencia": "Anual",
    },
    {
        "id": "wb_remesas_pib",
        "institucion": "Banco Mundial (World Bank Open Data API v2)",
        "titulo": "Remesas personales recibidas (% del PIB) - BX.TRF.PWKR.DT.GD.ZS",
        "pagina_origen": "https://data.worldbank.org/indicator/BX.TRF.PWKR.DT.GD.ZS?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/BX.TRF.PWKR.DT.GD.ZS?format=json&per_page=100",
        "archivo": "wb_ECU_BX.TRF.PWKR.DT.GD.ZS.json",
        "frecuencia": "Anual",
    },
    {
        "id": "wb_credito_privado_pib",
        "institucion": "Banco Mundial / FMI (World Bank Open Data API v2)",
        "titulo": "Crédito interno al sector privado (% del PIB) - FS.AST.PRVT.GD.ZS",
        "pagina_origen": "https://data.worldbank.org/indicator/FS.AST.PRVT.GD.ZS?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/FS.AST.PRVT.GD.ZS?format=json&per_page=100",
        "archivo": "wb_ECU_FS.AST.PRVT.GD.ZS.json",
        "frecuencia": "Anual",
    },
    {
        "id": "wb_consumo_hogares",
        "institucion": "Banco Mundial (World Bank Open Data API v2)",
        "titulo": "Crecimiento del gasto de consumo final de los hogares (% anual) - NE.CON.PRVT.KD.ZG",
        "pagina_origen": "https://data.worldbank.org/indicator/NE.CON.PRVT.KD.ZG?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/NE.CON.PRVT.KD.ZG?format=json&per_page=100",
        "archivo": "wb_ECU_NE.CON.PRVT.KD.ZG.json",
        "frecuencia": "Anual",
    },
    {
        "id": "wb_morosidad_bancaria_total_fmi",
        "institucion": "Banco Mundial / FMI FSI (World Bank Open Data API v2)",
        "titulo": "Préstamos bancarios en mora respecto al total de préstamos brutos (%) - FB.AST.NPER.ZS",
        "pagina_origen": "https://data.worldbank.org/indicator/FB.AST.NPER.ZS?locations=EC",
        "url": "https://api.worldbank.org/v2/country/ECU/indicator/FB.AST.NPER.ZS?format=json&per_page=100",
        "archivo": "wb_ECU_FB.AST.NPER.ZS.json",
        "frecuencia": "Anual",
    },
]


def download_file(url: str, dest: Path) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=HEADERS)
    last_err: Exception | None = None
    for verify in (True, False):
        try:
            with urllib.request.urlopen(req, timeout=90, context=make_ssl_context(verify)) as resp:
                data = resp.read()
            dest.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            return len(data), sha
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"No se pudo descargar {url}: {last_err}")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    for src in SOURCES:
        dest = RAW_DIR / src["archivo"]
        print(f"Descargando {src['id']} -> {dest.name} ...")
        size, sha256 = download_file(src["url"], dest)
        now_utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        now_ec = (
            dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))
            .replace(microsecond=0)
            .isoformat()
        )
        entry = {
            **src,
            "fecha_descarga_utc": now_utc,
            "fecha_descarga_ecuador": now_ec,
            "bytes": size,
            "sha256": sha256,
        }
        manifest.append(entry)
        print(f"  OK ({size:,} bytes, sha256={sha256[:12]}...)")
        time.sleep(0.25)

    manifest_path = RAW_DIR / "fuentes_descarga.json"
    manifest_path.write_text(
        json.dumps(
            {
                "proyecto": "econometria-morosidad-ecuador",
                "fecha_generacion_ecuador": dt.datetime.now(
                    dt.timezone(dt.timedelta(hours=-5))
                )
                .replace(microsecond=0)
                .isoformat(),
                "archivos": manifest,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nManifiesto guardado en {manifest_path}")


if __name__ == "__main__":
    main()
