#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PoC Crawler Auto Proxy - v2
Perbaikan:
 - Menunggu hasil sannysoft dengan polling JS (lebih andal)
 - Simpan snapshot HTML & screenshot jika parse gagal (debug)
 - Pencarian indikator nowsecure lebih luas
 - Tetap menjaga perbaikan sebelumnya (no excludeSwitches, safe quit)
"""

import os
import time
import json
import zipfile
import shutil
import random
import tempfile
from datetime import datetime

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# -------------------------
# CONFIG (hardcoded proxy; set USE_PROXY=False to disable)
# -------------------------
USE_PROXY = True
PROXY_HOST = "my.proxy.host"
PROXY_PORT = 3128
PROXY_USER = "alice"
PROXY_PASS = "hunter2"

AUTO_TARGET = None  # set 1/2/3 to auto-run, or None for interactive
# -------------------------

# disable destructor to avoid WinError on shutdown (we quit explicitly)
try:
    uc.Chrome.__del__ = lambda self: None
except Exception:
    pass

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
]

def random_user_agent():
    return random.choice(DEFAULT_USER_AGENTS)

# create proxy extension
def create_proxy_plugin(proxy_host, proxy_port, proxy_user, proxy_pass):
    plugin_dir = tempfile.mkdtemp(prefix="proxy_plugin_")
    manifest = {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy - Auth",
        "permissions": ["proxy","tabs","unlimitedStorage","storage","<all_urls>","webRequest","webRequestBlocking"],
        "background": {"scripts": ["background.js"]}
    }
    background_js = f"""
