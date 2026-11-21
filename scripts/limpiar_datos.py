#!/usr/bin/env python3
"""
Limpieza documentada y validación de datos macroeconómicos y de morosidad
del crédito de consumo en Ecuador.

Fuentes procesadas (ubicadas en data/raw/):
- Superintendencia de Bancos del Ecuador (SB): Boletín de Series Mensuales Banca Privada (Dic 2025)
- Banco Central del Ecuador (BCE): IEM m2085 (1.10.2a, 1.10.3a, 4.2.1, 4.2.5, 4.5.1)
- Banco Mundial (World Bank API v2): Series anuales ECU (2003-2025)

Produce:
- data/processed/raw_integrado_mensual_pre_limpieza.csv (insumo reproducible para OpenRefine)
- data/processed/ecuador_sb_serie_historica_mensual.csv (2003-01 a 2025-12, n=276)
- data/processed/ecuador_morosidad_mensual_limpio.csv (2021-06 a 2025-10, n=53)
- data/processed/ecuador_morosidad_anual_limpio.csv (2003 a 2025, n=23)
- data/processed/reporte_validacion.json (pruebas de faltantes, duplicados, tipos y rangos)
"""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed"

MES_MAP = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def parse_year(val: object) -> int | None:
    if val is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(val).strip())
    return int(m.group(0)) if m else None


def parse_month(val: object) -> int | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    for nombre, num in MES_MAP.items():
        if s.startswith(nombre):
            return num
    return None


