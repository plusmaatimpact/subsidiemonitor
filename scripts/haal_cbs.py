#!/usr/bin/env python3
"""Plusmaat Subsidiemonitor - vernieuwt de CBS-gegevens.

Haalt voor alle gemeenten in de monitor (en hun vergelijkingsgemeenten):
  * Iv3-lasten per taakveldcluster uit 'Gemeenten <jaar> onbewerkte Iv3-data' (begroting)
  * de toegerekende overhead (taakveld 0.4, naar rato van directe lasten)
  * inwoners op 1 januari (CBS 37230ned) per gemeente en per centrumregio
en schrijft data/iv3.json, overhead.json, overheadTotaal.json, inwonersIv3.json en regio.json.

Gebruik: python scripts/haal_cbs.py [--jaar 2026]
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IV3_BASE = "https://dataderden.cbs.nl/ODataApi/OData/"
CAT = "https://dataderden.cbs.nl/ODataCatalog/Tables?$format=json&$select=Identifier,Title&$filter=" + urllib.parse.quote("substringof('Gemeenten',Title)")
BEV = "https://opendata.cbs.nl/ODataApi/OData/37230ned/"

CLUSTERS = {
    "Cultuur (musea, podia, erfgoed, bibliotheek)": ["5.3", "5.4", "5.5", "5.6"],
    "Sport": ["5.1", "5.2"],
    "Welzijn en burgerparticipatie": ["6.1"],
    "Opvang en beschermd wonen": ["6.811", "6.812"],
    "Volksgezondheid": ["7.1"],
    "Onderwijsbeleid": ["4.3"],
    "Economie": ["3.1", "3.2", "3.3", "3.4"],
}
EXCL_CAT = {"L6.1", "L7.1", "L7.4", "L7.5"}          # financiële transacties, reserves, verrekeningen
FIN_TV = {"0.4", "0.5", "0.61", "0.62", "0.63", "0.64", "0.7", "0.8", "0.9", "0.10", "0.11"}
OVERHEAD_EXTRA = {"Nijmegen": ["0.8"]}               # gemeenten die overhead ook elders boeken
ALIAS = {"Den Haag": "'s-Gravenhage"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "plusmaat-subsidiemonitor"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def all_rows(url):
    out = []
    while url:
        j = get(url)
        out += j.get("value", [])
        url = j.get("odata.nextLink")
    return out


def match(name, dims):
    """Zoekt de code van een gemeentenaam in een dimensielijst [{Key, Title}]."""
    n = ALIAS.get(name, name).strip().lower()
    for d in dims:
        t = d["Title"].strip().lower()
        if t == n or t.startswith(n + " (") or t.split(" (")[0] == n:
            return d["Key"].strip()
    return None


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save(name, data):
    (DATA / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jaar", type=int, help="Begrotingsjaar van de Iv3-tabel (standaard: nieuwste)")
    a = ap.parse_args()

    tabellen = []
    for t in get(CAT)["value"]:
        m = re.match(r"Gemeenten (\d{4}) onbewerkte Iv3-data", t["Title"].strip())
        if m:
            tabellen.append((int(m[1]), t["Identifier"]))
    tabellen.sort()
    if a.jaar:
        tabellen = [t for t in tabellen if t[0] == a.jaar]
    if not tabellen:
        print("Geen Iv3-tabel gevonden.")
        return 1
    jaar, tabel = tabellen[-1]
    base = IV3_BASE + tabel + "/"
    print(f"Iv3-tabel {tabel} (begroting {jaar})")

    namen = {g["gemeente"] for g in load("gemeenten.json")}
    for p in load("peers.json"):
        namen |= {p["gemeente"], p["vergelijking"]}
    namen |= {x["gemeente"] for x in load("iv3.json")}

    gdims = get(base + "Gemeenten?$format=json")["value"]
    vs = next(v["Key"] for v in get(base + "Verslagsoort?$format=json")["value"] if v["Key"].strip().endswith("X000"))
    codes = {}
    for n in sorted(namen):
        c = match(n, gdims)
        if c:
            codes[n] = c
        else:
            print(f"  ! {n} niet gevonden in de Iv3-tabel; overgeslagen")

    iv3, overhead, ohtot = [], [], []
    for n, code in codes.items():
        f = f"Gemeenten eq '{code.ljust(9)}' and Verslagsoort eq '{vs}' and startswith(Categorie,'L')"
        url = base + "TypedDataSet?$format=json&$select=Categorie,TaakveldBalanspost,k_1ePlaatsing_1,k_2ePlaatsing_2&$filter=" + urllib.parse.quote(f)
        tv = {}
        for r in all_rows(url):
            cat, t = r["Categorie"].strip(), r["TaakveldBalanspost"].strip()
            if not re.fullmatch(r"[0-8]\.\d+", t):
                continue
            v = r.get("k_2ePlaatsing_2")
            if v is None:
                v = r.get("k_1ePlaatsing_1")
            if v is None:
                continue
            x = tv.setdefault(t, {"l": 0, "o": 0, "gr": 0})
            if cat not in EXCL_CAT:
                x["l"] += v
            if cat in ("L4.2", "L4.3.8"):
                x["o"] += v
            if cat == "L4.3.3":
                x["gr"] += v
        if not tv:
            print(f"  ! geen begrotingsgegevens voor {n}")
            continue
        oh = sum(tv.get(t, {}).get("l", 0) for t in ["0.4"] + OVERHEAD_EXTRA.get(n, []))
        basis = sum(x["l"] for t, x in tv.items() if t not in FIN_TV)
        for c, ks in CLUSTERS.items():
            l = sum(tv.get(k, {}).get("l", 0) for k in ks)
            iv3.append({"gemeente": n, "cluster": c, "lasten": l * 1000,
                        "overdrachten": sum(tv.get(k, {}).get("o", 0) for k in ks) * 1000,
                        "bijdrageGR": sum(tv.get(k, {}).get("gr", 0) for k in ks) * 1000})
            overhead.append({"gemeente": n, "cluster": c, "overheadToegerekend": round(oh * l / basis) * 1000 if basis else 0})
        iv3.append({"gemeente": n, "cluster": "Totaal alle taakvelden", "lasten": sum(x["l"] for x in tv.values()) * 1000,
                    "overdrachten": sum(x["o"] for x in tv.values()) * 1000, "bijdrageGR": sum(x["gr"] for x in tv.values()) * 1000})
        ohtot.append({"gemeente": n, "overhead": oh * 1000, "directeLasten": basis * 1000,
                      "opmerking": "Overhead geboekt op 0.4 én " + ", ".join(OVERHEAD_EXTRA[n]) if n in OVERHEAD_EXTRA else ""})
        print(f"  {n}: lasten € {sum(x['l'] for x in tv.values()) / 1000:,.0f} mln")

    save("iv3.json", iv3)
    save("overhead.json", overhead)
    save("overheadTotaal.json", ohtot)

    # inwoners op 1 januari
    per = [p["Key"] for p in get(BEV + "Perioden?$format=json")["value"] if p["Key"].endswith("MM01")]
    periode = sorted(per)[-1]
    rdims = [r for r in get(BEV + "RegioS?$format=json")["value"] if r["Key"].startswith("GM")]

    def inwoners(naam, code=None):
        k = code or match(naam, rdims)
        if not k:
            return None
        f = f"RegioS eq '{k.strip().ljust(6)}' and Perioden eq '{periode}'"
        v = get(BEV + "TypedDataSet?$format=json&$select=BevolkingAanHetBeginVanDePeriode_1&$filter=" + urllib.parse.quote(f))["value"]
        return v[0]["BevolkingAanHetBeginVanDePeriode_1"] if v else None

    inw = []
    for n, code in codes.items():
        v = inwoners(n, code)
        if v:
            inw.append({"gemeente": n, "inwoners": v})
    save("inwonersIv3.json", inw)
    gem = load("gemeenten.json")
    for g in gem:
        hit = next((x for x in inw if x["gemeente"] == g["gemeente"]), None)
        if hit:
            g["inwoners"] = hit["inwoners"]
    save("gemeenten.json", gem)

    regio = load("regio.json")
    for r in regio:
        delen = [x.strip() for x in re.split(r"[;,]", r.get("gemeenten", "")) if x.strip()]
        waarden = [inwoners(x) for x in delen]
        if delen and all(waarden):
            r["inwonersRegio"] = sum(waarden)
        else:
            mis = [d for d, w in zip(delen, waarden) if not w]
            print(f"  ! regio {r['regio']}: inwoners niet herberekend (onbekend: {', '.join(mis) or 'geen gemeentenlijst'})")
    save("regio.json", regio)
    print(f"Inwoners per {periode[:4]}-01-01 bijgewerkt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
