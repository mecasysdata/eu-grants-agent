"""
EU Grants Agent - FINALNA VERZIA v7
Mecasys koncern — 3 oblasti:
  1. Strojárska výroba / Industry 4.0
  2. Agro/Bio divízia
  3. Obrana + špeciálne aplikácie
"""

import requests
import re
import smtplib
import time
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

# === KONFIG ===
EMAIL_ODOSIELATEL = "mecasysdata@gmail.com"
EMAIL_HESLO       = "jeze ycaa dpty cvll"
EMAIL_PRIJEMCA    = "maria.genzorova@mecasys.sk"

# === SME DETEKCIA ===
SME_KLUCOVE_SLOVA = [
    "sme", "small and medium", "small enterprise", "medium enterprise",
    "smes", "sme instrument", "eic accelerator", "sme support"
]

# === SAFE GET ===
def safe_get(meta, key):
    lst = meta.get(key, [])
    return (lst[0] if lst else "") or ""

# === 3 OBLASTI S KLUCOVYMI SLOVAMI ===
OBLASTI = {
    "🏭 Strojárstvo / Industry 4.0": [
        "industry 4.0", "industry 5.0", "advanced manufacturing",
        "smart factory", "smart manufacturing", "factory automation",
        "industrial automation", "process automation", "digital twin",
        "cyber-physical", "industrial digitalisation", "industrial digitalization",
        "industrial ai", "manufacturing process", "production process",
        "additive manufacturing", "3d printing", "human-robot", "industrial hub",
        "cobots", "cobot", "made in europe", "factory of the future",
        "industrial iot", "iiot", "new approaches for human/ai collaboration",
        "factory processes and automation", "advanced manufacturing for key products",
        "testing", "assembly", "prototype",
    ],

    "🌱 Agro / Bio / Circular": [
        "mycelium", "mycorrhiz", "bioplastic", "polyhydroxyalkanoate",
        "controlled environment agriculture", "vertical farming",
        "precision agriculture", "smart farming", "agri-tech", "agritech",
        "bio-based", "biobased", "circular bio", "bioeconomy", "bio-economy",
        "plant growth", "horticulture", "soil health", "microbiome",
        "biodegradable", "biomaterial", "fermentation", "biotechnology for",
        "sustainable packaging", "circular packaging", "bio-based textile",
        "bioremediation", "algae", "aquaponics", "hydroponics",
    ],

    "🛡️ Obrana / Drony / Oceány": [
        "unmanned", "uav", "drone", "autonomous vehicle", "autonomous vessel",
        "autonomous systems", "counter-unmanned", "counter-drone",
        "dual use", "dual-use", "defence", "defense", "military",
        "ocean cleaning", "marine litter", "plastic pollution ocean",
        "water purification", "water treatment", "decontamination",
        "border surveillance", "critical infrastructure protection",
        "cbrn", "security technology", "naval", "underwater",
        "swarm", "autonomous underwater", "auv",
    ],
}

#Irelevantne oblasti — vynechame ak neobsahuju nase slova

IRELEVANTNE_SLOVA = [
    "cultural heritage", "intangible heritage", "medieval",
    "democracy", "election", "voting", "political party",
    "lgbtiq", "gender equality", "minority rights",
    "dementia", "cancer survivor", "oncology treatment",
    "fisheries management", "coral reef", "deep sea biology",
    "particle physics", "nuclear fusion plasma",
    "palaeoclimate", "archaeology",
]


# === ODSTRANENIE DUPLIKATOV — PRIORITA STROJARSTVO ===
strojarske = set(OBLASTI["🏭 Strojárstvo / Industry 4.0"])
for oblast in ["🌱 Agro / Bio / Circular", "🛡️ Obrana / Drony / Oceány"]:
    OBLASTI[oblast] = [kw for kw in OBLASTI[oblast] if kw not in strojarske]


def skontroluj_vyzvu(res):
    meta = res.get("metadata", {})
    summary = res.get("summary", "") or ""

    desc_raw = safe_get(meta, "descriptionByte")
    desc_clean = re.sub(r"<[^>]+>", " ", desc_raw)
    desc_clean = re.sub(r"\s+", " ", desc_clean).strip()

    tags = meta.get("tags", [])
    tags_text = " ".join(tags)
    dest_desc = safe_get(meta, "destinationDescription")
    call_title = safe_get(meta, "callTitle")

    fulltext = f"{summary} {tags_text} {desc_clean} {dest_desc} {call_title}".lower()

    # SME detekcia
    je_sme = any(kw in fulltext for kw in SME_KLUCOVE_SLOVA)

    # Irelevantné
    for slovo in IRELEVANTNE_SLOVA:
        if slovo in fulltext and not any(
            kw in fulltext for kws in OBLASTI.values() for kw in kws
        ):
            return None, None, je_sme

    # Oblasti
    for oblast, klucove_slova in OBLASTI.items():
        for kw in klucove_slova:
            if kw in fulltext:
                return oblast, kw, je_sme

    return None, None, je_sme


