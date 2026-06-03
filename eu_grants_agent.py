import requests
import time
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

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

def obsahuje_klucove_slovo(text):
    text_lower = text.lower()
    for slovo in KLUCOVE_SLOVA:
        if slovo in text_lower:
            return slovo
    return None

def ziskaj_vyzvy():
    print("Stahujem zoznam vyziev cez EC Search API...")
    vyzvy = []
    strana = 1
    na_stranku = 50

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    while True:
        # Oficialny EC Search API endpoint
        url = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
        params = {
            "apiKey": "PGENMD98pp",
            "text": "*",
            "pageSize": na_stranku,
            "pageNumber": strana,
            "sortBy": "startDate",
            "order": "DESC",
        }

        # Pridame filter na status ako query parameter
        query = {
            "bool": {
                "must": [
                    {"terms": {"status": ["31094501", "31094502"]}}
                ]
            }
        }

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            print("API status: {}".format(resp.status_code))

            if resp.status_code != 200:
                print("Skusam alternativny endpoint...")
                break

            data = resp.json()
            polozky = data.get("results", [])
            celkovo = data.get("total", {})
            if isinstance(celkovo, dict):
                celkovo = celkovo.get("value", 0)

            print("Strana {}: najdenych {} poloziek z celkovo {}".format(strana, len(polozky), celkovo))

            for p in polozky:
                md = p.get("metadata", {})

                # Ziskaj identifier
                identifier = md.get("identifier", [""])
                if isinstance(identifier, list):
                    identifier = identifier[0] if identifier else ""
                identifier = str(identifier)

                # Ziskaj nazov
                nazov = md.get("title", [""])
                if isinstance(nazov, list):
                    nazov = nazov[0].get("value", "") if nazov and isinstance(nazov[0], dict) else (nazov[0] if nazov else "")
                nazov = str(nazov)

                # Ziskaj status
                status = md.get("statusLabel", [""])
                if isinstance(status, list):
                    status = status[0] if status else ""
                status = str(status)

                # Filter - chceme len Forthcoming a Open
                if status not in ["Forthcoming", "Open for submission"]:
                    continue

                # Ziskaj deadline
                deadline = md.get("deadlineDate", [""])
                if isinstance(deadline, list):
                    deadline = deadline[0] if deadline else ""
                deadline = str(deadline)[:10]

                # Ziskaj programme
                programme = md.get("programmeName", [""])
                if isinstance(programme, list):
                    programme = programme[0] if programme else ""
                programme = str(programme)

                if identifier:
                    link = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{}".format(identifier)
                    vyzvy.append({
                        "nazov": nazov,
                        "identifier": identifier,
                        "status": status,
                        "deadline": deadline,
                        "programme": programme,
                        "link": link,
                    })

            if len(polozky) < na_stranku or len(vyzvy) >= int(celkovo or 0):
                break

            strana += 1
            time.sleep(0.5)

        except Exception as e:
            print("Chyba pri API: {}".format(e))
            break

    # Ak API nevratilo nic, skus priamy endpoint
    if not vyzvy:
        print("Skusam priamy EC topics endpoint...")
        vyzvy = ziskaj_vyzvy_priamo()

    print("Celkovo vyziev na spracovanie: {}".format(len(vyzvy)))
    return vyzvy


