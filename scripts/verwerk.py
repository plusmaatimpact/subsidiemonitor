#!/usr/bin/env python3
"""Plusmaat Subsidiemonitor - verwerkt aanleveringen.

Leest elk Excel- of CSV-bestand in de map aanleveringen/, controleert het met
dezelfde regels als het Dataloket, werkt de bestanden in data/ bij en
verplaatst het bestand naar aanleveringen/verwerkt/ of aanleveringen/afgewezen/.
Elke verwerking komt in data/log.json.

Gebruik: python scripts/verwerk.py   (vanuit de hoofdmap van de repository)
"""
import csv
import datetime as dt
import io
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IN = ROOT / "aanleveringen"

DOMEINEN = ["Zorg & welzijn", "Cultuur", "Jeugd & onderwijs", "Sport & bewegen", "Participatie & samenleving",
            "Werk & inkomen", "Armoede & schulden", "Wonen & leefomgeving", "Economie & duurzaamheid", "Veiligheid", "Overig"]
TYPES = ["Stichting", "Vereniging", "B.V.", "Coöperatie", "Regeling / budgetpost", "Onbekend (niet uit naam af te leiden)"]
STATUS = ["Aangevraagd", "In uitvoering", "Afgerond"]
VORMEN = ["Quickscan", "Standaard MKBA", "Uitgebreide MKBA", "Jaarlijkse update"]
WAT = ["gemeente", "posten", "studie", "vergelijking", "regio"]


def K(k, req, typ, waarden=None, mn=None, mx=None):
    return {"k": k, "req": req, "type": typ, "waarden": waarden, "min": mn, "max": mx}


SPEC = {
    "subsidieposten": {"naam": "Subsidieposten", "kolommen": [
        K("gemeente", 1, "tekst"), K("jaar", 1, "jaar"), K("instelling", 1, "tekst"), K("categorie", 1, "tekst"),
        K("domein", 1, "keuze", DOMEINEN), K("type", 0, "keuze", TYPES), K("bedrag", 0, "euro", mn=0), K("bron", 0, "tekst")]},
    "gemeentegegevens": {"naam": "Gemeentegegevens", "kolommen": [
        K("gemeente", 1, "tekst"), K("inwoners", 1, "geheel", mn=1), K("jaar", 1, "jaar"), K("bron", 1, "tekst"),
        K("reikwijdte", 1, "tekst"), K("opmerking", 0, "tekst")]},
    "impactstudies": {"naam": "Impactstudies", "kolommen": [
        K("gemeente", 1, "tekst"), K("instelling", 1, "tekst"), K("status", 1, "keuze", STATUS), K("studievorm", 1, "keuze", VORMEN),
        K("rendement", 0, "decimaal", mn=0), K("nettoBatenGemeente", 0, "euro"), K("datum", 0, "datum"), K("opmerking", 0, "tekst")]},
    "vergelijkingsgemeenten": {"naam": "Vergelijkingsgemeenten", "kolommen": [
        K("gemeente", 1, "tekst"), K("vergelijking", 1, "tekst"), K("rang", 1, "geheel", mn=1, mx=3),
        K("amigoIntegraal", 0, "decimaal", mn=0, mx=1), K("amigoSociaal", 0, "decimaal", mn=0, mx=1), K("amigoSES", 0, "decimaal", mn=0, mx=1),
        K("motivering", 1, "tekst")]},
    "centrumregios": {"naam": "Centrumregio’s", "kolommen": [
        K("gemeente", 1, "tekst"), K("regio", 1, "tekst"), K("gemeenten", 1, "tekst"), K("inwonersRegio", 0, "geheel", mn=1), K("bron", 1, "tekst")]},
    "studievormen": {"naam": "Studievormen en prijzen", "kolommen": [
        K("studievorm", 1, "keuze", VORMEN), K("prijs", 1, "euro", mn=0), K("weken", 1, "geheel", mn=1), K("uren", 1, "geheel", mn=1), K("wat", 1, "tekst")]},
    "verwijderingen": {"naam": "Verwijderingen", "kolommen": [
        K("wat", 1, "keuze", WAT), K("gemeente", 1, "tekst"), K("instelling", 0, "tekst"), K("jaar", 0, "jaar"),
        K("vergelijking", 0, "tekst"), K("reden", 1, "tekst")]},
}