def spracuj_vysledky(results):
    najdene = []
    for res in results:
        meta = res.get("metadata", {})

        identifier = safe_get(meta, "identifier").strip()
        if not identifier:
            url = res.get("url", "")
            m = re.search(r'topic-details/([^/?]+)', url, re.IGNORECASE)
            identifier = m.group(1) if m else ""
        if not identifier:
            continue

        oblast, dovod, je_sme = skontroluj_vyzvu(res)
        if not oblast:
            continue

        # Deadline
        dl_raw = safe_get(meta, "deadlineDate")
        deadline_str = "N/A"
        if dl_raw:
            try:
                if "T" in str(dl_raw):
                    dt = datetime.fromisoformat(str(dl_raw).replace("Z", "+00:00"))
                else:
                    dt = datetime.fromtimestamp(int(dl_raw) / 1000, tz=timezone.utc)
                deadline_str = dt.strftime("%d.%m.%Y")
            except:
                deadline_str = str(dl_raw)[:10]

        status_raw = safe_get(meta, "status").strip()
        status_label = "Open" if status_raw == "31094501" else "Forthcoming"

        desc_raw = safe_get(meta, "descriptionByte")
        popis = re.sub(r"<[^>]+>", " ", desc_raw)
        popis = re.sub(r"\s+", " ", popis).strip()[:600]

        najdene.append({
            "identifier": identifier,
            "nazov": res.get("summary", identifier),
            "status": status_label,
            "deadline_str": deadline_str,
            "oblast": oblast,
            "dovod": dovod,
            "je_sme": je_sme,
            "call_title": safe_get(meta, "callTitle"),
            "dest_desc": safe_get(meta, "destinationDescription"),
            "programme": safe_get(meta, "frameworkProgramme") or "Horizon Europe",
            "tags": meta.get("tags", [])[:5],
            "popis": popis,
        })

    return najdene


def vytvor_zhrnutie(v):
    vety = []
    vety.append(f"Vyzva '{v['nazov'][:100]}' ({v['identifier']}).")
    if v.get("call_title"):
        vety.append(f"Call: {v['call_title']}.")
    if v.get("dest_desc"):
        vety.append(f"Ciel: {v['dest_desc'][:200]}.")
    if v.get("popis"):
        vety.append(v["popis"][:400] + "...")
    if v["deadline_str"] != "N/A":
        vety.append(f"Uzavierka: {v['deadline_str']}.")
    return " ".join(vety[:4])


# === EMAIL FARBY ===
OBLAST_FARBY = {
    "🏭 Strojárstvo / Industry 4.0": "#003399",
    "🌱 Agro / Bio / Circular": "#2e7d32",
    "🛡️ Obrana / Drony / Oceány": "#b71c1c",
}


def posli_email(najdene_podla_oblasti, celkovo):
    msg = MIMEMultipart("alternative")
    datum = datetime.now().strftime("%d.%m.%Y")
    total = sum(len(v) for v in najdene_podla_oblasti.values())

    if total:
        msg["Subject"] = f"EU Granty {datum} — {total} SME vyziev!"
    else:
        msg["Subject"] = f"EU Granty {datum} — Ziadne SME vyzvy"

    msg["From"] = EMAIL_ODOSIELATEL
    msg["To"] = EMAIL_PRIJEMCA

    sekcie_html = ""
    sekcie_text = ""

    for oblast, vyzvy in najdene_podla_oblasti.items():
        if not vyzvy:
            continue

        farba = OBLAST_FARBY.get(oblast, "#333")
        sekcie_text += f"\n\n{'='*60}\n{oblast} ({len(vyzvy)} SME vyziev)\n{'='*60}\n"
        sekcie_html += f"""
<h2 style="color:{farba};border-bottom:3px solid {farba};
padding-bottom:8px;margin-top:30px;">{oblast} ({len(vyzvy)})</h2>"""

        for i, v in enumerate(vyzvy, 1):
            link = (
                "https://ec.europa.eu/info/funding-tenders/opportunities/portal/"
                f"screen/opportunities/topic-details/{v['identifier']}"
            )
            tags_str = ", ".join(v.get("tags", []))
            zhrnutie = v.get("zhrnutie", "")

            sekcie_text += f"\n{i}. {v['nazov']}\n{zhrnutie}\nSME: ÁNO\nLink: {link}\n"

    msg.attach(MIMEText(sekcie_text, "plain", "utf-8"))
    msg.attach(MIMEText(sekcie_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ODOSIELATEL, EMAIL_HESLO)
        smtp.sendmail(EMAIL_ODOSIELATEL, EMAIL_PRIJEMCA, msg.as_bytes())


def main():
    print("=" * 60)
    print("EU GRANTS AGENT – SME ONLY MODE")
    print(f"Start: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 60)

    data = sedia_search(page_number=1)
    total = data.get("totalResults", 0)
    total_stran = (total // PAGE_SIZE) + 1

    najdene = {oblast: [] for oblast in OBLASTI}
    videne = set()

    def pridaj(vysledky):
        for v in vysledky:
            if not v["je_sme"]:
                continue  # SME filter

            if v["identifier"] not in videne:
                videne.add(v["identifier"])
                v["zhrnutie"] = vytvor_zhrnutie(v)
                najdene[v["oblast"]].append(v)
                print(f"[{v['oblast']}] SME:ÁNO | {v['nazov'][:60]}")

    pridaj(spracuj_vysledky(data.get("results", [])))

    for stranka in range(2, total_stran + 1):
        data2 = sedia_search(page_number=stranka)
        pridaj(spracuj_vysledky(data2.get("results", [])))
        time.sleep(0.15)

    posli_email(najdene, total)
    print("Hotovo!")


if __name__ == "__main__":
    main()
