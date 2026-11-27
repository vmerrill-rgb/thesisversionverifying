# -*- coding: utf-8 -*-
"""
dalton_validacion.py
===================
Validación estadística del Índice de Dalton entre períodos y evidencia de
quiebres estructurales sobre la base long-format de ideología del Congreso
de Chile (2002-2026), construida a partir de PP.ipynb.

USO
---
(a) Como script:      python dalton_validacion.py [ruta_csv] [carpeta_salida]
(b) Como notebook:    cada bloque `# %% [CELL nn]` es una celda independiente;
                      ejecutar en orden. La última celda genera el reporte.

Entrada requerida (columnas): n, Id, Name, Period, dim_IC_low, dim_ideology,
dim_IC_high, wnom_ideology, bay_ic_low, bay_ideology, bay_ic_high,
quant_parties, party_1..party_4, Sex, Birth_date.

CONSTRUCCIÓN DEL ÍNDICE (especificación exacta)
-----------------------------------------------
Por período t, con P_t el conjunto de partidos presentes:

    D_t = sqrt( sum_p s_p * ((y_p - ybar) / R)^2 )

    y_p = media de dim_ideology de los legisladores del partido p en t
          (centroide, no ponderado por asistencia)
    s_p = n_p / N_t, proporción de legisladores CON estimación válida en p
          (⚠ NO es la cuota oficial de escaños de la Cámara)
    ybar = sum_p s_p * y_p  (media ponderada por s_p)
    R    = (max_global - min_global) / 2  sobre TODOS los períodos válidos
           (denominador fijo para comparabilidad entre períodos; una variante
           con R recalculado por réplica se reporta como sensibilidad)

ESQUEMA INFERENCIAL
-------------------
- Unidad muestral: legislador (no período). Con 6 observaciones de período NO
  se aplican tests asintóticos de series de tiempo (Chow/Andrews clásicos no
  son apropiados: la "serie" tiene 6 puntos). Toda la inferencia es por
  remuestreo a nivel de legislador.
- Bootstrap por conglomerado (cluster) por Id de legislador: para la
  diferencia D_{t+1} - D_t se remuestrean Ids (con reemplazo) desde la unión
  de ambos períodos, conservando TODAS las filas de cada Id muestreado. Esto
  respeta la dependencia panel de los diputados que continúan entre períodos.
- Bootstrap independiente dentro de cada período: se reporta solo como
  sensibilidad (ignora la dependencia entre períodos; es optimista).
- Error de medición: simulación paramétrica con sigma_i = |IC_high - IC_low|/3.92
  (IC ~95% bajo normalidad; valor absoluto porque la base tiene intervalos
  con cotas invertidas, contados en el diagnóstico ETL).
- Test principal (confirmatorio, pre-especificado): contraste "post-reforma
  electoral 2018" = media(D, Periodo_5-6) vs media(D, Periodo_1-4), vía
  cluster bootstrap. El barrido de quiebres adyacentes y el sup-Wald se
  etiquetan EXPLORATORIOS.
- Corrección de multiplicidad: Holm-Bonferroni sobre las comparaciones
  adyacentes (5 hipótesis) y sobre los contrastes de dispersión por pares.

VERSIONES
---------
El reporte registra en tiempo de ejecución: versiones de Python, numpy,
pandas, scipy y plataforma. La semilla es fija (SEED), por lo que el reporte
es reproducible bit a bit en el mismo entorno.
"""

# %% [CELL 01] — Imports, parámetros globales y registro de versiones
from __future__ import annotations

import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:    
    from scipy import stats as sps
    TIENE_SCIPY = True
except ImportError:  # scipy es opcional solo para los tests de Levene/Fligner
    sps = None
    TIENE_SCIPY = False

# ------------------------- Parámetros del análisis -------------------------
CSV_PATH = "ideologia_congreso_chile_2002_2026_long_format.csv"  # ajustar ruta
OUT_DIR = Path(".")            # carpeta donde se escriben reporte y CSVs
B_BOOT = 1000                  # réplicas bootstrap dentro de período
B_CLUSTER = 1000               # réplicas bootstrap por conglomerado (Id)
B_MEAS = 1000                  # réplicas de simulación de error de medición
ALPHA = 0.05                   # nivel de significación
SEED = 20261007                # semilla fija (reproducibilidad exacta)

IDEOL, IC_LOW, IC_HIGH = "dim_ideology", "dim_IC_low", "dim_IC_high"
PERIOD, ID = "Period", "Id"
PARTY_COLS = ["party_1", "party_2", "party_3", "party_4"]
ATRIBUCIONES = ["salida", "unico"]  # modos de atribución partidaria

VERSIONES = {
    "python": platform.python_version(),
    "numpy": np.__version__,
    "pandas": pd.__version__,
    "scipy": __import__("scipy").__version__ if TIENE_SCIPY else "no disponible",
    "plataforma": platform.platform(),
    "semilla": SEED,
    "B_boot": B_BOOT,
    "B_cluster": B_CLUSTER,
    "B_medicion": B_MEAS,
    "alpha": ALPHA,
}

