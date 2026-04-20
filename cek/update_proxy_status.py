import requests
import json
import time
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Konfigurasi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Pengaturan kecepatan extreme
MAX_WORKERS = 5  # 5 proxy sekaligus
TIMEOUT = 1      # Timeout 1 detik (super cepat!)

def check_proxy(ip, port):
    """Check proxy - timeout 1 detik, tanpa retry"""
    url = API_URL.format(ip=ip, port=port)
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=TIMEOUT)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', '').upper()
            delay = data.get('delay', 'N/A')
            
            if status == 'ACTIVE':
                return True, f"ACTIVE ({delay}, {elapsed:.1f}s)", data
            else:
                return False, "INACTIVE", data
        else:
            return False, f"HTTP {response.status_code}", None
            
    except requests.exceptions.Timeout:
        return False, "TIMEOUT", None
    except requests.exceptions.ConnectionError:
        return False, "CONN ERR", None
    except Exception:
        return False, "ERROR", None

def read_proxies():
    """Baca proxy dari file.txt"""
    proxies = []
    
    if not os.path.exists(IP_FILE):
        print(f"❌ File tidak ditemukan: {IP_FILE}")
        return []
    
    try:
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
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def save_results(active_list, dead_list):
    """Simpan hasil ke file"""
    with open(OUTPUT_ACTIVE, 'w') as f:
        for item in active_list:
            f.write(f"{item['ip']},{item['port']},{item['country']},{item['isp']}\n")
    
    with open(OUTPUT_DEAD, 'w') as f:
        for item in dead_list:
            f.write(f"{item['ip']},{item['port']},{item['country']},{item['isp']}\n")

def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("\n" + "="*60)
    print("⚡ PROXY CHECKER - EXTREME FAST ⚡")
    print("="*60)
    print(f"📁 Path: {BASE_DIR}")
    print(f"⚡ Concurrent: {MAX_WORKERS} proxy sekaligus")
    print(f"⏱️  Timeout: {TIMEOUT} detik")
    print(f"⏰ Mulai: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)
    
    # Baca proxy
    proxies = read_proxies()
    if not proxies:
        print("\n❌ Tidak ada proxy untuk dicek!")
        return
    
    total = len(proxies)
    print(f"\n📊 Total proxy: {total}")
    print("\n" + "="*60)
    print("🔍 SCAN CEPAT (5 proxy bersamaan)")
    print("="*60 + "\n")
    
    active = []
    dead = []
    completed = 0
    start_time = time.time()
    
    # Concurrent checking dengan timeout 1 detik
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit semua tugas
        future_to_proxy = {
            executor.submit(check_proxy, p['ip'], p['port']): p 
            for p in proxies
        }
        
        # Proses hasil yang sudah selesai
        for future in as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            completed += 1
            ip, port = proxy['ip'], proxy['port']
            
            try:
                is_alive, status_msg, api_data = future.result(timeout=TIMEOUT+0.5)
                
                if is_alive:
                    final_country = api_data.get('country', proxy['country']) if api_data else proxy['country']
                    final_isp = api_data.get('isp', proxy['isp']) if api_data else proxy['isp']
                    
                    print(f"[{completed}/{total}] ✅ {ip}:{port} - {status_msg}")
                    active.append({
                        'ip': ip,
                        'port': port,
                        'country': final_country,
                        'isp': final_isp
                    })
                else:
                    print(f"[{completed}/{total}] ❌ {ip}:{port} - {status_msg}")
                    dead.append({
                        'ip': ip,
                        'port': port,
                        'country': proxy['country'],
                        'isp': proxy['isp']
                    })
                
                # Update file setiap selesai (realtime)
                save_results(active, dead)
                    
            except Exception:
                print(f"[{completed}/{total}] ❌ {ip}:{port} - TIMEOUT/ERROR")
                dead.append({
                    'ip': ip,
                    'port': port,
                    'country': proxy['country'],
                    'isp': proxy['isp']
                })
                save_results(active, dead)
    
    # Save final
    save_results(active, dead)
    
    elapsed = time.time() - start_time
    
    # Ringkasan
    print("\n" + "="*60)
    print("📊 RINGKASAN")
    print("="*60)
    print(f"✅ ACTIVE : {len(active)} proxy")
    print(f"❌ DEAD   : {len(dead)} proxy")
    print(f"📈 Rate   : {(len(active)/total*100):.1f}%")
    print(f"⏱️  Waktu  : {elapsed:.1f} detik")
    print(f"⚡ Speed  : {total/elapsed:.1f} proxy/detik")
    print("="*60)
    
    # Preview hasil
    if active:
        print(f"\n📄 Preview {OUTPUT_ACTIVE} (aktif):")
        print("-"*40)
        for item in active[:5]:
            print(f"   {item['ip']},{item['port']},{item['country']},{item['isp']}")
    
    if dead:
        print(f"\n📄 Preview {OUTPUT_DEAD} (mati):")
        print("-"*40)
        for item in dead[:3]:
            print(f"   {item['ip']},{item['port']},{item['country']},{item['isp']}")
    
    print("\n✨ Selesai!\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Dihentikan user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