def keyof(s):
    return re.sub(r"[\s_\-]", "", str(s or "").strip().lower())


def norm(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def parse_number(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = re.sub(r"[€\s]", "", norm(v))
    if not s:
        return None
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d+,\d+", s):
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return "NaN"


def parse_date(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d")
    s = norm(v)
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?", s)
    if m:
        return f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    return "NaN"


def read_table(path):
    """Geeft de rijen (lijst van lijsten) van tabblad 'Gegevens' of het eerste tabblad."""
    if path.suffix.lower() == ".csv":
        raw = path.read_bytes().decode("utf-8-sig", errors="replace")
        dialect = csv.Sniffer().sniff(raw[:2048], delimiters=";,\t") if raw.strip() else csv.excel
        return [row for row in csv.reader(io.StringIO(raw), dialect)]
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = next((wb[n] for n in wb.sheetnames if n.strip().lower() == "gegevens"), wb[wb.sheetnames[0]])
    return [list(r) for r in ws.iter_rows(values_only=True)]


def detect_soort(path, header):
    naam = path.name.lower()
    for sid in SPEC:
        if naam.startswith(sid):
            return sid
    hk = {keyof(h) for h in header if norm(h)}
    best = None
    for sid, sp in SPEC.items():
        req = {keyof(c["k"]) for c in sp["kolommen"] if c["req"]}
        if req <= hk:
            score = len(hk & {keyof(c["k"]) for c in sp["kolommen"]})
            if best is None or score > best[0]:
                best = (score, sid)
    return best[1] if best else None


def validate(sid, aoa):
    sp = SPEC[sid]
    issues = []

    def add(lvl, i, kol, msg):
        issues.append({"lvl": lvl, "rij": None if i is None else i + 2, "kol": kol, "msg": msg})

    header = [norm(h) for h in (aoa[0] if aoa else [])]
    idx = {}
    for i, h in enumerate(header):
        c = next((c for c in sp["kolommen"] if keyof(c["k"]) == keyof(h)), None)
        if c:
            idx[c["k"]] = i
        elif h:
            add("let", None, h, f"Onbekende kolom “{h}” wordt genegeerd.")
    for c in sp["kolommen"]:
        if c["req"] and c["k"] not in idx:
            add("fout", None, c["k"], f"Verplichte kolom “{c['k']}” ontbreekt.")
    body = [r for r in aoa[1:] if r and any(norm(x) for x in r)]
    if not body:
        add("fout", None, None, "Het bestand bevat geen gegevensrijen onder de kopregel.")
    if len(body) > 5000:
        add("fout", None, None, f"Te veel rijen ({len(body)}); maximaal 5000.")
    rows = []
    for i, r in enumerate(body[:5000]):
        o = {}
        for c in sp["kolommen"]:
            k = c["k"]
            if k not in idx:
                o[k] = None
                continue
            raw = r[idx[k]] if idx[k] < len(r) else None
            s = norm(raw)
            if s == "":
                o[k] = None
                if c["req"]:
                    add("fout", i, k, "Verplicht veld is leeg.")
                continue
            t = c["type"]
            if t == "tekst":
                o[k] = s
                continue
            if t == "keuze":
                v = next((w for w in c["waarden"] if keyof(w) == keyof(s)), None)
                if not v and k == "type" and keyof(s) == "onbekend":
                    v = TYPES[5]
                if not v:
                    add("fout", i, k, f"“{s}” is geen toegestane waarde.")
                o[k] = v or s
                continue
            if t == "datum":
                d = parse_date(raw)
                if d == "NaN":
                    add("fout", i, k, f"“{s}” is geen datum; gebruik jjjj-mm-dd.")
                o[k] = s if d == "NaN" else d
                continue
            n = parse_number(raw)
            if n == "NaN":
                add("fout", i, k, f"“{s}” is geen getal.")
                o[k] = s
                continue
            if t in ("geheel", "jaar") and not float(n).is_integer():
                add("fout", i, k, "Moet een heel getal zijn.")
            if t == "jaar" and not (2015 <= n <= 2040):
                add("fout", i, k, "Jaartal buiten 2015–2040.")
            if c["min"] is not None and n < c["min"]:
                add("fout", i, k, f"Minimaal {c['min']}.")
            if c["max"] is not None and n > c["max"]:
                add("fout", i, k, f"Maximaal {c['max']}.")
            if k == "bedrag" and 0 < n < 1000:
                add("let", i, k, "Klein bedrag: controleer of het niet in duizenden is opgegeven.")
            o[k] = int(round(n)) if t in ("euro", "geheel", "jaar") else n
        rows.append(o)

    # extra regels per soort
    if sid == "impactstudies":
        for i, r in enumerate(rows):
            if r.get("rendement") is not None and r.get("status") != "Afgerond":
                add("let", i, "rendement", "Rendement ingevuld bij een studie die nog niet is afgerond.")
    if sid == "vergelijkingsgemeenten":
        seen = {}
        for i, r in enumerate(rows):
            key = (r.get("gemeente"), r.get("rang"))
            if key in seen:
                add("fout", i, "rang", f"Rang {r.get('rang')} komt voor {r.get('gemeente')} al voor in rij {seen[key]}.")
            seen.setdefault(key, i + 2)
            if r.get("gemeente") and r.get("vergelijking") and r["gemeente"].lower() == r["vergelijking"].lower():
                add("fout", i, "vergelijking", "Een gemeente kan niet met zichzelf vergeleken worden.")
    if sid == "studievormen":
        seen = {}
        for i, r in enumerate(rows):
            if r.get("studievorm") in seen:
                add("fout", i, "studievorm", f"Studievorm staat al in rij {seen[r['studievorm']]}.")
            seen.setdefault(r.get("studievorm"), i + 2)
    if sid == "verwijderingen":
        for i, r in enumerate(rows):
            if r.get("wat") in ("posten", "studie") and not r.get("instelling"):
                add("fout", i, "instelling", "Vul de instelling in bij posten en studie.")
            if r.get("wat") == "vergelijking" and not r.get("vergelijking"):
                add("fout", i, "vergelijking", "Vul de vergelijkingsgemeente in.")
    return rows, issues


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save(name, data):
    (DATA / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def low(s):
    return str(s or "").strip().lower()


def apply(sid, rows, gemeenten_known):
    """Past de gecontroleerde rijen toe. Geeft (samenvatting, extra fouten) terug."""
    fouten = []
    if sid == "subsidieposten":
        posten = load("posten.json")
        gem = {g["gemeente"]: g for g in load("gemeenten.json")}
        combos = {(r["gemeente"], r["jaar"]) for r in rows}
        for g, _ in combos:
            if g not in gem:
                fouten.append(f"Gemeente “{g}” is onbekend. Lever eerst gemeentegegevens aan.")
        if fouten:
            return None, fouten
        oud = len(posten)
        posten = [p for p in posten if (p["gemeente"], p.get("jaar", gem.get(p["gemeente"], {}).get("jaar"))) not in combos]
        verwijderd = oud - len(posten)
        for r in rows:
            posten.append({"gemeente": r["gemeente"], "instelling": r["instelling"], "categorie": r["categorie"], "domein": r["domein"],
                           "type": r.get("type") or TYPES[5], "bedrag": r.get("bedrag"), "jaar": r["jaar"], "bron": r.get("bron") or ""})
        for i, p in enumerate(posten):
            p["post"] = i + 1
        save("posten.json", posten)
        return f"{len(rows)} posten geplaatst, {verwijderd} oude posten vervangen ({', '.join(f'{g} {j}' for g, j in sorted(combos))}).", []

    if sid == "gemeentegegevens":
        lst = load("gemeenten.json")
        nieuw = 0
        for r in rows:
            cur = next((g for g in lst if low(g["gemeente"]) == low(r["gemeente"])), None)
            rec = {"gemeente": r["gemeente"], "inwoners": r["inwoners"], "jaar": r["jaar"], "bron": r["bron"],
                   "reikwijdte": r["reikwijdte"], "opmerking": r.get("opmerking") or ""}
            if cur:
                cur.update(rec)
            else:
                lst.append(rec)
                nieuw += 1
        save("gemeenten.json", lst)
        inw = load("inwonersIv3.json")
        for r in rows:
            cur = next((x for x in inw if low(x["gemeente"]) == low(r["gemeente"])), None)
            if cur:
                cur["inwoners"] = r["inwoners"]
            else:
                inw.append({"gemeente": r["gemeente"], "inwoners": r["inwoners"]})
        save("inwonersIv3.json", inw)
        return f"{len(rows)} gemeenten bijgewerkt, waarvan {nieuw} nieuw.", []

    if sid == "impactstudies":
        lst = load("studies.json")
        nieuw = 0
        posten = load("posten.json")
        for r in rows:
            if not any(p["gemeente"] == r["gemeente"] and p["instelling"] == r["instelling"] for p in posten):
                fouten.append(f"Instelling “{r['instelling']}” staat niet in de posten van {r['gemeente']}.")
        if fouten:
            return None, fouten
        for r in rows:
            cur = next((s for s in lst if s["gemeente"] == r["gemeente"] and s["instelling"] == r["instelling"]), None)
            rec = {k: r.get(k) for k in ["gemeente", "instelling", "status", "studievorm", "rendement", "nettoBatenGemeente", "datum", "opmerking"]}
            if cur:
                cur.update(rec)
            else:
                lst.append(rec)
                nieuw += 1
        save("studies.json", lst)
        return f"{len(rows)} studies bijgewerkt, waarvan {nieuw} nieuw.", []

    if sid == "vergelijkingsgemeenten":
        lst = load("peers.json")
        gem = {r["gemeente"] for r in rows}
        lst = [p for p in lst if p["gemeente"] not in gem] + [
            {k: r.get(k) for k in ["gemeente", "vergelijking", "rang", "amigoIntegraal", "amigoSociaal", "amigoSES", "motivering"]} for r in rows]
        save("peers.json", lst)
        iv3 = {x["gemeente"] for x in load("iv3.json")}
        mis = sorted({r["vergelijking"] for r in rows} | gem)
        mis = [g for g in mis if g not in iv3]
        extra = f" Nog geen Iv3-gegevens voor: {', '.join(mis)}; start de actie ‘Vernieuw CBS-gegevens’." if mis else ""
        return f"Vergelijkingsgemeenten vervangen voor {', '.join(sorted(gem))}.{extra}", []

    if sid == "centrumregios":
        lst = load("regio.json")
        for r in rows:
            rec = {"gemeente": r["gemeente"], "regio": r["regio"], "gemeenten": ", ".join(x.strip() for x in r["gemeenten"].split(";") if x.strip()),
                   "inwonersRegio": r.get("inwonersRegio"), "bron": r["bron"]}
            cur = next((x for x in lst if x["gemeente"] == r["gemeente"]), None)
            if cur:
                if rec["inwonersRegio"] is None:
                    rec["inwonersRegio"] = cur.get("inwonersRegio")
                cur.update(rec)
            else:
                lst.append(rec)
        save("regio.json", lst)
        leeg = [r["gemeente"] for r in rows if r.get("inwonersRegio") is None]
        return f"{len(rows)} centrumregio’s bijgewerkt." + (f" Inwoners regio nog aanvullen voor: {', '.join(leeg)} (actie ‘Vernieuw CBS-gegevens’)." if leeg else ""), []

    if sid == "studievormen":
        save("studievormen.json", [{k: r.get(k) for k in ["studievorm", "prijs", "weken", "uren", "wat"]} for r in rows])
        return f"Lijst met {len(rows)} studievormen vervangen.", []

    if sid == "verwijderingen":
        delen = []
        for r in rows:
            g, wat = r["gemeente"], r["wat"]
            if wat == "gemeente":
                for f, key in [("posten.json", "gemeente"), ("gemeenten.json", "gemeente"), ("studies.json", "gemeente"),
                               ("peers.json", "gemeente"), ("regio.json", "gemeente"), ("context.json", "gemeente")]:
                    save(f, [x for x in load(f) if x.get(key) != g])
                delen.append(f"gemeente {g} verwijderd")
            elif wat == "posten":
                lst = load("posten.json")
                n = len(lst)
                lst = [p for p in lst if not (p["gemeente"] == g and p["instelling"] == r["instelling"] and (r.get("jaar") is None or p.get("jaar") == r["jaar"]))]
                for i, p in enumerate(lst):
                    p["post"] = i + 1
                save("posten.json", lst)
                delen.append(f"{n - len(lst)} posten van {r['instelling']} ({g}) verwijderd")
            elif wat == "studie":
                lst = load("studies.json")
                n = len(lst)
                save("studies.json", [s for s in lst if not (s["gemeente"] == g and s["instelling"] == r["instelling"])])
                delen.append(f"{n - len(load('studies.json'))} studie van {r['instelling']} ({g}) verwijderd")
            elif wat == "vergelijking":
                lst = load("peers.json")
                n = len(lst)
                save("peers.json", [p for p in lst if not (p["gemeente"] == g and low(p["vergelijking"]) == low(r["vergelijking"]))])
                delen.append(f"{n - len(load('peers.json'))} vergelijking {r['vergelijking']} bij {g} verwijderd")
            elif wat == "regio":
                lst = load("regio.json")
                n = len(lst)
                save("regio.json", [x for x in lst if x["gemeente"] != g])
                delen.append(f"{n - len(load('regio.json'))} centrumregio van {g} verwijderd")
        return "; ".join(delen) + ".", []
    return None, [f"Onbekende soort {sid}."]


def main():
    files = sorted([p for p in IN.iterdir() if p.is_file() and p.suffix.lower() in (".xlsx", ".xlsm", ".csv")], key=lambda p: p.name)
    if not files:
        print("Geen nieuwe aanleveringen.")
        return 0
    log = load("log.json")
    gemeenten_known = {g["gemeente"] for g in load("gemeenten.json")}
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    afgewezen = 0
    for path in files:
        entry = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "bestand": path.name}
        try:
            aoa = read_table(path)
            sid = detect_soort(path, aoa[0] if aoa else [])
            if not sid:
                raise ValueError("Kon niet bepalen welke gegevens dit zijn. Begin de bestandsnaam met de soort, bijvoorbeeld subsidieposten-delft-2027.xlsx.")
            rows, issues = validate(sid, aoa)
            entry.update({"soort": sid, "soortNaam": SPEC[sid]["naam"], "rijen": len(rows),
                          "gemeenten": sorted({r.get("gemeente") for r in rows if r.get("gemeente")})})
            fouten = [f"rij {x['rij']}: {x['msg']}" if x["rij"] else x["msg"] for x in issues if x["lvl"] == "fout"]
            lets = [f"rij {x['rij']}: {x['msg']}" if x["rij"] else x["msg"] for x in issues if x["lvl"] == "let"]
            if not fouten:
                samenvatting, extra = apply(sid, rows, gemeenten_known)
                fouten += extra
            if fouten:
                entry.update({"status": "afgewezen", "samenvatting": f"{len(fouten)} fouten; niets gewijzigd.", "meldingen": fouten[:50]})
                doel = IN / "afgewezen"
                afgewezen += 1
            else:
                entry.update({"status": "verwerkt", "samenvatting": samenvatting, "meldingen": lets[:50]})
                doel = IN / "verwerkt"
        except Exception as e:  # noqa: BLE001
            entry.update({"status": "afgewezen", "samenvatting": "Bestand kon niet worden verwerkt.", "meldingen": [str(e)]})
            doel = IN / "afgewezen"
            afgewezen += 1
        doel.mkdir(exist_ok=True)
        shutil.move(str(path), str(doel / f"{stamp}-{path.name}"))
        log.append(entry)
        print(f"[{entry['status']}] {path.name}: {entry.get('samenvatting')}")
        for m in entry.get("meldingen", [])[:10]:
            print("   -", m)
    save("log.json", log[-500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
