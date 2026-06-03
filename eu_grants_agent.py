import time
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

PORTAL_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals?isExactMatch=true&status=31094501,31094502&order=DESC&pageNumber=1&pageSize=50&sortBy=startDate"

def vytvor_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver


def obsahuje_klucove_slovo(text):
    text_lower = text.lower()
    for slovo in KLUCOVE_SLOVA:
        if slovo in text_lower:
            return slovo
    return None


def ziskaj_vyzvy(driver):
    print("Otváram EU Funding Portal...")
    driver.get(PORTAL_URL)
    time.sleep(5)

    # Zavrieme cookie banner ak existuje
    try:
        cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Accept') or contains(text(),'accept') or contains(text(),'Súhlasím')]")
        cookie_btn.click()
        time.sleep(2)
        print("Cookie banner zavretý.")
    except:
        pass

    vyzvy = []
    strana = 1

    while True:
        print("Spracovávam stranu {}...".format(strana))
        time.sleep(3)

        # Nájdi všetky výzvy na stránke - modré nadpisy v rámčekoch
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.eui-link, .topic-item a, .call-item a, h2 a, h3 a"))
            )
        except:
            print("Timeout pri čakaní na výzvy.")

        # Skús rôzne selektory pre nadpisy výziev
        linky = []
        for selektor in [
            "eui-card__title a",
            ".topic-item__title a",
            "a.ng-star-inserted",
            ".call-title a",
            "h2 a[href*='topic-details']",
            "a[href*='topic-details']",
        ]:
            linky = driver.find_elements(By.CSS_SELECTOR, selektor)
            if linky:
                print("Nájdených {} výziev cez selektor: {}".format(len(linky), selektor))
                break

        if not linky:
            # Pokus cez XPath
            linky = driver.find_elements(By.XPATH, "//a[contains(@href,'topic-details')]")
            print("Nájdených {} výziev cez XPath".format(len(linky)))

        if not linky:
            print("Žiadne výzvy nenájdené na strane {}. Screenshot debug:".format(strana))
            print("URL: {}".format(driver.current_url))
            print("Title: {}".format(driver.title))
            break

        # Zberi info o každej výzve na tejto strane
        for link in linky:
            try:
                nazov = link.text.strip()
                href = link.get_attribute("href") or ""
                if nazov and href:
                    vyzvy.append({"nazov": nazov, "link": href})
            except:
                pass

        print("Celkovo výziev doteraz: {}".format(len(vyzvy)))

        # Skús prejsť na ďalšiu stranu
        try:
            next_btn = driver.find_element(By.XPATH,
                "//button[@aria-label='Next page' or @aria-label='next' or contains(@class,'next') or contains(text(),'Next')]"
            )
            if next_btn.is_enabled() and next_btn.is_displayed():
                next_btn.click()
                strana += 1
                time.sleep(3)
            else:
                print("Tlačidlo Next nie je aktívne - koniec zoznamu.")
                break
        except:
            print("Tlačidlo Next nenájdené - koniec zoznamu.")
            break

        if strana > 30:  # Bezpečnostný limit
            break

    return vyzvy


def skontroluj_vyzvu(driver, vyzva):
    print("Otvaram: {}...".format(vyzva['nazov'][:60]))
    try:
        driver.get(vyzva['link'])
        time.sleep(3)

        # Zober celý text stránky
        try:
            obsah = driver.find_element(By.TAG_NAME, "body").text
        except:
            obsah = ""

        klucove_slovo = obsahuje_klucove_slovo(obsah)

        if klucove_slovo:
            # Skús získať Topic description sekciu
            popis = ""
            for selektor in [
                "[data-cy='topic-description']",
                ".topic-description",
                "#topic-description",
                "eui-tab[label*='Description'] div",
                "div.description",
            ]:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, selektor)
                    popis = el.text[:1500]
                    break
                except:
                    pass

            if not popis:
                popis = obsah[:1500]

            return klucove_slovo, popis

    except Exception as e:
        print("Chyba pri otvarani vyzvy: {}".format(e))

    return None, ""


