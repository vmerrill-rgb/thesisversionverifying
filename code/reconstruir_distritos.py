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
"""Reconstruye el cruce territorial con padrones y directorios, nunca por igualdad de IDs."""
import argparse
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# %%
import pandas as pd

# %%
from indices_diputados_chile import ID, P, X, MAIN, panel, clean, namekey

# %%
BCN = "https://www.bcn.cl/historiapolitica/corporaciones/periodo_detalle"
CAM = "https://opendata.camara.cl/camaradiputados/WServices/WSDiputado.asmx/retornarDiputadosXPeriodo"
SERVEL = "https://www.servel.cl/wp-content/uploads/2022/12/Candidatos_2017_Electos_14-03-2018.xlsx"
CAM22 = "https://www.camara.cl/camara/doc/listado2022.pdf"


# %%
def candidate(name, number, url, kind, *, reversed_name=False, chamber_id=""):
    return dict(name=name, number=int(number), url=url, kind=kind,
                reversed_name=reversed_name, chamber_id=chamber_id)


# %%
def bcn(path, year):
    url = f"{BCN}?inicio={year}-03-11&fin={year+4}-03-10&periodo=1990-2026&cam=Diputados"
    return [candidate(n.strip(), d, url, "BCN_periodo") for n, d in re.findall(
        r"^- ##### ([^\n]+)\s+Diputad[oa]\s*\|\s*Distrt?ito\s*N[°º]\s*(\d+)",
        path.read_text(encoding="utf-8"), re.M)]


# %%
def xml(path, cam_period):
    root = ET.parse(path)
    ns = {"c": root.getroot().tag.split("}")[0].removeprefix("{")}
    for rec in root.findall("c:DiputadoPeriodo", ns):
        district = rec.findtext("c:Distrito/c:Numero", namespaces=ns)
        if district:
            node = rec.find("c:Diputado", ns)
            names = ("Nombre", "Nombre2", "ApellidoPaterno", "ApellidoMaterno")
            name = " ".join(filter(None, [clean(node.findtext("c:"+c, namespaces=ns)) for c in names]))
            yield candidate(name, district, f"{CAM}?prmPeriodoID={cam_period}", "Camara_XML",
                            chamber_id=node.findtext("c:Id", namespaces=ns))


# %%
def servel(path):
    e = pd.read_excel(path, dtype=str, keep_default_na=False)
    for r in e.loc[e.tipo_eleccion.eq("DIPUTADOS") & e.electo.eq("S")].itertuples():
        name = " ".join((r.nombres_candidato, r.apellidopaterno, r.apellidomaterno))
        yield candidate(name, re.search(r"\d+", r.territorio)[0], SERVEL, "Servel_2017_electos")


# %%
def camara22(text):
    # Text extraction from official PDF; damaged glyph 'ti' occurs systematically in this PDF.
    text = text.replace("\ufffd", "ti")
    for n, d in re.findall(r"^([^\n@0-9*/|]{4,})\n(?:RM|[IVX]+) [^\n]+\s+"
                           r"(?:[^\n]+@congreso\.cl\s+)?N[°º]\s*(\d+)", text, re.M):
        n = n.strip()
        if len(n.split()) >= 3:
            yield candidate(n, d, CAM22, "Camara_PDF_2022", reversed_name=True)


# %%
def evidence_score(long_name, c):
    long = namekey(long_name).split()
    raw = namekey(c["name"]).split()
    keys = [raw[i:]+raw[:i] for i in range(2, len(raw))] if c["reversed_name"] else [raw]
    for key in keys:
        if key == long:
            return 2
    # Same two surname tokens, concordant first given name; accept reordered/omitted
    # secondary given names. Require uniqueness on BOTH sides below.
    if len(long) >= 3 and any(len(k) >= 3 and k[-2:] == long[-2:] and k[0] == long[0] for k in keys):
        return 1
    return 0


# %%
def match(rows, sources):
    out = {i: [] for i in range(len(rows))}
    for entries in sources:
        entries = list({(namekey(c["name"]), c["number"]): c for c in entries}.values())
        counts = Counter()
        options = {}
        for i, r in enumerate(rows):
            scored = [(evidence_score(r["Name"], c), j) for j, c in enumerate(entries)]
            highest = max((s for s, _ in scored), default=0)
            if highest:
                options[i] = (highest, [j for s, j in scored if highest == s])
                counts.update(options[i][1])
        for i, (score, js) in options.items():
            if len(js) == 1 and counts[js[0]] == 1:
                out[i].append({**entries[js[0]], "match": "nombre_exacto" if score == 2 else "nombre_y_apellidos_unicos"})
    return out


