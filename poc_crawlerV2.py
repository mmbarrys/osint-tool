import time
import random
import os
import zipfile
import json
import shutil  # <-- IMPORT BARU UNTUK MEMPERBAIKI BUG CLEANUP
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

# ==============================================================================
# KONFIGURASI (TUGAS TIM INFRASTRUKTUR - YUDI ARFAN)
# GANTI DENGAN KREDENSIAL PROXY RESIDENSIAL ANDA
# ==============================================================================
PROXY_HOST = 'gw.brightdata.com'
PROXY_PORT = 22225
PROXY_USER = 'brd-customer-12345'
PROXY_PASS = 'abcde12345'
# ==============================================================================


## --- LAPISAN 1: INFRASTRUKTUR (PROXY) --- ##
def create_proxy_plugin(proxy_host, proxy_port, proxy_user, proxy_pass):
    plugin_dir = 'proxy_plugin'
    # Hapus direktori lama jika ada (perbaikan bug minor)
    if os.path.exists(plugin_dir):
        shutil.rmtree(plugin_dir)
    os.makedirs(plugin_dir, exist_ok=True)

    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auto-Auth",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy_host}",
                port: {proxy_port}
            }},
            bypassList: ["localhost"]
        }}
    }};

    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{proxy_user}",
                password: "{proxy_pass}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    with open(os.path.join(plugin_dir, 'manifest.json'), 'w') as f:
        f.write(manifest_json)
    with open(os.path.join(plugin_dir, 'background.js'), 'w') as f:
        f.write(background_js)

    plugin_zip = f'{plugin_dir}.zip'
    # Hapus zip lama jika ada
    if os.path.exists(plugin_zip):
        os.remove(plugin_zip)
        
    with zipfile.ZipFile(plugin_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(plugin_dir):
            for file in files:
                zf.write(os.path.join(root, file), 
                         os.path.relpath(os.path.join(root, file), 
                                         os.path.join(plugin_dir, '..')))
    
    print(f"[*] [LAPISAN 1] Plugin proxy dinamis dibuat di: {plugin_zip}")
    return plugin_zip


## --- LAPISAN 2: KLIEN (EVASIF) --- ##
def setup_stealth_driver(proxy_plugin_zip):
    print("[*] [LAPISAN 2] Menginisiasi driver stealth...")
    
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    })

    print(f"[*] [LAPISAN 1] Memuat plugin proxy...")
    options.add_extension(proxy_plugin_zip)

    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
    except Exception as e:
        print(f"[!] [LAPISAN 2] GAGAL inisiasi driver: {e}")
        return None
        
    print("[+] [LAPISAN 1 & 2] Driver stealth + proxy aktif.")
    return driver


## --- LAPISAN 3: PERILAKU (MIMIKRI) --- ##
def simulate_human_behavior(driver):
    print("[*] [LAPISAN 3] Mensimulasikan perilaku manusia...")
    time.sleep(random.uniform(1.5, 3.5))
    scroll_depth = random.randint(400, 800)
    driver.execute_script(f"window.scrollBy(0, {scroll_depth});")
    print(f"    -> [LAPISAN 3] Scrolling {scroll_depth}px")
    time.sleep(random.uniform(1.1, 2.3))


## --- LAPISAN 4: PENANGANAN TANTANGAN (CAPTCHA) --- ##
def check_for_captcha(driver):
    print("[*] [LAPISAN 4] Memeriksa tantangan CAPTCHA...")
    try:
        page_text = driver.page_source.lower()
        if "verify you are human" in page_text or "prove you are human" in page_text:
            print("[!] [LAPISAN 4] TANTANGAN CAPTCHA DITEMUKAN!")
            return True
        print("[+] [LAPISAN 4] Tidak ada CAPTCHA terdeteksi.")
        return False
    except Exception:
        print("[+] [LAPISAN 4] Tidak ada CAPTCHA terdeteksi.")
        return False


