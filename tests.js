#!/usr/bin/env node
"use strict";

/**
 * Suite de pruebas automatizadas para econometria-morosidad-ecuador.
 * Ejecutar con: node tests.js
 * Sale con código 1 si alguna prueba falla y código 0 si todas pasan.
 * Sin dependencias externas (solo módulos nativos de Node.js).
 */

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const ROOT = __dirname;
let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  [PASS] ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`  [FAIL] ${name}`);
    console.error(`         ${err.message}`);
  }
}

function readText(relPath) {
  return fs.readFileSync(path.join(ROOT, relPath), "utf8");
}

function readJson(relPath) {
  return JSON.parse(readText(relPath));
}

function parseCsv(relPath) {
  const raw = readText(relPath).trim();
  const lines = raw.split(/\r?\n/);
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    // Manejo simple compatible con campos sin comas internas
    const vals = line.split(",");
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = vals[i] !== undefined ? vals[i] : "";
    });
    return obj;
  });
}

// Eliminación de Gauss-Jordan para invertir matriz cuadrada simétrica (X'X)
function invertMatrix(matrix) {
  const n = matrix.length;
  const aug = matrix.map((row, i) => [
    ...row.map((v) => Number(v)),
    ...Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)),
  ]);
  for (let col = 0; col < n; col++) {
    let pivotRow = col;
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(aug[r][col]) > Math.abs(aug[pivotRow][col])) pivotRow = r;
    }
    if (Math.abs(aug[pivotRow][col]) < 1e-12) {
      throw new Error("Matriz singular al calcular (X'X)^-1");
    }
    [aug[col], aug[pivotRow]] = [aug[pivotRow], aug[col]];
    const piv = aug[col][col];
    for (let j = 0; j < 2 * n; j++) aug[col][j] /= piv;
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const factor = aug[r][col];
      for (let j = 0; j < 2 * n; j++) aug[r][j] -= factor * aug[col][j];
    }
  }
  return aug.map((row) => row.slice(n));
}

function independentOLS(X, y) {
  const n = y.length;
  const k = X[0].length;
  const XtX = Array.from({ length: k }, () => Array(k).fill(0));
  const Xty = Array(k).fill(0);
  for (let i = 0; i < n; i++) {
    for (let a = 0; a < k; a++) {
      Xty[a] += X[i][a] * y[i];
      for (let b = 0; b < k; b++) {
        XtX[a][b] += X[i][a] * X[i][b];
      }
    }
  }
  const inv = invertMatrix(XtX);
  const beta = inv.map((row) => row.reduce((sum, v, idx) => sum + v * Xty[idx], 0));
  const yMean = y.reduce((a, b) => a + b, 0) / n;
  const resid = [];
  let sse = 0;
  let sst = 0;
  for (let i = 0; i < n; i++) {
    const yHat = X[i].reduce((sum, v, j) => sum + v * beta[j], 0);
    const e = y[i] - yHat;
    resid.push(e);
    sse += e * e;
    sst += (y[i] - yMean) ** 2;
  }
  let numDW = 0;
  for (let i = 1; i < n; i++) numDW += (resid[i] - resid[i - 1]) ** 2;
  return {
    beta,
    r2: 1 - sse / sst,
    dw: numDW / sse,
  };
}

console.log("=== Ejecutando suite de pruebas: econometria-morosidad-ecuador ===\n");

// 1. Existencia de entregables
test("Todos los archivos obligatorios existen y no están vacíos", () => {
  const requiredFiles = [
    "index.html",
    "style.css",
    "app.js",
    "README.md",
    "LICENSE",
    "tests.js",
    "scripts/descargar_datos.py",
    "scripts/limpiar_datos.py",
    "scripts/modelo_econometrico.py",
    "openrefine/historial_operaciones_openrefine.json",
    "data/raw/fuentes_descarga.json",
    "data/processed/raw_integrado_mensual_pre_limpieza.csv",
    "data/processed/ecuador_sb_serie_historica_mensual.csv",
    "data/processed/ecuador_morosidad_mensual_limpio.csv",
    "data/processed/ecuador_morosidad_anual_limpio.csv",
    "data/processed/reporte_validacion.json",
    "data/processed/resultados_econometricos.json",
    "tableau/ecuador_morosidad_consumo_mensual_tableau.csv",
    "tableau/ecuador_morosidad_consumo_anual_tableau.csv",
    "tableau/INSTRUCCIONES_TABLEAU_PUBLIC.md",
  ];
  for (const rel of requiredFiles) {
    const full = path.join(ROOT, rel);
    assert.ok(fs.existsSync(full), `Falta el archivo obligatorio: ${rel}`);
    assert.ok(fs.statSync(full).size > 0, `El archivo está vacío: ${rel}`);
  }
});