# %%
MANUAL = {
    # Reemplazos e inconsistencias de transcripción revisados contra fuentes de distrito.
    ("Periodo_5", "1093"): (19, "Patricia Irene Rubio Escobar",
                             "https://www.bcn.cl/historiapolitica/resenas_biograficas/wiki/Patricia_Irene_Rubio_Escobar"),
    ("Periodo_5", "1092"): (14, "Marcela Paz Alejandra Sandoval Osorio",
                             "https://www.bcn.cl/asesoriasparlamentarias/documentos.html?pagina=300&M=30&start=3740&cate=&t=&total=7892"),
    ("Periodo_5", "1095"): (15, "Juan Manuel Masferrer Vidal", "https://observatoriocongreso.cl/notas/"),
    ("Periodo_5", "209"): (17, "Pablo Samuel Prieto Lorca",
                            "https://www.bcn.cl/historiapolitica/resenas_parlamentarias/wiki/Pablo_Samuel_Prieto_Lorca"),
    ("Periodo_5", "974"): (19, "María Loreto Carvajal Ambiado",
                            "https://www.bcn.cl/historiapolitica/resenas_biograficas/wiki/Mar%C3%ADa_Loreto_Carvajal_Ambiado"),
    ("Periodo_6", "1115"): (17, "Mercedes Bulnes Núñez", CAM22),
    ("Periodo_6", "1135"): (10, "Johannes Kaiser Barents-von Hohenhagen",
                             "https://www.bcn.cl/historiapolitica/resenas_parlamentarias/wiki/Johannes_Kaiser_Barents-von_Hohenhagen"),
    ("Periodo_6", "1153"): (23, "Coca Ericka Ñanco Vásquez",
                             "https://www.bcn.cl/historiapolitica/resenas_biograficas/wiki/Coca_Ericka_%C3%91anco_V%C3%A1squez"),
}


# %%
def build(raw, pdf, ideology):
    d = panel(ideology)
    out = []
    for p, y, cper in zip(MAIN, (2010, 2014, 2018, 2022), (6, 8, 9, 10)):
        bfile = raw/f"bcnfull{y}.txt"
        bfile = bfile if bfile.exists() else raw/f"bcn{y}.txt"
        src = [bcn(bfile, y)]
        if y < 2018:
            src.append(xml(raw/f"roster{cper}.xml", cper))
        if y == 2018:
            src.append(servel(raw/"servel2017.xlsx"))
        if y == 2022:
            src.append(camara22(pdf))
        rows = d.loc[d[P].eq(p) & d[X].notna(), [ID, "Name"]].to_dict("records")
        linked = match(rows, src)
        for i, r in enumerate(rows):
            values = linked[i]
            if (p, r[ID]) in MANUAL:
                district, name, url = MANUAL[p, r[ID]]
                values.append({**candidate(name, district, url, "revision_individual"), "match": "revision_manual"})
            districts = {v["number"] for v in values}
            state = "verificado" if len(districts) == 1 else "conflicto" if districts else "sin_correspondencia"
            if state != "verificado":
                print(f"{state}: {p} {r['Id']:>4s} {r['Name']} {values}")
            out.append({P: p, ID: r[ID], "Distrito": next(iter(districts)) if len(districts) == 1 else None,
                        "Name_geografia": r["Name"], "Estado_geografia": state,
                        "Nombre_en_padron": " | ".join(v["name"] for v in values),
                        "Metodo_geografia": " | ".join(v["kind"]+":"+v["match"] for v in values),
                        "URL_geografia": " | ".join(v["url"] for v in values),
                        "Id_Camara_referencia": " | ".join(v["chamber_id"] for v in values if v["chamber_id"])})
    return pd.DataFrame(out)


# %%
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--raw", type=Path, required=True)
    cli.add_argument("--out", type=Path, required=True)
    cli.add_argument("--ideologia", type=Path, required=True)
    args = cli.parse_args()
    import sys
    build(args.raw, sys.stdin.read(), args.ideologia).to_csv(args.out, index=False, encoding="utf-8-sig")
