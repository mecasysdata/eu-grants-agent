"""
EU Grants Agent - OPRAVENA VERZIA
Hlavna oprava: odstraneny filter podla roku v identifikatore,
filtrovanie prebieha podla deadline datumu (je_aktualna()).
"""

import requests
import time
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# === KONFIG ===
EMAIL_ODOSIELATEL = "mecasysdata@gmail.com"
EMAIL_HESLO       = "jeze ycaa dpty cvll"
EMAIL_PRIJEMCA    = "maria.genzorova@mecasys.sk"

KLUCOVE_SLOVA = [
    "industry 4.0", "industry 5.0", "advanced manufacturing",
    "artificial intelligence", "machine learning", "automation",
    "automatization", "digital transformation", "smart factory",
    "cyber-physical", "internet of things", "iot", "robotics",
    "deep tech", "digitalization", "digitisation", "advanced technology",
    "emerging technology", "ai-driven", "ai-powered", "autonomous systems",
    "data-driven", "predictive", "smart manufacturing",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
}
# ==============

def obsahuje_klucove_slovo(text):
    t = text.lower()
    for slovo in KLUCOVE_SLOVA:
        if slovo in t:
            return slovo
    return None

def ziskaj_identifikatory():
    """
    Stiahne vsetky identifikatory z topic-list.html.
    OPRAVA: ziadny filter podla roku v nazve identifikatora —
    ten filter predhadzal takmer vsetky vyzvy (zostali len 4 z 7618).
    Filtrovanie podla aktualnosti prebehne neskor cez je_aktualna().
    """
    print("Stahujem topic-list.html...")
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topic-list.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        vsetky = re.findall(r'topic-details/([a-zA-Z0-9_\-\.]+)', resp.text)
        vsetky = list(dict.fromkeys(vsetky))  # deduplikacia, zachova poradie
        print("Celkom identifikatorov: {}".format(len(vsetky)))
        return vsetky
    except Exception as e:
        print("CHYBA topic-list: {}".format(e))
        return []

def ziskaj_detail(identifier):
    """
    Stiahne JSON detail pre dany identifikator.
    Identifikator musi byt lowercase — API to vyzaduje.
    """
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/{}.json".format(
        identifier.lower()
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def parsuj_vyzvu(detail, identifier):
    td = detail.get("TopicDetails", detail)
    nazov = td.get("title", "")

    fp = td.get("frameworkProgramme", {})
    programme = fp.get("description", "") if isinstance(fp, dict) else str(fp)

    # Status a deadline z actions[]
    status = ""
    deadline_str = ""
    deadline_ts = 0
    actions = td.get("actions", [])
    if actions:
        a = actions[0]
        s = a.get("status", {})
        if isinstance(s, dict):
            status = s.get("abbreviation", "")

        # OPRAVA: robustnejsie parsovanie deadline — dates[0] moze byt
        # integer alebo string, a moze byt None / "null"
        dates = a.get("deadlineDates", [])
        if dates and dates[0] is not None:
            try:
                deadline_ts = int(str(dates[0])) / 1000
                deadline_str = datetime.utcfromtimestamp(deadline_ts).strftime("%d.%m.%Y")
            except (ValueError, TypeError, OSError):
                deadline_str = str(dates[0])[:10]
                deadline_ts = 0

    # Popis — ocistit od HTML tagov
    popis_raw = td.get("description", "")
    popis = re.sub(r"<[^>]+>", " ", popis_raw)
    popis = re.sub(r"\s+", " ", popis).strip()

    keywords = " ".join(td.get("keywords", []))
    tags = " ".join(td.get("tags", []))

    return {
        "identifier": identifier,
        "nazov": nazov,
        "programme": programme,
        "status": status,
        "deadline_str": deadline_str,
        "deadline_ts": deadline_ts,
        "popis": popis,
        "fulltext": nazov + " " + popis + " " + keywords + " " + tags,
    }

