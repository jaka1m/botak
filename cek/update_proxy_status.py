import requests
import json
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Konfigurasi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Konfigurasi kecepatan
MAX_WORKERS = 10  # Jumlah thread parallel (bisa dinaikkan jadi 20)
TIMEOUT = 8       # Timeout per request (detik)
RETRY = 1         # Retry sekali saja

# Lock untuk writing file
write_lock = Lock()

def check_proxy(ip, port):
    """Check proxy status - cepat dengan timeout pendek"""
    url = API_URL.format(ip=ip, port=port)
    
    try:
        response = requests.get(url, timeout=TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', '').upper()
            delay = data.get('delay', 'N/A')
            
            if status == 'ACTIVE':
                return True, f"ACTIVE ({delay})", data
            else:
                return False, f"INACTIVE", data
        else:
            return False, f"HTTP {response.status_code}", None
            
    except requests.exceptions.Timeout:
        return False, "TIMEOUT", None
    except requests.exceptions.ConnectionError:
        return False, "CONNECTION ERR", None
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
        
        print(f"✅ Membaca {len(proxies)} proxy")
        return proxies
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def save_active_proxy(active_list):
    """Simpan proxyList.txt"""
    with write_lock:
        with open(OUTPUT_ACTIVE, 'w') as f:
            for item in active_list:
                f.write(f"{item['ip']},{item['port']},{item['country']},{item['isp']}\n")

def save_dead_proxy(dead_list):
    """Simpan dead.txt"""
    with write_lock:
        with open(OUTPUT_DEAD, 'w') as f:
            for item in dead_list:
                f.write(f"{item['ip']},{item['port']},{item['country']},{item['isp']}\n")

def main():
    # Clear screen
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("\n" + "="*70)
    print("🚀 PROXY CHECKER - SUPER CEPAT (Concurrent)")
    print("="*70)
    print(f"📁 Path: {BASE_DIR}")
    print(f"⚡ Parallel threads: {MAX_WORKERS}")
    print(f"⏰ Mulai: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)
    
    # Baca proxy
    proxies = read_proxies()
    if not proxies:
        print("\n❌ Tidak ada proxy untuk dicek!")
        return
    
    total = len(proxies)
    print(f"\n📊 Total proxy: {total}")
    print("\n" + "="*70)
    print("🔍 SCAN CEPAT (Semua proxy diproses bersamaan)")
    print("="*70 + "\n")
    
    active = []
    dead = []
    completed = 0
    start_time = time.time()
    
    # Gunakan ThreadPoolExecutor untuk concurrent processing
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit semua task
        future_to_proxy = {
            executor.submit(check_proxy, proxy['ip'], proxy['port']): proxy 
            for proxy in proxies
        }
        
        # Process hasil yang sudah selesai
        for future in as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            completed += 1
            
            ip = proxy['ip']
            port = proxy['port']
            country = proxy['country']
            isp = proxy['isp']
            
            try:
                is_alive, status_msg, api_data = future.result(timeout=TIMEOUT+2)
                
                if is_alive:
                    final_country = api_data.get('country', country) if api_data else country
                    final_isp = api_data.get('isp', isp) if api_data else isp
                    delay = api_data.get('delay', 'N/A') if api_data else 'N/A'
                    
                    print(f"[{completed:3d}/{total}] ✅ {ip}:{port} - ACTIVE ({delay}) - {final_country}")
                    
                    active.append({
                        'ip': ip,
                        'port': port,
                        'country': final_country,
                        'isp': final_isp
                    })
                else:
                    print(f"[{completed:3d}/{total}] ❌ {ip}:{port} - DEAD ({status_msg})")
                    
                    dead.append({
                        'ip': ip,
                        'port': port,
                        'country': country,
                        'isp': isp
                    })
                
                # Update file setiap 5 proxy atau di akhir
                if completed % 5 == 0 or completed == total:
                    save_active_proxy(active)
                    save_dead_proxy(dead)
                    
            except Exception as e:
                print(f"[{completed:3d}/{total}] ⚠️ {ip}:{port} - ERROR")
                dead.append({
                    'ip': ip,
                    'port': port,
                    'country': country,
                    'isp': isp
                })
    
    # Save final
    save_active_proxy(active)
    save_dead_proxy(dead)
    
    # Hitung kecepatan
    elapsed_time = time.time() - start_time
    speed = total / elapsed_time if elapsed_time > 0 else 0
    
    # Tampilkan ringkasan
    print("\n" + "="*70)
    print("📊 RINGKASAN")
    print("="*70)
    print(f"✅ ACTIVE : {len(active)} proxy")
    print(f"❌ DEAD   : {len(dead)} proxy")
    print(f"📈 Rate   : {(len(active)/total*100):.1f}% aktif")
    print(f"⚡ Waktu  : {elapsed_time:.2f} detik")
    print(f"🚀 Speed  : {speed:.1f} proxy/detik")
    print("="*70)
    
    # Preview hasil
    print(f"\n📄 Preview {OUTPUT_ACTIVE}:")
    print("-"*50)
    if active:
        for item in active[:5]:
            print(f"   {item['ip']},{item['port']},{item['country']},{item['isp']}")
        if len(active) > 5:
            print(f"   ... dan {len(active)-5} lainnya")
    else:
        print("   (tidak ada proxy aktif)")
    
    print("\n✨ Selesai!\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proses dihentikan user")
