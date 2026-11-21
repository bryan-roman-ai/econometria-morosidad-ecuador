# Econometría de la Morosidad del Crédito de Consumo en Ecuador (2003–2025)

> **Herramienta educativa. No es asesoría financiera.**

Proyecto de portafolio de econometría aplicada que responde con datos públicos oficiales, limpieza auditable y pruebas formales de supuestos a la pregunta:

**¿Qué variables macroeconómicas se asocian a la morosidad del crédito de consumo de la banca privada en Ecuador?**

---

## 1. Pregunta de negocio y relevancia

Al cierre de **diciembre de 2025**, el crédito de consumo representó el **40.55%** de la cartera bruta de la banca privada ecuatoriana, con una tasa de morosidad de **4.72%** (frente a **2.99%** en la cartera total) y una cobertura de provisiones de **149.89%** (Superintendencia de Bancos). Entender qué variables macroeconómicas —mercado laboral, inflación, tasa activa referencial, volumen colocado, crecimiento del PIB y profundización crediticia— co-varían con la morosidad de consumo es clave para el análisis de riesgo macrofinanciero, evitando conclusiones apresuradas basadas en correlaciones espurias en niveles.

---

## 2. Fuentes públicas oficiales y trazabilidad

Todos los archivos crudos fueron descargados mediante `scripts/descargar_datos.py` el **2026-11-21** y auditados con su tamaño y huella SHA-256 en [`data/raw/fuentes_descarga.json`](data/raw/fuentes_descarga.json). **Ningún dato fue inventado ni imputado artificialmente.**

