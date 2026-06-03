"""
EU Grants Agent - prechádza výzvy na EC Funding Portal
a posiela email s relevantnými výsledkami Majke každý pondelok o 7:30.
"""

import requests
import json
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
    print("Sťahujem zoznam výziev z EC Funding Portal...")
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
            print(f"Chyba pri sťahovaní strana {strana}: {e}")
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
                link = f"https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{identifier}"
                vyzvy.append({
                    "nazov": str(nazov),
                    "identifier": str(identifier),
                    "status": str(status),
                    "deadline": str(deadline)[:10],
                    "programme": str(programme),
                    "link": link,
                })

        print(f"Strana {strana}: {len(polozky)} výziev (celkom {len(vyzvy)})")
        celkovo = data.get("total", data.get("totalElements", 0))
        if isinstance(celkovo, dict):
            celkovo = celkovo.get("value", 0)
        if len(vyzvy) >= int(celkovo or 0) or len(polozky) < na_stranku:
            break
        strana += 1
        time.sleep(1)

    print(f"Celkovo výziev: {len(vyzvy)}")
    return vyzvy


def ziskaj_detail_vyzvy(identifier):
    url = f"https://ec.europa.eu/info/funding-tenders/opportunities/data/topicMgmt/topics/{identifier}"
    try:
        resp = requests.get(url, timeout=30, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Nepodarilo sa načítať detail {identifier}: {e}")
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

    vety = [f"Výzva {identifier} – „{nazov}" je súčasťou programu {programme}."]
    if popis:
        popis_vety = re.split(r'(?<=[.!?])\s+', popis)
        for v in [x for x in popis_vety if len(x) > 30][:2]:
            vety.append(v[:300] + ("..." if len(v) > 300 else ""))
    if action_type:
        vety.append(f"Typ akcie: {action_type}.")
    if deadline:
        vety.append(f"Uzávierka: {deadline}.")
    if len(vety) < 3:
        vety.append("Výzva sa zameriava na inovatívne technológie v oblasti digitálnej transformácie a priemyslu.")

    return " ".join(vety[:6])


def posli_email(najdene_vyzvy):
    msg = MIMEMultipart("alternative")
    datum = datetime.now().strftime('%d.%m.%Y')
    msg["Subject"] = f"EU Granty {datum} – {'Nové výzvy nájdené!' if najdene_vyzvy else 'Žiadne nové výzvy'}"
    msg["From"] = EMAIL_ODOSIELATEL
    msg["To"] = EMAIL_PRIJEMCA

    if not najdene_vyzvy:
        text = "Prepáč Majka, nič som nenašiel.\n\nAgent prehľadal všetky aktuálne výzvy (Forthcoming + Open for submission) a žiadna neobsahovala relevantné kľúčové slová."
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">🇪🇺 EU Granty – Týždenný prehľad</h2>
        <p>Prepáč Majka, nič som nenašiel.</p>
        <p style="color:#666;">Agent prehľadal všetky aktuálne výzvy a žiadna neobsahovala relevantné kľúčové slová týkajúce sa Industry 4.0/5.0, AI alebo automatizácie.</p>
        </body></html>"""
    else:
        pocet = len(najdene_vyzvy)
        text_vyzvy = ""
        html_vyzvy = ""
        for i, v in enumerate(najdene_vyzvy, 1):
            text_vyzvy += f"\n{'='*60}\n{i}. {v['nazov']}\n\n{v['zhrnutie']}\n\nLink: {v['link']}\n"
            html_vyzvy += f"""
            <div style="border:1px solid #ddd;border-radius:8px;padding:20px;margin-bottom:20px;">
                <h3 style="color:#003399;margin-top:0;">{i}. {v['nazov']}</h3>
                <p style="color:#333;line-height:1.7;">{v['zhrnutie']}</p>
                <a href="{v['link']}" style="background:#003399;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;display:inline-block;margin-top:8px;">
                    🔗 Otvoriť výzvu
                </a>
                <p style="color:#999;font-size:12px;margin-top:12px;">
                    Kľúčové slovo: <strong>{v.get('klucove_slovo','')}</strong> &nbsp;|&nbsp;
                    Status: {v.get('status','')} &nbsp;|&nbsp; Deadline: {v.get('deadline','N/A')}
                </p>
            </div>"""

        text = f"Ahoj Majka!\n\nNašiel som {pocet} relevantné výzvy:\n{text_vyzvy}\nAgent EU Grantov"
        html = f"""<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">🇪🇺 EU Granty – Nové relevantné výzvy</h2>
        <p>Ahoj Majka! 👋 Našiel som <strong>{pocet}</strong> relevantné výzvy pre teba:</p>
        {html_vyzvy}
        <p style="color:#aaa;font-size:11px;border-top:1px solid #eee;padding-top:10px;margin-top:20px;">
            Automaticky vygenerované agentom EU Grantov • {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </p></body></html>"""

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    print(f"Posielam email na {EMAIL_PRIJEMCA}...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ODOSIELATEL, EMAIL_HESLO)
            smtp.sendmail(EMAIL_ODOSIELATEL, EMAIL_PRIJEMCA, msg.as_bytes())
        print("Email úspešne odoslaný!")
    except Exception as e:
        print(f"Chyba pri odosielaní emailu: {e}")


def main():
    print("=" * 60)
    print("EU GRANTS AGENT – Spustený")
    print(f"Dátum: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 60)

    vyzvy = ziskaj_vyzvy(max_stranok=20)
    if not vyzvy:
        print("Žiadne výzvy sa nepodarilo stiahnuť.")
        posli_email([])
        return

    najdene = []
    print(f"\nPrehľadávam {len(vyzvy)} výziev...")

    for idx, vyzva in enumerate(vyzvy, 1):
        print(f"[{idx}/{len(vyzvy)}] {vyzva['identifier'][:50]}...", end="", flush=True)
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
            print(f" NAJDENE: '{klucove_slovo}'")
            if not detail:
                detail = ziskaj_detail_vyzvy(vyzva["identifier"])
            zhrnutie = vytvor_zhrnutie(vyzva["nazov"], detail, vyzva["identifier"])
            najdene.append({**vyzva, "zhrnutie": zhrnutie, "klucove_slovo": klucove_slovo})
        else:
            print(" -")

    print(f"\nVýsledok: {len(najdene)} relevantných výziev z {len(vyzvy)}")
    posli_email(najdene)
    print("Agent dokončil prácu!")


if __name__ == "__main__":
    main()
