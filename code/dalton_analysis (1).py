# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
# ---

# %%
"""
Estimación del Índice de Dalton (2008) sobre el long-format real
(ideologia_congreso_chile_2002_2026_long_format.csv), con dos atribuciones
de afiliación partidaria, SIN ponderar por asistencia, más diagnósticos
para investigar qué expande el rango efectivo de dim_ideology entre
períodos (missingness, incertidumbre del modelo dinámico, composición de
legisladores nuevos vs. continuos).

Columnas reales del CSV (confirmadas en PP.ipynb):
    n, Id, Name, Period, dim_IC_low, dim_ideology, dim_IC_high,
    wnom_ideology, bay_ic_low, bay_ideology, bay_ic_high,
    quant_parties, party_1, party_2, party_3, party_4, Sex, Birth_date

dim_ideology solo tiene 808/2574 filas no-nulas (31%) -- esto es
estructural (legislador ausente del período o sin suficiente info de
voto para estimar), no un error de carga.
"""

# %%
import numpy as np
import pandas as pd


# %%
CSV_PATH = "ideologia_congreso_chile_2002_2026_long_format.csv"  # ajustar ruta si difiere
IDEOL_COL = "dim_ideology"
PERIOD_COL = "Period"
ID_COL = "Id"          # identificador estable de legislador (usar Id, no Name, por homónimos)
PARTY_COLS = ["party_1", "party_2", "party_3", "party_4"]


