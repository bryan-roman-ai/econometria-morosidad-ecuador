# Instrucciones para construir el tablero en Tableau Public

> **Aviso:** Herramienta educativa. No es asesoría financiera.

Este documento detalla cómo cargar los archivos CSV finales en **Tableau Public** (versión web o escritorio gratuita) y construir un tablero ejecutivo reproducible sobre la morosidad del crédito de consumo en Ecuador y su asociación con variables macroeconómicas.

---

## 1. Archivos listos para importar

| Archivo | Granularidad | Cobertura | Filas | Uso recomendado en Tableau |
| :--- | :--- | :--- | :---: | :--- |
| `tableau/ecuador_morosidad_consumo_mensual_tableau.csv` | Mensual | Jun 2021 – Oct 2025 | 53 | Hoja principal: coyuntura, dispersión macro, ajuste MCO y residuos |
| `tableau/ecuador_morosidad_consumo_anual_tableau.csv` | Anual | 2003 – 2025 | 23 | Contexto estructural de largo plazo (PIB real, remesas, crédito/PIB) |

### Verificación de tipos de datos al conectar

1. Abrir **Tableau Public** → **Conectar** → **Archivo de texto** → seleccionar `ecuador_morosidad_consumo_mensual_tableau.csv`.
2. Verificar en la pestaña *Fuente de datos* que el separador sea coma (`,`), el separador decimal sea punto (`.`) y la codificación sea UTF-8.
3. Confirmar los tipos de campo:
   - `fecha` → **Fecha** (`YYYY-MM-DD`).
   - `periodo`, `regimen_coyuntural`, `pais` → **Cadena (texto)**.
   - `anio`, `mes` → **Número (entero)**.
   - Todas las métricas (`morosidad_consumo_pct`, `morosidad_total_pct`, `desempleo_pct`, `inflacion_anual_pct`, `tasa_consumo_pct`, `monto_consumo_musd`, `log_monto_consumo`, `prediccion_ols_niveles_pct`, `residuo_ols_niveles_pp`, y las columnas `d_*`) → **Número (decimal)**.
4. Opcional: agregar una segunda fuente de datos independiente con `ecuador_morosidad_consumo_anual_tableau.csv` (`fecha_cierre` como **Fecha**).

---

## 2. Campos calculados recomendados

Crear en el libro de trabajo mensual:

1. **Brecha Consumo vs. Total (pp)**
   ```tableau
   [morosidad_consumo_pct] - [morosidad_total_pct]
   ```
2. **Estado de Alerta de Morosidad**
   ```tableau
   IF [morosidad_consumo_pct] >= 5.0 THEN "Alta (≥ 5.0%)"
   ELSEIF [morosidad_consumo_pct] >= 4.0 THEN "Moderada (4.0% - 4.99%)"
   ELSE "Baja (< 4.0%)"
   END
   ```
3. **Variación Mensual del Monto Colocado (%)**
   ```tableau
   (EXP([d_log_monto_consumo]) - 1) * 100
   ```
4. **Residuo Absoluto (pp)** *(para tamaño de burbuja en diagnóstico)*
   ```tableau
   ABS([residuo_ols_niveles_pp])
   ```

---

## 3. Hojas sugeridas (4 vistas)

### Hoja 1 — Evolución mensual de morosidad vs. ajuste MCO (`Serie Temporal`)
- **Columnas:** `MES(fecha)` (continuo).
- **Filas:** `morosidad_consumo_pct` y `prediccion_ols_niveles_pct` con **Eje doble** y **Sincronizar eje**.
- **Marcas:**
  - `morosidad_consumo_pct`: Línea sólida azul oscuro, grosor medio.
  - `prediccion_ols_niveles_pct`: Línea punteada o de color secundario.
- **Línea de referencia:** Constante en `5.0%` con etiqueta `"Umbral de referencia 5%"`.
- **Anotaciones recomendadas:**
  - `2022-06`: Mínimo del período (`2.90%`).
  - `2024-09`: Pico coyuntural (`5.43%`, desaceleración y crisis energética).

### Hoja 2 — Dispersión macroeconómica interactiva (`Correlación vs. Diferencias`)
- Crear un **Parámetro** `p_variable_x` (Cadena, Lista):
  - `Tasa activa consumo (%)`
  - `Desempleo nacional (%)`
  - `Inflación anual IPC (%)`
  - `Δ Desempleo mensual (pp)`
