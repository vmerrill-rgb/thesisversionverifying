# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
import pandas as pd
import numpy as np

# %%
# Load long-format ideological estimates
df = pd.read_csv("ideologia_congreso_chile_2002_2026_long_format.csv")

# %%
df.info()

# %%
print(df)

# %%
columns_to_merge = ['party_1', 'party_2', 'party_3', 'party_4']

# 1. Forzar a que todas las columnas seleccionadas sean numéricas (los textos se convertirán en NaN)
for col in columns_to_merge:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 2. Reemplazar los valores vacíos (NaN) por 0 para que no rompan el cálculo
df[columns_to_merge] = df[columns_to_merge].fillna(0)

# 3. Ahora sí, crear la columna unificada sin errores
df['Party'] = df[columns_to_merge].idxmax(axis=1)

print(df[['Party'] + columns_to_merge].head(20))

# %%
columns_to_merge = ['party_1', 'party_2', 'party_3', 'party_4']

# 1. Identificar qué filas tienen un total de 0 en todas las columnas de partidos
# (Estas son las filas que originalmente eran NaN)
filas_vacias = (df[columns_to_merge].sum(axis=1) == 0)

# 2. Reemplazar el valor en 'Party' por None (o pd.NA) donde todas eran cero
df.loc[filas_vacias, 'Party'] = None

# 3. Verificar el resultado viendo el conteo de nulos actuales
print("Cantidad de valores faltantes (NaN) en la columna Party:")
print(df['Party'].isna().sum())

# 4. Mostrar las primeras filas para confirmar
print("\nVista previa de la columna:")
print(df['Party'].head(10))

# %%
print(df.head(10))

# %%
print(df['Party'].tail(20))

# %%
#normalización de índice estilo Dalton

# %%
#Ponderador grupal por Asistencia
import re
import unicodedata
from pathlib import Path
import pandas as pd

# %%
# Carpeta donde están tus archivos (ajusta si es necesario)
DATA_DIR = Path(r"C:\Users\merri\OneDrive - Universidad de Chile\'26\Seminario de Investigacion\Evidence and estimations")

PATH_2022_26 = DATA_DIR / "matriz__periodo_2022_26.csv"   # -> Periodo_6
PATH_2018_22 = DATA_DIR / "matriz__periodo_2018_22.csv"   # -> Periodo_5
PATH_2014_18 = DATA_DIR / "matriz__periodo_2014_18.csv"   # -> Periodo_4
PATH_2010_14 = DATA_DIR / "matriz__periodo_2010_14.csv"   # -> Periodo_3
PATH_2006_10 = DATA_DIR / "matriz__periodo_2006_10.csv"   # -> Periodo_2
PATH_2002_06 = DATA_DIR / "matriz__periodo_2002_06.csv"   # -> Periodo_1
PATH_LONG    = DATA_DIR / "ideologia_congreso_chile_2002_2026_long_format.csv"

# Columnas identificadoras (no son votos) en las matrices de asistencia
ID_COLS = ["n", "DiputadoId", "Nombre", "ApellidoPaterno", "ApellidoMaterno"]


# %%
#Repair
def fix_mojibake(text):
    '''Repara nombres con doble-encoding tipo MarA-a -> Maria, RenA(c) -> Rene.

    Estrategia: si el texto contiene el patron tipico de UTF-8 mal
    decodificado como Latin-1 (secuencias 'A' + vocal/consonante especial,
    o 'A'), se intenta:  text.encode('latin-1').decode('utf-8')
    Si funciona sin errores y no introduce caracteres de reemplazo, se usa
    el resultado corregido. En caso contrario se devuelve el texto original.
    '''
    if not isinstance(text, str) or text == "":
        return text

    # Señales típicas de mojibake UTF-8 -> Latin-1
    mojibake_markers = ("Ã", "Â", "â€", "�")
    if not any(marker in text for marker in mojibake_markers):
        return text

    try:
        repaired = text.encode("latin-1").decode("utf-8")
        if "�" not in repaired:
            return repaired
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    # Intento alternativo: cp1252 -> utf-8 (variante común en exportes de Excel)
    try:
        repaired = text.encode("cp1252").decode("utf-8")
        if "�" not in repaired:
            return repaired
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    return text


