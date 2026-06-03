"""
EU Grants Agent
- Stiahne zoznam vyziev z EC Funding Portal (topic-list.html)
- Filtruje len 2025/2026/2027 identifikatory
- Pre kazdu stiahne JSON detail
- Skontroluje ci deadline je v buducnosti (= skutocne otvorena/forthcoming)
- Hlada klucove slova v nazve + popise + keywords
- Posle email Majke s vysledkami
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

AKTUALNE_ROKY = ["2025", "2026", "2027"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"}
# ==============

def obsahuje_klucove_slovo(text):
    t = text.lower()
    for slovo in KLUCOVE_SLOVA:
        if slovo in t:
            return slovo
    return None

def ziskaj_identifikatory():
    print("Stahujem topic-list.html...")
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topic-list.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        vsetky = re.findall(r'topic-details/([a-zA-Z0-9_\-\.]+)', resp.text)
        vsetky = list(dict.fromkeys(vsetky))
        aktualne = [i for i in vsetky if any(rok in i for rok in AKTUALNE_ROKY)]
        print("Celkom: {} | Po filtri 2025-2027: {}".format(len(vsetky), len(aktualne)))
        return aktualne
    except Exception as e:
        print("CHYBA topic-list: {}".format(e))
        return []

def ziskaj_detail(identifier):
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/{}.json".format(
        identifier.lower())
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except:
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
        dates = a.get("deadlineDates", [])
        if dates:
            try:
                deadline_ts = int(str(dates[0])) / 1000
                deadline_str = datetime.utcfromtimestamp(deadline_ts).strftime("%d.%m.%Y")
            except:
                deadline_str = str(dates[0])[:10]

    # Popis
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
    """Vrati True ak vyzva ma deadline v buducnosti ALEBO status Forthcoming"""
    now_ts = datetime.now(timezone.utc).timestamp()

    # Forthcoming - este neotvorena ale bude
    if vyzva["status"] == "Forthcoming":
        return True

    # Open - otvorena a deadline este nenastal
    if vyzva["status"] == "Open" and vyzva["deadline_ts"] > now_ts:
        return True

    # Fallback: ak deadline je v buducnosti bez ohladu na status
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

def posli_email(najdene, celkovo_aktualnych):
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
            "Prehliadol som {} aktualne vyziev (deadline v buducnosti) "
            "a ziadna neobsahovala relevantne klucove slova "
            "(Industry 4.0/5.0, AI, automatizacia...)."
        ).format(celkovo_aktualnych)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
<h2 style="color:#003399;">EU Granty - Tyzdenny prehlad</h2>
<p>Prepac Majka, nic som nenasel.</p>
<p style="color:#555;">Prehliadol som <strong>{}</strong> aktualnych vyziev (s deadlinom v buducnosti)
a ziadna neobsahovala relevantne klucove slova tykajuce sa Industry 4.0/5.0,
AI alebo automatizacie.</p>
</body></html>""".format(celkovo_aktualnych)

    else:
        pocet = len(najdene)
        bloky_text = ""
        bloky_html = ""

        for i, v in enumerate(najdene, 1):
            link = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{}".format(
                v["identifier"])
            bloky_text += "\n{sep}\n{i}. {nazov}\n\n{zhrnutie}\n\nLink: {link}\n".format(
                sep="="*60, i=i, nazov=v["nazov"],
                zhrnutie=v["zhrnutie"], link=link)
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
</div>""".format(i=i, nazov=v["nazov"], zhrnutie=v["zhrnutie"],
                 link=link, kw=v["klucove_slovo"],
                 status=v["status"], deadline=v.get("deadline_str","N/A"))

        text = "Ahoj Majka!\n\nNasel som {} relevantnych vyziev z {} aktualnych:\n{}\nAgent EU Grantov".format(
            pocet, celkovo_aktualnych, bloky_text)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
<h2 style="color:#003399;">EU Granty - Nove relevantne vyzvy</h2>
<p>Ahoj Majka! Nasel som <strong>{pocet}</strong> relevantnych vyziev z {celkovo} aktualnych:</p>
{bloky}
<p style="color:#aaa;font-size:11px;border-top:1px solid #eee;
          padding-top:10px;margin-top:20px;">
  Automaticky vygenerovane agentom EU Grantov - {datum}
</p>
</body></html>""".format(pocet=pocet, celkovo=celkovo_aktualnych,
                         bloky=bloky_html,
                         datum=datetime.now().strftime("%d.%m.%Y %H:%M"))

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
    print("EU GRANTS AGENT")
    print("Start: {}".format(datetime.now().strftime("%d.%m.%Y %H:%M")))
    print("=" * 60)

    identifikatory = ziskaj_identifikatory()
    if not identifikatory:
        print("Ziadne identifikatory - koniec.")
        posli_email([], 0)
        return

    najdene = []
    aktualnych = 0
    chyby = 0
    start_time = time.time()
    LIMIT_SEKUND = 45 * 60  # 45 minut - bezpecnostny limit

    print("Spracovavam {} identifikatorov...".format(len(identifikatory)))

    for idx, ident in enumerate(identifikatory, 1):

        # Bezpecnostny timeout
        if time.time() - start_time > LIMIT_SEKUND:
            print("\nCasovy limit - posielam co mame ({}/{})".format(idx, len(identifikatory)))
            break

        print("[{}/{}] {}".format(idx, len(identifikatory), ident[:50]), end=" ", flush=True)

        detail = ziskaj_detail(ident)
        if detail is None:
            chyby += 1
            print("(404)")
            time.sleep(0.1)
            continue

        vyzva = parsuj_vyzvu(detail, ident)

        # Klucovy filter: chceme len vyzvy s deadlinom v buducnosti
        if not je_aktualna(vyzva):
            print("-> {} deadline: {}".format(vyzva["status"] or "?", vyzva["deadline_str"] or "N/A"))
            time.sleep(0.1)
            continue

        aktualnych += 1
        kw = obsahuje_klucove_slovo(vyzva["fulltext"])

        if kw:
            print("-> NAJDENE '{}' | deadline: {}".format(kw, vyzva["deadline_str"]))
            vyzva["klucove_slovo"] = kw
            vyzva["zhrnutie"] = vytvor_zhrnutie(vyzva)
            najdene.append(vyzva)
        else:
            print("-> Aktualna, bez zhody | deadline: {}".format(vyzva["deadline_str"]))

        time.sleep(0.15)

    print("\n" + "=" * 60)
    print("Aktualnych vyziev: {} | Relevantnych: {} | Chyby/404: {}".format(
        aktualnych, len(najdene), chyby))
    print("=" * 60)

    posli_email(najdene, aktualnych)
    print("Hotovo! {}".format(datetime.now().strftime("%d.%m.%Y %H:%M")))

if __name__ == "__main__":
    main()
