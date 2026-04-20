import requests
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Konfigurasi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# TWEAK DISINI
MAX_WORKERS = 50 

def check_proxy(proxy):
    """Fungsi pengecekan tunggal untuk thread"""
    ip, port = proxy['ip'], proxy['port']
    url = API_URL.format(ip=ip, port=port)
    try:
        # Timeout 3 detik sudah cukup untuk Cloudflare/Serverless environment
        response = requests.get(url, timeout=3) 
        if response.status_code == 200:
            data = response.json()
            if data.get('status', '').upper() == 'ACTIVE':
                delay = data.get('delay', 'N/A')
                country = data.get('country', proxy['country'])
                isp = data.get('isp', proxy['isp'])
                return True, f"{ip},{port},{country},{isp}", delay
        return False, f"{ip},{port},{proxy['country']},{proxy['isp']}", None
    except:
        return False, f"{ip},{port},{proxy['country']},{proxy['isp']}", None

def read_proxies():
    proxies = []
    if not os.path.exists(IP_FILE): return []
    with open(IP_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(',')
                if len(parts) >= 2:
                    proxies.append({
                        'ip': parts[0].strip(),
                        'port': parts[1].strip(),
                        'country': parts[2].strip() if len(parts) > 2 else 'Unknown',
                        'isp': parts[3].strip() if len(parts) > 3 else 'Unknown',
                    })
    return proxies

def main():
    # DIHAPUS: os.system('clear') penyebab error di GitHub Workflow
    
    print("🚀 PROXY CHECKER - RUNNING IN CI MODE")
    print("="*50)
    
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada proxy!"); return

    total = len(proxies)
    active_list = []
    dead_list = []
    start_time = time.time()

    print(f"📦 Total Proxy: {total}")
    print(f"🧵 Threads: {MAX_WORKERS}")
    print("="*50 + "\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(check_proxy, p): p for p in proxies}
        
        completed = 0
        for future in as_completed(future_to_proxy):
            completed += 1
            is_alive, line, delay = future.result()
            
            # Log lebih ringkas untuk GitHub Action agar tidak memenuhi log
            if is_alive:
                active_list.append(line)
                print(f"[{completed}/{total}] ✅ {line.split(',')[0]} | {delay}")
            else:
                dead_list.append(line)
                # Opsi: matikan print kalau tidak mau log GitHub kepenuhan info dead proxy
                # print(f"[{completed}/{total}] ❌ {line.split(',')[0]}")

    # Simpan hasil
    with open(OUTPUT_ACTIVE, 'w') as f: f.write("\n".join(active_list))
    with open(OUTPUT_DEAD, 'w') as f: f.write("\n".join(dead_list))

    elapsed = time.time() - start_time
    print("\n" + "="*50)
    print(f"✅ Selesai! Active: {len(active_list)} | Dead: {len(dead_list)}")
    print(f"⏱️ Total Waktu: {elapsed:.2f} detik")
    print("="*50)

if __name__ == "__main__":
    main()