// 2. Trazabilidad de fuentes públicas
test("Manifiesto de descarga registra URL, fecha y SHA-256 de SB, BCE y Banco Mundial", () => {
  const manifest = readJson("data/raw/fuentes_descarga.json");
  assert.ok(Array.isArray(manifest.archivos) && manifest.archivos.length >= 10, "Deben existir al menos 10 archivos fuente");
  const instText = manifest.archivos.map((a) => a.institucion).join(" | ");
  assert.ok(instText.includes("Superintendencia de Bancos"), "Falta fuente Superintendencia de Bancos");
  assert.ok(instText.includes("Banco Central del Ecuador"), "Falta fuente Banco Central del Ecuador");
  assert.ok(instText.includes("Banco Mundial"), "Falta fuente Banco Mundial");

  for (const a of manifest.archivos) {
    assert.match(a.url, /^https:\/\//, `URL inválida en ${a.id}`);
    assert.match(a.fecha_descarga_ecuador, /^\d{4}-\d{2}-\d{2}T/, `Fecha ISO inválida en ${a.id}`);
    assert.match(a.sha256, /^[a-f0-9]{64}$/, `SHA-256 inválido en ${a.id}`);
    assert.ok(a.bytes > 0, `Bytes inválidos en ${a.id}`);
  }
});

// 3. Reporte de validación de limpieza
test("Reporte de validación Python (faltantes, duplicados, tipos, rangos) tiene estado PASS", () => {
  const rep = readJson("data/processed/reporte_validacion.json");
  assert.strictEqual(rep.estado_global, "PASS");
  assert.strictEqual(rep.filas_limpias_mensuales, 53);
  assert.strictEqual(rep.filas_excluidas_por_ventana_completa, 7);
  for (const v of rep.validaciones) {
    assert.strictEqual(v.estado_global, "PASS", `Falló validación en ${v.dataset}`);
  }
});

// 4. Validación independiente en Node sobre CSVs finales para Tableau Public
test("CSV mensual para Tableau Public (n=53) sin faltantes, sin duplicados y en rangos válidos", () => {
  const rows = parseCsv("tableau/ecuador_morosidad_consumo_mensual_tableau.csv");
  assert.strictEqual(rows.length, 53, `Se esperaban 53 filas mensuales, se obtuvieron ${rows.length}`);
  const seen = new Set();
  const numCols = [
    "morosidad_consumo_pct",
    "morosidad_total_pct",
    "desempleo_pct",
    "inflacion_anual_pct",
    "tasa_consumo_pct",
    "monto_consumo_musd",
    "log_monto_consumo",
    "prediccion_ols_niveles_pct",
    "residuo_ols_niveles_pp",
  ];
  let prev = "";
  for (const r of rows) {
    assert.match(r.periodo, /^\d{4}-\d{2}$/, `Periodo inválido: ${r.periodo}`);
    assert.match(r.fecha, /^\d{4}-\d{2}-\d{2}$/, `Fecha ISO inválida: ${r.fecha}`);
    assert.ok(!seen.has(r.periodo), `Periodo duplicado: ${r.periodo}`);
    seen.add(r.periodo);
    assert.ok(r.periodo > prev, `Orden cronológico roto en ${r.periodo}`);
    prev = r.periodo;
    for (const c of numCols) {
      const val = Number(r[c]);
      assert.ok(r[c] !== "" && Number.isFinite(val), `Valor faltante o no numérico en ${c} (${r.periodo})`);
    }
    const mora = Number(r.morosidad_consumo_pct);
    assert.ok(mora >= 1.0 && mora <= 15.0, `Morosidad fuera de rango: ${mora}`);
  }
});

test("CSV anual para Tableau Public (2003–2025, n=23) sin faltantes ni duplicados", () => {
  const rows = parseCsv("tableau/ecuador_morosidad_consumo_anual_tableau.csv");
  assert.strictEqual(rows.length, 23, `Se esperaban 23 filas anuales, se obtuvieron ${rows.length}`);
  assert.strictEqual(rows[0].anio, "2003");
  assert.strictEqual(rows[rows.length - 1].anio, "2025");
  const seen = new Set();
  for (const r of rows) {
    assert.ok(!seen.has(r.anio), `Año duplicado: ${r.anio}`);
    seen.add(r.anio);
    for (const c of ["morosidad_consumo_pct", "pib_crecimiento_pct", "desempleo_pct", "inflacion_anual_pct", "credito_privado_pib_pct"]) {
      const val = Number(r[c]);
      assert.ok(r[c] !== "" && Number.isFinite(val), `Valor inválido en ${c} (${r.anio})`);
    }
  }
});

// 5. Validación del archivo JSON de historial de operaciones de OpenRefine
test("Historial JSON de OpenRefine tiene formato estándar y cubre transformación, filtro, orden y columnas derivadas", () => {
  const ops = readJson("openrefine/historial_operaciones_openrefine.json");
  assert.ok(Array.isArray(ops) && ops.length >= 10, "OpenRefine JSON debe ser un arreglo de operaciones");
  const opTypes = new Set();
  for (const op of ops) {
    assert.ok(typeof op.op === "string" && op.op.startsWith("core/"), `Operación inválida: ${op.op}`);
    assert.ok(typeof op.description === "string" && op.description.length > 5, "Falta descripción en operación OpenRefine");
    opTypes.add(op.op);
  }
  assert.ok(opTypes.has("core/text-transform"), "Falta core/text-transform en OpenRefine");
  assert.ok(opTypes.has("core/row-removal"), "Falta core/row-removal en OpenRefine");
  assert.ok(opTypes.has("core/row-reorder"), "Falta core/row-reorder en OpenRefine");
  assert.ok(opTypes.has("core/column-addition"), "Falta core/column-addition en OpenRefine");
});

// 6. Verificación matemática independiente de MCO (X'X)^-1 X'y contra statsmodels
test("Verificación algebraica independiente MCO (M1 Niveles) coincide con statsmodels (< 1e-5)", () => {
  const rows = parseCsv("tableau/ecuador_morosidad_consumo_mensual_tableau.csv");
  const res = readJson("data/processed/resultados_econometricos.json").modelos.mensual_niveles;
  const X = rows.map((r) => [
    1,
    Number(r.desempleo_pct),
    Number(r.inflacion_anual_pct),
    Number(r.tasa_consumo_pct),
    Number(r.log_monto_consumo),
  ]);
  const y = rows.map((r) => Number(r.morosidad_consumo_pct));
  const check = independentOLS(X, y);

  res.coeficientes.forEach((c, i) => {
    assert.ok(
      Math.abs(check.beta[i] - c.coef) < 1e-4,
      `Discrepancia en beta[${c.variable}]: JS=${check.beta[i]} vs statsmodels=${c.coef}`
    );
  });
  assert.ok(Math.abs(check.r2 - res.bondad_ajuste.r2) < 1e-5, `Discrepancia en R2: JS=${check.r2} vs statsmodels=${res.bondad_ajuste.r2}`);
  assert.ok(
    Math.abs(check.dw - res.supuestos.autocorrelacion.durbin_watson) < 1e-4,
    `Discrepancia en DW: JS=${check.dw} vs statsmodels=${res.supuestos.autocorrelacion.durbin_watson}`
  );
});

test("Verificación algebraica independiente MCO (M2 Primeras Diferencias) confirma inversión de signo de desempleo", () => {
  const rows = parseCsv("tableau/ecuador_morosidad_consumo_mensual_tableau.csv").filter((r) => r.d_morosidad_consumo_pct !== "");
  const res = readJson("data/processed/resultados_econometricos.json").modelos.mensual_diferencias;
  assert.strictEqual(rows.length, 52);
  const X = rows.map((r) => [
    1,
    Number(r.d_desempleo_pct),
    Number(r.d_inflacion_anual_pct),
    Number(r.d_tasa_consumo_pct),
    Number(r.d_log_monto_consumo),
  ]);
  const y = rows.map((r) => Number(r.d_morosidad_consumo_pct));
  const check = independentOLS(X, y);

  res.coeficientes.forEach((c, i) => {
    assert.ok(
      Math.abs(check.beta[i] - c.coef) < 1e-4,
      `Discrepancia M2 en beta[${c.variable}]: JS=${check.beta[i]} vs statsmodels=${c.coef}`
    );
  });
  assert.ok(check.beta[1] > 0, "En primeras diferencias ΔDesempleo debe ser positivo según los datos");
  assert.ok(check.dw >= 1.5 && check.dw <= 2.5, `DW en M2 debe estar en rango aceptable [1.5, 2.5], obtenido: ${check.dw}`);
});

// 7. Sincronización y lógica unitaria en app.js
test("app.js sincroniza los resultados reales y computeSimpleOLS pasa prueba exacta", () => {
  const app = require("./app.js");
  const jsonDisk = readJson("data/processed/resultados_econometricos.json");
  assert.ok(app.ECONOMETRIA_DATA !== null, "ECONOMETRIA_DATA no fue inyectado en app.js");
  assert.strictEqual(app.ECONOMETRIA_DATA.modelos.mensual_niveles.n, jsonDisk.modelos.mensual_niveles.n);
  assert.strictEqual(app.ECONOMETRIA_DATA.modelos.mensual_niveles.bondad_ajuste.r2, jsonDisk.modelos.mensual_niveles.bondad_ajuste.r2);
  assert.strictEqual(app.ECONOMETRIA_DATA.series.sb_historica_mensual.length, 276);

  // Prueba unitaria exacta y = 3 + 2x
  const ols = app.computeSimpleOLS([1, 2, 3, 4, 5], [5, 7, 9, 11, 13]);
  assert.ok(Math.abs(ols.slope - 2) < 1e-9);
  assert.ok(Math.abs(ols.intercept - 3) < 1e-9);
  assert.ok(Math.abs(ols.r - 1) < 1e-9);
});

// 8. Reglas comunes de sitio estático, español, accesibilidad, modo oscuro, aviso y pie
test("Sitio estático (index.html, style.css, app.js) cumple reglas comunes, accesibilidad y cero CDN", () => {
  const html = readText("index.html");
  const css = readText("style.css");
  const js = readText("app.js");
  const readme = readText("README.md");
  const license = readText("LICENSE");

  assert.ok(html.includes('<html lang="es">'), "index.html debe declarar lang='es'");
  assert.ok(!/<script[^>]+src=["']https?:\/\//i.test(html), "Prohibido cargar scripts desde CDN");
  assert.ok(!/<link[^>]+href=["']https?:\/\//i.test(html), "Prohibido cargar estilos/fuentes desde CDN");
  assert.ok(html.includes("Herramienta educativa. No es asesoría financiera."), "Falta aviso educativo obligatorio en index.html");
  assert.ok(readme.includes("Herramienta educativa. No es asesoría financiera."), "Falta aviso educativo obligatorio en README.md");
  assert.ok(html.includes("Hecho por Bryan Román"), "Falta autoría obligatoria en pie de index.html");
  assert.ok(html.includes("linkedin.com/in/bryan-roman-ai"), "Falta enlace LinkedIn obligatorio en index.html");
  assert.ok(readme.includes("linkedin.com/in/bryan-roman-ai"), "Falta enlace LinkedIn en README.md");
  assert.ok(html.includes('class="skip-link"'), "Falta skip-link de accesibilidad");
  assert.ok(html.includes('aria-live="polite"'), "Falta región aria-live");
  assert.ok(html.includes('id="theme-toggle"'), "Falta botón de modo claro/oscuro");
  assert.ok(css.includes('[data-theme="dark"]'), "Falta soporte de modo oscuro en style.css");
  assert.ok(css.includes("@media"), "Faltan media queries responsivas en style.css");
  assert.ok(js.includes("http://www.w3.org/2000/svg"), "Faltan gráficos SVG hechos a mano en app.js");
  assert.ok(license.includes("MIT License") && license.includes("Bryan Román"), "LICENSE debe ser MIT a nombre de Bryan Román");
});

test("Todos los IDs del DOM referenciados en app.js existen en index.html", () => {
  const html = readText("index.html");
  const js = readText("app.js");
  const matches = [...js.matchAll(/getElementById\(["']([^"']+)["']\)/g)].map((m) => m[1]);
  assert.ok(matches.length >= 15, "Se esperaban al menos 15 referencias getElementById en app.js");
  for (const id of new Set(matches)) {
    assert.ok(html.includes(`id="${id}"`), `ID '${id}' referenciado en app.js no existe en index.html`);
  }
});

console.log(`\nResultado: ${passed} pruebas pasaron, ${failed} fallaron.`);
if (failed > 0) {
  process.exit(1);
}
process.exit(0);