## --- FUNGSI UTAMA (INTEGRASI) --- ##
def main():
    targets = {
        # --- PERBAIKAN BUG UTAMA DI SINI ---
        "1": {"url": "https://httpbin.org/get", "name": "httpbin (Tes Infra)"}, 
        # ------------------------------------
        "2": {"url": "https://bot.sannysoft.com/", "name": "sannysoft (Tes Evasif)"},
        "3": {"url": "https://nowsecure.nl/", "name": "nowsecure (Tes Tempur)"}
    }

    print("--- PoC Crawler Arsitektur Hibrida (V3.1) ---")
    for key, value in targets.items():
        print(f"  {key}: {value['name']} ({value['url']})")
    
    choice = input("Pilih target (1, 2, atau 3): ")
    if choice not in targets:
        print("Pilihan tidak valid.")
        return

    TARGET_URL = targets[choice]["url"]
    TARGET_NAME = targets[choice]["name"].split(" ")[0]

    proxy_plugin_zip = None
    if 'ip.proxy.com' in PROXY_HOST or 'username' in PROXY_USER:
        print(f"[!] PERINGATAN: Kredensial proxy belum diisi. Melanjutkan tanpa proxy.")
        proxy_plugin_zip = None
    else:
        proxy_plugin_zip = create_proxy_plugin(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS)
    
    driver = None
    plugin_dir_path = 'proxy_plugin' # Definisikan path di sini
    try:
        if proxy_plugin_zip:
            driver = setup_stealth_driver(proxy_plugin_zip)
        else:
            print("[*] [LAPISAN 2] Menginisiasi driver stealth (TANPA PROXY)...")
            driver = uc.Chrome()
        
        if driver is None:
            return

        print(f"[*] Menavigasi ke target: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        simulate_human_behavior(driver)
        
        if check_for_captcha(driver):
            print("[!] Misi dihentikan oleh sistem pertahanan (CAPTCHA).")
        
        else:
            print("[+] Target berhasil diakses tanpa CAPTCHA.")
            print("[*] Memulai analisis konten...")
            
            if "httpbin" in TARGET_URL:
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                json_data = json.loads(soup.find('pre').text)
                print("\n--- [ANALISIS] HASIL HTTPBIN ---")
                # --- PERBAIKAN BUG PARSING DI SINI ---
                print(f"  User-Agent Terkirim: {json_data['headers'].get('User-Agent')}")
                print(f"  IP Asal (Origin): {json_data['origin']}")
                # ------------------------------------
                print("  (Tim Infra: Pastikan IP Origin BUKAN IP Anda!)")
            
            elif "sannysoft" in TARGET_URL:
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                results = soup.find_all('tr', class_=['passed', 'failed'])
                print("\n--- [ANALISIS] HASIL SANNYSOFT ---")
                for res in results:
                    test_name = res.find('td', class_='test-name').text.strip()
                    status = res['class'][0] 
                    print(f"  Test: {test_name:<30} | Status: {status.upper()}")
                print("  (Tim Evasif: Targetkan semua status 'PASSED')")

            elif "nowsecure" in TARGET_URL:
                print("\n--- [ANALISIS] HASIL NOWSECURE ---")
                if "Why are you here?" in driver.page_source:
                    print("[+] HASIL: BERHASIL! Lolos deteksi nowsecure.nl.")
                else:
                    print("[!] HASIL: GAGAL. Halaman 'Why are you here?' tidak ditemukan.")

        screenshot_file = f"hasil_test_{TARGET_NAME}.png"
        driver.save_screenshot(screenshot_file)
        print(f"\n[+] [QA] Screenshot disimpan ke: {screenshot_file}")

    except Exception as e:
        print(f"\n[!] Terjadi kesalahan operasional: {e}")
    finally:
        if driver:
            print("[*] Menutup driver...")
            driver.quit()
            
        # --- PERBAIKAN BUG CLEANUP DI SINI ---
        plugin_zip_path = 'proxy_plugin.zip'
        if os.path.exists(plugin_zip_path):
            os.remove(plugin_zip_path)
        if os.path.exists(plugin_dir_path):
            # Gunakan shutil.rmtree untuk menghapus direktori dan isinya
            shutil.rmtree(plugin_dir_path) 
        # ------------------------------------
        print("[*] Misi selesai.")

if __name__ == "__main__":
    main()