# %%
# ----------------------------------------------------------------------
# 0. Carga y filtro de observaciones válidas
#
# Se descartan las filas período-legislador que no tienen dato ideológico
# en dim_ideology, dim_IC_low o dim_IC_high (cotas de intervalo o índice
# faltante) -- ya sea porque el legislador no formaba parte del parlamento
# ese período, o porque el modelo dinámico no pudo estimarle un ideal
# point por baja participación en votaciones nominales. Antes de descartar,
# se reporta aparte cualquier Id que quede SIN NINGÚN dato ideológico en
# NINGÚN período -- eso es una señal de posible problema de matching de
# IDs entre bases, no de ausencia genuina, y no debe descartarse en
# silencio junto con el resto.
# ----------------------------------------------------------------------
def cargar_datos(path=CSV_PATH):
    df = pd.read_csv(path)
    for c in [IDEOL_COL, "dim_IC_low", "dim_IC_high"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# %%
def diagnostico_missingness_estructural(df, id_col=ID_COL,
                                         cols_ideol=(IDEOL_COL, "dim_IC_low", "dim_IC_high"),
                                         party_cols=PARTY_COLS, quant_col="quant_parties"):
    """Chequeo previo al filtro: para las filas con algún dato ideológico
    faltante, ¿tienen también party_1/quant_parties faltantes (consistente
    con 'no estaba en el parlamento')? Y separadamente: ¿hay algún Id que
    no tenga NINGÚN dato ideológico válido en NINGÚN período? Esos casos
    se reportan, no se descartan en silencio."""
    cols_presentes = [c for c in cols_ideol if c in df.columns]
    mask_falta_ideol = df[cols_presentes].isna().any(axis=1)

    tiene_partido = df[party_cols].notna().any(axis=1)
    tiene_quant = df[quant_col].notna() if quant_col in df.columns else pd.Series(False, index=df.index)

    inconsistentes = df[mask_falta_ideol & (tiene_partido | tiene_quant)]
    n_inconsistentes = len(inconsistentes)

    ids_totales = set(df[id_col].unique())
    ids_con_algun_dato = set(df.loc[~mask_falta_ideol, id_col].unique())
    ids_sin_ningun_dato = ids_totales - ids_con_algun_dato

    print(f"Filas con dato ideológico faltante pero CON partido/quant_parties asignado: {n_inconsistentes}")
    print("  (si es alto: el filtro no es inocuo, puede estar sesgando hacia legisladores más activos)")
    print(f"IDs sin NINGÚN dato ideológico válido en NINGÚN período: {len(ids_sin_ningun_dato)}")
    if ids_sin_ningun_dato:
        print(f"  IDs afectados (revisar matching, no descartar en silencio): {sorted(ids_sin_ningun_dato)[:20]}"
              f"{' ...' if len(ids_sin_ningun_dato) > 20 else ''}")
    print()
    return {
        "n_inconsistentes": n_inconsistentes,
        "ids_sin_ningun_dato": ids_sin_ningun_dato,
    }


# %%
def filtrar_filas_validas(df, cols_ideol=(IDEOL_COL, "dim_IC_low", "dim_IC_high")):
    """Elimina filas período-legislador sin dato ideológico (en cualquiera
    de dim_ideology, dim_IC_low, dim_IC_high). Se asume ya reportado el
    diagnóstico de diagnostico_missingness_estructural antes de llamar a
    esta función."""
    cols_presentes = [c for c in cols_ideol if c in df.columns]
    return df.dropna(subset=cols_presentes).copy()


# %%
def resumen_missingness(df, ideol_col=IDEOL_COL, period_col=PERIOD_COL):
    """Diagnóstico Mecanismo 1: ¿la cobertura de dim_ideology varía entre
    períodos? Si Periodo_5/6 tienen menor tasa de missingness relativa
    (más legisladores CON estimación válida sobre el total), la muestra
    efectiva de cada período no es comparable y el rango puede expandirse
    por composición, no por polarización real."""
    tot = df.groupby(period_col).size().rename("n_total_filas")
    validos = df.groupby(period_col)[ideol_col].apply(lambda s: s.notna().sum()).rename("n_validos")
    out = pd.concat([tot, validos], axis=1)
    out["pct_cobertura"] = (out["n_validos"] / out["n_total_filas"] * 100).round(1)
    return out


# %%
def resumen_incertidumbre(df, period_col=PERIOD_COL,
                           low_col="dim_IC_low", high_col="dim_IC_high",
                           ideol_col=IDEOL_COL):
    """Diagnóstico Mecanismo 2: ancho del intervalo de confianza en las
    colas (percentil 10 inferior y percentil 90 superior de dim_ideology
    por período) vs. ancho en el centro. Si el IC se angosta en las colas
    en los períodos de mayor rango, más info de voto está permitiendo
    estimaciones puntuales mas extremas con la MISMA o mayor confianza,
    lo cual es un mecanismo estadístico legítimo de expansión de rango,
    no necesariamente polarización political real."""
    filas = []
    for periodo, g in df.dropna(subset=[ideol_col]).groupby(period_col):
        g = g.copy()
        g["ancho_ic"] = g[high_col] - g[low_col]
        p10 = g[ideol_col].quantile(0.10)
        p90 = g[ideol_col].quantile(0.90)
        cola_baja = g[g[ideol_col] <= p10]["ancho_ic"].mean()
        cola_alta = g[g[ideol_col] >= p90]["ancho_ic"].mean()
        centro = g[(g[ideol_col] > p10) & (g[ideol_col] < p90)]["ancho_ic"].mean()
        filas.append({
            period_col: periodo,
            "ancho_ic_cola_baja": round(cola_baja, 4),
            "ancho_ic_centro": round(centro, 4),
            "ancho_ic_cola_alta": round(cola_alta, 4),
        })
    return pd.DataFrame(filas)


# %%
def resumen_nuevos_vs_continuos(df, id_col=ID_COL, period_col=PERIOD_COL,
                                 ideol_col=IDEOL_COL):
    """Diagnóstico Mecanismo 3: separa, en cada período, a los legisladores
    que YA tenían dim_ideology válido en el período inmediatamente anterior
    ('continuos') de los que aparecen con estimación válida por primera vez
    ('nuevos'). Si los 'nuevos' concentran las posiciones más extremas y
    empujan el rango, es evidencia de entrada de actores genuinamente
    distintos (Mecanismo 3), no artefacto de escala."""
    periodos_ordenados = sorted(df[period_col].unique(),
                                 key=lambda p: int(p.split("_")[-1]) if "_" in str(p) else p)
    valido = df.dropna(subset=[ideol_col])
    ids_por_periodo = {p: set(valido[valido[period_col] == p][id_col]) for p in periodos_ordenados}

    filas = []
    ids_previos = set()
    for p in periodos_ordenados:
        ids_actuales = ids_por_periodo[p]
        nuevos_ids = ids_actuales - ids_previos
        continuos_ids = ids_actuales & ids_previos

        sub = valido[valido[period_col] == p]
        nuevos = sub[sub[id_col].isin(nuevos_ids)][ideol_col]
        continuos = sub[sub[id_col].isin(continuos_ids)][ideol_col]

        filas.append({
            period_col: p,
            "n_nuevos": len(nuevos),
            "media_nuevos": round(nuevos.mean(), 3) if len(nuevos) else np.nan,
            "sd_nuevos": round(nuevos.std(), 3) if len(nuevos) else np.nan,
            "n_continuos": len(continuos),
            "media_continuos": round(continuos.mean(), 3) if len(continuos) else np.nan,
            "sd_continuos": round(continuos.std(), 3) if len(continuos) else np.nan,
        })
        ids_previos = ids_previos | ids_actuales  # acumulativo
    return pd.DataFrame(filas)


# %%
# ----------------------------------------------------------------------
# 1. Normalización -- denominador FIJO para todo el panel
# ----------------------------------------------------------------------
def get_global_half_range(df, col=IDEOL_COL):
    validos = df[col].dropna()
    rango_min, rango_max = validos.min(), validos.max()
    amplitud = rango_max - rango_min
    return {
        "rango_min": rango_min,
        "rango_max": rango_max,
        "amplitud": amplitud,
        "media_rango": amplitud / 2,
    }


# %%
# ----------------------------------------------------------------------
# 2. Atribución de partido
#
# quant_parties = número de partidos distintos a los que estuvo afiliado
# el legislador DENTRO del período (no un conteo agregado del panel).
# party_1...party_4 se asumen ordenadas temporalmente (primera a última
# afiliación dentro del período). Se infiere por posición de columna:
#   - 'partido de salida' -> última columna no-NA (party_4 > party_3 >
#     party_2 > party_1), representa la afiliación de salida del período.
#   - 'partido único' -> exige quant_parties == 1, y ADEMÁS valida por
#     conteo posicional (debe haber exactamente 1 columna party_n no-NA);
#     si no coincide, se marca como inconsistencia en vez de asumirla.
# ----------------------------------------------------------------------
def _validar_consistencia_quant_parties(df, party_cols=PARTY_COLS, quant_col="quant_parties"):
    """Chequeo de consistencia: quant_parties debe coincidir con el
    conteo real de columnas party_n no-NA en la fila. Reporta -- no
    corrige silenciosamente -- las filas donde no coinciden."""
    conteo_real = df[party_cols].notna().sum(axis=1)
    mask_incons = df[quant_col].notna() & (conteo_real != df[quant_col])
    n_incons = mask_incons.sum()
    if n_incons:
        print(f"Aviso: {n_incons} filas donde quant_parties no coincide con el conteo real "
              f"de columnas party_n no-NA (revisar antes de confiar en el filtro 'partido único').")
    return mask_incons


# %%
def asignar_partido_ultima_afiliacion(df, party_cols=PARTY_COLS):
    """'Partido de salida': última columna party_n no-NA (primera a última
    afiliación dentro del período -> se toma la última, es decir la de
    salida)."""
    df = df.copy()

    def ultimo_no_na(row):
        vals = [row[c] for c in party_cols if pd.notna(row[c])]
        return vals[-1] if vals else np.nan

    df["partido_asignado"] = df.apply(ultimo_no_na, axis=1)
    return df


# %%
def asignar_partido_primera_afiliacion(df, party_cols=PARTY_COLS):
    """Complemento simetrico: 'partido de entrada', primera columna
    party_n no-NA dentro del período. Útil como contraste de robustez
    frente a 'partido de salida'."""
    df = df.copy()

    def primero_no_na(row):
        vals = [row[c] for c in party_cols if pd.notna(row[c])]
        return vals[0] if vals else np.nan

    df["partido_asignado"] = df.apply(primero_no_na, axis=1)
    return df


# %%
def asignar_partido_unico(df, party_cols=PARTY_COLS, quant_col="quant_parties"):
    """'Partido único': quant_parties == 1 (sin cambios intra-período).
    Se valida cruzando con el conteo real de columnas party_n no-NA;
    las filas inconsistentes se excluyen explícitamente en vez de
    asumir que quant_parties es siempre correcto."""
    df = df.copy()
    mask_incons = _validar_consistencia_quant_parties(df, party_cols, quant_col)
    mask_unico = (df[quant_col] == 1) & (~mask_incons)
    df = df[mask_unico].copy()

    def unico_no_na(row):
        vals = [row[c] for c in party_cols if pd.notna(row[c])]
        return vals[0] if vals else np.nan

    df["partido_asignado"] = df.apply(unico_no_na, axis=1)
    return df.dropna(subset=["partido_asignado"])


# %%
# ----------------------------------------------------------------------
# 3. Centroides + seat share (sin ponderar por asistencia)
# ----------------------------------------------------------------------
def calcular_centroides_y_seatshare(df, period_col=PERIOD_COL,
                                     party_col="partido_asignado",
                                     ideol_col=IDEOL_COL):
    df = df.dropna(subset=[ideol_col, party_col])
    centroides = (
        df.groupby([period_col, party_col])[ideol_col]
        .mean()
        .reset_index()
        .rename(columns={ideol_col: "centroide"})
    )
    escanos = (
        df.groupby([period_col, party_col])
        .size()
        .reset_index(name="n_bancas")
    )
    out = centroides.merge(escanos, on=[period_col, party_col])
    total_bancas = out.groupby(period_col)["n_bancas"].transform("sum")
    out["seat_share"] = out["n_bancas"] / total_bancas
    return out.rename(columns={party_col: "partido"})


# %%
# ----------------------------------------------------------------------
# 4. Índice de Dalton
# ----------------------------------------------------------------------
def dalton_index(party_centroids, half_range, period_col=PERIOD_COL):
    filas = []
    for periodo, g in party_centroids.groupby(period_col):
        v = g["seat_share"].values
        v = v / v.sum()
        y = g["centroide"].values
        y_bar = np.sum(v * y)
        di = np.sqrt(np.sum(v * ((y - y_bar) / half_range) ** 2))
        filas.append({period_col: periodo, "dalton_index": round(di, 3),
                      "n_partidos": len(g)})
    return pd.DataFrame(filas)


# %%
# ----------------------------------------------------------------------
# 5. Descomposición ANOVA (entre vs. intra partido) -- ya solicitado antes
# ----------------------------------------------------------------------
def descomposicion_anova(df, period_col=PERIOD_COL, party_col="partido_asignado",
                          ideol_col=IDEOL_COL):
    df = df.dropna(subset=[ideol_col, party_col])
    filas = []
    for periodo, g in df.groupby(period_col):
        media_global = g[ideol_col].mean()
        n_total = len(g)
        var_entre = var_intra = 0.0
        for partido, gp in g.groupby(party_col):
            n_p = len(gp)
            media_p = gp[ideol_col].mean()
            var_entre += n_p * (media_p - media_global) ** 2
            var_intra += ((gp[ideol_col] - media_p) ** 2).sum()
        var_entre /= n_total
        var_intra /= n_total
        var_total = var_entre + var_intra
        filas.append({
            period_col: periodo,
            "var_entre_partidos": round(var_entre, 4),
            "var_intra_partidos": round(var_intra, 4),
            "pct_var_intra": round(100 * var_intra / var_total, 1) if var_total > 0 else np.nan,
        })
    return pd.DataFrame(filas)


# %%
# ----------------------------------------------------------------------
# 6. Orquestador principal
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# 6b. Chequeo institucional: escaños oficiales de la Cámara vs. n_validos
#
# Ley 20.840 (2015) reemplazó el sistema binominal por uno proporcional
# y aumentó la Cámara de 120 a 155 diputados, vigente desde las
# elecciones de noviembre 2017 / asunción marzo 2018 (BCN). Esto explica
# mecánicamente por qué n_validos salta de ~121-123 (Periodos 1-4) a
# ~155-163 (Periodos 5-6) -- no es artefacto del modelo, es un cambio
# institucional real y fechado. La variación dentro de cada régimen
# (121 vs. 123; 163 vs. 157) es consistente con vacancias/reemplazos
# (reelección parcial, fallecimientos, renuncias) a lo largo del
# período -- chequeable empíricamente contrastando cuántos Id distintos
# aparecen por período vs. el número de escaños nominales.
# ----------------------------------------------------------------------
ESCANOS_OFICIALES = {
    # ajustar las etiquetas de período si no calzan 1:1 con tu columna Period
    "Periodo_1": 120,  # 2002-2006, sistema binominal
    "Periodo_2": 120,  # 2006-2010
    "Periodo_3": 120,  # 2010-2014
    "Periodo_4": 120,  # 2014-2018 (última legislatura binominal)
    "Periodo_5": 155,  # 2018-2022, primera legislatura proporcional (Ley 20.840)
    "Periodo_6": 155,  # 2022-2026
}


# %%
def chequeo_escanos_oficiales(df, id_col=ID_COL, period_col=PERIOD_COL,
                               ideol_col=IDEOL_COL, escanos_oficiales=ESCANOS_OFICIALES):
    """Contrasta n_validos (Id únicos con dato ideológico válido) contra
    el número oficial de escaños de la Cámara en cada período. El exceso
    sobre el número oficial (n_validos - escanos_oficiales) es atribuible
    a rotación dentro del período (vacancias, reemplazos, renuncias) --
    NO a un error de conteo."""
    filas = []
    for periodo, g in df.groupby(period_col):
        ids_validos = g.loc[g[ideol_col].notna(), id_col].nunique()
        oficial = escanos_oficiales.get(periodo, np.nan)
        filas.append({
            period_col: periodo,
            "n_ids_validos": ids_validos,
            "escanos_oficiales": oficial,
            "exceso_por_rotacion": ids_validos - oficial if pd.notna(oficial) else np.nan,
        })
    return pd.DataFrame(filas)


# %%
def analisis_completo(csv_path=CSV_PATH):
    df_crudo = cargar_datos(csv_path)

    print("=== Diagnóstico previo: missingness estructural (antes de filtrar) ===")
    diag_estructural = diagnostico_missingness_estructural(df_crudo)

    print("=== Filtrando filas período-legislador sin dato ideológico "
          "(dim_ideology, dim_IC_low o dim_IC_high) ===")
    n_antes = len(df_crudo)
    df = filtrar_filas_validas(df_crudo)
    print(f"  Filas antes: {n_antes} -> filas después: {len(df)} "
          f"({n_antes - len(df)} eliminadas)")
    if diag_estructural["ids_sin_ningun_dato"]:
        print(f"  NOTA: {len(diag_estructural['ids_sin_ningun_dato'])} Id(s) quedaron sin ningún "
              f"dato ideológico en ningún período -- revisar matching antes de asumir ausencia real.")
    print()

    print("=== Diagnóstico 1: cobertura de dim_ideology por período (Mecanismo 1) ===")
    cobertura = resumen_missingness(df_crudo)
    print(cobertura)
    print()

    print("=== Diagnóstico 2: ancho de IC en colas vs. centro (Mecanismo 2) ===")
    incertidumbre = resumen_incertidumbre(df)
    print(incertidumbre.to_string(index=False))
    print()

    print("=== Diagnóstico 3: legisladores nuevos vs. continuos por período (Mecanismo 3) ===")
    nuevos_vs_continuos = resumen_nuevos_vs_continuos(df)
    print(nuevos_vs_continuos.to_string(index=False))
    print()

    print("=== Diagnóstico institucional: escaños oficiales de la Cámara vs. n_validos ===")
    print("    (Ley 20.840, 2015: pasa de 120 a 155 diputados desde la legislatura 2018-2022)")
    escanos = chequeo_escanos_oficiales(df_crudo)
    print(escanos.to_string(index=False))
    print()

    rango_info = get_global_half_range(df)
    half_range = rango_info["media_rango"]
    print(f"Normalización (denominador fijo, media del rango global): {half_range:.4f}")
    print(f"  Rango global observado: [{rango_info['rango_min']:.4f}, {rango_info['rango_max']:.4f}]")
    print()

    # atribución 1: partido de salida
    df_salida = asignar_partido_ultima_afiliacion(df)
    cent_salida = calcular_centroides_y_seatshare(df_salida, party_col="partido_asignado")
    di_salida = dalton_index(cent_salida, half_range).rename(
        columns={"dalton_index": "dalton_partido_salida"})

    # atribución 2: partido único (via quant_parties == 1, ya en el CSV)
    df_unico = asignar_partido_unico(df)
    cent_unico = calcular_centroides_y_seatshare(df_unico, party_col="partido_asignado")
    di_unico = dalton_index(cent_unico, half_range).rename(
        columns={"dalton_index": "dalton_partido_unico"})

    tabla = di_salida[[PERIOD_COL, "dalton_partido_salida"]].merge(
        di_unico[[PERIOD_COL, "dalton_partido_unico"]], on=PERIOD_COL, how="outer"
    )

    anova = descomposicion_anova(df_salida, party_col="partido_asignado")
    anova["pct_var_entre"] = (100 - anova["pct_var_intra"]).round(1)
    tabla = tabla.merge(anova[[PERIOD_COL, "pct_var_entre", "pct_var_intra"]], on=PERIOD_COL, how="left")
    tabla = tabla.sort_values(PERIOD_COL).reset_index(drop=True)

    print("=== Tabla comparativa completa: Índice de Dalton, todos los períodos ===")
    print(tabla.to_string(index=False))
    print()

    return {
        "tabla_dalton": tabla,
        "cobertura": cobertura,
        "incertidumbre": incertidumbre,
        "nuevos_vs_continuos": nuevos_vs_continuos,
        "escanos_oficiales": escanos,
        "rango_info": rango_info,
    }


# %%
if __name__ == "__main__":
    resultados = analisis_completo()