- Crear campo calculado `X Seleccionado`:
  ```tableau
  CASE [p_variable_x]
  WHEN "Tasa activa consumo (%)" THEN [tasa_consumo_pct]
  WHEN "Desempleo nacional (%)" THEN [desempleo_pct]
  WHEN "Inflación anual IPC (%)" THEN [inflacion_anual_pct]
  WHEN "Δ Desempleo mensual (pp)" THEN [d_desempleo_pct]
  END
  ```
- Crear campo calculado `Y Seleccionado` (si el parámetro es `Δ Desempleo mensual (pp)`, usar `[d_morosidad_consumo_pct]`; en caso contrario `[morosidad_consumo_pct]`).
- **Columnas:** `X Seleccionado` (Dimensión o desagregado en *Análisis → Agregar medidas: desmarcar*).
- **Filas:** `Y Seleccionado`.
- **Color:** `regimen_coyuntural`.
- **Análisis:** Arrastrar **Línea de tendencia → Lineal** para mostrar $R^2$ y p-valor en el tooltip.
- *Propósito analítico:* permite demostrar visualmente cómo la relación con el desempleo cambia de negativa en niveles (efecto tendencia post-COVID) a positiva en primeras diferencias ($\hat{\alpha}_1 = +0.18$, $p_{\text{HAC}} = 0.040$).

### Hoja 3 — Diagnóstico de residuos del modelo (`Validación de Supuestos`)
- **Columnas:** `prediccion_ols_niveles_pct` (desagregado).
- **Filas:** `residuo_ols_niveles_pp`.
- **Color:** `regimen_coyuntural`.
- **Línea de referencia:** Constante en `0` (línea horizontal punteada).
- **Tooltip:** Incluir `periodo`, `morosidad_consumo_pct`, `prediccion_ols_niveles_pct`, `residuo_ols_niveles_pp`.

### Hoja 4 — Contexto estructural 2003–2025 (`Largo Plazo SB + Banco Mundial`)
- Usar `ecuador_morosidad_consumo_anual_tableau.csv`.
- **Columnas:** `AÑO(fecha_cierre)` (continuo).
- **Filas:** `morosidad_consumo_pct` (línea) y `pib_crecimiento_pct` (barras en eje secundario con color divergente rojo/verde).
- **Anotaciones:** Crisis petrolera 2016 (`8.42%` promedio anual), Pandemia 2020 (`PIB -9.25%` con diferimientos), Recuperación 2022 (`3.07%`), Contracción 2024 (`PIB -1.94%`, mora `5.24%`).

---

## 4. Diseño del Dashboard (1280 × 820 px)

1. **Encabezado superior (90 px):** Título *"Morosidad del Crédito de Consumo en Ecuador (2003–2025): Análisis Econométrico"* + subtítulo metodológico + banner visible *"Herramienta educativa. No es asesoría financiera."*
2. **Fila de KPIs (100 px):** 4 tarjetas de texto grande:
   - Morosidad consumo cierre Dic 2025 (`4.72%`, SB)
   - $R^2$ ajustado MCO mensual (`0.680`, $n=53$)
   - $\Delta$ Desempleo en 1ras diferencias (`+0.18 pp`, $p_{\text{HAC}}=0.040$)
   - Durbin-Watson: `1.28` (niveles) → `1.83` (diferencias)
3. **Cuerpo principal (2 × 2):**
   - Arriba izquierda: Hoja 1 (Serie temporal mensual vs. MCO)
   - Arriba derecha: Hoja 2 (Dispersión con selector `p_variable_x`)
   - Abajo izquierda: Hoja 3 (Residuos vs. ajustados)
   - Abajo derecha: Hoja 4 (Largo plazo 2003–2025 SB + Banco Mundial)
4. **Filtros globales:** `regimen_coyuntural` (aplicado a Hojas 1–3) y control del parámetro `p_variable_x`.
5. **Pie de página:** Fuentes oficiales (Superintendencia de Bancos, Banco Central del Ecuador, Banco Mundial, descargadas el 2026-11-21) · *Hecho por Bryan Román · linkedin.com/in/bryan-roman-ai*.