def je_aktualna(vyzva):
    """
    Vrati True ak vyzva je otvorena alebo pripravovana.
    Toto je jediny spravny sposob filtrovania — podla deadline datumu,
    nie podla roku v identifikatore.
    """
    now_ts = datetime.now(timezone.utc).timestamp()

    if vyzva["status"] == "Forthcoming":
        return True

    if vyzva["status"] == "Open" and vyzva["deadline_ts"] > now_ts:
        return True

    # Fallback: deadline v buducnosti bez ohladu na status string
    if vyzva["deadline_ts"] > now_ts:
        return True

    return False

def vytvor_zhrnutie(v):
    vety = []
    vety.append("Vyzva '{}' ({}) je sucastou programu {}.".format(
        v["nazov"][:100], v["identifier"], v["programme"] or "Horizon Europe"))

    if v["popis"]:
        popis_vety = re.split(r'(?<=[.!?])\s+', v["popis"])
        relevantne = [s for s in popis_vety if len(s) > 40][:3]
        for s in relevantne:
            vety.append(s[:300] + ("..." if len(s) > 300 else ""))

    if v["deadline_str"]:
        vety.append("Uzavierka podavania ziadosti: {}.".format(v["deadline_str"]))

    if len(vety) < 3:
        vety.append("Vyzva sa zameriava na inovativne technologie v oblasti AI a digitalnej transformacie.")

    return " ".join(vety[:6])

def posli_email(najdene, celkovo_aktualnych, celkovo_spracovanych):
    msg = MIMEMultipart("alternative")
    datum = datetime.now().strftime("%d.%m.%Y")

    if najdene:
        msg["Subject"] = "EU Granty {} - {} relevantnych vyziev!".format(datum, len(najdene))
    else:
        msg["Subject"] = "EU Granty {} - Ziadne relevantne vyzvy".format(datum)
    msg["From"] = EMAIL_ODOSIELATEL
    msg["To"]   = EMAIL_PRIJEMCA

    if not najdene:
        text = (
            "Prepac Majka, nic som nenasel.\n\n"
            "Spracoval som {} identifikatorov, z toho {} aktualnych vyziev "
            "(deadline v buducnosti alebo Forthcoming) "
            "a ziadna neobsahovala relevantne klucove slova "
            "(Industry 4.0/5.0, AI, automatizacia...)."
        ).format(celkovo_spracovanych, celkovo_aktualnych)

        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
<h2 style="color:#003399;">EU Granty - Tyzdenny prehlad</h2>
<p>Prepac Majka, nic som nenasel.</p>
<p style="color:#555;">
  Spracoval som <strong>{sprac}</strong> identifikatorov,
  z toho <strong>{akt}</strong> aktualnych vyziev (deadline v buducnosti).<br>
  Ziadna neobsahovala relevantne klucove slova tykajuce sa Industry 4.0/5.0,
  AI alebo automatizacie.
</p>
</body></html>""".format(sprac=celkovo_spracovanych, akt=celkovo_aktualnych)

    else:
        pocet = len(najdene)
        bloky_text = ""
        bloky_html = ""

        for i, v in enumerate(najdene, 1):
            link = (
                "https://ec.europa.eu/info/funding-tenders/opportunities/portal/"
                "screen/opportunities/topic-details/{}".format(v["identifier"])
            )
            bloky_text += "\n{sep}\n{i}. {nazov}\n\n{zhrnutie}\n\nLink: {link}\n".format(
                sep="=" * 60, i=i, nazov=v["nazov"],
                zhrnutie=v["zhrnutie"], link=link
            )
            bloky_html += """
<div style="border:1px solid #ddd;border-radius:8px;padding:20px;
            margin-bottom:20px;background:#fafafa;">
  <h3 style="color:#003399;margin-top:0;">{i}. {nazov}</h3>
  <p style="color:#333;line-height:1.7;">{zhrnutie}</p>
  <a href="{link}"
     style="background:#003399;color:white;padding:10px 20px;
            text-decoration:none;border-radius:5px;
            display:inline-block;margin-top:8px;font-weight:bold;">
     Otvorit vyzvu &rarr;
  </a>
  <p style="color:#999;font-size:12px;margin-top:12px;">
    Klucove slovo: <strong>{kw}</strong> &nbsp;|&nbsp;
    Status: {status} &nbsp;|&nbsp; Deadline: {deadline}
  </p>