var config = {{
  mode: "fixed_servers",
  rules: {{
    singleProxy: {{
      scheme: "http",
      host: "{proxy_host}",
      port: parseInt({proxy_port})
    }},
    bypassList: ["localhost", "127.0.0.1"]
  }}
}};
chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
function callbackFn(details) {{
  return {{ authCredentials: {{ username: "{proxy_user}", password: "{proxy_pass}" }} }};
}}
chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
"""
    with open(os.path.join(plugin_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(plugin_dir, "background.js"), "w", encoding="utf-8") as f:
        f.write(background_js)

    plugin_zip = os.path.join(tempfile.gettempdir(), f"proxy_plugin_{int(time.time())}.zip")
    with zipfile.ZipFile(plugin_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(plugin_dir, "manifest.json"), arcname="manifest.json")
        zf.write(os.path.join(plugin_dir, "background.js"), arcname="background.js")

    print(f"[*] [LAPISAN 1] Plugin proxy dibuat: {plugin_zip} (temp dir: {plugin_dir})")
    return plugin_zip, plugin_dir

# setup uc.Chrome
def setup_stealth_driver(proxy_zip=None, headless=False, user_agent=None):
    print("[*] [LAPISAN 2] Menginisiasi driver stealth...")
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
    prefs = {"credentials_enable_service": False, "profile.password_manager_enabled": False}
    options.add_experimental_option("prefs", prefs)
    ua = user_agent or random_user_agent()
    options.add_argument(f"--user-agent={ua}")
    print(f"    -> User-Agent dipakai: {ua}")

    if proxy_zip:
        try:
            options.add_extension(proxy_zip)
            print("[*] [LAPISAN 1] Proxy extension ditambahkan.")
        except Exception as e:
            print(f"[!] Gagal menambahkan extension proxy: {e}")

    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        print(f"[!] Gagal inisiasi uc.Chrome: {e}")
        return None

    # basic evasive injection
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); window.chrome = window.chrome || {};"
        })
    except Exception:
        pass

    print("[+] [LAPISAN 2] Driver siap.")
    return driver

def simulate_human_behavior(driver):
    time.sleep(random.uniform(1.0, 2.5))
    for _ in range(random.randint(1,3)):
        amount = random.randint(200,800)
        try:
            driver.execute_script(f"window.scrollBy(0, {amount});")
        except Exception:
            pass
        time.sleep(random.uniform(0.6,1.2))

def check_for_captcha(driver):
    try:
        src = driver.page_source.lower()
        if "verify you are human" in src or "prove you are human" in src or "captcha" in src:
            return True
        return False
    except Exception:
        return False

# --- New: robust wait for sannysoft results by polling JS ---
def wait_for_sannysoft_results(driver, timeout=40, poll_interval=1.0):
    """
    Poll JS: return number of result rows matching tr.passed|tr.failed
    Returns list length (int) if found >0, otherwise 0 on timeout.
    """
    start = time.time()
    last_err = None
    while True:
        try:
            # execute simple JS to count result rows
            count = driver.execute_script(
                "return document.querySelectorAll('tr.passed, tr.failed').length || 0;"
            )
            if isinstance(count, int) and count > 0:
                return count
        except WebDriverException as e:
            last_err = e
            # continue polling until timeout
        if time.time() - start > timeout:
            # timeout
            if last_err:
                raise TimeoutException(f"sannysoft wait timeout after {timeout}s; last error: {last_err}")
            raise TimeoutException(f"sannysoft wait timeout after {timeout}s; no results found")
        time.sleep(poll_interval)

# helper debug snapshot
def save_debug_snapshot(driver, name_prefix):
    os.makedirs("debug_snapshots", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    html_file = os.path.join("debug_snapshots", f"{name_prefix}_{ts}.html")
    png_file = os.path.join("debug_snapshots", f"{name_prefix}_{ts}.png")
    try:
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception as e:
        print(f"[!] Gagal simpan HTML snapshot: {e}")
    try:
        driver.save_screenshot(png_file)
    except Exception:
        pass
    print(f"[*] Debug snapshot saved: {html_file}, {png_file}")
    return html_file, png_file

def run_target(driver, target_url, target_name):
    print(f"[*] Menavigasi ke {target_url} ...")
    driver.get(target_url)
    simulate_human_behavior(driver)

    if check_for_captcha(driver):
        print("[!] CAPTCHA terdeteksi — hentikan analisis.")
        save_debug_snapshot(driver, f"captcha_{target_name}")
        return

    if "httpbin.org/get" in target_url:
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            pre = soup.find("pre")
            if pre:
                data = json.loads(pre.text)
                print("\n--- [ANALISIS] HTTPBIN ---")
                print(f"  User-Agent terkirim: {data.get('headers', {}).get('User-Agent')}")
                print(f"  Origin (IP): {data.get('origin')}")
            else:
                print("[!] Tidak menemukan <pre> pada httpbin.")
        except Exception as e:
            print(f"[!] Error parsing httpbin: {e}")
            save_debug_snapshot(driver, "httpbin_err")

    elif "bot.sannysoft.com" in target_url:
        print("[*] Menunggu hasil JS sannysoft (polling)...")
        try:
            count = wait_for_sannysoft_results(driver, timeout=40, poll_interval=1.0)
            print(f"[+] Ditemukan {count} baris hasil pada sannysoft. Mem-parsing...")
            soup = BeautifulSoup(driver.page_source, "html.parser")
            rows = soup.find_all("tr", class_=["passed", "failed"])
            if not rows:
                print("[!] Warning: JS reported rows but parsing returned none. Saving snapshot.")
                save_debug_snapshot(driver, "sannysoft_mismatch")
            else:
                print("\n--- [ANALISIS] SANNYSOFT ---")
                for r in rows:
                    td = r.find("td")
                    name = td.text.strip() if td else "<unknown>"
                    status = (r.get("class") or ["unknown"])[0]
                    print(f"  Test: {name:<40} | Status: {status.upper()}")
        except TimeoutException as te:
            print(f"[!] Gagal menunggu/parse sannysoft: {te}")
            save_debug_snapshot(driver, "sannysoft_timeout")
        except Exception as e:
            print(f"[!] Error saat parse sannysoft: {e}")
            save_debug_snapshot(driver, "sannysoft_error")

    elif "nowsecure.nl" in target_url:
        print("[*] Analisis nowsecure (cek indikator lebih luas)...")
        try:
            page = driver.page_source
            lowered = page.lower()
            found = False
            checks = [
                "why are you here?",
                "why are you here",
                "are you human",
                "please enable javascript",
                "challenge"
            ]
            for chk in checks:
                if chk in lowered:
                    found = True
                    print(f"[+] Menemukan indikator nowsecure: '{chk}'")
                    break
            # also check H1/title
            try:
                soup = BeautifulSoup(page, "html.parser")
                h1 = soup.find("h1")
                title = soup.title.text if soup.title else ""
                if h1 and "why" in h1.text.lower():
                    found = True
                    print(f"[+] H1 indicates challenge: {h1.text.strip()}")
                if title and "nowsecure" in title.lower() and not found:
                    # keep as neutral info
                    print(f"    -> Title: {title.strip()}")
            except Exception:
                pass

            if not found:
                print("[!] Tidak menemukan indikator 'Why are you here?' atau challenge. Halaman mungkin berbeda.")
                save_debug_snapshot(driver, "nowsecure_no_indicator")
            else:
                print("[+] Deteksi indikator nowsecure ditemukan (lihat snapshot untuk detail).")
        except Exception as e:
            print(f"[!] Gagal analisis nowsecure: {e}")
            save_debug_snapshot(driver, "nowsecure_error")
    else:
        print("[!] Target tidak dikenali untuk parsing khusus. Simpan snapshot.")
        save_debug_snapshot(driver, "unknown_target")

# safe filename
def safe_filename(name):
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip() or "screenshot"

def main():
    targets = {
        1: {"url": "https://httpbin.org/get", "name": "httpbin"},
        2: {"url": "https://bot.sannysoft.com/", "name": "sannysoft"},
        3: {"url": "https://nowsecure.nl/", "name": "nowsecure"}
    }

    if AUTO_TARGET and AUTO_TARGET in targets:
        choice = AUTO_TARGET
    else:
        print("--- PoC Crawler Arsitektur Hibrida (Auto Proxy) v2 ---")
        for k,v in targets.items():
            print(f"  {k}: {v['name']} ({v['url']})")
        try:
            choice = int(input("Pilih target (1,2,3): ").strip())
        except Exception:
            print("Pilihan tidak valid. Keluar.")
            return

    if choice not in targets:
        print("Pilihan tidak valid. Keluar.")
        return

    target = targets[choice]
    proxy_zip = None
    proxy_dir = None
    driver = None

    try:
        if USE_PROXY:
            try:
                proxy_zip, proxy_dir = create_proxy_plugin(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS)
            except Exception as e:
                print(f"[!] Gagal buat plugin proxy: {e}. Lanjut tanpa proxy.")
                proxy_zip = None
                proxy_dir = None
        else:
            print("[*] USE_PROXY=False, lanjut tanpa proxy.")

        driver = setup_stealth_driver(proxy_zip=proxy_zip, headless=False)
        if driver is None:
            print("[!] Gagal buat driver. Keluar.")
            return

        run_target(driver, target["url"], target["name"])

        # screenshot
        fname = f"hasil_test_{safe_filename(target['name'])}.png"
        try:
            driver.save_screenshot(fname)
            print(f"[+] Screenshot tersimpan: {fname}")
        except Exception as e:
            print(f"[!] Gagal simpan screenshot: {e}")

    except Exception as e:
        print(f"[!] Terjadi kesalahan (umum): {e}")

    finally:
        if driver:
            try:
                print("[*] Menutup driver...")
                driver.quit()
                del driver
            except Exception as e:
                print(f"[!] Error ketika menutup driver: {e}")

        # cleanup plugin files if created
        try:
            if proxy_zip and os.path.exists(proxy_zip):
                os.remove(proxy_zip)
            if proxy_dir and os.path.exists(proxy_dir):
                shutil.rmtree(proxy_dir)
        except Exception:
            pass

        print("[*] Selesai.")

if __name__ == "__main__":
    main()