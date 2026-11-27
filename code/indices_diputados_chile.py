"""Panel de diputados, polarización por partido y participación nominal (Python 3.10+)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd


P = "Period"
ID = "Id"
X = "dim_ideology"
PS = [f"party_{i}" for i in range(1, 5)]
KEY = [ID, P]
PER = {f"Periodo_{i}": y for i, y in enumerate(range(2002, 2030, 4), 1)}
MAIN = tuple(f"Periodo_{i}" for i in range(3, 7))
ELECTION = {y - 1: p for p, y in PER.items()}
DS = "https://dataverse.harvard.edu/api/access/datafile/"
PUBLIC = {
    "ideologia": 11755355,
    "matriz": dict(zip(MAIN, (11752364, 11752367, 11752365, 11752366))),
    "militancia": dict(zip(MAIN, (11751775, 11751776, 11751774, 11751773))),
}
PINNED_SHA = {
    11755355: "c53194846a4296f0a5380d177c269082a2e1d57ab342062002629522d61b83f8",
    11752364: "748a879f21888cd3dce337a4de6fcb75eed3d27211f694a264f1ab62e9245d23",
    11752367: "ea1e77af6a763d71154c05531a7b9e658b91101bc2ae1327e32cc2886941f306",
    11752365: "09afffaad6ab6a344dab1ad3b7bb00dc0a1de837d65172c3b44130dfc8b78506",
    11752366: "2b0f927498378a37c07acacafeb10f72eb1a34dc2cf679094992e62a9c8ef4f7",
    11751775: "d4f470fcbc8b96556a21fc95089fd471c0ba1161e935076244ac433895c276e3",
    11751776: "985491311de040b6100142a55c768ccf8d5f992098e04f4cd69a41c73398239f",
    11751774: "19baced862619403649446659e3dbb7ead405aef98bf6edb804f08e4a242e17e",
    11751773: "ac87a42e6af49bed44717be816c55062df6fe90d8d73b53eb5481cc0d873dce7",
}
META_VOTOS = ["n", "DiputadoId", "Nombre", "ApellidoPaterno", "ApellidoMaterno"]
VOTOS = {"afirmativo": "Afirmativo", "en contra": "En_Contra", "abstencion": "Abstencion",
         "dispensado": "Dispensado", "no vota": "No_Vota", "pareado": "Pareado", "": "Sin_Registro"}
MISSING = {"", "na", "nan", "null", "n/a", "<na>"}
MODES = ("salida", "unico", "salida_fechada", "unico_fechado")
REGIONS = {15: "Arica y Parinacota", 1: "Tarapacá", 2: "Antofagasta", 3: "Atacama", 4: "Coquimbo",
           5: "Valparaíso", 13: "Metropolitana", 6: "O’Higgins", 7: "Maule", 8: "Biobío y Ñuble",
           9: "La Araucanía", 14: "Los Ríos", 10: "Los Lagos", 11: "Aysén", 12: "Magallanes"}
OLD = [(1, 15), (2, 1), (4, 2), (6, 3), (9, 4), (15, 5), (31, 13), (35, 6), (40, 7),
       (47, 8), (52, 9), (54, 14), (58, 10), (59, 11), (60, 12)]
NEW = [(1, 15), (2, 1), (3, 2), (4, 3), (5, 4), (7, 5), (14, 13), (16, 6), (18, 7),
       (21, 8), (23, 9), (24, 14), (26, 10), (27, 11), (28, 12)]
SEATS_NEW = [3, 3, 5, 5, 7, 8, 8, 8, 7, 8, 6, 7, 5, 6, 5, 4, 7, 4,
             5, 8, 5, 4, 7, 5, 4, 5, 3, 3]


def clean(v):
    if pd.isna(v):
        return ""
    s = " ".join(str(v).split())
    return "" if s.casefold() in MISSING else s


def namekey(v):
    s = clean(v)
    if any(c in s for c in ("Ã", "Â", "â€")):
        for enc in ("cp1252", "latin1"):
            try:
                s = s.encode(enc).decode("utf8")
                break
            except UnicodeError:
                continue
    s = unicodedata.normalize("NFKD", s.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def period(v):
    s = namekey(v)
    m = re.fullmatch(r"periodo? ([1-7])", s)
    if m:
        return f"Periodo_{m[1]}"
    for p, y in PER.items():
        if s in (str(y), f"{y} {y+4}", f"{y} {(y+4)%100:02d}"):
            return p
    raise ValueError(f"Período no reconocido: {v!r}. Use Periodo_1…Periodo_7 o año inicial.")


def id_key(v):
    s = clean(v)
    if not s or not re.fullmatch(r"\d+(?:\.0+)?", s) or int(s.split(".")[0]) < 1:
        raise ValueError(f"Identificador inválido: {v!r}")
    return str(int(s.split(".")[0]))


def validate_keys(df, key, label):
    if df[key].isna().any().any() or df[key].eq("").any().any():
        raise ValueError(f"{label}: clave vacía en {key}")
    dup = df[df.duplicated(key, keep=False)]
    if not dup.empty:
        raise ValueError(f"{label}: clave duplicada {key}: {dup[key].head(12).to_dict('records')}")


def required(df, names, label):
    missing = set(names) - set(df)
    if missing:
        raise ValueError(f"{label}: faltan columnas {sorted(missing)}; disponibles {list(df)[:30]}")


def read(path, *, sheet=0, header=0):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, sheet_name=sheet, header=header, dtype=str, keep_default_na=False)
    for enc in ("utf-8-sig", "cp1252", "latin1"):
        try:
            with path.open(encoding=enc, newline="") as f:
                for _ in range(header):
                    next(f)
                line = next(f)
                sep = csv.Sniffer().sniff(line, delimiters=",;\t").delimiter
                columns = next(csv.reader([line], delimiter=sep))
                if len(set(columns)) != len(columns):
                    raise ValueError(f"{path}: encabezados duplicados.")
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding=enc, sep=sep, header=header)
        except UnicodeError:
            continue
    raise ValueError(f"No se pudo leer {path}")


def numeric(s):
    return pd.to_numeric(s.map(clean), errors="coerce").replace([np.inf, -np.inf], np.nan)


def panel(path):
    df = read(path)
    required(df, [ID, P, "Name", X, "quant_parties", *PS], "ideología")
    df["Id_fuente"] = df[ID]
    df["Period_fuente"] = df[P]
    df[P] = df[P].map(period)
    df[ID] = df[ID].map(id_key)
    validate_keys(df, KEY, "ideología")
    if not df[P].isin(MAIN).any():
        raise ValueError("Sin filas de 2010–2026 en la base de ideología.")
    cols = [X, "dim_IC_low", "dim_IC_high", "wnom_ideology", "bay_ideology", "bay_ic_low", "bay_ic_high"]
    for c in cols:
        if c not in df:
            df[c] = np.nan
        else:
            df[f"{c}_no_numerico"] = df[c].map(clean).ne("") & numeric(df[c]).isna()
            df[c] = numeric(df[c])
    df["quant_parties"] = numeric(df["quant_parties"])
    for c in PS:
        df[c] = df[c].map(lambda v: clean(v).upper()).replace("", np.nan)
    df["n_slots_partido"] = df[PS].notna().sum(axis=1)
    df["n_partidos_distintos"] = df[PS].nunique(axis=1)
    df["quant_inconsistente"] = (df["quant_parties"].notna() &
        (df["quant_parties"].ne(df["n_partidos_distintos"]) | df["n_slots_partido"].ne(df["n_partidos_distintos"])))
    df["salida"] = df[PS].ffill(axis=1).iloc[:, -1]
    df["unico"] = df["salida"].where(df["quant_parties"].eq(1) & df["n_slots_partido"].eq(1))
    for prefix, center, low, high in (("dim", X, "dim_IC_low", "dim_IC_high"),
                                      ("bay", "bay_ideology", "bay_ic_low", "bay_ic_high")):
        both = df[low].notna() & df[high].notna()
        df[f"{prefix}_IC_invertido"] = both & df[low].gt(df[high])
        lo, hi = np.minimum(df[low], df[high]), np.maximum(df[low], df[high])
        df[f"{prefix}_IC_valido"] = both & hi.gt(lo) & df[center].between(lo, hi)
        df[f"{prefix}_IC_low_ordenado"], df[f"{prefix}_IC_high_ordenado"] = lo, hi
    return df


def attach(df, addon, label):
    validate_keys(addon, KEY, label)
    out = df.merge(addon, on=KEY, how="left", validate="one_to_one", sort=False)
    if len(out) != len(df) or not out[KEY].equals(df[KEY].reset_index(drop=True)):
        raise AssertionError(f"{label}: cambió el universo o el orden de la base long.")
    return out


def identify_source_id(v, p, name):
    # Cambio de ID documentado en A_Ideology_Estimation.R de Fábrega.
    if p == "Periodo_5" and v == "1064" and namekey(name) == "pablo prieto lorca":
        return "209"
    return v


def party_dates(path, p):
    d = read(path)
    required(d, ["Id", "Alias", "FechaInicio", "FechaTermino"], f"militancia {p}")
    d["Id"] = d["Id"].map(id_key)
    validate_keys(d, ["Id"], f"militancia {p}")
    y = PER[p]
    lo, hi = f"{y}-03-11", "2025-06-30" if y == 2022 else f"{y+4}-03-10"
    alias = [c for c in d if re.fullmatch(r"Alias(?:\.\d+)?", c)]
    rows = []
    for r in d.to_dict("records"):
        name = r.get("nombre_completo") or " ".join(clean(r.get(k)) for k in ("Nombre", "Nombre2", "ApellidoPaterno", "ApellidoMaterno"))
        spans, dates_bad = [], False
        for c in alias:
            pg = clean(r[c]).upper()
            if not pg:
                continue
            suffix = c.removeprefix("Alias")
            a, b = clean(r.get("FechaInicio" + suffix))[:10], clean(r.get("FechaTermino" + suffix))[:10]
            a_ok = re.fullmatch(r"\d{4}-\d{2}-\d{2}", a) and pd.notna(pd.to_datetime(a, errors="coerce"))
            b_ok = re.fullmatch(r"\d{4}-\d{2}-\d{2}", b) and pd.notna(pd.to_datetime(b, errors="coerce"))
            if not a_ok or (b and (not b_ok or b < a)):
                dates_bad = True
                continue
            if a <= hi and (not b or b >= lo):
                spans.append((a, b, pg))
        spans = sorted(set(spans))
        groups = {span[2] for span in spans}
        latest = {s[2] for s in spans if s[0] == spans[-1][0]} if spans else set()
        overlaps = any(a[2] != b[2] and max(a[0], b[0], lo) <= min(a[1] or hi, b[1] or hi, hi)
                       for i, a in enumerate(spans) for b in spans[i+1:])
        # A same-day boundary can occur in historical administrative records; flag it but
        # use the most recent documented start unless two alternatives start on that date.
        rows.append({ID: identify_source_id(r[ID], p, name), P: p, "Id_militancia_fuente": r[ID],
                     "Name_militancia_fuente": name, "militancias_en_ventana": "|".join(sorted(groups)),
                     "n_militancias_fechadas": len(groups), "fecha_militancia_invalida": dates_bad,
                     "militancia_conflicto_ultimo_inicio": len(latest) > 1,
                     "militancia_solapada": overlaps,
                     "salida_fechada": next(iter(latest)) if len(latest) == 1 else np.nan,
                     "unico_fechado": next(iter(groups)) if len(groups) == 1 and not dates_bad else np.nan})
    return pd.DataFrame(rows)


def rollcalls(path, p, exclude=()):
    df = read(path)
    required(df, META_VOTOS, f"matriz {p}")
    if set(exclude) - set(df):
        raise ValueError(f"No aparecen columnas excluidas en {path}: {set(exclude)-set(df)}")
    names = df[META_VOTOS[2:]].apply(lambda r: " ".join(filter(None, map(clean, r))), axis=1)
    cols = [c for c in df if c not in {*META_VOTOS, *exclude}]
    if not cols or any(not re.fullmatch(r"\d+", c) for c in cols):
        bad = [c for c in cols if not re.fullmatch(r"\d+", c)]
        raise ValueError(f"Matriz {p}: sin votos o columnas no identificadas como IDs de votación: {bad[:15]}. "
                         "Excluya metadatos confirmados mediante --no-voto.")
    raw = df[cols].to_numpy(dtype=object)
    tokens, inverse = np.unique(raw.astype(str), return_inverse=True)
    normalized = np.asarray([namekey(v) for v in tokens], dtype=object)[inverse].reshape(raw.shape)
    other = set(np.unique(normalized)) - set(VOTOS)
    if other:
        raise ValueError(f"Matriz {p}: códigos de voto desconocidos {sorted(other)}. Revisar diccionario.")
    original = df["DiputadoId"].map(id_key)
    validate_keys(pd.DataFrame({"DiputadoId": original}), ["DiputadoId"], f"matriz {p}")
    out = pd.DataFrame({ID: [identify_source_id(i, p, n) for i, n in zip(original, names)], P: p,
                        "DiputadoId": original, "Name_matriz": names})
    for v, c in VOTOS.items():
        out[c] = np.sum(normalized == v, axis=1)
    out["Total_Votaciones"] = len(cols)
    if not out[list(VOTOS.values())].sum(axis=1).eq(len(cols)).all():
        raise AssertionError("Los códigos de voto no concilian con el total.")
    out["Votos_binarios"] = out["Afirmativo"] + out["En_Contra"]
    out["Asistencia"] = out["Votos_binarios"] / out["Total_Votaciones"]
    out["Participacion_con_abstencion"] = (out["Votos_binarios"] + out["Abstencion"]) / out["Total_Votaciones"]
    validate_keys(out, KEY, f"matriz {p}")
    return out


def validate_name_ids(base, add, col, label):
    both = base[[*KEY, "Name"]].merge(add[[*KEY, col]], on=KEY, validate="one_to_one")
    wrong = both[both["Name"].map(namekey).ne(both[col].map(namekey))]
    if not wrong.empty:
        raise ValueError(f"{label}: ID válido pero nombres distintos, revisar identidad: "
                         f"{wrong[[*KEY, 'Name', col]].head(12).to_dict('records')}")


def district_region(d, p):
    scheme = OLD if PER[p] < 2018 else NEW
    if d < 1 or d > scheme[-1][0]:
        raise ValueError(f"Distrito fuera del esquema {p}: {d}")
    return next(code for end, code in scheme if d <= end)


def geography(path):
    geo = read(path)
    required(geo, [*KEY, "Distrito"], "geografía")
    geo[P], geo[ID] = geo[P].map(period), geo[ID].map(id_key)
    validate_keys(geo, KEY, "geografía")
    geo["Distrito"] = geo["Distrito"].map(lambda d: int(id_key(d)) if clean(d) else pd.NA).astype("Int64")
    # Published electoral geography is preserved separately from the equivalent panel geography.
    geo["Nro.Region"] = [
        (16 if PER[p] >= 2018 and d == 19 else district_region(int(d), p)) if pd.notna(d) else np.nan
        for d, p in zip(geo["Distrito"], geo[P])]
    geo["Region"] = geo["Nro.Region"].map({**REGIONS, 8: "Biobío", 16: "Ñuble"})
    geo["Nro.Region_armonizada"] = geo["Nro.Region"].replace({16: 8})
    geo["Region_armonizada"] = geo["Nro.Region_armonizada"].map(REGIONS)
    return geo


def election(path, year, base, sheet, header):
    d = read(path, sheet=sheet, header=header)
    aliases = {namekey(c): c for c in d}
    names = ["nombres", "primer apellido", "segundo apellido", "cargo"]
    if not all(k in aliases for k in names):
        raise ValueError(f"{path}: se esperan Nombres, Primer apellido, Segundo apellido y Cargo.")
    geo = [c for c in d if namekey(c) in ("nro region", "n region", "region", "distrito",
                                          "nro distrito", "n distrito", "codigo region", "electo", "resultado")]
    d = d[d[aliases["cargo"]].map(namekey).eq("diputado")].copy()
    if d.empty:
        raise ValueError(f"{path}: sin registros Cargo=DIPUTADO")
    d["Name_electoral"] = d[[aliases[c] for c in names[:3]]].apply(lambda r: " ".join(filter(None, map(clean, r))), axis=1)
    d["Name_key"] = d["Name_electoral"].map(namekey)
    d = d[d["Name_key"].ne("")].copy()
    keys = ["Name_key", *geo]
    d = d[["Name_electoral", *keys]].drop_duplicates(keys)
    d["_candidato_ambiguo"] = d.duplicated("Name_key", keep=False)
    p = ELECTION[year]
    track = base.loc[base[P].eq(p) & base[X].notna(), [ID, "Name"]].copy()
    track["Name_key"] = track["Name"].map(namekey)
    track = track[track["Name_key"].ne("") & ~track.duplicated("Name_key", keep=False)]
    good = d[~d["_candidato_ambiguo"]].merge(track, on="Name_key", how="left", validate="one_to_one")
    bad = d[d["_candidato_ambiguo"]].assign(Id=pd.NA, Name=pd.NA)
    return pd.concat([good, bad], ignore_index=True).assign(
        Period=p, Eleccion=year, Estado_cruce=lambda z: np.select(
            [z["_candidato_ambiguo"], z[ID].notna()], ["candidatura_ambigua", "candidato_vinculado"],
            default="sin_ideologia_publicada" if track.empty else "sin_vinculo"))


def stats(g, mode, R, with_parts=False):
    part = g.groupby(mode, sort=True)[X].agg(n="size", centroide="mean", sd="std")
    n = len(g)
    if not n:
        return {"n_legisladores": 0, "n_partidos": 0, "estado_indice": "sin_datos"}, part
    s, a = part["n"].to_numpy() / n, part["centroide"].to_numpy()
    mu, var = float(s @ a), float(np.var(g[X], ddof=0))
    between = float(s @ (a - mu)**2)
    lookup = g[mode].map(part["centroide"]).to_numpy()
    within = float(np.mean((g[X].to_numpy() - lookup)**2))
    if not (np.isclose(s.sum(), 1) and part["n"].sum() == n and np.isclose(mu, g[X].mean())
            and np.isclose(var, between + within, rtol=1e-10, atol=1e-12)):
        raise AssertionError("Falló conciliación de cuotas, centroides o varianza.")
    good = len(part) >= 2 and np.isfinite(R) and R > 0
    mad = float(np.mean(np.abs(a - a.mean()))) if good else np.nan
    wmad = float(s @ np.abs(a - mu)) if good else np.nan
    info = {"n_legisladores": n, "n_partidos": len(part), "n_partidos_n1": int(part["n"].eq(1).sum()),
            "cuota_grupos_n1": float(part.loc[part["n"].eq(1), "n"].sum() / n),
            "n_partidos_n2_mas": int(part["n"].ge(2).sum()), "cuota_mayor": float(s.max()),
            "partidos_efectivos": float(1 / (s @ s)), "media": mu, "sd_ideologia": g[X].std(),
            "var_total": var, "var_entre": between, "var_intra": within,
            "fraccion_var_entre": between / var if var else np.nan,
            "dalton_raw": np.sqrt(between) if good else np.nan,
            "dalton": np.sqrt(between) / R if good else np.nan,
            "mad_party": mad, "mad_party_normalized": mad / R,
            "mad_ponderado": wmad, "mad_ponderado_normalizado": wmad / R,
            "estado_indice": "estimado" if good else "un_partido" if len(part) == 1 else "sin_escala"}
    if good and (wmad > np.sqrt(between) + 1e-12 or info["dalton"] > 1 + 1e-12):
        raise AssertionError("MAD ponderado excede RMS o Dalton excede rango de esta escala observada.")
    if with_parts:
        part["cuota_muestra"] = s
        part["var_entre_aporte"] = s * (a - mu)**2
    return info, part


def sample(d, mode):
    return d[d[X].notna() & d[mode].notna()]


def pop(d, p):
    return d[d[P].eq(p)]


def safe_ratio(a, b):
    return a / b if b else np.nan


def dispersion(weights, x, party, R):
    sizes = np.bincount(party, weights=weights, minlength=int(party.max()+1))
    valid = sizes > 0
    if valid.sum() < 2:
        return np.nan
    sums = np.bincount(party, weights=weights*x, minlength=len(sizes))
    y = sums[valid] / sizes[valid]
    s = sizes[valid] / sizes.sum()
    return float(np.sqrt(s @ (y - s @ y)**2) / R)


def contrast(period_frames, mode, R, coeffs, rng, B, infer=True):
    n_by_p = [len(g) for g in period_frames]
    pts = [stats(g, mode, R)[0].get("dalton", np.nan) for g in period_frames]
    both = set.intersection(*(set(g[ID]) for g in period_frames))
    common = sorted(set.union(*(set(g[ID]) for g in period_frames)))
    row = {"n_min_periodo": min(n_by_p), "n_id_union": len(common), "n_id_todos": len(both),
           "delta": float(np.asarray(coeffs) @ pts), "B_validas": 0,
           "estado_contraste": "sin_contraste" if not np.isfinite(pts).all() else "puntual"}
    if not np.isfinite(pts).all() or not infer or min(n_by_p) < 10 or B < 199:
        return row
    index = {i: j for j, i in enumerate(common)}
    frames = [(g[ID].map(index).to_numpy(), g[X].to_numpy(), pd.factorize(g[mode], sort=True)[0])
              for g in period_frames]
    draws = []
    for z in rng.multinomial(len(common), np.repeat(1/len(common), len(common)), size=B):
        vals = [dispersion(z[i], x, pa, R) for i, x, pa in frames]
        draws.append(np.asarray(coeffs) @ vals)
    draws = np.asarray(draws)
    draws = draws[np.isfinite(draws)]
    row["B_validas"] = len(draws)
    if len(draws) < 0.95*B or np.ptp(draws) <= 1e-12:
        row["estado_contraste"] = "bootstrap_no_informativo"
        return row
    row["se_composicion"] = float(np.std(draws, ddof=1))
    row["p025_remuestreo"], row["p975_remuestreo"] = np.quantile(draws, (0.025, .975))
    row["estado_contraste"] = "remuestreo_condicional"
    return row


def jknife(g, mode, R):
    if len(g) < 3 or not np.isfinite(R):
        return np.nan, np.nan
    x, parties = g[X].to_numpy(), pd.factorize(g[mode], sort=True)[0]
    weights = np.ones(len(g))
    full = dispersion(weights, x, parties, R)
    if not np.isfinite(full):
        return np.nan, np.nan
    values = []
    for i in range(len(weights)):
        weights[i] = 0
        values.append(dispersion(weights, x, parties, R))
        weights[i] = 1
    a = np.asarray(values)
    return float(np.max(np.abs(a-full))) if np.isfinite(a).all() else np.nan, float(np.isfinite(a).mean())


def proxy(g, rest, mode, R, m):
    # Use the SAME parties and local shares. Shrink toward estimates excluding the target region.
    z = g.groupby(mode)[X].agg(["mean", "size"])
    outside = rest.groupby(mode)[X].mean().reindex(z.index)
    s = z["size"].to_numpy() / z["size"].sum()
    supported_share = float(z.loc[outside.notna(), "size"].sum() / len(g))
    if len(z) < 2 or not np.isfinite(R):
        return np.nan, np.nan, supported_share
    pool = z["mean"].where(outside.isna(), (m*outside + z["size"]*z["mean"])/(m+z["size"])).to_numpy()
    value = np.sqrt(s @ (pool-s @ pool)**2) / R
    pure = np.nan
    if outside.notna().all():
        raw = outside.to_numpy()
        pure = np.sqrt(s @ (raw-s @ raw)**2) / R
    return float(value), pure, supported_share


def seats(p):
    weights = [2]*60 if PER[p] < 2018 else SEATS_NEW
    answer = {r: 0 for r in REGIONS}
    for d, w in enumerate(weights, 1):
        answer[district_region(d, p)] += w
    assert sum(answer.values()) == (120 if PER[p] < 2018 else 155)
    return answer


def reconciliation(d, p, votes, geo):
    g = pop(d, p)
    valid = g[X].notna()
    cv = g["Asistencia"].notna()
    cg = g["Distrito"].notna()
    party = g["salida"].notna()
    low, hi = g["dim_IC_low"], g["dim_IC_high"]
    roster_ids = set(pop(votes, p)[ID]) if votes is not None else set()
    ideology_ids = set(g.loc[valid, ID])
    geo_ids = set(pop(geo, p)[ID]) if geo is not None else set()
    outside_panel = {label: sorted(ids-set(g[ID]), key=int) for label, ids in
                     (("matriz_fuera_long", roster_ids), ("geo_fuera_long", geo_ids))}
    differences = {"matriz_sin_dim": sorted(roster_ids-ideology_ids, key=int),
                   "dim_sin_matriz": sorted(ideology_ids-roster_ids, key=int) if votes is not None else [],
                   **outside_panel}
    row = {P: p, "inicio": f"{PER[p]}-03-11", "fin": f"{PER[p]+4}-03-10",
           "fin_votos_publicados": "2025-06 (corte publicado)" if PER[p] == 2022 else "",
           "escanos_nominales": sum(seats(p).values()), "filas_long": len(g),
           "dim_validos": int(valid.sum()), "dim_sin_partido_codificado": int((valid & ~party).sum()),
           "partido_codificado_sin_dim": int((~valid & party).sum()),
           "cuant_partidos_inconsistentes": int(g["quant_inconsistente"].sum()),
           "dim_intervalos_invertidos": int(g["dim_IC_invertido"].sum()),
           "bay_intervalos_invertidos": int(g["bay_IC_invertido"].sum()),
           "dim_con_cota_faltante": int((valid & (low.isna() | hi.isna())).sum()),
           "dim_con_intervalo_utilizable": int((valid & g["dim_IC_valido"]).sum()),
           "dim_con_partido_fechado": int((valid & g["salida_fechada"].notna()).sum()),
           "dim_con_afiliacion_distinta": int((valid & party & g["salida_fechada"].notna() &
                                               g["salida"].ne(g["salida_fechada"])).sum()),
           "militancia_conflicto_ultimo_inicio": int(g.get("militancia_conflicto_ultimo_inicio", pd.Series(dtype=bool)).eq(True).sum()),
           "militancia_solapada": int(g.get("militancia_solapada", pd.Series(dtype=bool)).eq(True).sum()),
           "n_en_matriz": len(roster_ids) if votes is not None and p in set(votes[P]) else np.nan,
           "dim_en_matriz": int((valid & cv).sum()) if p in set(votes[P]) else np.nan,
           "cobertura_dim_sobre_matriz": safe_ratio((valid & cv).sum(), len(roster_ids)),
           "dim_con_region": int((valid & cg).sum()) if geo is not None else np.nan,
           "n_con_region": int(cg.sum()) if geo is not None else np.nan}
    row["n_matriz_menos_escanos"] = row["n_en_matriz"] - row["escanos_nominales"]
    row["dim_malformados"] = int(g.get("dim_ideology_no_numerico", pd.Series(dtype=bool)).eq(True).sum())
    row["fechas_militancia_invalidas"] = int(g.get("fecha_militancia_invalida", pd.Series(dtype=bool)).eq(True).sum())
    return row, [{P: p, "incidencia": k, ID: i} for k, values in differences.items() for i in values]


def diagnostics(d, p):
    frame = pop(d, p)
    rows = []
    for left, right in ((X, "wnom_ideology"), (X, "bay_ideology"), ("wnom_ideology", "bay_ideology")):
        e = frame[[left, right]].dropna()
        rho = e[left].rank().corr(e[right].rank()) if len(e) >= 5 and e.nunique().min() >= 2 else np.nan
        rows.append({P: p, "modelo_a": left, "modelo_b": right, "n_pares": len(e), "rho_spearman": rho})
    return rows


def summarize(d, att, geo, out, B, seed, min_n, min_cov, max_loo, m_pool):
    a = d[d[P].isin(MAIN)]
    observed = a[X].dropna()
    R = (observed.max() - observed.min())/2 if len(observed) else np.nan
    if not np.isfinite(R) or R <= 0:
        raise ValueError("No hay rango ideológico positivo en los períodos objetivo.")

    def write(name, rows, columns=None):
        dat = pd.DataFrame(rows, columns=columns)
        if len(dat) or columns is not None:
            dat.to_csv(out/f"{name}.csv", index=False, encoding="utf-8-sig")

    cuentas, issues, validaciones, partisan, national, regional, regional_p, attend, selection, refit, without_ind = (
        [] for _ in range(11))
    can_date = a["salida_fechada"].notna().any()
    modes = MODES if can_date else MODES[:2]
    date_periods = set(a.loc[a[X].notna() & a["salida_fechada"].notna(), P])
    select_mode = "salida_fechada" if set(MAIN) <= date_periods else "salida"
    for p in MAIN:
        pg = pop(a, p)
        present = pg[pg[X].notna() | pg["salida"].notna() | pg["Asistencia"].notna() | pg["Distrito"].notna()]
        c, problems = reconciliation(d, p, att, geo)
        cuentas.append(c)
        issues.extend(problems)
        validaciones.extend(diagnostics(d, p))
        if p in set(att[P]):
            h = pop(att, p)
            q = h["Asistencia"]
            row = {P: p, "n_matriz": len(h), "Total_Votaciones": int(h.Total_Votaciones.iloc[0]),
                   "media_binaria": q.mean(), "sd_binaria": q.std(), "p10_binaria": q.quantile(.1),
                   "mediana_binaria": q.median(), "p90_binaria": q.quantile(.9),
                   "min_binaria": q.min(), "max_binaria": q.max(), "n_binaria_menor_10pct": int(q.lt(.10).sum()),
                   "media_con_abstencion": h["Participacion_con_abstencion"].mean()}
            row.update({c: int(h[c].sum()) for c in VOTOS.values()})
            if sum(row[c] for c in VOTOS.values()) != len(h)*row["Total_Votaciones"]:
                raise AssertionError("Conteo período×votación no concilia.")
            attend.append(row)
        for mode in modes:
            g = sample(pg, mode)
            point, parts = stats(g, mode, R, with_parts=True)
            national.append({P: p, "atribucion": mode, **point})
            for k, detail in parts.iterrows():
                partisan.append({P: p, "atribucion": mode, "partido_asignado": k, **detail.to_dict()})
            if mode in ("salida", "salida_fechada"):
                gg = g[g[mode].ne("IND")]
                ou, _ = stats(gg, mode, R)
                without_ind.append({P: p, "atribucion": mode, "n_excluido_IND": len(g)-len(gg),
                                    "n_legisladores": len(gg), "dalton_sin_IND": ou.get("dalton", np.nan),
                                    "mad_party_sin_IND": ou.get("mad_party", np.nan)})
            if geo is None:
                continue
            by_region = seats(p)
            if int(present["Distrito"].notna().sum()) != sum(
                    present["Nro.Region_armonizada"].eq(code).sum() for code in REGIONS):
                raise AssertionError("Los distritos no concilian con regiones.")
            for code, label in REGIONS.items():
                local = g[g["Nro.Region_armonizada"].eq(code)]
                rest = g[g["Nro.Region_armonizada"].notna() & g["Nro.Region_armonizada"].ne(code)]
                reg_n = int(present["Nro.Region_armonizada"].eq(code).sum())
                part_stat, pr = stats(local, mode, R, with_parts=True)
                coverage = safe_ratio(len(local), reg_n)
                max_j, frac_j = jknife(local, mode, R)
                failures = []
                if len(local) < min_n:
                    failures.append("n_bajo")
                if not np.isfinite(coverage) or coverage < min_cov:
                    failures.append("cobertura_baja_o_nd")
                if part_stat.get("n_partidos_n2_mas", 0) < 2:
                    failures.append("menos_de_2_grupos_replicados")
                if not np.isfinite(max_j) or max_j > max_loo:
                    failures.append("loo_inestable_o_nd")
                key = {P: p, "atribucion": mode, "Nro.Region_armonizada": code, "Region_armonizada": label}
                pooled, pure, share = proxy(local, rest, mode, R, m_pool) if len(local) else (np.nan,)*3
                territorial = np.nan
                if len(local):
                    deltas = local[X] - local[mode].map(rest.groupby(mode)[X].mean())
                    if deltas.notna().all():
                        territorial = deltas.abs().mean()/R
                regional.append({**key, "escanos_nominales": by_region[code], "n_personas_mapeadas": reg_n,
                                 "cobertura_indice_sobre_mapeadas": coverage,
                                 "n_mapeadas_menos_escanos": reg_n-by_region[code], **part_stat,
                                 "loo_max_abs_dalton": max_j, "loo_fraccion_valida": frac_j,
                                 "publicable_directo_regla": not failures,
                                 "alerta_soporte": "|".join(failures),
                                 "dalton_con_centroides_contraidos": pooled,
                                 "dalton_centroides_otras_regiones": pure,
                                 "cuota_con_referencia_fuera_region": share,
                                 "mad_personas_vs_su_partido_fuera_region": territorial})
                for k, detail in pr.iterrows():
                    regional_p.append({**key, "partido_asignado": k, **detail.to_dict()})
    support_profiles = []
    if geo is not None:
        rr = pd.DataFrame(regional)
        for code, g in rr[rr.atribucion.eq(select_mode)].groupby("Nro.Region_armonizada", sort=True):
            stable = len(g) == len(MAIN) and g.publicable_directo_regla.all()
            selection.append({"Nro.Region_armonizada": code, "Region_armonizada": REGIONS[code],
                              "atribucion": select_mode, "n_periodos_aprobados": int(g.publicable_directo_regla.sum()),
                              "n_min_4_periodos": g.n_legisladores.min(),
                              "cobertura_min": g.cobertura_indice_sobre_mapeadas.min(skipna=False),
                              "loo_max_4_periodos": g.loo_max_abs_dalton.max(skipna=False),
                              "region_panel_comun": bool(stable)})
        chosen = {row["Nro.Region_armonizada"] for row in selection if row["region_panel_comun"]}
        terra = rr[rr.atribucion.eq(select_mode)]
        for name, n0, c0, j0 in (("flexible", 6, .85, .16), ("principal", min_n, min_cov, max_loo),
                                  ("estricto", 10, .95, .08)):
            mask = (terra.n_legisladores.ge(n0) & terra.cobertura_indice_sobre_mapeadas.ge(c0) &
                    terra.n_partidos_n2_mas.ge(2) & terra.loo_max_abs_dalton.le(j0))
            n_period = terra.loc[mask].groupby("Nro.Region_armonizada").size()
            supported = sorted(n_period[n_period.eq(len(MAIN))].index)
            for p in MAIN:
                allp = sample(pop(a, p), select_mode)
                z = allp[allp["Nro.Region_armonizada"].isin(supported)]
                support_profiles.append({"perfil": name, P: p, "n_min": n0, "cobertura_min": c0, "loo_max": j0,
                                         "n_regiones": len(supported), "regiones": "|".join(REGIONS[i] for i in supported),
                                         "n_legisladores": len(z), "fraccion_nacional": safe_ratio(len(z), len(allp)),
                                         "dalton_en_pool": stats(z, select_mode, R)[0].get("dalton", np.nan)})
        for p in MAIN:
            allp = sample(pop(a, p), select_mode)
            r = allp[allp["Nro.Region_armonizada"].isin(chosen)]
            point, _ = stats(r, select_mode, R)
            refit.append({P: p, "atribucion": select_mode, "n_regiones_panel": len(chosen),
                          "fraccion_casos_nacionales_en_panel": safe_ratio(len(r), len(allp)), **point})

    rng = np.random.default_rng(seed)
    contrasts, links = [], []
    for mode in ("salida", "salida_fechada") if can_date else ("salida",):
        pts = {p: sample(pop(a, p), mode) for p in MAIN}
        for left, right in zip(MAIN, MAIN[1:]):
            g, h = pts[left], pts[right]
            both = set(g[ID]) & set(h[ID])
            contrasts.append({"atribucion": mode, "familia": "adyacentes", "desde": left, "hasta": right,
                              **contrast([g, h], mode, R, [-1, 1], rng, B)})
            continuous = [z[z[ID].isin(both)] for z in (g, h)]
            contrasts.append({"atribucion": mode, "familia": "continuos_sensibilidad", "desde": left, "hasta": right,
                              **contrast(continuous, mode, R, [-1, 1], rng, B, infer=False)})
            q = continuous[0][[ID, X]].merge(continuous[1][[ID, X]], on=ID, validate="one_to_one", suffixes=("_antes", "_despues"))
            if mode == select_mode and len(q) >= 5:
                x1, x2 = q[f"{X}_antes"], q[f"{X}_despues"]
                links.append({"desde": left, "hasta": right, "n_continuos": len(q),
                              "rho_ideal_continuos": x1.rank().corr(x2.rank()) if x1.nunique() >= 2 and x2.nunique() >= 2 else np.nan,
                              "sd_antes_mismos_id": x1.std(), "sd_despues_mismos_id": x2.std()})
        contrasts.append({"atribucion": mode, "familia": "pre_post_2018_descriptivo",
                          "desde": "Periodo_3+Periodo_4", "hasta": "Periodo_5+Periodo_6",
                          **contrast(list(pts.values()), mode, R, [-.5, -.5, .5, .5], rng, B)})
    comp = d.copy()
    comp.to_csv(out/"base_composicion.csv", index=False, encoding="utf-8-sig")
    write("conciliacion_periodos", cuentas)
    write("incidencias_identidad", issues, [P, "incidencia", ID])
    write("convergencia_modelos_por_periodo", validaciones)
    write("continuos_escala_diagnostico", links)
    write("indices_nacionales", national)
    write("partidos_nacionales", partisan)
    write("sensibilidad_sin_IND", without_ind)
    write("indices_regionales", regional)
    write("soporte_partido_region", regional_p)
    write("panel_regional_comun", selection)
    write("indices_pool_panel_comun", refit)
    write("sensibilidad_soporte_regional", support_profiles)
    write("asistencia_por_periodo", attend)
    write("contrastes_dalton", contrasts)
    return {"R": float(R), "min_dim": float(observed.min()), "max_dim": float(observed.max()),
            "n_dim_para_R": len(observed), "atribucion_panel_regional": select_mode,
            "n_regiones_panel_comun": sum(row["region_panel_comun"] for row in selection) if geo is not None else None}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get_public(kind, p, directory):
    ident = PUBLIC[kind] if p is None else PUBLIC[kind][p]
    url = f"{DS}{ident}?format=original"
    path = directory/f"{kind}_{ident}.csv"
    directory.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if (curl := shutil.which("curl")) is not None:
            payload = subprocess.run([curl, "--fail", "--silent", "--show-error", "--location",
                                      "--retry", "1", "--max-time", "60", url],
                                     check=True, stdout=subprocess.PIPE).stdout
        else:
            with urlopen(url, timeout=60) as f:
                payload = f.read()
        if hashlib.sha256(payload).hexdigest() != PINNED_SHA[ident]:
            raise ValueError(f"Descarga no coincide con la versión fijada en {url}; no se guardó.")
        path.write_bytes(payload)
    if digest(path) != PINNED_SHA[ident]:
        raise ValueError(f"Archivo público alterado en caché: {path}. Use una caché nueva o pase su archivo local explícitamente.")
    return path, url


def kv(args, convert):
    entries = {}
    for s in args or ():
        label, equals, value = s.partition("=")
        if not equals or not value:
            raise ValueError(f"Se esperaba CLAVE=VALOR, no {s!r}")
        key = convert(label)
        if key in entries:
            raise ValueError(f"Clave repetida: {key}")
        entries[key] = value
    return entries


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--publico", action="store_true", help="Descarga archivos Dataverse faltantes por ID fijo.")
    cli.add_argument("--cache", type=Path, default=Path("datos_publicos_cache"))
    cli.add_argument("--ideologia", type=Path)
    cli.add_argument("--matriz", action="append", metavar="PERIODO=ARCHIVO")
    cli.add_argument("--militancia", action="append", metavar="PERIODO=ARCHIVO")
    cli.add_argument("--geografia", type=Path, help="CSV con Id, Period, Distrito.")
    cli.add_argument("--eleccion", action="append", metavar="AÑO=ARCHIVO")
    cli.add_argument("--hoja-eleccion", default="Votación por comuna")
    cli.add_argument("--encabezado-eleccion", type=int, default=6)
    cli.add_argument("--no-voto", action="append", default=[], metavar="COLUMNA")
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--B", type=int, default=3999, help="0 para omitir bootstrap; de otro modo >=199.")
    cli.add_argument("--semilla", type=int, default=20261007)
    cli.add_argument("--region-min-n", type=int, default=8)
    cli.add_argument("--region-min-cobertura", type=float, default=.85)
    cli.add_argument("--region-max-loo", type=float, default=.12)
    cli.add_argument("--region-m-pool", type=float, default=4)
    args = cli.parse_args(argv)
    if ((args.B and args.B < 199) or args.semilla < 0 or args.encabezado_eleccion < 0 or args.region_min_n < 3
            or not 0 < args.region_min_cobertura <= 1 or not 0 < args.region_max_loo <= 1 or args.region_m_pool < 0
            or not np.isfinite(args.region_m_pool)):
        cli.error("Parámetros de soporte, réplicas, semilla o encabezado inválidos.")
    if args.out.exists() and any(args.out.iterdir()):
        cli.error("--out debe ser nuevo o estar vacío.")
    tracks = {}

    def register(label, path, url=None):
        path = Path(path)
        tracks[label] = {"archivo": path.name, "sha256": digest(path), "url": url}
        return path

    def item(kind, p, path):
        label = f"{kind}:{p}" if p else kind
        if path:
            return register(label, path)
        if args.publico:
            return register(label, *get_public(kind, p, args.cache))
        return None

    ide = item("ideologia", None, args.ideologia)
    if ide is None:
        cli.error("Indique --ideologia ARCHIVO o --publico.")
    df = panel(ide)
    all_att, all_party = [], []
    ap, pp = kv(args.matriz, period), kv(args.militancia, period)
    if (set(ap)|set(pp)) - set(MAIN):
        cli.error("Matrices y militancias auxiliares corresponden a Periodo_3…Periodo_6.")
    for p in MAIN:
        path = item("matriz", p, ap.get(p))
        if path:
            all_att.append(rollcalls(path, p, args.no_voto))
        path = item("militancia", p, pp.get(p))
        if path:
            all_party.append(party_dates(path, p))
    att = pd.concat(all_att, ignore_index=True) if all_att else pd.DataFrame(columns=[*KEY, "Asistencia"])
    if not att.empty:
        validate_name_ids(df, att, "Name_matriz", "asistencia")
        df = attach(df, att, "asistencia")
    else:
        df["Asistencia"] = np.nan
    if all_party:
        apd = pd.concat(all_party, ignore_index=True)
        validate_name_ids(df, apd, "Name_militancia_fuente", "militancias")
        df = attach(df, apd, "militancias")
    else:
        df["salida_fechada"] = df["unico_fechado"] = np.nan
    geo_path = args.geografia
    bundled = Path(__file__).with_name("distritos_diputados_2010_2026.csv")
    if geo_path is None and args.publico and bundled.exists() and digest(ide) == PINNED_SHA[PUBLIC["ideologia"]]:
        geo_path = bundled
    geo = None
    if geo_path is not None:
        geo = geography(register("geografia", geo_path))
        if "Name_geografia" in geo:
            validate_name_ids(df, geo, "Name_geografia", "geografía")
        df = attach(df, geo, "geografía")
    else:
        df["Distrito"] = np.nan
    els = kv(args.eleccion, int)
    if set(els) - set(ELECTION):
        cli.error("--eleccion requiere un año ordinario conocido (p. ej. 2013, 2017, 2021 o 2025).")
    args.out.mkdir(parents=True, exist_ok=True)
    for year, path in els.items():
        pts = election(register(f"eleccion:{year}", path), year, df, args.hoja_eleccion, args.encabezado_eleccion)
        pts.to_csv(args.out/f"auditoria_electoral_{year}.csv", index=False, encoding="utf-8-sig")
    summary = summarize(df, att, geo, args.out, args.B, args.semilla, args.region_min_n, args.region_min_cobertura,
                        args.region_max_loo, args.region_m_pool)
    manifest = {"versiones": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
                "insumos": tracks, "periodos_indice": MAIN, "partido_panel_regional": summary["atribucion_panel_regional"],
                "opciones": {"excluir_columnas_matriz": args.no_voto, "hoja_eleccion": args.hoja_eleccion,
                             "fila_encabezado_electoral_base_0": args.encabezado_eleccion},
                "B": args.B, "semilla": args.semilla, **summary, "regla_soporte": {
                    "n_min": args.region_min_n, "cobertura_min": args.region_min_cobertura,
                    "n_min_grupos_con_n_ge_2": 2, "max_loo": args.region_max_loo, "m_pool": args.region_m_pool}}
    (args.out/"manifiesto.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf8")
    print(f"Resultados verificados en {args.out.resolve()}. R = {summary['R']:.6f}.")


if __name__ == "__main__":
    main()