| Institución | Serie / Archivo local | Frecuencia | Fecha de descarga (EC) | URL oficial |
| :--- | :--- | :--- | :--- | :--- |
| **Superintendencia de Bancos (SB)** | Boletín de Series Mensuales Banca Privada Dic 2025 (`sb_series_banca_privada_dic2025.zip`) | Mensual (2003-01 a 2025-12) | 2026-11-21 | [Portal Estadístico SB](https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos-2/) |
| **Banco Central del Ecuador (BCE)** | IEM 1.10.2a Tasas activas efectivas referenciales por segmento (`bce_IEM-1102a-e.xlsx`) | Mensual (2021-05 a 2025-11) | 2026-11-21 | [IEM-1102a-e.xlsx](https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-1102a-e.xlsx) |
| **Banco Central del Ecuador (BCE)** | IEM 1.10.3a Monto de operaciones activas por segmento (`bce_IEM-1103a-e.xlsx`) | Mensual (2021-05 a 2025-11) | 2026-11-21 | [IEM-1103a-e.xlsx](https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-1103a-e.xlsx) |
| **BCE / INEC** | IEM 4.2.1 Índice de Precios al Consumidor e Inflación (`bce_IEM-421-e.xlsx`) | Mensual (2020-01 a 2025-11) | 2026-11-21 | [IEM-421-e.xlsx](https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-421-e.xlsx) |
| **BCE / INEC** | IEM 4.2.5 Mercado Laboral ENEMDU Nacional (`bce_IEM-425-e.xlsx`) | Mensual (2021-01 a 2025-10) | 2026-11-21 | [IEM-425-e.xlsx](https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/m2085/IEM-425-e.xlsx) |
| **BCE** | IEM 1.10.2, 1.10.3 y 4.5.1 (histórico previo y confianza del consumidor) | Mensual | 2026-11-21 | [Índice IEM m2085](https://contenido.bce.fin.ec/documentos/PublicacionesNotas/Catalogo/IEMensual/Indices/m2085112025.html) |
| **Banco Mundial (API v2)** | Crecimiento PIB real (`NY.GDP.MKTP.KD.ZG`) | Anual (2003–2025) | 2026-11-21 | [API ECU NY.GDP.MKTP.KD.ZG](https://api.worldbank.org/v2/country/ECU/indicator/NY.GDP.MKTP.KD.ZG?format=json&per_page=100) |
| **Banco Mundial / OIT (API v2)** | Desempleo total % población activa (`SL.UEM.TOTL.ZS`) | Anual (2003–2025) | 2026-11-21 | [API ECU SL.UEM.TOTL.ZS](https://api.worldbank.org/v2/country/ECU/indicator/SL.UEM.TOTL.ZS?format=json&per_page=100) |
| **Banco Mundial / FMI (API v2)** | Inflación anual IPC (`FP.CPI.TOTL.ZG`) | Anual (2003–2025) | 2026-11-21 | [API ECU FP.CPI.TOTL.ZG](https://api.worldbank.org/v2/country/ECU/indicator/FP.CPI.TOTL.ZG?format=json&per_page=100) |
| **Banco Mundial (API v2)** | Remesas recibidas % PIB (`BX.TRF.PWKR.DT.GD.ZS`) | Anual (2003–2025) | 2026-11-21 | [API ECU BX.TRF.PWKR.DT.GD.ZS](https://api.worldbank.org/v2/country/ECU/indicator/BX.TRF.PWKR.DT.GD.ZS?format=json&per_page=100) |
| **Banco Mundial / FMI (API v2)** | Crédito interno al sector privado % PIB (`FS.AST.PRVT.GD.ZS`) | Anual (2003–2025) | 2026-11-21 | [API ECU FS.AST.PRVT.GD.ZS](https://api.worldbank.org/v2/country/ECU/indicator/FS.AST.PRVT.GD.ZS?format=json&per_page=100) |
| **Banco Mundial / FMI (API v2)** | Morosidad bancaria total FSI (`FB.AST.NPER.ZS`) y consumo hogares (`NE.CON.PRVT.KD.ZG`) | Anual (2003–2025) | 2026-11-21 | [API ECU FB.AST.NPER.ZS](https://api.worldbank.org/v2/country/ECU/indicator/FB.AST.NPER.ZS?format=json&per_page=100) |

---

## 3. Limpieza documentada y validación (Python + OpenRefine)

1. **Script Python (`scripts/limpiar_datos.py`):**
   - Extrae la serie mensual de la hoja `GRAF CARTERA` de la SB (`2003-01` a `2025-12`, **n = 276 meses**).
   - Parsea las hojas oficiales del IEM del BCE (`1.10.2a`, `1.10.3a`, `4.2.1`, `4.2.5`) y las series anuales del Banco Mundial (`2003–2025`, **n = 23 años**).
   - Genera `data/processed/raw_integrado_mensual_pre_limpieza.csv` (60 meses 2021–2025 antes de limpieza) y excluye explícitamente —sin imputación— los **7 meses** sin cobertura completa: `2021-01` a `2021-04` (anteriores a la unificación normativa del segmento *Consumo* en mayo 2021), `2021-05` (sin tasa referencial publicada en el mes de transición) y `2025-11` a `2025-12` (aún sin cierre mensual ENEMDU en IEM m2085).
   - Resultado mensual homogéneo: **junio 2021 – octubre 2025 (n = 53 meses)**.
2. **Historial equivalente de OpenRefine (`openrefine/historial_operaciones_openrefine.json`):**
   - Contiene **19 operaciones GREL** estándar (`core/text-transform`, `core/row-removal`, `core/row-reorder`, `core/column-addition`) aplicables directamente en OpenRefine sobre `data/processed/raw_integrado_mensual_pre_limpieza.csv` para reproducir la limpieza paso a paso.
3. **Pruebas de validación (`data/processed/reporte_validacion.json`):**
   - **Faltantes:** `0` valores nulos en columnas analíticas de los 3 datasets limpios.
   - **Duplicados:** `0` claves duplicadas en `periodo` / `anio`.
   - **Tipos:** verificación estricta de tipos numéricos finitos y fechas ISO `YYYY-MM-DD`.
   - **Rangos económicos y orden cronológico:** `PASS` en las 3 series (`ecuador_sb_serie_historica_mensual`, `ecuador_morosidad_mensual_limpio`, `ecuador_morosidad_anual_limpio`).

---

## 4. Metodología econométrica y fórmulas (`statsmodels`)

Definición contable oficial (Superintendencia de Bancos):

$$\text{MorosidadConsumo}_t = \frac{\text{Cartera Improductiva de Consumo}_t}{\text{Cartera Bruta de Consumo}_t} \times 100$$

### Especificaciones estimadas (`scripts/modelo_econometrico.py`)

1. **Modelo 1 — MCO Mensual en Niveles (Jun 2021 – Oct 2025, $n = 53$):**
   $$\text{MorosidadConsumo}_t = \beta_0 + \beta_1 \text{Desempleo}_t + \beta_2 \text{InflaciónIPC}_t + \beta_3 \text{TasaConsumo}_t + \beta_4 \ln(\text{MontoConsumo}_t) + \varepsilon_t$$
2. **Modelo 2 — MCO Mensual en Primeras Diferencias (Jul 2021 – Oct 2025, $n = 52$):**
   $$\Delta \text{MorosidadConsumo}_t = \alpha_0 + \alpha_1 \Delta \text{Desempleo}_t + \alpha_2 \Delta \text{InflaciónIPC}_t + \alpha_3 \Delta \text{TasaConsumo}_t + \alpha_4 \Delta \ln(\text{MontoConsumo}_t) + u_t$$
3. **Modelo 3 y Modelo 4 — Largo Plazo Anual (SB + API Banco Mundial, 2003–2025, $n = 23$ niveles / $n = 22$ diferencias):**
   $$\text{MorosidadConsumo}_t = \gamma_0 + \gamma_1 \text{PIB}_t + \gamma_2 \text{Desempleo}_t + \gamma_3 \text{InflaciónIPC}_t + \gamma_4 \text{CréditoPrivadoPIB}_t + \nu_t$$
   y su contraparte en primeras diferencias anuales ($\Delta$).

En los cuatro modelos se reportan errores estándar clásicos MCO y errores robustos a heterocedasticidad y autocorrelación **Newey-West (HAC)**, junto con pruebas de **Shapiro-Wilk / Jarque-Bera** (normalidad), **Breusch-Pagan** (heterocedasticidad), **VIF** (multicolinealidad) y **Durbin-Watson / Breusch-Godfrey** (autocorrelación).

---

## 5. Resultados empíricos y diagnóstico de supuestos

### Resumen comparativo de los 4 modelos

| Modelo | Muestra | $n$ | $R^2$ | $R^2_{\text{adj}}$ | Shapiro $p$ | Breusch-Pagan $p$ | VIF máx | Durbin-Watson |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M1: Mensual Niveles** | 2021-06 a 2025-10 | 53 | 0.7049 | 0.6803 | 0.1596 | 0.0700 | 1.49 | **1.2751** (alerta) |
| **M2: Mensual 1ras Dif.** | 2021-07 a 2025-10 | 52 | 0.2451 | 0.1809 | <0.0001 | 0.1654 | 1.12 | **1.8337** (ok) |
| **M3: Anual Niveles** | 2003 a 2025 | 23 | 0.3475 | 0.2025 | 0.5861 | 0.0025 | 1.61 | **0.5710** (alerta) |
| **M4: Anual 1ras Dif.** | 2004 a 2025 | 22 | 0.4024 | 0.2618 | 0.4850 | 0.8158 | 1.64 | **1.5327** (ok) |

### Coeficientes principales (con errores Newey-West HAC)

| Variable | M1 Niveles ($\hat{\beta}$, $p_{\text{HAC}}$) | M2 1ras Dif. ($\hat{\alpha}$, $p_{\text{HAC}}$) |
| :--- | :---: | :---: |
| Desempleo / $\Delta$ Desempleo | `−0.8026` ($p = 0.0001$) | **`+0.1789`** ($p = 0.0402$) |
| Inflación IPC / $\Delta$ Inflación | `−0.2597` ($p = 0.0010$) | `−0.1076` ($p = 0.2078$) |
| Tasa activa consumo / $\Delta$ Tasa | `+2.6577` ($p < 0.0001$) | `+0.9443` ($p = 0.0720$) |
| $\ln(\text{Monto consumo})$ / $\Delta \ln(\text{Monto})$ | `+3.2910` ($p = 0.0001$) | **`+1.1117`** ($p = 0.0119$) |

En el **Modelo 4 (Anual en primeras diferencias 2004–2025, $n = 22$)**, donde se cumplen simultáneamente los cuatro supuestos clásicos, los regresores estadísticamente significativos bajo Newey-West HAC son **$\Delta$ Desempleo** (`+0.6008`, $p_{\text{HAC}} = 0.0313$) y **$\Delta$ Crédito interno privado / PIB** (`−0.3615`, $p_{\text{HAC}} = 0.0007$).

---

## 6. Interpretación honesta y limitaciones

- **Correlación no implica causalidad.** Los coeficientes miden asociaciones condicionales en datos agregados, no efectos causales identificados experimentalmente.
- **Trampa de correlación en niveles:** El signo negativo del desempleo en M1 (`−0.8026`) no significa que un mayor desempleo reduzca la mora; obedece a la trayectoria post-pandemia (en 2021–2022 los diferimientos regulatorios mantuvieron la mora en mínimos de `2.90%` mientras el desempleo bajaba desde `5.39%`; luego en 2023–2025 la mora repuntó hasta `5.43%` con desempleo abierto entre `3.2%` y `3.8%`). Al diferenciar las series (M2 y M4), desaparece la autocorrelación severa y el desempleo muestra la asociación **positiva** esperada por la teoría económica.
- **Techos de tasas y endogeneidad:** La tasa activa de consumo varía dentro de una franja estrecha (`15.89%` a `16.56%`) acotada por techos máximos regulatorios; su asociación positiva puede incluir respuesta endógena de los bancos ante mayor percepción de riesgo.
- **Choques normativos y muestra acotada:** Los diferimientos COVID-19 (2020–2021) y las resoluciones de alivio financiero (2024–2025) afectan el registro contable de cartera improductiva; además, $n = 53$ meses y $n = 23$ años limitan la potencia estadística para modelos con múltiples rezagos.

---

## 7. Tableau Public y sitio estático

- **Archivos para Tableau Public:**
  - `tableau/ecuador_morosidad_consumo_mensual_tableau.csv`
  - `tableau/ecuador_morosidad_consumo_anual_tableau.csv`
  - Guía detallada de campos calculados, 4 hojas y diseño del dashboard: [`tableau/INSTRUCCIONES_TABLEAU_PUBLIC.md`](tableau/INSTRUCCIONES_TABLEAU_PUBLIC.md).
- **Sitio estático interactivo:** Abrir `index.html` directamente en cualquier navegador moderno (o servir con `python3 -m http.server 8000`). Construido únicamente con `index.html`, `style.css` y `app.js` (sin frameworks, sin CDN, gráficos SVG construidos a mano, responsive, modo claro/oscuro y accesible).

---

## 8. Cómo ejecutar el proyecto

### 1. Reproducir limpieza y estimación econométrica (Python)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas statsmodels scipy openpyxl

# (Opcional) Volver a descargar archivos oficiales desde SB, BCE y Banco Mundial:
python scripts/descargar_datos.py

# Ejecutar limpieza documentada y pruebas de validación:
python scripts/limpiar_datos.py

# Estimar modelos MCO/HAC, diagnósticos, sincronizar app.js y exportar CSV para Tableau:
python scripts/modelo_econometrico.py
```

### 2. Ejecutar suite de pruebas automatizadas (`Node.js`)

```bash
node tests.js
```

El script `tests.js` verifica integridad de archivos, trazabilidad de fuentes, validación de CSVs (cero faltantes, cero duplicados, tipos y rangos), estructura del JSON de OpenRefine, consistencia con `app.js`, verificación independiente de álgebra matricial MCO $(X'X)^{-1}X'y$ contra `statsmodels`, accesibilidad y reglas de sitio estático. Sale con código `1` si alguna prueba falla.

### 3. Abrir el sitio estático

```bash
python3 -m http.server 8000
# Luego visitar http://localhost:8000
```

---

## Licencia y autoría

Distribuido bajo licencia **MIT** (ver [`LICENSE`](LICENSE)).

**Herramienta educativa. No es asesoría financiera.**  
Hecho por Bryan Román · [linkedin.com/in/bryan-roman-ai](https://www.linkedin.com/in/bryan-roman-ai)