# %% [CELL 02] — Carga, chequeos ETL y filtro de filas válidas
def ordenar_periodos(labels) -> list:
    """Ordena etiquetas tipo 'Periodo_k' por su número final."""
    return sorted(labels, key=lambda p: int(str(p).split("_")[-1]))


def cargar_datos(path: str = CSV_PATH) -> pd.DataFrame:
    """Carga el CSV long-format y coerciona a numérico las columnas ideológicas.

    Además normaliza a NaN los strings 'NA'/'NaN'/'' en las columnas de
    partido y quant_parties, por si el CSV fue exportado conservándolos
    como texto (como ocurre en una rama del ETL de PP.ipynb).
    """
    df = pd.read_csv(path)
    for c in (IDEOL, IC_LOW, IC_HIGH):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in PARTY_COLS + ["quant_parties"]:
        if c in df.columns:
            df[c] = df[c].replace({"NA": np.nan, "NaN": np.nan, "": np.nan})
    if "quant_parties" in df.columns:
        df["quant_parties"] = pd.to_numeric(df["quant_parties"], errors="coerce")
    return df


def chequeos_etl(df: pd.DataFrame) -> dict:
    """Diagnósticos de sanidad de la fusión de datos, ANTES de filtrar.

    Cubre los errores de ETL identificados en PP.ipynb: filas duplicadas
    Id-Period (romperían la cardinalidad de merges), intervalos con cotas
    invertidas (ancho negativo), inconsistencias entre quant_parties y el
    conteo real de columnas party_n, y cobertura desigual por período.
    """
    diag = {}
    diag["filas_totales"] = int(len(df))
    diag["filas_duplicadas_Id_Period"] = int(df.duplicated(subset=[ID, PERIOD]).sum())

    ancho = df[IC_HIGH] - df[IC_LOW]
    diag["anchos_IC_negativos"] = int((ancho < 0).sum())
    diag["anchos_IC_cero"] = int((ancho == 0).sum())
    diag["anchos_IC_nan"] = int(ancho.isna().sum())

    conteo_partidos = df[PARTY_COLS].notna().sum(axis=1)
    diag["quant_parties_inconsistente"] = int(
        (df["quant_parties"].notna() & (conteo_partidos != df["quant_parties"])).sum()
    )
    diag["filas_con_ideologia_sin_partido"] = int(
        (df[IDEOL].notna() & conteo_partidos.eq(0)).sum()
    )

    cobertura = (
        df.groupby(PERIOD)[IDEOL]
        .agg(n_total="size", n_validos=lambda s: s.notna().sum())
        .assign(pct=lambda d: (100 * d["n_validos"] / d["n_total"]).round(1))
        .reindex(ordenar_periodos(df[PERIOD].unique()))
    )
    diag["cobertura_por_periodo"] = cobertura
    return diag