</div>""".format(
                i=i, nazov=v["nazov"], zhrnutie=v["zhrnutie"],
                link=link, kw=v["klucove_slovo"],
                status=v["status"], deadline=v.get("deadline_str", "N/A")
            )

        text = (
            "Ahoj Majka!\n\n"
            "Nasel som {} relevantnych vyziev z {} aktualnych "
            "(spracovanych celkovo {}):\n{}\nAgent EU Grantov"
        ).format(pocet, celkovo_aktualnych, celkovo_spracovanych, bloky_text)

        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
<h2 style="color:#003399;">EU Granty - Nove relevantne vyzvy</h2>
<p>Ahoj Majka! Nasel som <strong>{pocet}</strong> relevantnych vyziev
   z {celkovo} aktualnych (spracovanych {sprac}):</p>
{bloky}
<p style="color:#aaa;font-size:11px;border-top:1px solid #eee;
          padding-top:10px;margin-top:20px;">
  Automaticky vygenerovane agentom EU Grantov - {datum}
</p>
</body></html>""".format(
            pocet=pocet, celkovo=celkovo_aktualnych,
            sprac=celkovo_spracovanych,
            bloky=bloky_html,
            datum=datetime.now().strftime("%d.%m.%Y %H:%M")
        )

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    print("Posielam email na {}...".format(EMAIL_PRIJEMCA))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ODOSIELATEL, EMAIL_HESLO)
            smtp.sendmail(EMAIL_ODOSIELATEL, EMAIL_PRIJEMCA, msg.as_bytes())
        print("Email odoslany!")
    except Exception as e:
        print("CHYBA email: {}".format(e))

def main():
    print("=" * 60)
    print("EU GRANTS AGENT - OPRAVENA VERZIA")
    print("Start: {}".format(datetime.now().strftime("%d.%m.%Y %H:%M")))
    print("=" * 60)

    identifikatory = ziskaj_identifikatory()
    if not identifikatory:
        print("Ziadne identifikatory - koniec.")
        posli_email([], 0, 0)
        return

    najdene = []
    aktualnych = 0
    chyby = 0
    spracovanych = 0
    start_time = time.time()
    LIMIT_SEKUND = 45 * 60  # 45 minut

    print("Spracovavam {} identifikatorov...".format(len(identifikatory)))
    print("(Filtrovanie prebieha podla deadline datumu, nie podla roku v nazve)\n")

    for idx, ident in enumerate(identifikatory, 1):

        if time.time() - start_time > LIMIT_SEKUND:
            print("\nCasovy limit 45 min - posielam co mame ({}/{})".format(
                idx, len(identifikatory)))
            break

        print("[{}/{}] {}".format(idx, len(identifikatory), ident[:50]),
              end=" ", flush=True)

        detail = ziskaj_detail(ident)
        if detail is None:
            chyby += 1
            print("(404/chyba)")
            time.sleep(0.1)
            continue

        spracovanych += 1
        vyzva = parsuj_vyzvu(detail, ident)

        if not je_aktualna(vyzva):
            print("-> {} deadline: {}".format(
                vyzva["status"] or "uzavreta", vyzva["deadline_str"] or "N/A"))
            time.sleep(0.1)
            continue

        aktualnych += 1
        kw = obsahuje_klucove_slovo(vyzva["fulltext"])

        if kw:
            print("-> *** NAJDENE '{}' | deadline: {} ***".format(
                kw, vyzva["deadline_str"]))
            vyzva["klucove_slovo"] = kw
            vyzva["zhrnutie"] = vytvor_zhrnutie(vyzva)
            najdene.append(vyzva)
        else:
            print("-> Aktualna, bez zhody kw | deadline: {}".format(
                vyzva["deadline_str"]))

        time.sleep(0.15)

    print("\n" + "=" * 60)
    print("Spracovanych:    {}".format(spracovanych))
    print("Aktualnych:      {}".format(aktualnych))
    print("Relevantnych:    {}".format(len(najdene)))
    print("Chyby/404:       {}".format(chyby))
    print("=" * 60)

    posli_email(najdene, aktualnych, spracovanych)
    print("Hotovo! {}".format(datetime.now().strftime("%d.%m.%Y %H:%M")))

if __name__ == "__main__":
    main()
