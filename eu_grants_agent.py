"""
EU Grants Agent - prechádza výzvy na EC Funding Portal
a posiela email s relevantnými výsledkami Majke každý pondelok o 7:30.
"""
 
import requests
import time
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
 
# ============================================================
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
# ============================================================
 
def ziskaj_vyzvy(max_stranok=20):
    print("Stahujem zoznam vyziev z EC Funding Portal...")
    vyzvy = []
    strana = 1
    na_stranku = 50
 
    while strana <= max_stranok:
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicMgmt/topics"
        params = {
            "status": "31094501,31094502",
            "order": "DESC",
            "pageNumber": strana,
            "pageSize": na_stranku,
            "sortBy": "startDate",
        }
        try:
            resp = requests.get(url, params=params, timeout=30, headers={"Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print("Chyba pri stahovani strana {}: {}".format(strana, e))
            break
 
        polozky = data.get("topics", data.get("results", []))
        if not polozky:
            break
 
        for p in polozky:
            identifier = p.get("identifier", p.get("id", ""))
            nazov = p.get("title", p.get("name", ""))
            if isinstance(nazov, list):
                nazov = nazov[0].get("value", "") if nazov else ""
            status = p.get("statusLabel", p.get("status", ""))
            deadline = p.get("deadlineDate", p.get("deadline", ""))
            if isinstance(deadline, list):
                deadline = deadline[0] if deadline else ""
            programme = p.get("programmeName", p.get("programme", ""))
            if isinstance(programme, list):
                programme = programme[0] if programme else ""
 
            if identifier:
                link = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{}".format(identifier)
                vyzvy.append({
                    "nazov": str(nazov),
                    "identifier": str(identifier),
                    "status": str(status),
                    "deadline": str(deadline)[:10],
                    "programme": str(programme),
                    "link": link,
                })
 
        print("Strana {}: {} vyziev (celkom {})".format(strana, len(polozky), len(vyzvy)))
        celkovo = data.get("total", data.get("totalElements", 0))
        if isinstance(celkovo, dict):
            celkovo = celkovo.get("value", 0)
        if len(vyzvy) >= int(celkovo or 0) or len(polozky) < na_stranku:
            break
        strana += 1
        time.sleep(1)
 
    print("Celkovo vyziev: {}".format(len(vyzvy)))
    return vyzvy
 
 
def ziskaj_detail_vyzvy(identifier):
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicMgmt/topics/{}".format(identifier)
    try:
        resp = requests.get(url, timeout=30, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("Nepodarilo sa nacitat detail {}: {}".format(identifier, e))
        return {}
 
 
def obsahuje_klucove_slovo(text):
    text_lower = text.lower()
    for slovo in KLUCOVE_SLOVA:
        if slovo in text_lower:
            return slovo
    return None
 
 
def vytvor_zhrnutie(nazov, detail, identifier):
    md = detail.get("metadata", detail)
    popis_raw = ""
    for kluc in ["topicDesc", "description", "objectives", "summary"]:
        val = md.get(kluc, "")
        if isinstance(val, list):
            val = " ".join([v.get("value", "") if isinstance(v, dict) else str(v) for v in val])
        if val:
            popis_raw = val
            break
 
    popis = re.sub(r"<[^>]+>", " ", popis_raw)
    popis = re.sub(r"\s+", " ", popis).strip()
 
    programme = md.get("programmeName", "Horizon Europe")
    if isinstance(programme, list):
        programme = programme[0] if programme else "Horizon Europe"
 
    deadline = str(md.get("deadlineDate", ""))[:10]
    if isinstance(md.get("deadlineDate"), list):
        deadline = str(md["deadlineDate"][0])[:10] if md["deadlineDate"] else ""
 
    action_type = md.get("typeOfAction", "")
    if isinstance(action_type, list):
        action_type = action_type[0] if action_type else ""
 
    vety = ["Vyzva {} - '{}' je sucastou programu {}.".format(identifier, nazov, programme)]
    if popis:
        popis_vety = re.split(r'(?<=[.!?])\s+', popis)
        for v in [x for x in popis_vety if len(x) > 30][:2]:
            vety.append(v[:300] + ("..." if len(v) > 300 else ""))
    if action_type:
        vety.append("Typ akcie: {}.".format(action_type))
    if deadline:
        vety.append("Uzavierka: {}.".format(deadline))
    if len(vety) < 3:
        vety.append("Vyzva sa zameriava na inovativne technologie v oblasti digitalnej transformacie a priemyslu.")
 
    return " ".join(vety[:6])
 
 
def posli_email(najdene_vyzvy):
    msg = MIMEMultipart("alternative")
    datum = datetime.now().strftime('%d.%m.%Y')
    if najdene_vyzvy:
        msg["Subject"] = "EU Granty {} - Nove vyzvy najdene!".format(datum)
    else:
        msg["Subject"] = "EU Granty {} - Ziadne nove vyzvy".format(datum)
    msg["From"] = EMAIL_ODOSIELATEL
    msg["To"] = EMAIL_PRIJEMCA
 
    if not najdene_vyzvy:
        text = "Prepac Majka, nic som nenasel.\n\nAgent prehliadal vsetky aktualne vyzvy (Forthcoming + Open for submission) a ziadna neobsahovala relevantne klucove slova."
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">EU Granty - Tyzdenny prehlad</h2>
        <p>Prepac Majka, nic som nenasel.</p>
        <p style="color:#666;">Agent prehliadal vsetky aktualne vyzvy a ziadna neobsahovala relevantne klucove slova tykajuce sa Industry 4.0/5.0, AI alebo automatizacie.</p>
        </body></html>"""
    else:
        pocet = len(najdene_vyzvy)
        text_vyzvy = ""
        html_vyzvy = ""
        for i, v in enumerate(najdene_vyzvy, 1):
            text_vyzvy += "\n{}\n{}. {}\n\n{}\n\nLink: {}\n".format("="*60, i, v['nazov'], v['zhrnutie'], v['link'])
            html_vyzvy += """
            <div style="border:1px solid #ddd;border-radius:8px;padding:20px;margin-bottom:20px;">
                <h3 style="color:#003399;margin-top:0;">{}. {}</h3>
                <p style="color:#333;line-height:1.7;">{}</p>
                <a href="{}" style="background:#003399;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;display:inline-block;margin-top:8px;">
                    Otvorit vyzvu
                </a>
                <p style="color:#999;font-size:12px;margin-top:12px;">
                    Klucove slovo: <strong>{}</strong> &nbsp;|&nbsp;
                    Status: {} &nbsp;|&nbsp; Deadline: {}
                </p>
            </div>""".format(i, v['nazov'], v['zhrnutie'], v['link'], v.get('klucove_slovo',''), v.get('status',''), v.get('deadline','N/A'))
 
        text = "Ahoj Majka!\n\nNasel som {} relevantne vyzvy:\n{}\nAgent EU Grantov".format(pocet, text_vyzvy)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">EU Granty - Nove relevantne vyzvy</h2>
        <p>Ahoj Majka! Nasel som <strong>{}</strong> relevantne vyzvy pre teba:</p>
        {}
        <p style="color:#aaa;font-size:11px;border-top:1px solid #eee;padding-top:10px;margin-top:20px;">
            Automaticky vygenerovane agentom EU Grantov - {}
        </p></body></html>""".format(pocet, html_vyzvy, datetime.now().strftime('%d.%m.%Y %H:%M'))
 
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
 
    print("Posielam email na {}...".format(EMAIL_PRIJEMCA))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ODOSIELATEL, EMAIL_HESLO)
            smtp.sendmail(EMAIL_ODOSIELATEL, EMAIL_PRIJEMCA, msg.as_bytes())
        print("Email uspesne odoslany!")
    except Exception as e:
        print("Chyba pri odosielani emailu: {}".format(e))
 
 
def main():
    print("=" * 60)
    print("EU GRANTS AGENT - Spusteny")
    print("Datum: {}".format(datetime.now().strftime('%d.%m.%Y %H:%M')))
    print("=" * 60)
 
    vyzvy = ziskaj_vyzvy(max_stranok=20)
    if not vyzvy:
        print("Ziadne vyzvy sa nepodarilo stiahnut.")
        posli_email([])
        return
 
    najdene = []
    print("\nPrehliadam {} vyziev...".format(len(vyzvy)))
 
    for idx, vyzva in enumerate(vyzvy, 1):
        print("[{}/{}] {}...".format(idx, len(vyzvy), vyzva['identifier'][:50]), end="", flush=True)
        klucove_slovo = obsahuje_klucove_slovo(vyzva["nazov"])
        detail = {}
 
        if not klucove_slovo:
            detail = ziskaj_detail_vyzvy(vyzva["identifier"])
            popis = ""
            md = detail.get("metadata", detail)
            for kluc in ["topicDesc", "description", "objectives", "summary"]:
                val = md.get(kluc, "")
                if isinstance(val, list):
                    val = " ".join([v.get("value", "") if isinstance(v, dict) else str(v) for v in val])
                if val:
                    popis += " " + val
            klucove_slovo = obsahuje_klucove_slovo(popis)
            time.sleep(0.5)
 
        if klucove_slovo:
            print(" NAJDENE: '{}'".format(klucove_slovo))
            if not detail:
                detail = ziskaj_detail_vyzvy(vyzva["identifier"])
            zhrnutie = vytvor_zhrnutie(vyzva["nazov"], detail, vyzva["identifier"])
            najdene.append({**vyzva, "zhrnutie": zhrnutie, "klucove_slovo": klucove_slovo})
        else:
            print(" -")
 
    print("\nVysledok: {} relevantnych vyziev z {}".format(len(najdene), len(vyzvy)))
    posli_email(najdene)
    print("Agent dokoncil pracu!")
 