def filtrar_validas(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina filas período-legislador sin ideología o sin cotas de IC."""
    return df.dropna(subset=[IDEOL, IC_LOW, IC_HIGH]).copy()


# %% [CELL 03] — Atribución partidaria (dos variantes, como en PP.ipynb)
def asignar_partido(df: pd.DataFrame, modo: str = "salida") -> pd.DataFrame:
    """Crea la columna 'partido_asignado'.

    modo='salida': última columna party_n no vacía (afiliación de salida del
                   período; usa todas las filas válidas).
    modo='unico' : filas con quant_parties == 1 Y exactamente una columna
                   party_n no vacía (validación cruzada; excluye switchers).
    """
    df = df.copy()

    def ultima(fila):
        vals = [fila[c] for c in PARTY_COLS if pd.notna(fila[c])]
        return vals[-1] if vals else np.nan

    if modo == "salida":
        df["partido_asignado"] = df.apply(ultima, axis=1)
    elif modo == "unico":
        conteo = df[PARTY_COLS].notna().sum(axis=1)
        consistente = df["quant_parties"].notna() & (conteo == df["quant_parties"])
        mascara = (df["quant_parties"] == 1) & consistente
        df = df[mascara].copy()
        df["partido_asignado"] = df[PARTY_COLS].bfill(axis=1).iloc[:, 0]
    else:
        raise ValueError("modo debe ser 'salida' o 'unico'")
    return df.dropna(subset=["partido_asignado"])


# %% [CELL 04] — Índice de Dalton: construcción y estimaciones puntuales
def dalton_arrays(x: np.ndarray, partidos: np.ndarray, half_range: float) -> float:
    """D_t = sqrt(sum_p s_p ((y_p - ybar)/R)^2) sobre arreglos numpy.

    Equivalente vectorial del cálculo por groupby; se usa dentro de los
    remuestreos por eficiencia.
    """
    _, inv = np.unique(partidos, return_inverse=True)
    n = np.bincount(inv).astype(float)
    cent = np.bincount(inv, weights=x) / n
    s = n / n.sum()
    ybar = float(np.sum(s * cent))
    return float(np.sqrt(np.sum(s * ((cent - ybar) / half_range) ** 2)))


def rango_global(df: pd.DataFrame, col: str = IDEOL) -> dict:
    v = df[col].dropna()
    return {
        "rango_min": float(v.min()),
        "rango_max": float(v.max()),
        "half_range": float((v.max() - v.min()) / 2),
    }


def tabla_dalton(df_filtrado: pd.DataFrame, half_range: float, modo: str) -> pd.DataFrame:
    dfa = asignar_partido(df_filtrado, modo)
    filas = []
    for p in ordenar_periodos(dfa[PERIOD].unique()):
        g = dfa[dfa[PERIOD] == p]
        filas.append(
            {
                PERIOD: p,
                "n_legisladores": int(len(g)),
                "n_partidos": int(g["partido_asignado"].nunique()),
                "dalton": dalton_arrays(
                    g[IDEOL].to_numpy(), g["partido_asignado"].to_numpy(), half_range
                ),
            }
        )
    return pd.DataFrame(filas)


# %% [CELL 05] — Incertidumbre (i): bootstrap no paramétrico dentro de período
def bootstrap_periodo(g: pd.DataFrame, half_range: float, B: int, rng) -> np.ndarray:
    """Remuestrea legisladores (filas) con reemplazo dentro del período y
    recalcula el Dalton en cada réplica. Captura la incertidumbre conjunta
    de centroides y de las proporciones s_p. IGNORA la dependencia entre
    períodos (ver CELL 07): usar solo como sensibilidad."""
    x = g[IDEOL].to_numpy()
    pa = g["partido_asignado"].to_numpy()
    out = np.empty(B)
    for b in range(B):
        sel = rng.integers(0, len(x), len(x))
        out[b] = dalton_arrays(x[sel], pa[sel], half_range)
    return out


# %% [CELL 06] — Incertidumbre (ii): error de medición del ideal point (vía IC)
def simulacion_error_medicion(g: pd.DataFrame, half_range: float, B: int, rng) -> dict:
    """Simula x*_i ~ N(dim_ideology, sigma_i) con sigma_i = |IC_high-IC_low|/3.92
    y recalcula el Dalton. Propaga la incertidumbre de estimación del ideal
    point (modelo dinámico) al índice. El valor absoluto cubre intervalos con
    cotas invertidas; su frecuencia se reporta en el diagnóstico ETL."""
    x = g[IDEOL].to_numpy()
    pa = g["partido_asignado"].to_numpy()
    sigma = np.abs(g[IC_HIGH].to_numpy() - g[IC_LOW].to_numpy()) / 3.92
    out = np.empty(B)
    for b in range(B):
        out[b] = dalton_arrays(rng.normal(x, sigma), pa, half_range)
    return {"draws": out, "n_ic_ancho_negativo": int(((g[IC_HIGH] - g[IC_LOW]) < 0).sum())}


# %% [CELL 07] — Incertidumbre (iii): cluster bootstrap por legislador (para deltas)
def bootstrap_delta_cluster(
    g_t: pd.DataFrame, g_t1: pd.DataFrame, half_range: float, B: int, rng
) -> np.ndarray:
    """Bootstrap de D_{t+1} - D_t por conglomerados de legislador (Id).

    1. Ids elegibles = union de Ids presentes en t y t+1 (panel no balanceado).
    2. Se remuestrean Ids con reemplazo (mismo número de clusters).
    3. Para cada Id muestreado se conservan TODAS sus filas en cada período;
       los tamaños de muestra y las proporciones partidarias varían por réplica.
    4. delta_b = D_{t+1}^{(b)} - D_t^{(b)}.

    Este esquema respeta la correlación entre períodos de los diputados que
    continúan (aprox. la mitad de cada legislatura), que el bootstrap
    independiente subestima. Es el test PRINCIPAL del script.
    """
    gt = g_t.reset_index(drop=True)
    g1 = g_t1.reset_index(drop=True)
    xt, pt = gt[IDEOL].to_numpy(), gt["partido_asignado"].to_numpy()
    x1, p1 = g1[IDEOL].to_numpy(), g1["partido_asignado"].to_numpy()
    idx_t = gt.groupby(ID).indices   # dict Id -> posiciones
    idx_1 = g1.groupby(ID).indices
    ids = sorted(set(idx_t) | set(idx_1))
    m = len(ids)
    deltas = np.empty(B)
    for b in range(B):
        samp = rng.integers(0, m, m)
        piezas_t = [idx_t[ids[i]] for i in samp if ids[i] in idx_t]
        piezas_1 = [idx_1[ids[i]] for i in samp if ids[i] in idx_1]
        if not piezas_t or not piezas_1:  # caso límite: período sin clusters
            deltas[b] = np.nan
            continue
        st = np.concatenate(piezas_t)
        s1 = np.concatenate(piezas_1)
        deltas[b] = dalton_arrays(x1[s1], p1[s1], half_range) - dalton_arrays(
            xt[st], pt[st], half_range
        )
    return deltas[~np.isnan(deltas)]


# %% [CELL 08] — Tests de diferencias consecutivas (con Holm) y contraste post-2018
def p_valor_bilateral(draws: np.ndarray, valor: float = 0.0) -> float:
    """p bilateral bootstrap con corrección de muestra finita (r+1)/(B+1):
    evita p = 0 exacto cuando ninguna réplica cruza el valor nulo. Con B
    réplicas, el mínimo p alcanzable es 2/(B+1)."""
    r = int(min(np.sum(draws <= valor), np.sum(draws >= valor)))
    return float(min(1.0, 2.0 * (r + 1.0) / (len(draws) + 1.0)))


def holm(pvals: list) -> np.ndarray:
    """Ajuste Holm-Bonferroni (control de FWE bajo dependencia cualquiera)."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    orden = np.argsort(p)
    escalados = p[orden] * (m - np.arange(m))
    escalados = np.maximum.accumulate(escalados)
    ajustados = np.empty(m)
    ajustados[orden] = np.minimum(escalados, 1.0)
    return ajustados


def tabla_diferencias(pares: list, deltas_cluster: dict, tabla_puntual: pd.DataFrame) -> pd.DataFrame:
    """Tabla de diferencias consecutivas D_{t+1} - D_t.

    delta: estimación puntual observada. IC y p-valor vienen del cluster
    bootstrap (CELL 07). p_holm: ajuste sobre las 5 comparaciones adyacentes.
    """
    filas = []
    for (t, t1) in pares:
        draws = deltas_cluster[(t, t1)]
        d_obs = (
            tabla_puntual.loc[tabla_puntual[PERIOD] == t1, "dalton"].iloc[0]
            - tabla_puntual.loc[tabla_puntual[PERIOD] == t, "dalton"].iloc[0]
        )
        ci = np.percentile(draws, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
        filas.append(
            {
                "comparacion": f"{t} -> {t1}",
                "dalton_t": tabla_puntual.loc[tabla_puntual[PERIOD] == t, "dalton"].iloc[0],
                "dalton_t1": tabla_puntual.loc[tabla_puntual[PERIOD] == t1, "dalton"].iloc[0],
                "delta": d_obs,
                "se_cluster": float(np.std(draws, ddof=1)),
                "ic95_low": float(ci[0]),
                "ic95_high": float(ci[1]),
                "p_bootstrap": p_valor_bilateral(draws),
            }
        )
    out = pd.DataFrame(filas)
    out["p_holm"] = holm(out["p_bootstrap"].tolist())
    out["significativo_5pct"] = out["p_holm"] < ALPHA
    return out


def contraste_post_reforma(dfa: pd.DataFrame, tabla_puntual: pd.DataFrame,
                          half_range: float, B: int, rng) -> dict:
    """Contraste CONFIRMATORIO pre-especificado: reforma electoral de 2018
    (Ley 20.840, primera legislatura proporcional en Periodo_5).

    H0: media(D, Periodo_1-4) = media(D, Periodo_5-6). Estadístico: diferencia
    de medias sobre los valores de Dalton, con distribución bootstrap por
    conglomerado de legislador (Id) sobre TODOS los períodos a la vez (un solo
    remuestreo de Ids por réplica, respetando la dependencia panel entre todos
    los períodos). Con 6 observaciones de período se evita deliberadamente
    cualquier test asintótico.
    """
    periodos = ordenar_periodos(dfa[PERIOD].unique())
    num = lambda p: int(str(p).split("_")[-1])
    pre = [p for p in periodos if num(p) <= 4]
    post = [p for p in periodos if num(p) >= 5]

    d_obs = tabla_puntual.set_index(PERIOD)["dalton"]
    dif_obs = float(np.mean([d_obs[p] for p in post]) - np.mean([d_obs[p] for p in pre]))

    # frames por período: (x, partidos, indices por Id como posiciones)
    frames = {}
    for p in periodos:
        g = dfa[dfa[PERIOD] == p].reset_index(drop=True)
        frames[p] = (g[IDEOL].to_numpy(), g["partido_asignado"].to_numpy(),
                     g.groupby(ID).indices)
    ids = sorted(set().union(*[set(f[2].keys()) for f in frames.values()]))
    m = len(ids)
    draws = np.full(B, np.nan)
    for b in range(B):
        samp = rng.integers(0, m, m)
        daltons = {}
        ok = True
        for p in periodos:
            x, pa, idx = frames[p]
            piezas = [idx[ids[i]] for i in samp if ids[i] in idx]
            if not piezas:  # período sin legisladores muestreados (caso límite)
                ok = False
                break
            sel = np.concatenate(piezas)
            daltons[p] = dalton_arrays(x[sel], pa[sel], half_range)
        if ok:
            draws[b] = np.mean([daltons[p] for p in post]) - np.mean([daltons[p] for p in pre])
    draws = draws[~np.isnan(draws)]
    p_valor = p_valor_bilateral(draws)
    ci = np.percentile(draws, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return {
        "contraste": "media(D, Periodo_5-6) - media(D, Periodo_1-4)",
        "delta_post_reforma": dif_obs,
        "ic95_low": float(ci[0]),
        "ic95_high": float(ci[1]),
        "p_bootstrap": p_valor,
        "B_validas": int(len(draws)),
    }


# %% [CELL 09] — Quiebres estructurales (EXPLORATORIO) y dispersión por legislador
def tests_quiebre_exploratorios(deltas_cluster: dict, pares: list) -> pd.DataFrame:
    """Wald por quiebre adyacente + sup-Wald conjunto, calibrados por bootstrap.

    W_k = (delta_k / se_k)^2, con se_k del cluster bootstrap. La distribución
    nula se obtiene CENTRANDO las réplicas bootstrap (draws - delta_obs), lo que
    las ubica bajo H0: delta = 0; el sup-Wald usa max_k W*_k por réplica para
    controlar la búsqueda sobre 4 candidatos de quiebre. Esto es un diagnóstico
    de remuestreo de muestra finita, NO un test Chow/Andrews clásico: con 6
    observaciones de período los tests asintóticos de series de tiempo no son
    válidos.
    """
    deltas = np.array(
        [
            tabla_puntual_global.loc[tabla_puntual_global[PERIOD] == t1, "dalton"].iloc[0]
            - tabla_puntual_global.loc[tabla_puntual_global[PERIOD] == t, "dalton"].iloc[0]
            for (t, t1) in pares
        ]
    )
    ses = np.array([np.std(deltas_cluster[p], ddof=1) for p in pares])
    draws = np.column_stack([deltas_cluster[p] for p in pares])
    centradas = draws - deltas  # bajo H0
    W = (deltas / ses) ** 2
    W_star = (centradas / ses) ** 2
    sup_W = float(np.max(W))
    B_ok = W_star.shape[0]
    p_conjunto = float(min(1.0, (np.sum(np.max(W_star, axis=1) >= sup_W) + 1) / (B_ok + 1)))
    filas = []
    for i, (t, t1) in enumerate(pares):
        filas.append(
            {
                "quiebre": f"{t} -> {t1}",
                "delta": deltas[i],
                "se_cluster": ses[i],
                "wald": W[i],
                # p con corrección (r+1)/(B+1): nunca exactamente cero
                "p_bootstrap": float(
                    min(1.0, (np.sum(W_star[:, i] >= W[i]) + 1) / (B_ok + 1))
                ),
            }
        )
    out = pd.DataFrame(filas)
    out["p_holm"] = holm(out["p_bootstrap"].tolist())
    out.attrs["sup_wald"] = sup_W
    out.attrs["p_sup_wald"] = p_conjunto
    return out


def tests_dispersion_legislador(dfa: pd.DataFrame) -> dict:
    """Tests de homogeneidad de dispersión de dim_ideology ENTRE períodos, a
    nivel de legislador (complemento del Dalton: este pondera por partidos;
    estos tests miran la dispersión cruda de la cámara).

    - Brown-Forsythe (levene center='median'): robusto a no normalidad.
    - Fligner-Killeen: robusto, recomendado con n desiguales por grupo.
    Global (6 grupos) y por pares consecutivos con Holm.
    """
    if not TIENE_SCIPY:
        return {"aviso": "scipy no disponible: tests de dispersión omitidos"}
    grupos = [g[IDEOL].to_numpy() for _, g in dfa.groupby(PERIOD, sort=False)]
    etiquetas = ordenar_periodos(dfa[PERIOD].unique())
    res = {
        "etiquetas": etiquetas,
        "brown_forsythe_global": sps.levene(*grupos, center="median"),
        "fligner_killeen_global": sps.fligner(*grupos),
    }
    filas = []
    for i in range(len(etiquetas) - 1):
        a = dfa.loc[dfa[PERIOD] == etiquetas[i], IDEOL]
        b = dfa.loc[dfa[PERIOD] == etiquetas[i + 1], IDEOL]
        filas.append(
            {
                "comparacion": f"{etiquetas[i]} -> {etiquetas[i+1]}",
                "p_brown_forsythe": float(sps.levene(a, b, center="median").pvalue),
                "p_fligner_killeen": float(sps.fligner(a, b).pvalue),
            }
        )
    tabla = pd.DataFrame(filas)
    tabla["p_bf_holm"] = holm(tabla["p_brown_forsythe"].tolist())
    tabla["p_fk_holm"] = holm(tabla["p_fligner_killeen"].tolist())
    res["pares_consecutivos"] = tabla
    return res


# %% [CELL 10] — Robustez: continuos, atribución única y normalización variable
def robustez_continuos(df_filtrado, half_range, pares, B, rng):
    """Repite los deltas cluster restringidos a legisladores con estimación
    válida en AMBOS períodos del par (mismo panel de individuos). Aísla el
    cambio de dispersión del cambio de composición (entradas/salidas)."""
    dfa = asignar_partido(df_filtrado, "salida")
    filas = []
    for (t, t1) in pares:
        gt = dfa[dfa[PERIOD] == t]
        g1 = dfa[dfa[PERIOD] == t1]
        comunes = np.intersect1d(gt[ID].unique(), g1[ID].unique())
        gt = gt[gt[ID].isin(comunes)]
        g1 = g1[g1[ID].isin(comunes)]
        if len(gt) < 10 or len(g1) < 10:
            continue
        draws = bootstrap_delta_cluster(gt, g1, half_range, B, rng)
        d_obs = dalton_arrays(g1[IDEOL].to_numpy(), g1["partido_asignado"].to_numpy(), half_range) - \
                dalton_arrays(gt[IDEOL].to_numpy(), gt["partido_asignado"].to_numpy(), half_range)
        ci = np.percentile(draws, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
        filas.append(
            {
                "comparacion": f"{t} -> {t1}",
                "n_continuos": int(len(comunes)),
                "delta_continuos": d_obs,
                "ic95_low": float(ci[0]),
                "ic95_high": float(ci[1]),
                "p_bootstrap": p_valor_bilateral(draws),
            }
        )
    out = pd.DataFrame(filas)
    if len(out):
        out["p_holm"] = holm(out["p_bootstrap"].tolist())
    return out


def robustez_normalizacion(df_filtrado, B, rng):
    """Sensibilidad del denominador: en cada réplica se remuestrean los
    legisladores dentro de CADA período, se recalcula el rango global CONJUNTO
    y con ese R variable se computa el Dalton de cada período. Reporta la
    distribución del rango y la correlación entre Dalton con R fijo vs R
    variable (si es ~1, la normalización no es lo que impulsa el resultado)."""
    dfa = asignar_partido(df_filtrado, "salida")
    periodos = ordenar_periodos(dfa[PERIOD].unique())
    datos = {
        p: (
            dfa.loc[dfa[PERIOD] == p, IDEOL].to_numpy(),
            dfa.loc[dfa[PERIOD] == p, "partido_asignado"].to_numpy(),
        )
        for p in periodos
    }
    rango_fijo = rango_global(df_filtrado)["half_range"]
    dalton_fijo = np.array(
        [dalton_arrays(*datos[p], rango_fijo) for p in periodos]
    )
    dalton_var = np.empty((B, len(periodos)))
    rangos = np.empty(B)
    for b in range(B):
        pool = []
        for p in periodos:
            x, pa = datos[p]
            sel = rng.integers(0, len(x), len(x))
            pool.append(x[sel])
            datos_sel = (x[sel], pa[sel])
            datos[p] = datos_sel  # reutiliza la misma selección para el Dalton
        todo = np.concatenate(pool)
        r_b = (todo.max() - todo.min()) / 2
        rangos[b] = r_b
        for j, p in enumerate(periodos):
            x, pa = datos[p]
            dalton_var[b, j] = dalton_arrays(x, pa, r_b)
        # restaurar datos originales
        datos = {
            p: (
                dfa.loc[dfa[PERIOD] == p, IDEOL].to_numpy(),
                dfa.loc[dfa[PERIOD] == p, "partido_asignado"].to_numpy(),
            )
            for p in periodos
        }
    corr = np.corrcoef(dalton_fijo, dalton_var.mean(axis=0))[0, 1]
    return {
        "half_range_fijo": rango_fijo,
        "media_half_range_variable": float(rangos.mean()),
        "sd_half_range_variable": float(rangos.std(ddof=1)),
        "corr_dalton_fijo_vs_variable": float(corr),
    }


# %% [CELL 11] — Orquestador, reporte y guardado de resultados
def run_all(csv_path: str = CSV_PATH, out_dir=OUT_DIR) -> dict:
    global tabla_puntual_global
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    # 1) Carga + ETL
    df_raw = cargar_datos(csv_path)
    diag = chequeos_etl(df_raw)
    df = filtrar_validas(df_raw)
    print(f"[ETL] Filas: {len(df_raw)} -> válidas: {len(df)} "
          f"({len(df_raw)-len(df)} eliminadas sin ideología/IC)")
    for k in ("filas_duplicadas_Id_Period", "anchos_IC_negativos",
              "quant_parties_inconsistente", "filas_con_ideologia_sin_partido"):
        print(f"[ETL] {k}: {diag[k]}")

    # 2) Estimaciones puntuales (ambas atribuciones)
    rango = rango_global(df)
    R = rango["half_range"]
    print(f"\n[DALTON] Rango global: [{rango['rango_min']:.4f}, "
          f"{rango['rango_max']:.4f}] | half-range fijo R = {R:.4f}")
    resultados = {"versiones": VERSIONES, "diagnostico_etl": diag, "rango": rango}
    tablas, deltas_cluster_all = {}, {}
    for modo in ATRIBUCIONES:
        dfa = asignar_partido(df, modo)
        tab = tabla_dalton(df, R, modo)
        tablas[modo] = tab
        print(f"\n[DALTON] Estimaciones puntuales (atribución: {modo})")
        print(tab.round(4).to_string(index=False))

        pares = [
            (tab[PERIOD].iloc[i], tab[PERIOD].iloc[i + 1])
            for i in range(len(tab) - 1)
        ]
        deltas_cluster = {
            (t, t1): bootstrap_delta_cluster(
                dfa[dfa[PERIOD] == t], dfa[dfa[PERIOD] == t1], R, B_CLUSTER, rng
            )
            for (t, t1) in pares
        }
        deltas_cluster_all[modo] = deltas_cluster
        tabla_puntual_global = tab  # usada por tests_quiebre_exploratorios

        tabla_dif = tabla_diferencias(pares, deltas_cluster, tab)
        post = contraste_post_reforma(dfa, tab, R, B_CLUSTER, rng)
        quiebres = tests_quiebre_exploratorios(deltas_cluster, pares)

        # bootstrap independiente y error de medición (sensibilidad)
        boot_indep = {
            p: bootstrap_periodo(dfa[dfa[PERIOD] == p], R, B_BOOT, rng)
            for p in tab[PERIOD]
        }
        meas = {
            p: simulacion_error_medicion(dfa[dfa[PERIOD] == p], R, B_MEAS, rng)
            for p in tab[PERIOD]
        }

        print(f"\n[TESTS] Diferencias consecutivas (cluster bootstrap, {modo})")
        print(tabla_dif.round(4).to_string(index=False))
        print(f"\n[TESTS] Contraste post-reforma 2018 ({modo}):")
        print(f"  delta = {post['delta_post_reforma']:.4f} | "
              f"IC95 = [{post['ic95_low']:.4f}, {post['ic95_high']:.4f}] | "
              f"p = {post['p_bootstrap']:.4f}")
        print(f"\n[TESTS] Quiebres exploratorios ({modo}) [sup-Wald = "
              f"{quiebres.attrs['sup_wald']:.3f}, p = "
              f"{quiebres.attrs['p_sup_wald']:.4f}]")
        print(quiebres.round(4).to_string(index=False))

        se_boot = {p: float(np.std(v, ddof=1)) for p, v in boot_indep.items()}
        se_meas = {p: float(np.std(v["draws"], ddof=1)) for p, v in meas.items()}
        print(f"\n[TESTS] SE por período ({modo}) — bootstrap indep. vs error de medición:")
        for p in tab[PERIOD]:
            print(f"  {p}: se_boot = {se_boot[p]:.4f} | se_med = {se_meas[p]:.4f}")

        resultados[modo] = {
            "tabla_dalton": tab,
            "tabla_diferencias": tabla_dif,
            "post_reforma": post,
            "quiebres": quiebres,
            "se_boot_indep": se_boot,
            "se_error_medicion": se_meas,
            "n_ic_negativo_total": int(sum(v["n_ic_ancho_negativo"] for v in meas.values())),
        }

    # 3) Tests de dispersión a nivel legislador (atribución salida)
    dfa_salida = asignar_partido(df, "salida")
    disp = tests_dispersion_legislador(dfa_salida)
    resultados["dispersion_legislador"] = disp
    if "pares_consecutivos" in disp:
        print("\n[TESTS] Dispersión cruda por legislador (Brown-Forsythe / Fligner-Killeen)")
        print(disp["pares_consecutivos"].to_string(index=False))
        print(f"  Global BF p = {disp['brown_forsythe_global'].pvalue:.2e} | "
              f"Global FK p = {disp['fligner_killeen_global'].pvalue:.2e}")

    # 4) Robustez
    pares_salida = [
        (tablas["salida"][PERIOD].iloc[i], tablas["salida"][PERIOD].iloc[i + 1])
        for i in range(len(tablas["salida"]) - 1)
    ]
    rob_cont = robustez_continuos(df, R, pares_salida, B_CLUSTER, rng)
    rob_norm = robustez_normalizacion(df, B_BOOT, rng)
    resultados["robustez_continuos"] = rob_cont
    resultados["robustez_normalizacion"] = rob_norm
    print("\n[ROBUSTEZ] Deltas solo con legisladores continuos (cluster bootstrap)")
    print(rob_cont.round(4).to_string(index=False) if len(rob_cont) else "  (sin pares)")
    print("\n[ROBUSTEZ] Normalización: R fijo vs variable")
    for k, v in rob_norm.items():
        print(f"  {k}: {v}")

    # 5) Guardado
    pref = "dalton"
    tablas["salida"].to_csv(out_dir / f"{pref}_puntuales_salida.csv", index=False)
    tablas["unico"].to_csv(out_dir / f"{pref}_puntuales_unico.csv", index=False)
    for modo in ATRIBUCIONES:
        resultados[modo]["tabla_diferencias"].to_csv(
            out_dir / f"{pref}_diferencias_{modo}.csv", index=False)
        resultados[modo]["quiebres"].to_csv(
            out_dir / f"{pref}_quiebres_{modo}.csv", index=False)
    diag["cobertura_por_periodo"].to_csv(out_dir / f"{pref}_etl_cobertura.csv")
    if "pares_consecutivos" in disp:
        disp["pares_consecutivos"].to_csv(out_dir / f"{pref}_dispersion_legislador.csv", index=False)
    if len(rob_cont):
        rob_cont.to_csv(out_dir / f"{pref}_robustez_continuos.csv", index=False)

    reporte = generar_reporte(resultados)
    (out_dir / "reporte_validacion_dalton.md").write_text(reporte, encoding="utf-8")
    print(f"\n[REPORTE] Guardado en: {(out_dir / 'reporte_validacion_dalton.md').resolve()}")
    return resultados


def generar_reporte(res: dict) -> str:
    """Reporte markdown autocontenido: resultados, construcción, versiones y
    salvedades de validación estadística/econométrica."""
    lin = []
    v = res["versiones"]
    lin.append("# Validación estadística: Índice de Dalton, Chile 2002-2026\n")
    lin.append("## 1. Entorno y parámetros\n")
    lin.append(f"- Python {v['python']} | numpy {v['numpy']} | pandas {v['pandas']} "
               f"| scipy {v['scipy']} | {v['plataforma']}")
    lin.append(f"- Semilla fija: {v['semilla']} | B(cluster) = {v['B_cluster']}, "
               f"B(período) = {v['B_boot']}, B(medición) = {v['B_medicion']}, "
               f"alpha = {v['alpha']}\n")

    lin.append("## 2. Diagnóstico ETL\n")
    d = res["diagnostico_etl"]
    for k in ("filas_totales", "filas_duplicadas_Id_Period", "anchos_IC_negativos",
              "anchos_IC_cero", "quant_parties_inconsistente",
              "filas_con_ideologia_sin_partido"):
        lin.append(f"- {k}: {d[k]}")
    lin.append("\nCobertura por período:\n")
    lin.append("```\n" + d["cobertura_por_periodo"].to_string() + "\n```\n")

    lin.append("## 3. Construcción\n")
    lin.append("D_t = sqrt(sum_p s_p ((y_p - ybar)/R)^2), con y_p centroide "
               "partidario de dim_ideology, s_p proporción de legisladores "
               "con estimación válida (NO cuota oficial de escaños), R = "
               f"{res['rango']['half_range']:.4f} (mitad del rango global, fijo).\n")

    for modo in ATRIBUCIONES:
        lin.append(f"## 4. Resultados — atribución '{modo}'\n")
        lin.append("### Dalton por período\n")
        lin.append("```\n" + res[modo]["tabla_dalton"].round(4).to_string(index=False) + "\n```\n")
        lin.append("### Diferencias consecutivas (cluster bootstrap por legislador)\n")
        lin.append("```\n" + res[modo]["tabla_diferencias"].round(4).to_string(index=False) + "\n```\n")
        p = res[modo]["post_reforma"]
        lin.append("### Contraste confirmatorio post-reforma 2018\n")
        lin.append(f"- {p['contraste']}: delta = {p['delta_post_reforma']:.4f}, "
                   f"IC95 = [{p['ic95_low']:.4f}, {p['ic95_high']:.4f}], "
                   f"p = {p['p_bootstrap']:.4f}\n")
        q = res[modo]["quiebres"]
        lin.append("### Quiebres exploratorios (Wald + sup-Wald bootstrap)\n")
        lin.append("```\n" + q.round(4).to_string(index=False) + "\n```")
        lin.append(f"- sup-Wald = {q.attrs['sup_wald']:.3f}, p = {q.attrs['p_sup_wald']:.4f}\n")

    lin.append("## 5. Dispersión cruda por legislador\n")
    disp = res["dispersion_legislador"]
    if "pares_consecutivos" in disp:
        lin.append("```\n" + disp["pares_consecutivos"].to_string(index=False) + "\n```")
        lin.append(f"- Global Brown-Forsythe p = {disp['brown_forsythe_global'].pvalue:.2e}; "
                   f"Fligner-Killeen p = {disp['fligner_killeen_global'].pvalue:.2e}\n")

    lin.append("## 6. Robustez\n")
    lin.append("### Solo legisladores continuos\n")
    lin.append("```\n" + (res["robustez_continuos"].round(4).to_string(index=False)
                          if len(res["robustez_continuos"]) else "(vacío)") + "\n```\n")
    rn = res["robustez_normalizacion"]
    lin.append("### Normalización fija vs variable\n")
    lin.append(f"- R fijo = {rn['half_range_fijo']:.4f}; R variable: media = "
               f"{rn['media_half_range_variable']:.4f} (sd {rn['sd_half_range_variable']:.4f}); "
               f"corr(Dalton fijo, Dalton variable) = {rn['corr_dalton_fijo_vs_variable']:.3f}\n")

    lin.append("## 7. Salvedades de validación\n")
    lin.append("""
1. Serie de período corta (K=6): no se aplican tests asintóticos de quiebres
   (Chow, CUSUM, Andrews). Toda la inferencia es bootstrap a nivel de
   legislador; el sup-Wald es un diagnóstico de muestra finita recalibrado
   por remuestreo, y el contraste post-2018 es el único pre-especificado.
2. s_p es la proporción de legisladores CON estimación válida, no la cuota
   oficial de escaños. Como la cobertura varía entre períodos
   (~28% vs ~38%), si el missingness correlaciona con partido/ideología el
   Dalton de períodos con menor cobertura está sesgado (riesgo MNAR).
3. Dependencia panel: los deltas usan cluster bootstrap por Id (legislador),
   que respeta la correlación de diputados que continúan entre períodos; el
   bootstrap independiente se reporta como cota optimista.
4. Error de medición: sigma_i = |IC_high - IC_low|/3.92 asume IC ~95% normal;
   los intervalos con cotas invertidas (conteo en sección 2) usan el valor
   absoluto del ancho.
5. Atribución partidaria: 'salida' usa switchers; 'unico' los excluye. Si los
   resultados difieren entre atribuciones, la conclusión no es robusta al
   criterio de asignación de partido.
6. Permutación de etiquetas de período NO se usa como test principal: los
   períodos difieren institucional y composicionalmente, violando el
   supuesto de intercambiabilidad del test de permutación.
7. Multiplicidad: Holm sobre las 5 comparaciones adyacentes y sobre los
   contrastes de dispersión por pares.
""")
    return "\n".join(lin)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        CSV_PATH = sys.argv[1]
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "."
    RESULTADOS = run_all(CSV_PATH, carpeta)