def parse_sb_monthly() -> pd.DataFrame:
    """Extrae la serie mensual de cartera y morosidad desde el ZIP oficial de la SB."""
    zip_path = RAW_DIR / "sb_series_banca_privada_dic2025.zip"
    with zipfile.ZipFile(zip_path) as zf:
        xlsx_candidates = [n for n in zf.namelist() if n.lower().endswith(".xlsx")]
        if not xlsx_candidates:
            raise ValueError("No se encontró archivo .xlsx dentro del ZIP de la SB")
        xlsx_bytes = zf.read(xlsx_candidates[0])

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb["GRAF CARTERA"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    fechas = rows[13][3:]
    mora_prod = rows[14][3:]
    mora_cons = rows[15][3:]
    mora_viv = rows[16][3:]
    mora_micro = rows[17][3:]
    mora_tot = rows[19][3:]
    comp_cons = rows[7][3:]
    cob_cons = rows[24][3:]

    registros = []
    for d, mp, mc, mv, mm, mt, cc, cob in zip(
        fechas, mora_prod, mora_cons, mora_viv, mora_micro, mora_tot, comp_cons, cob_cons
    ):
        if d is None:
            continue
        dt_val = pd.to_datetime(d)
        registros.append(
            {
                "fecha": dt_val.strftime("%Y-%m-%d"),
                "periodo": dt_val.strftime("%Y-%m"),
                "anio": int(dt_val.year),
                "mes": int(dt_val.month),
                "morosidad_consumo_pct": round(float(mc) * 100.0, 6),
                "morosidad_total_pct": round(float(mt) * 100.0, 6),
                "morosidad_productivo_pct": round(float(mp) * 100.0, 6),
                "morosidad_vivienda_pct": round(float(mv) * 100.0, 6),
                "morosidad_microcredito_pct": round(float(mm) * 100.0, 6),
                "participacion_consumo_pct": round(float(cc) * 100.0, 6),
                "cobertura_consumo_pct": round(float(cob) * 100.0, 6),
            }
        )

    df = pd.DataFrame(registros).sort_values("periodo").reset_index(drop=True)
    return df


def parse_bce_monthly(filename: str, col_map: dict[str, int], start_row: int = 9) -> pd.DataFrame:
    """Parsea tablas mensuales estandarizadas del IEM del Banco Central del Ecuador."""
    wb = openpyxl.load_workbook(RAW_DIR / filename, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    current_year: int | None = None
    registros = []
    for row in rows[start_row:]:
        if not row:
            continue
        y = parse_year(row[0] if len(row) > 0 else None)
        m = parse_month(row[1] if len(row) > 1 else None)
        if y is not None:
            current_year = y
        if current_year is not None and m is not None:
            rec: dict[str, object] = {"periodo": f"{current_year:04d}-{m:02d}"}
            has_any_val = False
            for col_name, idx in col_map.items():
                val = row[idx] if idx < len(row) else None
                if val is not None and str(val).strip() != "":
                    try:
                        rec[col_name] = float(val)
                        has_any_val = True
                    except (TypeError, ValueError):
                        rec[col_name] = np.nan
                else:
                    rec[col_name] = np.nan
            if has_any_val:
                registros.append(rec)

    return pd.DataFrame(registros).drop_duplicates(subset=["periodo"]).sort_values("periodo").reset_index(drop=True)


def parse_wb_annual(filename: str, col_name: str) -> pd.DataFrame:
    """Lee un indicador JSON descargado desde la API v2 del Banco Mundial."""
    payload = json.loads((RAW_DIR / filename).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Estructura inesperada en archivo del Banco Mundial: {filename}")
    recs = []
    for item in payload[1]:
        if item.get("value") is not None:
            recs.append({"anio": int(item["date"]), col_name: float(item["value"])})
    return pd.DataFrame(recs).sort_values("anio").reset_index(drop=True)


def classify_regime(periodo: str) -> str:
    if periodo <= "2022-06":
        return "Post-pandemia y reactivación (2021-2022 S1)"
    if periodo <= "2023-12":
        return "Normalización crediticia e inflación moderada (2022 S2-2023)"
    if periodo <= "2024-12":
        return "Desaceleración y crisis energética (2024)"
    return "Estabilización reciente (2025)"


def run_validation_suite(
    name: str,
    df: pd.DataFrame,
    key_col: str,
    required_numeric: list[str],
    bounds: dict[str, tuple[float, float]],
    iso_date_col: str | None = None,
) -> dict:
    """Ejecuta pruebas de faltantes, duplicados, tipos y rangos."""
    checks: list[dict] = []

    # 1. Faltantes
    null_counts = {c: int(df[c].isna().sum()) for c in [key_col] + required_numeric}
    total_nulls = sum(null_counts.values())
    checks.append(
        {
            "prueba": "sin_valores_faltantes",
            "estado": "PASS" if total_nulls == 0 else "FAIL",
            "detalle": f"Total nulos en columnas analíticas: {total_nulls}",
            "por_columna": null_counts,
        }
    )

    # 2. Duplicados
    dup_count = int(df[key_col].duplicated().sum())
    checks.append(
        {
            "prueba": "sin_claves_duplicadas",
            "estado": "PASS" if dup_count == 0 else "FAIL",
            "detalle": f"Registros duplicados en '{key_col}': {dup_count}",
        }
    )

    # 3. Tipos numéricos y finitud
    bad_types = []
    for col in required_numeric:
        if not pd.api.types.is_numeric_dtype(df[col]):
            bad_types.append(f"{col} ({df[col].dtype})")
        elif not np.isfinite(df[col]).all():
            bad_types.append(f"{col} (inf/nan)")
    checks.append(
        {
            "prueba": "tipos_numericos_y_finitud",
            "estado": "PASS" if not bad_types else "FAIL",
            "detalle": "Todas las columnas requeridas son numéricas finitas"
            if not bad_types
            else f"Columnas inválidas: {', '.join(bad_types)}",
        }
    )

    # 4. Formato de fecha ISO (si aplica)
    if iso_date_col is not None:
        bad_dates = int((~df[iso_date_col].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")).sum())
        checks.append(
            {
                "prueba": "formato_fecha_iso",
                "estado": "PASS" if bad_dates == 0 else "FAIL",
                "detalle": f"Fechas fuera de formato YYYY-MM-DD en '{iso_date_col}': {bad_dates}",
            }
        )

    # 5. Orden cronológico estricto
    is_sorted = bool(df[key_col].is_monotonic_increasing)
    checks.append(
        {
            "prueba": "orden_cronologico_estricto",
            "estado": "PASS" if is_sorted else "FAIL",
            "detalle": f"Columna '{key_col}' ordenada ascendentemente: {is_sorted}",
        }
    )

    # 6. Rangos económicos válidos
    out_of_range = {}
    for col, (lo, hi) in bounds.items():
        if col in df.columns:
            mn, mx = float(df[col].min()), float(df[col].max())
            if mn < lo or mx > hi:
                out_of_range[col] = {"min": mn, "max": mx, "esperado": [lo, hi]}
    checks.append(
        {
            "prueba": "rangos_economicos_validos",
            "estado": "PASS" if not out_of_range else "FAIL",
            "detalle": "Todos los indicadores dentro de rangos económicos plausibles"
            if not out_of_range
            else f"Fuera de rango: {out_of_range}",
        }
    )

    passed = all(c["estado"] == "PASS" for c in checks)
    return {
        "dataset": name,
        "filas": int(len(df)),
        "columnas": int(df.shape[1]),
        "rango_clave": [str(df[key_col].iloc[0]), str(df[key_col].iloc[-1])],
        "estado_global": "PASS" if passed else "FAIL",
        "pruebas": checks,
    }


def main() -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Serie histórica completa SB (2003-01 a 2025-12)
    df_sb = parse_sb_monthly()
    df_sb.to_csv(PROC_DIR / "ecuador_sb_serie_historica_mensual.csv", index=False)

    # 2. Tablas mensuales BCE
    df_tasas = parse_bce_monthly(
        "bce_IEM-1102a-e.xlsx",
        {"tasa_consumo_pct": 8, "tasa_max_consumo_pct": 9},
    )
    df_monto = parse_bce_monthly(
        "bce_IEM-1103a-e.xlsx",
        {"monto_consumo_musd": 5},
    )
    df_ipc = parse_bce_monthly(
        "bce_IEM-421-e.xlsx",
        {"ipc_indice": 2, "inflacion_anual_pct": 3, "inflacion_mensual_pct": 4},
    )
    df_lab = parse_bce_monthly(
        "bce_IEM-425-e.xlsx",
        {"empleo_adecuado_pct": 3, "subempleo_pct": 5, "desempleo_pct": 8},
    )

    # 3. Extracto crudo mensual integrado (2021-01 a 2025-12) ANTES de limpieza
    # Este archivo es exactamente el insumo tabular sobre el que aplica OpenRefine
    df_sb_2021 = df_sb[df_sb["anio"] >= 2021].copy()
    df_raw_m = (
        df_sb_2021[
            [
                "fecha",
                "periodo",
                "anio",
                "mes",
                "morosidad_consumo_pct",
                "morosidad_total_pct",
                "participacion_consumo_pct",
                "cobertura_consumo_pct",
            ]
        ]
        .merge(df_lab, on="periodo", how="left")
        .merge(df_ipc, on="periodo", how="left")
        .merge(df_tasas, on="periodo", how="left")
        .merge(df_monto, on="periodo", how="left")
        .sort_values("periodo")
        .reset_index(drop=True)
    )
    df_raw_m.to_csv(PROC_DIR / "raw_integrado_mensual_pre_limpieza.csv", index=False)

    # Registro explícito de filas excluidas en la limpieza (cero imputación inventada)
    cols_modelo_mensual = [
        "morosidad_consumo_pct",
        "desempleo_pct",
        "empleo_adecuado_pct",
        "subempleo_pct",
        "inflacion_anual_pct",
        "tasa_consumo_pct",
        "monto_consumo_musd",
    ]
    mask_complete = df_raw_m[cols_modelo_mensual].notna().all(axis=1)
    filas_excluidas = df_raw_m.loc[~mask_complete, ["periodo"] + cols_modelo_mensual]
    auditoria_exclusiones = []
    for _, row in filas_excluidas.iterrows():
        faltantes = [c for c in cols_modelo_mensual if pd.isna(row[c])]
        auditoria_exclusiones.append(
            {
                "periodo": str(row["periodo"]),
                "columnas_faltantes": faltantes,
                "motivo": (
                    "Anterior a vigencia de segmentación unificada 'Consumo' (May 2021)"
                    if str(row["periodo"]) < "2021-05"
                    else (
                        "Mes de transición normativa sin tasa activa efectiva referencial publicada"
                        if str(row["periodo"]) == "2021-05"
                        else "Cierre aún no publicado en boletín ENEMDU / IEM m2085"
                    )
                ),
            }
        )

    # 4. Dataset mensual limpio (2021-06 a 2025-10, n=53)
    df_m = df_raw_m.loc[mask_complete].copy()
    df_m = df_m.drop_duplicates(subset=["periodo"]).sort_values("periodo").reset_index(drop=True)

    # Normalización de tipos y variables derivadas (equivalentes a OpenRefine)
    for c in [
        "morosidad_consumo_pct",
        "morosidad_total_pct",
        "participacion_consumo_pct",
        "cobertura_consumo_pct",
        "empleo_adecuado_pct",
        "subempleo_pct",
        "desempleo_pct",
        "ipc_indice",
        "inflacion_anual_pct",
        "inflacion_mensual_pct",
        "tasa_consumo_pct",
        "tasa_max_consumo_pct",
        "monto_consumo_musd",
    ]:
        df_m[c] = pd.to_numeric(df_m[c], errors="raise").round(6)

    df_m["log_monto_consumo"] = np.log(df_m["monto_consumo_musd"]).round(6)
    df_m["tasa_real_aprox_pct"] = (df_m["tasa_consumo_pct"] - df_m["inflacion_anual_pct"]).round(6)
    df_m["brecha_tasa_maxima_pct"] = (df_m["tasa_max_consumo_pct"] - df_m["tasa_consumo_pct"]).round(6)
    df_m["regimen_coyuntural"] = df_m["periodo"].map(classify_regime)

    # Primeras diferencias mensuales (para robustez ante autocorrelación / tendencia)
    df_m["d_morosidad_consumo_pct"] = df_m["morosidad_consumo_pct"].diff().round(6)
    df_m["d_desempleo_pct"] = df_m["desempleo_pct"].diff().round(6)
    df_m["d_inflacion_anual_pct"] = df_m["inflacion_anual_pct"].diff().round(6)
    df_m["d_tasa_consumo_pct"] = df_m["tasa_consumo_pct"].diff().round(6)
    df_m["d_log_monto_consumo"] = df_m["log_monto_consumo"].diff().round(6)

    df_m.to_csv(PROC_DIR / "ecuador_morosidad_mensual_limpio.csv", index=False)

    # 5. Dataset anual de largo plazo (2003 a 2025, n=23): SB + Banco Mundial API
    df_sb_anual = (
        df_sb.groupby("anio", as_index=False)
        .agg(
            morosidad_consumo_pct=("morosidad_consumo_pct", "mean"),
            morosidad_consumo_dic_pct=("morosidad_consumo_pct", "last"),
            morosidad_total_pct=("morosidad_total_pct", "mean"),
            participacion_consumo_pct=("participacion_consumo_pct", "mean"),
            cobertura_consumo_pct=("cobertura_consumo_pct", "mean"),
            meses_reportados=("mes", "count"),
        )
    )
    wb_series = [
        ("wb_ECU_NY.GDP.MKTP.KD.ZG.json", "pib_crecimiento_pct"),
        ("wb_ECU_SL.UEM.TOTL.ZS.json", "desempleo_pct"),
        ("wb_ECU_FP.CPI.TOTL.ZG.json", "inflacion_anual_pct"),
        ("wb_ECU_BX.TRF.PWKR.DT.GD.ZS.json", "remesas_pib_pct"),
        ("wb_ECU_FS.AST.PRVT.GD.ZS.json", "credito_privado_pib_pct"),
        ("wb_ECU_NE.CON.PRVT.KD.ZG.json", "consumo_hogares_crec_pct"),
        ("wb_ECU_FB.AST.NPER.ZS.json", "morosidad_fmi_bm_pct"),
    ]
    df_a = df_sb_anual.copy()
    for fn, col in wb_series:
        df_a = df_a.merge(parse_wb_annual(fn, col), on="anio", how="inner")

    df_a = df_a.drop_duplicates(subset=["anio"]).sort_values("anio").reset_index(drop=True)
    df_a["fecha_cierre"] = df_a["anio"].map(lambda y: f"{int(y):04d}-12-31")
    for c in df_a.columns:
        if c not in ("anio", "meses_reportados", "fecha_cierre"):
            df_a[c] = pd.to_numeric(df_a[c], errors="raise").round(6)

    df_a["d_morosidad_consumo_pct"] = df_a["morosidad_consumo_pct"].diff().round(6)
    df_a["d_pib_crecimiento_pct"] = df_a["pib_crecimiento_pct"].diff().round(6)
    df_a["d_desempleo_pct"] = df_a["desempleo_pct"].diff().round(6)
    df_a["d_inflacion_anual_pct"] = df_a["inflacion_anual_pct"].diff().round(6)
    df_a["d_credito_privado_pib_pct"] = df_a["credito_privado_pib_pct"].diff().round(6)

    df_a.to_csv(PROC_DIR / "ecuador_morosidad_anual_limpio.csv", index=False)

    # 6. Suite de pruebas de validación
    reportes = [
        run_validation_suite(
            name="ecuador_sb_serie_historica_mensual",
            df=df_sb,
            key_col="periodo",
            required_numeric=[
                "morosidad_consumo_pct",
                "morosidad_total_pct",
                "participacion_consumo_pct",
                "cobertura_consumo_pct",
            ],
            bounds={
                "morosidad_consumo_pct": (0.5, 25.0),
                "morosidad_total_pct": (0.5, 25.0),
                "participacion_consumo_pct": (10.0, 65.0),
                "cobertura_consumo_pct": (30.0, 600.0),
            },
            iso_date_col="fecha",
        ),
        run_validation_suite(
            name="ecuador_morosidad_mensual_limpio",
            df=df_m,
            key_col="periodo",
            required_numeric=[
                "morosidad_consumo_pct",
                "morosidad_total_pct",
                "desempleo_pct",
                "empleo_adecuado_pct",
                "subempleo_pct",
                "inflacion_anual_pct",
                "tasa_consumo_pct",
                "monto_consumo_musd",
                "log_monto_consumo",
            ],
            bounds={
                "morosidad_consumo_pct": (1.0, 15.0),
                "desempleo_pct": (1.0, 15.0),
                "empleo_adecuado_pct": (20.0, 60.0),
                "subempleo_pct": (5.0, 40.0),
                "inflacion_anual_pct": (-5.0, 15.0),
                "tasa_consumo_pct": (10.0, 20.0),
                "monto_consumo_musd": (200.0, 3000.0),
            },
            iso_date_col="fecha",
        ),
        run_validation_suite(
            name="ecuador_morosidad_anual_limpio",
            df=df_a,
            key_col="anio",
            required_numeric=[
                "morosidad_consumo_pct",
                "morosidad_total_pct",
                "pib_crecimiento_pct",
                "desempleo_pct",
                "inflacion_anual_pct",
                "remesas_pib_pct",
                "credito_privado_pib_pct",
                "morosidad_fmi_bm_pct",
            ],
            bounds={
                "morosidad_consumo_pct": (1.0, 20.0),
                "pib_crecimiento_pct": (-15.0, 15.0),
                "desempleo_pct": (1.0, 15.0),
                "inflacion_anual_pct": (-5.0, 20.0),
                "remesas_pib_pct": (0.5, 15.0),
                "credito_privado_pib_pct": (10.0, 100.0),
            },
            iso_date_col="fecha_cierre",
        ),
    ]

    global_pass = all(r["estado_global"] == "PASS" for r in reportes)
    resumen = {
        "estado_global": "PASS" if global_pass else "FAIL",
        "filas_crudas_mensuales_2021_2025": int(len(df_raw_m)),
        "filas_limpias_mensuales": int(len(df_m)),
        "filas_excluidas_por_ventana_completa": len(auditoria_exclusiones),
        "detalle_exclusiones": auditoria_exclusiones,
        "validaciones": reportes,
    }
    (PROC_DIR / "reporte_validacion.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("=== REPORTE DE LIMPIEZA Y VALIDACIÓN ===")
    for r in reportes:
        print(f"- {r['dataset']}: {r['estado_global']} (n={r['filas']}, rango={r['rango_clave'][0]}..{r['rango_clave'][1]})")
    print(f"Exclusiones documentadas (sin imputación): {len(auditoria_exclusiones)} meses")

    if not global_pass:
        print("ERROR: Al menos una prueba de validación falló.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