def vytvor_zhrnutie(nazov, popis, link):
    popis_cistý = re.sub(r'\s+', ' ', popis).strip()
    vety = re.split(r'(?<=[.!?])\s+', popis_cistý)
    relevantne = [v for v in vety if len(v) > 40][:3]

    zhrnutie = "Vyzva '{}'. ".format(nazov[:100])
    if relevantne:
        zhrnutie += " ".join(relevantne[:3])
    else:
        zhrnutie += "Vyzva obsahuje relevantne klucove slova pre Industry 4.0/5.0 a digitalne technologie."

    return zhrnutie[:800]


def posli_email(najdene_vyzvy, celkovo_vyziev):
    msg = MIMEMultipart("alternative")
    datum = datetime.now().strftime('%d.%m.%Y')
    if najdene_vyzvy:
        msg["Subject"] = "EU Granty {} - Nove vyzvy najdene!".format(datum)
    else:
        msg["Subject"] = "EU Granty {} - Ziadne nove vyzvy".format(datum)
    msg["From"] = EMAIL_ODOSIELATEL
    msg["To"] = EMAIL_PRIJEMCA

    if not najdene_vyzvy:
        text = "Prepac Majka, nic som nenasel.\n\nPrehliadol som {} vyziev a ziadna neobsahovala relevantne klucove slova (Industry 4.0/5.0, AI, automatizacia...).".format(celkovo_vyziev)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">EU Granty - Tyzdenny prehlad</h2>
        <p>Prepac Majka, nic som nenasel.</p>
        <p style="color:#666;">Prehliadol som <strong>{}</strong> vyziev a ziadna neobsahovala relevantne klucove slova tykajuce sa Industry 4.0/5.0, AI alebo automatizacie.</p>
        </body></html>""".format(celkovo_vyziev)
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
                    Klucove slovo: <strong>{}</strong>
                </p>
            </div>""".format(i, v['nazov'], v['zhrnutie'], v['link'], v.get('klucove_slovo', ''))

        text = "Ahoj Majka!\n\nNasel som {} relevantne vyzvy z celkovo {}:\n{}\nAgent EU Grantov".format(pocet, celkovo_vyziev, text_vyzvy)
        html = """<html><body style="font-family:Arial,sans-serif;padding:20px;max-width:700px;">
        <h2 style="color:#003399;">EU Granty - Nove relevantne vyzvy</h2>
        <p>Ahoj Majka! Nasel som <strong>{}</strong> relevantne vyzvy z celkovo {} prehliadanych:</p>
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
    print("EU GRANTS AGENT - Spusteny (Selenium verzia)")
    print("Datum: {}".format(datetime.now().strftime('%d.%m.%Y %H:%M')))
    print("=" * 60)

    driver = vytvor_driver()

    try:
        # Krok 1: Zober zoznam vyziev
        vyzvy = ziskaj_vyzvy(driver)

        if not vyzvy:
            print("Ziadne vyzvy nenajdene.")
            posli_email([], 0)
            return

        print("\nNajdeno {} vyziev, prehlidam obsah...".format(len(vyzvy)))

        # Krok 2: Otvor kazdu vyzvu a hladaj klucove slova
        najdene = []
        for idx, vyzva in enumerate(vyzvy, 1):
            print("[{}/{}]".format(idx, len(vyzvy)), end=" ", flush=True)
            klucove_slovo, popis = skontroluj_vyzvu(driver, vyzva)

            if klucove_slovo:
                print("NAJDENE: '{}'".format(klucove_slovo))
                zhrnutie = vytvor_zhrnutie(vyzva['nazov'], popis, vyzva['link'])
                najdene.append({
                    **vyzva,
                    "zhrnutie": zhrnutie,
                    "klucove_slovo": klucove_slovo
                })
            else:
                print("-")

        print("\nVysledok: {} relevantnych z {}".format(len(najdene), len(vyzvy)))
        posli_email(najdene, len(vyzvy))

    finally:
        driver.quit()
        print("Agent dokoncil pracu!")


if __name__ == "__main__":
    main()