# %%
#cleaning
def normalize_name_part(text):
    '''Limpia espacios y capitaliza cada palabra de un fragmento de nombre.'''
    if not isinstance(text, str):
        return ""
    text = fix_mojibake(text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)  # colapsa espacios múltiples/tabs
    if text == "":
        return ""

    def cap_word(word):
        # Maneja apóstrofes y guiones dentro de la palabra (O'Higgins, Pérez-Díaz)
        parts = re.split(r"([-'])", word)
        return "".join(p.capitalize() if p not in ("-", "'") else p for p in parts)

    return " ".join(cap_word(w) for w in text.split(" "))


def build_full_name(nombre, apellido_paterno, apellido_materno):
    '''Concatena Nombre + ApellidoPaterno + ApellidoMaterno en formato Name.'''
    partes = [
        normalize_name_part(nombre),
        normalize_name_part(apellido_paterno),
        normalize_name_part(apellido_materno),
    ]
    partes = [p for p in partes if p]  # descarta vacíos
    return " ".join(partes)


def normalize_for_matching(text):
    '''Version sin tildes/mayusculas, solo para hacer el merge mas robusto
    ante pequenas diferencias de tildes entre bases (no se usa como columna
    final Name, solo como llave auxiliar de emparejamiento).'''
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()



# %%
#dataset loading
def load_table(path):
    '''Carga un csv o xlsx probando varios encodings comunes si es CSV.'''
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)

    encodings_to_try = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    last_err = None
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc, keep_default_na=False)
            return df
        except (UnicodeDecodeError, LookupError) as e:
            last_err = e
            continue
    raise last_err



# %%
#attendance computation
def compute_attendance(df_raw, period_label, id_cols=ID_COLS):
    '''Calcula la asistencia por diputado para una matriz de votacion.

    Asistencia = (Afirmativo + En Contra) / (cualquier otra entrada de voto)
    El denominador cuenta TODAS las columnas de votacion (todas las columnas
    que no son identificadoras), sin importar su valor.
    '''
    df = df_raw.copy()

    # Arregla encoding en las columnas de nombre antes de todo
    for col in ("Nombre", "ApellidoPaterno", "ApellidoMaterno"):
        if col in df.columns:
            df[col] = df[col].map(fix_mojibake)

    # Columna Name (C + D + E) en formato Primera Letra Mayúscula
    df["Name"] = df.apply(
        lambda r: build_full_name(
            r.get("Nombre", ""), r.get("ApellidoPaterno", ""), r.get("ApellidoMaterno", "")
        ),
        axis=1,
    )

    # Columnas de votación = todas menos las identificadoras
    vote_cols = [c for c in df.columns if c not in id_cols and c != "Name"]

    votes = df[vote_cols]

    afirmativo = (votes == "Afirmativo").sum(axis=1)
    en_contra = (votes == "En Contra").sum(axis=1)
    total_votaciones = votes.shape[1]  # cualquier otra entrada = todas las columnas de voto

    out = pd.DataFrame({
        "Name": df["Name"],
        "Period": period_label,
        "Afirmativo": afirmativo,
        "En_Contra": en_contra,
        "Total_Votaciones": total_votaciones,
    })
    out["Asistencia"] = (out["Afirmativo"] + out["En_Contra"]) / out["Total_Votaciones"]

    # Llave auxiliar sin tildes/mayúsculas para un merge más tolerante
    out["Name_key"] = out["Name"].map(normalize_for_matching)

    return out



# %%

df_2022_26_raw = load_table(PATH_2022_26)
df_2018_22_raw = load_table(PATH_2018_22)  
df_2014_18_raw = load_table(PATH_2014_18)
df_2010_14_raw = load_table(PATH_2010_14)
df_2006_10_raw = load_table(PATH_2006_10)
df_2002_06_raw = load_table(PATH_2002_06)

asistencia_2022_26 = compute_attendance(df_2022_26_raw, period_label="Periodo_6")
asistencia_2018_22 = compute_attendance(df_2018_22_raw, period_label="Periodo_5")
asistencia_2014_18 = compute_attendance(df_2014_18_raw, period_label="Periodo_4")
asistencia_2010_14 = compute_attendance(df_2010_14_raw, period_label="Periodo_3")
asistencia_2006_10 = compute_attendance(df_2006_10_raw, period_label="Periodo_2")
asistencia_2002_06 = compute_attendance(df_2002_06_raw, period_label="Periodo_1")

asistencia_total = pd.concat([asistencia_2022_26, asistencia_2018_22, asistencia_2014_18, asistencia_2010_14, asistencia_2006_10, asistencia_2002_06], ignore_index=True)
asistencia_total.tail(20)

# %%
#attendance repair
df_long_raw = load_table(PATH_LONG)

