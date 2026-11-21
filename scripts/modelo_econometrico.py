#!/usr/bin/env python3
"""
Estimación econométrica (MCO / OLS con statsmodels), pruebas de supuestos
clásicos y exportación de tablas listas para Tableau Public.

Modelos estimados con datos 100% oficiales (SB, BCE, Banco Mundial):
1. mensual_niveles (Jun 2021 - Oct 2025, n=53): MCO + errores robustos Newey-West HAC
2. mensual_diferencias (Jul 2021 - Oct 2025, n=52): Robustez en primeras diferencias
3. anual_niveles (2003 - 2025, n=23): Serie estructural larga (SB + API Banco Mundial)
4. anual_diferencias (2004 - 2025, n=22): Primeras diferencias anuales (SB + Banco Mundial)

Diagnósticos calculados con statsmodels y scipy:
- Normalidad de residuos: Shapiro-Wilk y Jarque-Bera
- Heterocedasticidad: Breusch-Pagan
- Multicolinealidad: Factor de Inflación de la Varianza (VIF)
- Autocorrelación: Durbin-Watson y Breusch-Godfrey (rezago 1)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROC_DIR = BASE_DIR / "data" / "processed"
TABLEAU_DIR = BASE_DIR / "tableau"

LABELS_ES = {
    "const": "Intercepto (β₀)",
    "desempleo_pct": "Desempleo nacional (%)",
    "inflacion_anual_pct": "Inflación anual IPC (%)",
    "tasa_consumo_pct": "Tasa activa referencial consumo (%)",
    "log_monto_consumo": "Log monto crédito consumo (ln MUSD)",
    "d_desempleo_pct": "Δ Desempleo nacional (pp)",
    "d_inflacion_anual_pct": "Δ Inflación anual IPC (pp)",
    "d_tasa_consumo_pct": "Δ Tasa activa consumo (pp)",
    "d_log_monto_consumo": "Δ Log monto consumo (≈ tasa crec.)",
    "pib_crecimiento_pct": "Crecimiento PIB real (%)",
    "credito_privado_pib_pct": "Crédito interno privado (% PIB)",
    "remesas_pib_pct": "Remesas personales (% PIB)",
    "d_pib_crecimiento_pct": "Δ Crecimiento PIB real (pp)",
    "d_credito_privado_pib_pct": "Δ Crédito privado / PIB (pp)",
}


def fit_and_diagnose(
    model_id: str,
    titulo: str,
    ecuacion: str,
    df: pd.DataFrame,
    period_col: str,
    y_col: str,
    x_cols: list[str],
    hac_lags: int,
) -> tuple[dict, pd.Series, pd.Series]:
    sub = df[[period_col, y_col] + x_cols].dropna().reset_index(drop=True)
    X = sm.add_constant(sub[x_cols])
    y = sub[y_col]

    ols = sm.OLS(y, X).fit()
    hac = ols.get_robustcov_results(cov_type="HAC", maxlags=hac_lags)

    resid = ols.resid
    fitted = ols.fittedvalues

    # Supuesto 1: Normalidad
    sw_stat, sw_p = stats.shapiro(resid)
    jb_stat, jb_p, skew, kurt = jarque_bera(resid)

    # Supuesto 2: Heterocedasticidad (Breusch-Pagan)
    bp_lm, bp_lmp, bp_f, bp_fp = het_breuschpagan(resid, X)

    # Supuesto 3: Multicolinealidad (VIF)
    vifs = []
    for idx, col in enumerate(x_cols):
        vif_val = float(variance_inflation_factor(X.values, idx + 1))
        vifs.append(
            {
                "variable": col,
                "etiqueta": LABELS_ES.get(col, col),
                "vif": round(vif_val, 4),
                "alerta": vif_val >= 5.0,
            }
        )
    max_vif = max(v["vif"] for v in vifs)

    # Supuesto 4: Autocorrelación (Durbin-Watson + Breusch-Godfrey orden 1)
    dw = float(durbin_watson(resid))
    bg_lm, bg_lmp, bg_f, bg_fp = acorr_breusch_godfrey(ols, nlags=1, result_object=False)

    # Tabla de coeficientes (OLS + HAC + IC 95%)
    ci_ols = ols.conf_int(alpha=0.05)
    ci_hac = hac.conf_int(alpha=0.05)
    coeficientes = []
    for i, name in enumerate(X.columns):
        coeficientes.append(
            {
                "variable": name,
                "etiqueta": LABELS_ES.get(name, name),
                "coef": round(float(ols.params[name]), 6),
                "se_ols": round(float(ols.bse[name]), 6),
                "t_ols": round(float(ols.tvalues[name]), 4),
                "p_ols": round(float(ols.pvalues[name]), 6),
                "ic95_ols": [
                    round(float(ci_ols.loc[name, 0]), 6),
                    round(float(ci_ols.loc[name, 1]), 6),
                ],
                "se_hac": round(float(hac.bse[i]), 6),
                "t_hac": round(float(hac.tvalues[i]), 4),
                "p_hac": round(float(hac.pvalues[i]), 6),
                "ic95_hac": [
                    round(float(ci_hac[i, 0]), 6),
                    round(float(ci_hac[i, 1]), 6),
                ],
                "significativo_5pct_hac": bool(hac.pvalues[i] < 0.05),
            }
        )

    # Evaluaciones legibles de supuestos
    dw_estado = (
        "Aceptable (sin autocorrelación severa)"
        if 1.5 <= dw <= 2.5
        else (
            "Autocorrelación positiva detectada (se aplican errores HAC y primeras diferencias)"
            if dw < 1.5
            else "Autocorrelación negativa detectada"
        )
    )

    result = {
        "id": model_id,
        "titulo": titulo,
        "ecuacion": ecuacion,
        "rango_muestral": [str(sub[period_col].iloc[0]), str(sub[period_col].iloc[-1])],
        "n": int(ols.nobs),
        "k_regresores": len(x_cols),
        "hac_lags": hac_lags,
        "bondad_ajuste": {
            "r2": round(float(ols.rsquared), 6),
            "r2_ajustado": round(float(ols.rsquared_adj), 6),
            "f_estadistico": round(float(ols.fvalue), 4),
            "f_pvalor": float(f"{ols.f_pvalue:.6e}"),
            "rmse": round(float(np.sqrt(np.mean(resid**2))), 6),
            "aic": round(float(ols.aic), 4),
            "bic": round(float(ols.bic), 4),
        },
        "coeficientes": coeficientes,
        "supuestos": {
            "normalidad": {
                "shapiro_w": round(float(sw_stat), 4),
                "shapiro_p": round(float(sw_p), 6),
                "jarque_bera": round(float(jb_stat), 4),
                "jarque_bera_p": round(float(jb_p), 6),
                "asimetria": round(float(skew), 4),
                "curtosis": round(float(kurt), 4),
                "cumple_5pct": bool(sw_p >= 0.05),
                "conclusion": (
                    "No se rechaza normalidad de residuos al 5%."
                    if sw_p >= 0.05
                    else "Se rechaza normalidad estricta al 5% (colas pesadas por episodios coyunturales)."
                ),
            },
            "heterocedasticidad_breusch_pagan": {
                "lm_estadistico": round(float(bp_lm), 4),
                "lm_pvalor": round(float(bp_lmp), 6),
                "f_estadistico": round(float(bp_f), 4),
                "f_pvalor": round(float(bp_fp), 6),
                "cumple_5pct": bool(bp_lmp >= 0.05),
                "conclusion": (
                    "No se rechaza homocedasticidad al 5% (errores HAC reportados como resguardo)."
                    if bp_lmp >= 0.05
                    else "Se detecta heterocedasticidad al 5%; inferencia respaldada con errores Newey-West HAC."
                ),
            },
            "multicolinealidad_vif": {
                "max_vif": round(max_vif, 4),
                "cumple_umbral_5": bool(max_vif < 5.0),
                "por_variable": vifs,
                "conclusion": (
                    f"Sin multicolinealidad severa (VIF máximo = {max_vif:.2f} < 5)."
                    if max_vif < 5.0
                    else f"Alerta de multicolinealidad (VIF máximo = {max_vif:.2f} ≥ 5)."
                ),
            },
            "autocorrelacion": {
                "durbin_watson": round(dw, 4),
                "breusch_godfrey_lm1": round(float(bg_lm), 4),
                "breusch_godfrey_p1": round(float(bg_lmp), 6),
                "cumple_rango_dw": bool(1.5 <= dw <= 2.5),
                "conclusion": dw_estado,
            },
        },
        "observaciones": [
            {
                "periodo": str(sub[period_col].iloc[idx]),
                "y_observado": round(float(y.iloc[idx]), 6),
                "y_ajustado": round(float(fitted.iloc[idx]), 6),
                "residuo": round(float(resid.iloc[idx]), 6),
            }
            for idx in range(len(sub))
        ],
    }
    return result, fitted, resid


def main() -> None:
    TABLEAU_DIR.mkdir(parents=True, exist_ok=True)

    df_sb = pd.read_csv(PROC_DIR / "ecuador_sb_serie_historica_mensual.csv")
    df_m = pd.read_csv(PROC_DIR / "ecuador_morosidad_mensual_limpio.csv")
    df_a = pd.read_csv(PROC_DIR / "ecuador_morosidad_anual_limpio.csv")
    fuentes = json.loads((RAW_DIR / "fuentes_descarga.json").read_text(encoding="utf-8"))
    validacion = json.loads((PROC_DIR / "reporte_validacion.json").read_text(encoding="utf-8"))

    # 1. Modelo principal mensual en niveles (2021-06 a 2025-10, n=53)
    m_niveles, fit_m, res_m = fit_and_diagnose(
        model_id="mensual_niveles",
        titulo="Modelo 1: MCO Mensual en Niveles (Jun 2021 – Oct 2025)",
        ecuacion=(
            "MorosidadConsumo_t = β₀ + β₁·Desempleo_t + β₂·InflaciónIPC_t "
            "+ β₃·TasaConsumo_t + β₄·ln(MontoConsumo_t) + ε_t"
        ),
        df=df_m,
        period_col="periodo",
        y_col="morosidad_consumo_pct",
        x_cols=["desempleo_pct", "inflacion_anual_pct", "tasa_consumo_pct", "log_monto_consumo"],
        hac_lags=3,
    )

    # 2. Modelo mensual en primeras diferencias (2021-07 a 2025-10, n=52)
    m_dif, _, _ = fit_and_diagnose(
        model_id="mensual_diferencias",
        titulo="Modelo 2: MCO Mensual en Primeras Diferencias (Jul 2021 – Oct 2025)",
        ecuacion=(
            "ΔMorosidadConsumo_t = α₀ + α₁·ΔDesempleo_t + α₂·ΔInflaciónIPC_t "
            "+ α₃·ΔTasaConsumo_t + α₄·Δln(MontoConsumo_t) + u_t"
        ),
        df=df_m,
        period_col="periodo",
        y_col="d_morosidad_consumo_pct",
        x_cols=["d_desempleo_pct", "d_inflacion_anual_pct", "d_tasa_consumo_pct", "d_log_monto_consumo"],
        hac_lags=2,
    )

    # 3. Modelo anual estructural en niveles (2003 - 2025, n=23)
    a_niveles, fit_a, res_a = fit_and_diagnose(
        model_id="anual_niveles",
        titulo="Modelo 3: MCO Anual de Largo Plazo en Niveles (2003 – 2025)",
        ecuacion=(
            "MorosidadConsumo_t = γ₀ + γ₁·PIB_t + γ₂·Desempleo_t "
            "+ γ₃·InflaciónIPC_t + γ₄·CréditoPrivadoPIB_t + ν_t"
        ),
        df=df_a,
        period_col="anio",
        y_col="morosidad_consumo_pct",
        x_cols=["pib_crecimiento_pct", "desempleo_pct", "inflacion_anual_pct", "credito_privado_pib_pct"],
        hac_lags=2,
    )

    # 4. Modelo anual en primeras diferencias (2004 - 2025, n=22)
    a_dif, _, _ = fit_and_diagnose(
        model_id="anual_diferencias",
        titulo="Modelo 4: MCO Anual en Primeras Diferencias (2004 – 2025)",
        ecuacion=(
            "ΔMorosidadConsumo_t = δ₀ + δ₁·ΔPIB_t + δ₂·ΔDesempleo_t "
            "+ δ₃·ΔInflaciónIPC_t + δ₄·ΔCréditoPrivadoPIB_t + ω_t"
        ),
        df=df_a,
        period_col="anio",
        y_col="d_morosidad_consumo_pct",
        x_cols=["d_pib_crecimiento_pct", "d_desempleo_pct", "d_inflacion_anual_pct", "d_credito_privado_pib_pct"],
        hac_lags=1,
    )

    # Correlaciones de Pearson bivariadas (mensual niveles y diferencias)
    corr_vars = [
        "morosidad_consumo_pct",
        "desempleo_pct",
        "empleo_adecuado_pct",
        "subempleo_pct",
        "inflacion_anual_pct",
        "tasa_consumo_pct",
        "log_monto_consumo",
    ]
    correlaciones_mensuales = {}
    for col in corr_vars[1:]:
        r, p = stats.pearsonr(df_m["morosidad_consumo_pct"], df_m[col])
        correlaciones_mensuales[col] = {
            "etiqueta": LABELS_ES.get(col, col),
            "r_pearson": round(float(r), 4),
            "p_valor": round(float(p), 6),
        }

    # Estadísticas descriptivas clave
    desc_cols = [
        "morosidad_consumo_pct",
        "morosidad_total_pct",
        "desempleo_pct",
        "inflacion_anual_pct",
        "tasa_consumo_pct",
        "monto_consumo_musd",
    ]
    descriptivas_mensuales = {}
    for col in desc_cols:
        s = df_m[col]
        descriptivas_mensuales[col] = {
            "media": round(float(s.mean()), 4),
            "desv_est": round(float(s.std(ddof=1)), 4),
            "min": round(float(s.min()), 4),
            "mediana": round(float(s.median()), 4),
            "max": round(float(s.max()), 4),
        }

    # Exportar CSV finales listos para Tableau Public
    df_tab_m = df_m.copy()
    df_tab_m["prediccion_ols_niveles_pct"] = fit_m.round(6).values
    df_tab_m["residuo_ols_niveles_pp"] = res_m.round(6).values
    df_tab_m["pais"] = "Ecuador"
    df_tab_m["fuente_morosidad"] = "Superintendencia de Bancos (Banca Privada)"
    df_tab_m["fuente_macro"] = "Banco Central del Ecuador (IEM m2085 / INEC)"
    df_tab_m.to_csv(TABLEAU_DIR / "ecuador_morosidad_consumo_mensual_tableau.csv", index=False)

    df_tab_a = df_a.copy()
    df_tab_a["prediccion_ols_anual_pct"] = fit_a.round(6).values
    df_tab_a["residuo_ols_anual_pp"] = res_a.round(6).values
    df_tab_a["pais"] = "Ecuador"
    df_tab_a["fuente_morosidad"] = "Superintendencia de Bancos (Banca Privada)"
    df_tab_a["fuente_macro"] = "Banco Mundial (API v2 - ECU)"
    df_tab_a.to_csv(TABLEAU_DIR / "ecuador_morosidad_consumo_anual_tableau.csv", index=False)

    # Ensamblar JSON maestro de resultados (también alimentará app.js)
    # Incluimos las series completas verificadas para renderizado SVG 100% fiel
    sb_hist_records = df_sb[
        [
            "periodo",
            "anio",
            "mes",
            "morosidad_consumo_pct",
            "morosidad_total_pct",
            "participacion_consumo_pct",
            "cobertura_consumo_pct",
        ]
    ].round(4).to_dict(orient="records")

    mensual_records = df_tab_m[
        [
            "periodo",
            "fecha",
            "morosidad_consumo_pct",
            "morosidad_total_pct",
            "desempleo_pct",
            "empleo_adecuado_pct",
            "subempleo_pct",
            "inflacion_anual_pct",
            "tasa_consumo_pct",
            "tasa_max_consumo_pct",
            "monto_consumo_musd",
            "log_monto_consumo",
            "d_morosidad_consumo_pct",
            "d_desempleo_pct",
            "d_inflacion_anual_pct",
            "d_tasa_consumo_pct",
            "d_log_monto_consumo",
            "prediccion_ols_niveles_pct",
            "residuo_ols_niveles_pp",
            "regimen_coyuntural",
        ]
    ].replace({np.nan: None}).to_dict(orient="records")

    anual_records = df_tab_a[
        [
            "anio",
            "morosidad_consumo_pct",
            "morosidad_total_pct",
            "morosidad_fmi_bm_pct",
            "pib_crecimiento_pct",
            "desempleo_pct",
            "inflacion_anual_pct",
            "remesas_pib_pct",
            "credito_privado_pib_pct",
            "prediccion_ols_anual_pct",
            "residuo_ols_anual_pp",
        ]
    ].round(4).to_dict(orient="records")

    payload = {
        "meta": {
            "proyecto": "econometria-morosidad-ecuador",
            "autor": "Bryan Román",
            "fecha_descarga_datos": fuentes["fecha_generacion_ecuador"],
            "aviso": "Herramienta educativa. No es asesoría financiera.",
        },
        "fuentes": [
            {
                "id": f["id"],
                "institucion": f["institucion"],
                "titulo": f["titulo"],
                "url": f["url"],
                "pagina_origen": f["pagina_origen"],
                "archivo": f["archivo"],
                "frecuencia": f["frecuencia"],
                "fecha_descarga_ecuador": f["fecha_descarga_ecuador"],
                "bytes": f["bytes"],
                "sha256_corto": f["sha256"][:16],
            }
            for f in fuentes["archivos"]
        ],
        "validacion_limpieza": validacion,
        "descriptivas_mensuales": descriptivas_mensuales,
        "correlaciones_mensuales": correlaciones_mensuales,
        "modelos": {
            "mensual_niveles": m_niveles,
            "mensual_diferencias": m_dif,
            "anual_niveles": a_niveles,
            "anual_diferencias": a_dif,
        },
        "series": {
            "sb_historica_mensual": sb_hist_records,
            "mensual_modelo": mensual_records,
            "anual_largo_plazo": anual_records,
        },
    }

    out_json = PROC_DIR / "resultados_econometricos.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Inyectar payload verificado en app.js para que el sitio estático funcione offline y via file://
    app_js_path = BASE_DIR / "app.js"
    if app_js_path.exists():
        app_src = app_js_path.read_text(encoding="utf-8")
        start_marker = "/* __ECONOMETRIA_DATA_START__ */"
        end_marker = "/* __ECONOMETRIA_DATA_END__ */"
        if start_marker in app_src and end_marker in app_src:
            before, rest = app_src.split(start_marker, 1)
            _, after = rest.split(end_marker, 1)
            compact_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            updated = f"{before}{start_marker}\n  const ECONOMETRIA_DATA = {compact_json};\n  {end_marker}{after}"
            app_js_path.write_text(updated, encoding="utf-8")
            print(f"  - {app_js_path} (datos econométricos sincronizados)")

    print("=== MODELOS ECONOMÉTRICOS ESTIMADOS (statsmodels) ===")
    for mid, mres in payload["modelos"].items():
        ba = mres["bondad_ajuste"]
        sup = mres["supuestos"]
        print(
            f"- {mid:20s} | n={mres['n']:2d} | R2={ba['r2']:.4f} | R2_adj={ba['r2_ajustado']:.4f} "
            f"| Shapiro p={sup['normalidad']['shapiro_p']:.4f} "
            f"| BP p={sup['heterocedasticidad_breusch_pagan']['lm_pvalor']:.4f} "
            f"| maxVIF={sup['multicolinealidad_vif']['max_vif']:.2f} "
            f"| DW={sup['autocorrelacion']['durbin_watson']:.4f}"
        )
    print(f"\nExportados:\n  - {out_json}\n  - {TABLEAU_DIR / 'ecuador_morosidad_consumo_mensual_tableau.csv'}\n  - {TABLEAU_DIR / 'ecuador_morosidad_consumo_anual_tableau.csv'}")


if __name__ == "__main__":
    main()