def ziskaj_vyzvy_priamo():
    """Zalohy endpoint - priamy EC API"""
    vyzvy = []
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

    for strana in range(1, 21):
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicMgmt/topics"
        params = {
            "status": "31094501,31094502",
            "pageNumber": strana,
            "pageSize": 50,
            "sortBy": "startDate",
            "order": "DESC",
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            print("Priamy API strana {}: status {}".format(strana, resp.status_code))
            data = resp.json()

            # Skus rozne kluce
            polozky = (data.get("fundingOpportunities", {}).get("fundingOpportunity", []) or
                      data.get("topics", []) or
                      data.get("results", []) or
                      data.get("items", []))

            if not polozky:
                print("Obsah odpovede: {}".format(str(data)[:300]))
                break

            for p in polozky:
                identifier = str(p.get("identifier", p.get("id", p.get("topicId", ""))))
                nazov = p.get("title", p.get("name", p.get("topicTitle", "")))
                if isinstance(nazov, dict):
                    nazov = nazov.get("value", "")
                nazov = str(nazov)
                status = str(p.get("statusLabel", p.get("status", "")))
                deadline = str(p.get("deadlineDate", p.get("deadline", "")))[:10]
                programme = str(p.get("programmeName", p.get("programme", "")))

                if identifier:
                    link = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{}".format(identifier)
                    vyzvy.append({
                        "nazov": nazov,
                        "identifier": identifier,
                        "status": status,
                        "deadline": deadline,
                        "programme": programme,
                        "link": link,
                    })

            print("  Najdenych {} vyziev (celkom {})".format(len(polozky), len(vyzvy)))

            celkovo = data.get("total", data.get("totalElements", data.get("count", 0)))
            if isinstance(celkovo, dict):
                celkovo = celkovo.get("value", 0)
            if len(vyzvy) >= int(celkovo or 0) or len(polozky) < 50:
                break

            time.sleep(0.5)

        except Exception as e:
            print("Chyba priamy endpoint strana {}: {}".format(strana, e))
            break

    return vyzvy


def ziskaj_detail_vyzvy(identifier):
    """Stiahne detail konkretnej vyzvy"""
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicMgmt/topics/{}".format(identifier)
    try:
        resp = requests.get(url, timeout=30,
                           headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print("  Chyba detail {}: {}".format(identifier, e))
    return {}


def vytvor_zhrnutie(nazov, detail, identifier):
    md = detail.get("metadata", detail)

    popis_raw = ""
    for kluc in ["topicDesc", "description", "objectives", "summary", "expectedOutcome"]:
        val = md.get(kluc, "")
        if isinstance(val, list):
            val = " ".join([v.get("value", "") if isinstance(v, dict) else str(v) for v in val])
        if val and len(str(val)) > 50:
            popis_raw = str(val)
            break

    popis = re.sub(r"<[^>]+>", " ", popis_raw)
    popis = re.sub(r"\s+", " ", popis).strip()

    programme = md.get("programmeName", "Horizon Europe")
    if isinstance(programme, list):
        programme = programme[0] if programme else "Horizon Europe"

    deadline = str(md.get("deadlineDate", ""))[:10]
    if isinstance(md.get("deadlineDate"), list):
        l = md["deadlineDate"]
        deadline = str(l[0])[:10] if l else ""

    action_type = md.get("typeOfAction", "")
    if isinstance(action_type, list):
        action_type = action_type[0] if action_type else ""

    vety = ["Vyzva {} - '{}' je sucastou programu {}.".format(identifier, nazov[:120], programme)]

    if popis:
        popis_vety = re.split(r'(?<=[.!?])\s+', popis)
        relevantne = [v for v in popis_vety if len(v) > 40][:2]
        for v in relevantne:
            vety.append(v[:350] + ("..." if len(v) > 350 else ""))

    if action_type:
        vety.append("Typ akcie: {}.".format(action_type))
    if deadline:
        vety.append("Uzavierka podavania ziadosti: {}.".format(deadline))
    if len(vety) < 3:
        vety.append("Vyzva sa zameriava na inovativne technologie v oblasti digitalnej transformacie, AI a priemyslu.")

    return " ".join(vety[:6])


def posli_email(najdene_vyzvy, celkovo_vyziev):
    msg = MIMEMultipart("alternative")
    datum = datetime.now().strftime('%d.%m.%Y')
    if najdene_vyzvy:
        msg["Subject"] = "EU Granty {} - {} relevantnych vyziev!".format(datum, len(najdene_vyzvy))
    else:
        msg["Subject"] = "EU Granty {} - Ziadne nove vyzvy".format(datum)
    msg["From"] = EMAIL_ODOSIELATEL
    msg["To"] = EMAIL_PRIJEMCA

    if not najdene_vyzvy:
        text = "Prepac Majka, nic som nenasel.\n\nPrehliadol som {} vyziev (Forthcoming + Open for submission) a ziadna neobsahovala relevantne klucove slova (Industry 4.0/5.0, AI, automatizacia...).".format(celkovo_vyziev)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">EU Granty - Tyzdenny prehlad</h2>
        <p>Prepac Majka, nic som nenasel.</p>
        <p style="color:#666;">Prehliadol som <strong>{}</strong> vyziev (Forthcoming + Open for submission) a ziadna neobsahovala relevantne klucove slova tykajuce sa Industry 4.0/5.0, AI alebo automatizacie.</p>
        </body></html>""".format(celkovo_vyziev)
    else:
        pocet = len(najdene_vyzvy)
        text_vyzvy = ""
        html_vyzvy = ""
        for i, v in enumerate(najdene_vyzvy, 1):
            text_vyzvy += "\n{}\n{}. {}\n\n{}\n\nLink: {}\n".format(
                "="*60, i, v['nazov'], v['zhrnutie'], v['link'])
            html_vyzvy += """
            <div style="border:1px solid #ddd;border-radius:8px;padding:20px;margin-bottom:20px;background:#fafafa;">
                <h3 style="color:#003399;margin-top:0;">{}. {}</h3>
                <p style="color:#333;line-height:1.7;">{}</p>
                <a href="{}" style="background:#003399;color:white;padding:10px 20px;
                   text-decoration:none;border-radius:5px;display:inline-block;margin-top:8px;font-weight:bold;">
                   Otvorit vyzvu &rarr;
                </a>
                <p style="color:#999;font-size:12px;margin-top:12px;">
                    Klucove slovo: <strong>{}</strong> &nbsp;|&nbsp;
                    Status: {} &nbsp;|&nbsp; Deadline: {}
                </p>
            </div>""".format(
                i, v['nazov'], v['zhrnutie'], v['link'],
                v.get('klucove_slovo',''), v.get('status',''), v.get('deadline','N/A'))

        text = "Ahoj Majka!\n\nNasel som {} relevantnych vyziev z {} prehliadanych:\n{}\nAgent EU Grantov".format(
            pocet, celkovo_vyziev, text_vyzvy)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">EU Granty - Nove relevantne vyzvy</h2>
        <p>Ahoj Majka! Nasel som <strong>{}</strong> relevantnych vyziev z {} prehliadanych:</p>
        {}
        <p style="color:#aaa;font-size:11px;border-top:1px solid #eee;padding-top:10px;margin-top:20px;">
            Automaticky vygenerovane agentom EU Grantov - {}
        </p></body></html>""".format(pocet, celkovo_vyziev, html_vyzvy, datetime.now().strftime('%d.%m.%Y %H:%M'))

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    print("Posielam email na {}...".format(EMAIL_PRIJEMCA))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ODOSIELATEL, EMAIL_HESLO)
            smtp.sendmail(EMAIL_ODOSIELATEL, EMAIL_PRIJEMCA, msg.as_bytes())
        print("Email uspesne odoslany!")
    except Exception as e:
        print("CHYBA pri odosielani emailu: {}".format(e))


def main():
    print("=" * 60)
    print("EU GRANTS AGENT - Spusteny")
    print("Datum: {}".format(datetime.now().strftime('%d.%m.%Y %H:%M')))
    print("=" * 60)

    vyzvy = ziskaj_vyzvy()

    if not vyzvy:
        print("Ziadne vyzvy sa nepodarilo stiahnut.")
        posli_email([], 0)
        return

    najdene = []
    print("\nPrehlidam {} vyziev...".format(len(vyzvy)))

    for idx, vyzva in enumerate(vyzvy, 1):
        print("[{}/{}] {}...".format(idx, len(vyzvy), vyzva['identifier'][:40]), end="", flush=True)

        # Skontroluj nazov
        klucove_slovo = obsahuje_klucove_slovo(vyzva["nazov"])
        detail = {}

        # Ak nie je v nazve, stiahni detail a skontroluj popis
        if not klucove_slovo:
            detail = ziskaj_detail_vyzvy(vyzva["identifier"])
            popis = ""
            md = detail.get("metadata", detail)
            for kluc in ["topicDesc", "description", "objectives", "summary", "expectedOutcome"]:
                val = md.get(kluc, "")
                if isinstance(val, list):
                    val = " ".join([v.get("value", "") if isinstance(v, dict) else str(v) for v in val])
                if val:
                    popis += " " + str(val)
            klucove_slovo = obsahuje_klucove_slovo(popis)
            time.sleep(0.3)

        if klucove_slovo:
            print(" NAJDENE: '{}'".format(klucove_slovo))
            if not detail:
                detail = ziskaj_detail_vyzvy(vyzva["identifier"])
            zhrnutie = vytvor_zhrnutie(vyzva["nazov"], detail, vyzva["identifier"])
            najdene.append({**vyzva, "zhrnutie": zhrnutie, "klucove_slovo": klucove_slovo})
        else:
            print(" -")

    print("\nVysledok: {} relevantnych vyziev z {}".format(len(najdene), len(vyzvy)))
    posli_email(najdene, len(vyzvy))
    print("Agent dokoncil pracu!")


if __name__ == "__main__":
    main()