# Arregla posible mojibake también en la base long, por si acaso
if "Name" in df_long_raw.columns:
    df_long_raw["Name"] = df_long_raw["Name"].map(fix_mojibake)

df_long = df_long_raw.copy()
df_long["Name_key"] = df_long["Name"].map(normalize_for_matching)

df_long.head()

# %%
# --- Merge 1: exacto por Period + Name ---
merged = df_long.merge(
    asistencia_total.drop(columns=["Name_key"]),
    on=["Period", "Name"],
    how="left",
    suffixes=("", "_asistencia"),
)
sin_match = merged["Asistencia"].isna().sum()
print(f"Filas sin emparejar tras el merge exacto (Period + Name): {sin_match} de {len(merged)}")

# %%
# --- Merge 2 (fallback): para los que no calzaron, reintentar con Name_key ---
if sin_match > 0:
    faltantes_idx = merged[merged["Asistencia"].isna()].index

    fallback = df_long.loc[faltantes_idx, ["Period", "Name_key"]].reset_index().merge(
        asistencia_total,
        on=["Period", "Name_key"],
        how="left",
    ).set_index("index")

    cols_to_fill = ["Afirmativo", "En_Contra", "Total_Votaciones", "Asistencia"]
    for col in cols_to_fill:
        merged.loc[faltantes_idx, col] = fallback[col]

    sin_match_final = merged["Asistencia"].isna().sum()
    print(f"Filas sin emparejar tras el fallback por Name_key: {sin_match_final} de {len(merged)}")

    if sin_match_final > 0:
        print()
        print("Ejemplos de diputados que no lograron emparejarse (revisar nombres manualmente):")
        display(merged.loc[merged["Asistencia"].isna(), ["Period", "Name"]].drop_duplicates())

# %%

merged_final = merged.drop(columns=["Name_key"])
merged_final.head(20)

# %%

# Guardar resultado
OUT_PATH = DATA_DIR.parent / "ideologia_con_asistencia.csv"
merged_final.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"Guardado en: {OUT_PATH.resolve()}")


# %%
# Estadística descriptiva de Asistencia por Period: media, sd, cuantiles, mínimo, máximo
def resumen_asistencia(df, col="Asistencia", group_col="Period"):
    resumen = df.groupby(group_col)[col].agg(
        n="count",
        media="mean",
        sd="std",
        minimo="min",
        q1=lambda s: s.quantile(0.25),
        mediana=lambda s: s.quantile(0.50),
        q3=lambda s: s.quantile(0.75),
        maximo="max",
    )
    return resumen[["n", "media", "sd", "minimo", "q1", "mediana", "q3", "maximo"]]

descriptivos_asistencia = resumen_asistencia(merged_final)
print(descriptivos_asistencia)

# %%
merged_final.info()

# %%
# Rango de dim_ideology en la base final ya emparejada con asistencia
col_ideologia = "dim_ideology"  # ajusta el nombre exacto si es distinto en tu base

if col_ideologia in merged_final.columns:
    merged_final[col_ideologia] = pd.to_numeric(merged_final[col_ideologia], errors="coerce")

    minimo = merged_final[col_ideologia].min()
    maximo = merged_final[col_ideologia].max()
    n_validos = merged_final[col_ideologia].notna().sum()
    n_nulos = merged_final[col_ideologia].isna().sum()

    print(f"Rango de {col_ideologia}: [{minimo}, {maximo}]")
    print(f"Valores válidos: {n_validos} | Valores nulos/no numéricos: {n_nulos}")

    # Rango por Period, útil si la escala cambia entre Periodo_4 y Periodo_6
    print()
    print("Rango por Period:")
    print(merged_final.groupby("Period")[col_ideologia].agg(["min", "max", "count"]))
else:
    print(f"La columna '{col_ideologia}' no existe en merged_final.")
    print("Columnas disponibles:", list(merged_final.columns))


# %%
# Estadística descriptiva de dim_ideology por Period: media, sd, cuantiles, mínimo, máximo
def resumen_descriptivo(df, col, group_col="Period"):
    resumen = df.groupby(group_col)[col].agg(
        n="count",
        media="mean",
        sd="std",
        minimo="min",
        q1=lambda s: s.quantile(0.25),
        mediana=lambda s: s.quantile(0.50),
        q3=lambda s: s.quantile(0.75),
        maximo="max",
    )
    return resumen[["n", "media", "sd", "minimo", "q1", "mediana", "q3", "maximo"]]

col_ideologia = "dim_ideology"  # ajusta si el nombre exacto en tu base es distinto

