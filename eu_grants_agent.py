# ╔══════════════════════════════════════════════════════════════════╗
# ║   MecaSys – EC Funding Monitor  |  FINAL                       ║
# ║   Funguje v: Google Colab aj GitHub Actions                     ║
# ╚══════════════════════════════════════════════════════════════════╝

# ══════════════════════════════════════════════════════════════════
# KONFIGURÁCIA
# ══════════════════════════════════════════════════════════════════

EMAIL_ODOSIELATEL = "mecasysdata@gmail.com"
EMAIL_HESLO       = "jeze ycaa dpty cvll"  # Gmail App Password
EMAIL_PRIJEMCA    = "maria.genzorova@mecasys.sk"

HISTORIA_SUBOR = "seen_identifiers.json"  # ukladá GitHub Actions aj Colab

OBLASTI = {
    "🏭 Strojárstvo / Industry 4.0": [
        "industry 4.0", "industry 5.0", "advanced manufacturing",
        "smart factory", "smart manufacturing", "factory automation",
        "industrial automation", "process automation", "digital twin",
        "industry hub", "industrial digitalisation", "industrial digitalization",
        "industrial ai", "manufacturing process", "production process",
        "additive manufacturing", "3d printing", "human-robot", "industrial hub",
        "cobots", "cobot", "made in europe", "factory of the future",
        "industrial iot", "iiot", "new approaches for human/ai collaboration",
        "factory processes and automation", "advanced manufacturing for key products",
        "testing", "assembly", "prototype",
    ],
    "🌱 Agro / Bio / Circular": [
        "bioplastic", "polyhydroxyalkanoate",
        "controlled environment agriculture", "precision agriculture",
        "smart farming", "agri-tech", "agritech",
        "bio-based", "biobased", "circular bio", "bioeconomy", "bio-economy",
        "plant growth", "horticulture", "soil health", "microbiome",
        "biodegradable", "biomaterial", "biotechnology for",
        "sustainable packaging", "circular packaging", "bio-based textile",
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

SME_KLUCOVE_SLOVA = [
    "sme", "small and medium", "small enterprise", "medium enterprise",
    "smes", "sme instrument", "eic accelerator", "sme support", "cascade financing",
]

OBLAST_PORADIE = [
    "🏭 Strojárstvo / Industry 4.0",
    "🌱 Agro / Bio / Circular",
    "🛡️ Obrana / Drony / Oceány",
]

SEARCH_KW = {
    "🏭 Strojárstvo / Industry 4.0": [
        "industry 4.0", "industry 5.0", "advanced manufacturing",
        "smart factory", "smart manufacturing", "factory automation",
        "industrial automation", "process automation", "digital twin",
        "industrial digitalisation", "industrial ai", "manufacturing process",
        "additive manufacturing", "3d printing", "human-robot",
        "cobots", "cobot", "made in europe", "factory of the future",
        "industrial iot", "iiot", "prototype",
    ],
    "🌱 Agro / Bio / Circular": [
        "bioplastic", "precision agriculture", "smart farming",
        "bio-based", "bioeconomy", "plant growth", "horticulture",
        "soil health", "biodegradable", "biomaterial",
        "sustainable packaging", "circular packaging",
    ],
    "🛡️ Obrana / Drony / Oceány": [
        "unmanned", "uav", "drone", "autonomous vehicle",
        "autonomous systems", "counter-drone", "dual-use",
        "defence", "ocean cleaning", "water purification",
        "border surveillance", "cbrn", "naval", "underwater", "swarm",
    ],
    "SME": [
        "sme", "small and medium", "eic accelerator", "cascade financing",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
}

# ══════════════════════════════════════════════════════════════════
# POMOCNÉ FUNKCIE
# ══════════════════════════════════════════════════════════════════

import requests, json, re, time, os, smtplib
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Colab HTML náhľad – funguje len v Colab, v GitHub Actions sa preskočí
try:
    from IPython.display import display, HTML
    V_COLAB = True
except ImportError:
    V_COLAB = False

def p(msg):
    print(msg, flush=True)

def _strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    return re.sub(r'\s+', ' ', text).strip()

def _skrat(text, vety=5):
    if not text or len(text) < 40:
        return text or '—'
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    sents = [s.strip() for s in sents if len(s.strip()) > 20]
    if not sents:
        return (text[:500] + '…') if len(text) > 500 else text
    r = ' '.join(sents[:vety])
    return (r[:800] + '…') if len(r) > 800 else r

def _obsahuje(text, slova):
    t = text.lower()
    return any(w in t for w in slova)

def _najdi(text, slova):
    t = text.lower()
    return [w for w in slova if w in t]

def _ts_to_dt(ts_ms):
    try:
        return datetime(1970,1,1,tzinfo=timezone.utc) + timedelta(milliseconds=int(ts_ms))
    except:
        return None

# ══════════════════════════════════════════════════════════════════
# KROK 1 – Search API → všetky unikátne výzvy
# ══════════════════════════════════════════════════════════════════

def hladaj_kw(slovo, page=1):
    url = f"https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text={slovo}&pageSize=50&pageNumber={page}"
    files = {
        "sort"     : (None, json.dumps({"order": "DESC", "field": "startDate"}), "application/json"),
        "query"    : (None, json.dumps({"bool": {"must": [
                        {"terms": {"type": ["1","2","8"]}},
                        {"terms": {"status": ["31094501","31094502"]}}
                     ]}}), "application/json"),
        "languages": (None, json.dumps(["en"]), "application/json"),
    }
    r = requests.post(url, files=files, headers=HEADERS, timeout=30)
    return r.json()

def ziskaj_vsetky_vyzvy():
    vsetky = {}
    for oblast, slova in SEARCH_KW.items():
        for slovo in slova:
            try:
                data = hladaj_kw(slovo)
            except Exception as e:
                p(f"  ⚠️  Chyba pri '{slovo}': {e}")
                continue
            total = data.get('totalResults', 0)
            pages = (total + 49) // 50
            nove  = 0
            for page in range(1, pages + 1):
                if page > 1:
                    data = hladaj_kw(slovo, page)
                for hit in data.get('results', []):
                    ident = hit['metadata']['identifier'][0]
                    if ident not in vsetky:
                        vsetky[ident] = hit
                        vsetky[ident]['_oblast'] = oblast
                        vsetky[ident]['_kw']     = slovo
                        nove += 1
                time.sleep(0.3)
            p(f"  '{slovo}': {total} celkom, {nove} nových (spolu: {len(vsetky)})")
    return vsetky

# ══════════════════════════════════════════════════════════════════
# KROK 2 – História → len nové výzvy
# ══════════════════════════════════════════════════════════════════

def nacitaj_historiu():
    if os.path.exists(HISTORIA_SUBOR):
        with open(HISTORIA_SUBOR, 'r') as f:
            return json.load(f)
    return {}

def uloz_historiu(historia):
    with open(HISTORIA_SUBOR, 'w') as f:
        json.dump(historia, f, indent=2)
    p(f"✅ História uložená: {len(historia)} výziev")

# ══════════════════════════════════════════════════════════════════
# KROK 3 – Detail JSON → plný popis + klasifikácia
# ══════════════════════════════════════════════════════════════════

def ziskaj_detail(identifier):
    url = f"https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/{identifier.lower()}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get('TopicDetails', {})
    except:
        pass
    return {}

def klasifikuj_vyzvu(hit, detail):
    nazov    = hit.get('summary', '')
    popis    = _strip_html(detail.get('description', ''))
    fulltext = f"{nazov} {popis}".lower()

    zhodne = [o for o in OBLAST_PORADIE if _obsahuje(fulltext, OBLASTI[o])]
    if not zhodne:
        if _obsahuje(fulltext, SME_KLUCOVE_SLOVA):
            zhodne = ["🏭 Strojárstvo / Industry 4.0"]
        else:
            return None

    hlavna = "🏭 Strojárstvo / Industry 4.0"
    oblast = hlavna if hlavna in zhodne else zhodne[0]

    meta   = hit['metadata']
    pub_ts = detail.get('publicationDateLong', 0)
    pub_dt = _ts_to_dt(pub_ts)

    return {
        "identifier": meta['identifier'][0],
        "nazov"     : nazov,
        "oblast"    : oblast,
        "kw"        : _najdi(fulltext, OBLASTI[oblast])[:6],
        "kw_sme"    : _najdi(fulltext, SME_KLUCOVE_SLOVA),
        "sme"       : _obsahuje(fulltext, SME_KLUCOVE_SLOVA),
        "programme" : meta.get('frameworkProgramme', [''])[0],
        "status"    : meta.get('status', [''])[0],
        "startDate" : meta.get('startDate', [''])[0][:10],
        "deadline"  : meta.get('deadlineDate', [''])[0][:10],
        "pub_datum" : pub_dt.strftime('%d.%m.%Y') if pub_dt else '—',
        "zhrnutie"  : _skrat(popis, 5),
        "link"      : meta.get('url', [''])[0],
    }

# ══════════════════════════════════════════════════════════════════
# KROK 4 – Email
# ══════════════════════════════════════════════════════════════════

def odosli_email(vysledky, celkovo):
    datum = datetime.now().strftime("%-d. %-m. %Y")

    if celkovo == 0:
        predmet   = f"EC Funding Monitor – {datum} – nič nové"
        html_telo = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:780px;margin:auto;padding:24px;">
          <div style="background:#1a2340;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:20px;">📢 EC Funding Monitor – {datum}</h1>
          </div>
          <div style="border:1px solid #dde3ea;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px;">
            <p style="font-size:15px;">Ahoj Majka, dnes som nič nové nenašiel. 🙂</p>
            <hr style="border:none;border-top:1px solid #e0e6ef;margin:20px 0 12px;">
            <p style="font-size:12px;color:#888;">Automaticky – MecaSys EC Funding Monitor</p>
          </div>
        </body></html>"""
    else:
        predmet = f"EC Funding Monitor – {datum} – {celkovo} nových výziev"
        bloky   = ""
        for oblast in OBLAST_PORADIE:
            if oblast not in vysledky:
                continue
            bloky += f'<h2 style="color:#1a2340;border-bottom:2px solid #c8d0e0;padding-bottom:6px;margin-top:30px;">{oblast}</h2>'
            for v in vysledky[oblast]:
                sme_badge = ('<span style="background:#e8f5e9;color:#2e7d32;padding:2px 7px;'
                             'border-radius:10px;font-size:12px;margin-left:6px;">✅ SME</span>'
                             if v["sme"] else "")
                kw_text = ", ".join(v["kw"]) if v["kw"] else "—"
                sme_kw  = f'<br><b>SME KW:</b> {", ".join(v["kw_sme"])}' if v["kw_sme"] else ""
                bloky += f"""
                <div style="border:1px solid #dde3ea;border-radius:8px;padding:16px 20px;
                            margin-bottom:18px;background:#fafbfc;">
                  <h3 style="margin:0 0 6px;color:#1a2340;font-size:15px;">{v['nazov']}{sme_badge}</h3>
                  <p style="margin:0 0 8px;font-size:13px;color:#555;">
                    <b>Program:</b> {v['programme']} &nbsp;|&nbsp;
                    <b>Stav:</b> {v['status']} &nbsp;|&nbsp;
                    <b>Otvorenie:</b> {v['startDate']} &nbsp;|&nbsp;
                    <b>Uzávierka:</b> {v['deadline']}
                  </p>
                  <p style="margin:0 0 8px;font-size:13px;color:#333;line-height:1.6;">{v['zhrnutie']}</p>
                  <p style="margin:0 0 6px;font-size:12px;color:#777;"><b>KW:</b> {kw_text}{sme_kw}</p>
                  <a href="{v['link']}" style="color:#1565c0;font-size:13px;">🔗 {v['link']}</a>
                </div>"""

        html_telo = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:780px;margin:auto;padding:24px;">
          <div style="background:#1a2340;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:20px;">📢 EC Funding Monitor – {datum}</h1>
            <p style="margin:6px 0 0;font-size:14px;opacity:.85;">
              Nových relevantných výziev: <strong>{celkovo}</strong>
            </p>
          </div>
          <div style="border:1px solid #dde3ea;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px;">
            {bloky}
            <hr style="border:none;border-top:1px solid #e0e6ef;margin:30px 0 16px;">
            <p style="font-size:12px;color:#888;">
              Automaticky vygenerované – MecaSys EC Funding Monitor<br>
              Zdroj: <a href="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals"
                        style="color:#1565c0;">EC Funding &amp; Tenders Portal</a>
            </p>
          </div>
        </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = predmet
    msg["From"]    = EMAIL_ODOSIELATEL
    msg["To"]      = EMAIL_PRIJEMCA
    msg.attach(MIMEText(html_telo, "html", "utf-8"))

    p(f"Odosielam email na {EMAIL_PRIJEMCA} ...")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ODOSIELATEL, EMAIL_HESLO)
            server.sendmail(EMAIL_ODOSIELATEL, EMAIL_PRIJEMCA, msg.as_string())
        p("✅ Email odoslaný!")
    except Exception as e:
        p(f"❌ Chyba emailu: {e}")

# ══════════════════════════════════════════════════════════════════
# HLAVNÝ TOK
# ══════════════════════════════════════════════════════════════════

def main():
    p("=" * 60)
    p(f"MecaSys EC Funding Monitor – {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    p("=" * 60)

    # 1. Stiahni výzvy
    p("\n▶ KROK 1 – Sťahujem výzvy ...")
    vsetky_raw = ziskaj_vsetky_vyzvy()
    p(f"✅ Celkovo unikátnych výziev: {len(vsetky_raw)}")

    # 2. Porovnaj s históriou
    p("\n▶ KROK 2 – Porovnávam s históriou ...")
    historia       = nacitaj_historiu()
    aktualne_ids   = list(vsetky_raw.keys())
    nove_ids       = [i for i in aktualne_ids if i not in historia]
    prvy_beh       = len(historia) == 0

    p(f"História        : {len(historia)} výziev")
    p(f"Aktuálne výzvy  : {len(aktualne_ids)}")
    p(f"Nové (nevidené) : {len(nove_ids)}")

    ids_na_spracovanie = aktualne_ids if prvy_beh else nove_ids
    p(f"Na spracovanie  : {len(ids_na_spracovanie)} výziev")

    # 3. Stiahni detaily a klasifikuj
    p(f"\n▶ KROK 3 – Sťahujem detaily (~{len(ids_na_spracovanie)*0.3/60:.1f} min) ...")
    vysledky = defaultdict(list)
    chyby    = 0
    total    = len(ids_na_spracovanie)

    for i, ident in enumerate(ids_na_spracovanie):
        detail = ziskaj_detail(ident)
        if not detail:
            chyby += 1
            time.sleep(0.2)
            continue
        v = klasifikuj_vyzvu(vsetky_raw[ident], detail)
        if v:
            vysledky[v['oblast']].append(v)
        if (i+1) % 50 == 0:
            p(f"  [{i+1:4d}/{total}] relevantných: {sum(len(x) for x in vysledky.values())} | chýb: {chyby}")
        time.sleep(0.3)

    celkovo = sum(len(v) for v in vysledky.values())
    p(f"\n✅ Relevantných výziev: {celkovo}")
    for o in OBLAST_PORADIE:
        if o in vysledky:
            p(f"   {o}: {len(vysledky[o])}")

    # Textový výpis
    SEP = "─" * 80
    for oblast in OBLAST_PORADIE:
        if oblast not in vysledky:
            continue
        p(f"\n{'═'*80}")
        p(f"  {oblast}  ({len(vysledky[oblast])} výziev)")
        p('═'*80)
        for i, v in enumerate(vysledky[oblast], 1):
            sme = "  [✅ SME]" if v["sme"] else ""
            p(f"\n{i}. {v['nazov']}{sme}")
            p(f"   ID        : {v['identifier']}")
            p(f"   Program   : {v['programme']}  |  Stav: {v['status']}")
            p(f"   Otvorenie : {v['startDate']}  |  Uzávierka: {v['deadline']}")
            p(f"   KW        : {', '.join(v['kw'][:5])}")
            if v["kw_sme"]:
                p(f"   SME KW    : {', '.join(v['kw_sme'])}")
            p(f"   Zhrnutie  : {v['zhrnutie'][:300]}")
            p(f"   🔗 {v['link']}")
            p(SEP)

    # HTML náhľad (len v Colab)
    if V_COLAB and celkovo > 0:
        html = """<style>
          .card{border:1px solid #dde3ea;border-radius:8px;padding:14px 18px;
                margin:10px 0;background:#fafbfc;font-family:Arial,sans-serif}
          .card h3{margin:0 0 5px;color:#1a2340;font-size:14px}
          .meta{font-size:12px;color:#555;margin:0 0 6px}
          .zhr{font-size:13px;color:#333;line-height:1.5;margin:0 0 5px}
          .kw{font-size:11px;color:#777;margin:0 0 4px}
          .lnk a{font-size:12px;color:#1565c0;word-break:break-all}
          .sme{background:#e8f5e9;color:#2e7d32;padding:2px 7px;border-radius:10px;font-size:11px;margin-left:6px}
          .oh{background:#1a2340;color:#fff;padding:10px 16px;border-radius:6px;margin:22px 0 8px;font-size:15px}
        </style>"""
        for oblast in OBLAST_PORADIE:
            if oblast not in vysledky:
                continue
            html += f'<div class="oh">{oblast} – {len(vysledky[oblast])} výziev</div>'
            for v in vysledky[oblast]:
                sme  = '<span class="sme">✅ SME</span>' if v["sme"] else ""
                skw  = f' &nbsp;<b>SME KW:</b> {", ".join(v["kw_sme"])}' if v["kw_sme"] else ""
                html += f"""<div class="card">
                  <h3>{v['nazov']}{sme}</h3>
                  <p class="meta"><b>ID:</b> {v['identifier']} &nbsp;|&nbsp;
                    <b>Program:</b> {v['programme']} &nbsp;|&nbsp;
                    <b>Stav:</b> {v['status']} &nbsp;|&nbsp;
                    <b>Otvorenie:</b> {v['startDate']} &nbsp;|&nbsp;
                    <b>Uzávierka:</b> {v['deadline']}</p>
                  <p class="zhr">{v['zhrnutie']}</p>
                  <p class="kw"><b>KW:</b> {', '.join(v['kw'][:6])}{skw}</p>
                  <p class="lnk"><a href="{v['link']}" target="_blank">🔗 {v['link']}</a></p>
                </div>"""
        display(HTML(html))

    # 4. Odošli email
    p("\n▶ KROK 4 – Odosielam email ...")
    odosli_email(vysledky, celkovo)

    # 5. Ulož históriu
    nova_historia = {**historia, **{i: datetime.now().strftime("%Y-%m-%d") for i in ids_na_spracovanie}}
    uloz_historiu(nova_historia)

    p("\n" + "=" * 60)
    p("Hotovo!")
    p("=" * 60)

if __name__ == "__main__":
    main()
