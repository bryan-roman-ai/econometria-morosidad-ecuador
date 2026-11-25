#!/usr/bin/env python3
"""Actualización 2026 (24-nov-2026): morosidad del crédito de consumo hasta octubre de 2026 y estimación de diciembre de 2026.

Fuente: Superintendencia de Bancos del Ecuador, Boletín de Series — Total Subsistema Banca Privada, corte OCT 2026
(data/raw/sb_series_banca_privada_oct2026.zip; hoja GRAF CARTERA, misma estructura que el corte dic-2025).
Control: el valor de dic-2025 de este archivo (4.719 %) coincide con el del estudio original.

Dos estimaciones transparentes de dic-2026 (NO son dato oficial):
  1. Estacional: oct-2026 + mediana del cambio oct→dic en 2015-2025 (rango = percentiles 10-90).
  2. Autorregresiva: MCO morosidad_t = a + b·morosidad_{t-1} + c·dic + d·nov, 2015-01..2026-10, errores HAC; se proyecta nov y dic.
Uso: python scripts/actualizacion_2026.py  → data/processed/actualizacion_2026.json
"""
import io, json, zipfile, hashlib
from pathlib import Path
import numpy as np, openpyxl, pandas as pd, statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "data/raw/sb_series_banca_privada_oct2026.zip"
URL = ("https://www.superbancos.gob.ec/estadisticas/portalestudios/wp-admin/admin-ajax.php?action=shareonedrive-download&dl=1"
       "&id=01ONK3WL7U5X2E36NT4NH2W7T7LI22G2H7&drive_id=b!Iz-mji9B1EqK1eiAuGWU7x82x3m7uftFja_xK_rSLWY6gLR41EOqTYg222Ho8lwD"
       "&account_id=341c37a6-daa9-4b83-adad-506b00ccb984&listtoken=cb2dcac486c20e9c7a63b3bc95e58f46")

with zipfile.ZipFile(ZIP) as zf:
    xl = zf.read(next(n for n in zf.namelist() if n.lower().endswith(".xlsx")))
rows = list(openpyxl.load_workbook(io.BytesIO(xl), read_only=True, data_only=True)["GRAF CARTERA"].iter_rows(values_only=True))
fechas = rows[13][3:]
def serie(i):
    return pd.Series({pd.to_datetime(d).to_period("M"): float(v) * 100 for d, v in zip(fechas, rows[i][3:])
                      if d is not None and v is not None}).sort_index()
mc, mt, cob, part = serie(15), serie(19), serie(24), serie(7)
assert abs(mc[pd.Period("2025-12", "M")] - 4.7185) < 0.01, "el archivo no coincide con el estudio original"

oct26 = mc[pd.Period("2026-10", "M")]
dd = [(y, mc[pd.Period(f"{y}-12", "M")] - mc[pd.Period(f"{y}-10", "M")]) for y in range(2015, 2026)]
d = np.array([x[1] for x in dd])
est = {"dic2026": oct26 + np.median(d), "p10": oct26 + np.percentile(d, 10), "p90": oct26 + np.percentile(d, 90)}

df = pd.DataFrame({"y": mc}); df["lag"] = df.y.shift(1)
df["dic"] = (df.index.month == 12).astype(int); df["nov"] = (df.index.month == 11).astype(int)
df = df[df.index >= pd.Period("2015-01", "M")].dropna()
m = sm.OLS(df.y, sm.add_constant(df[["lag", "dic", "nov"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
p = m.params
nov = p.const + p.lag * oct26 + p.nov
dic = p.const + p.lag * nov + p.dic
ic90 = 1.645 * np.sqrt(m.scale) * np.sqrt(1 + p.lag ** 2)

out = {
    "fuente": {"institucion": "Superintendencia de Bancos del Ecuador", "titulo": "Boletín de Series — Total Subsistema Banca Privada, corte OCT 2026",
               "pagina_origen": "https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos-2/", "url": URL,
               "sha256_zip": hashlib.sha256(ZIP.read_bytes()).hexdigest(), "control_dic2025": round(mc[pd.Period("2025-12", "M")], 4)},
    "mensual_2026": {str(k): {"morosidad_consumo_pct": round(mc[k], 3), "morosidad_total_pct": round(mt[k], 3),
                              "cobertura_consumo_pct": round(cob[k], 2), "participacion_consumo_pct": round(part[k], 2)}
                     for k in mc.index if k >= pd.Period("2025-12", "M")},
    "promedio_ene_oct": {"2025": round(mc["2025-01":"2025-10"].mean(), 3), "2026": round(mc["2026-01":"2026-10"].mean(), 3)},
    "estimacion_dic2026": {
        "estacional": {k: round(v, 3) for k, v in est.items()} | {"cambios_oct_dic_2015_2025": [[y, round(v, 3)] for y, v in dd]},
        "autorregresiva": {"nov2026": round(nov, 3), "dic2026": round(dic, 3), "ic90_mas_menos": round(ic90, 3), "r2": round(m.rsquared, 3),
                           "n": int(m.nobs), "coeficientes": {k: round(v, 4) for k, v in p.items()},
                           "p_hac": {k: round(v, 4) for k, v in m.pvalues.items()}},
        "aviso": "Estimación estadística, no dato oficial. El dato real de diciembre lo publica la Superintendencia de Bancos.",
    },
}
(ROOT / "data/processed/actualizacion_2026.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out["estimacion_dic2026"], ensure_ascii=False)[:600])