if col_ideologia in merged_final.columns:
    merged_final[col_ideologia] = pd.to_numeric(merged_final[col_ideologia], errors="coerce")
    descriptivos_ideologia = resumen_descriptivo(merged_final, col_ideologia)
    print(descriptivos_ideologia)
else:
    print(f"La columna '{col_ideologia}' no existe en merged_final.")
    print("Columnas disponibles:", list(merged_final.columns))


# %%
# Estadística descriptiva de dim_ideology por Period: media, sd, cuantiles, min, max,
# distancia media-max, distancia media-min, rango max-min
def resumen_descriptivo(df, col, group_col="Period"):
    resumen = df.groupby(group_col)[col].agg(
        n="count",
        media="mean",
        sd="std",
        minimo="min",
        p1=lambda s: s.quantile(0.01),
        q1=lambda s: s.quantile(0.25),
        mediana=lambda s: s.quantile(0.50),
        p99=lambda s: s.quantile(0.99),
        q3=lambda s: s.quantile(0.75),
        maximo="max",
    )
    resumen["dist_media_max"] = resumen["maximo"] - resumen["media"]
    resumen["dist_media_min"] = resumen["media"] - resumen["minimo"]
    resumen["rango_max_min"] = resumen["maximo"] - resumen["minimo"]
    resumen = resumen.round(3)
    return resumen[["n", "media", "sd", "minimo", "p1", "q1", "mediana", "p99", "q3", "maximo",
                     "dist_media_max", "dist_media_min", "rango_max_min"]]

col_ideologia = "dim_ideology"  # ajusta si el nombre exacto en tu base es distinto

if col_ideologia in merged_final.columns:
    merged_final[col_ideologia] = pd.to_numeric(merged_final[col_ideologia], errors="coerce")
    descriptivos_ideologia = resumen_descriptivo(merged_final, col_ideologia)
    print(descriptivos_ideologia)
else:
    print(f"La columna '{col_ideologia}' no existe en merged_final.")
    print("Columnas disponibles:", list(merged_final.columns))

# %%
#Dalton index first computations
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

import numpy as np
import pandas as pd


CSV_PATH = "ideologia_congreso_chile_2002_2026_long_format.csv"  # ajustar ruta si difiere
IDEOL_COL = "dim_ideology"
PERIOD_COL = "Period"
ID_COL = "Id"          # identificador estable de legislador (usar Id, no Name, por homónimos)
PARTY_COLS = ["party_1", "party_2", "party_3", "party_4"]


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


def filtrar_filas_validas(df, cols_ideol=(IDEOL_COL, "dim_IC_low", "dim_IC_high")):
    """Elimina filas período-legislador sin dato ideológico (en cualquiera
    de dim_ideology, dim_IC_low, dim_IC_high). Se asume ya reportado el
    diagnóstico de diagnostico_missingness_estructural antes de llamar a
    esta función."""
    cols_presentes = [c for c in cols_ideol if c in df.columns]
    return df.dropna(subset=cols_presentes).copy()


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

    anova_salida = descomposicion_anova(df_salida, party_col="partido_asignado")
    anova_salida["pct_var_entre_salida"] = (100 - anova_salida["pct_var_intra"]).round(1)
    anova_salida = anova_salida.rename(columns={"pct_var_intra": "pct_var_intra_salida"})

    anova_unico = descomposicion_anova(df_unico, party_col="partido_asignado")
    anova_unico["pct_var_entre_unico"] = (100 - anova_unico["pct_var_intra"]).round(1)
    anova_unico = anova_unico.rename(columns={"pct_var_intra": "pct_var_intra_unico"})

    tabla = tabla.merge(
        anova_salida[[PERIOD_COL, "pct_var_entre_salida", "pct_var_intra_salida"]],
        on=PERIOD_COL, how="left"
    ).merge(
        anova_unico[[PERIOD_COL, "pct_var_entre_unico", "pct_var_intra_unico"]],
        on=PERIOD_COL, how="left"
    )
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


if __name__ == "__main__":
    resultados = analisis_completo()


# %%
cols = ["wnom_ideology", "bay_ideology"]

# Reemplazar literalmente el string 'NA' por NaN
merged_final[cols] = merged_final[cols].replace("NA", np.nan)

# Convertir a numérico (coerce convierte lo no numérico en NaN)
for c in cols:
    merged_final[c] = pd.to_numeric(merged_final[c], errors="coerce")


# %%
corr_spearman = merged_final["wnom_ideology"].corr(merged_final["bay_ideology"], method="spearman")
print(corr_spearman)
