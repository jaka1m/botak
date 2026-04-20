import requests
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'active.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Gunakan session untuk reuse koneksi
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

def check_proxy(ip, port):
    """Check proxy - super cepat tanpa retry"""
    url = API_URL.format(ip=ip, port=port)
    try:
        response = session.get(url, timeout=3)  # Timeout 3 detik
        if response.status_code == 200:
            data = response.json()
            if data.get('status', '').upper() == 'ACTIVE':
                return True, data.get('delay', 'N/A'), data
        return False, None, None
    except:
        return False, None, None

def read_proxies():
    proxies = []
    if not os.path.exists(IP_FILE):
        print(f"❌ File tidak ditemukan: {IP_FILE}")
        return []
    
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
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("\n" + "="*50)
    print("🚀 PROXY CHECKER - SUPER CEPAT (CONCURRENT)")
    print("="*50)
    print(f"⏰ Mulai: {datetime.now().strftime('%H:%M:%S')}\n")
    
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada proxy!")
        return
    
    total = len(proxies)
    active = []
    dead = []
    start_time = time.time()
    
    # Gunakan thread pool (sesuaikan max_workers dengan kebutuhan)
    max_workers = min(50, total)  # Maksimal 50 koneksi parallel
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit semua task
        future_to_proxy = {}
        for p in proxies:
            future = executor.submit(check_proxy, p['ip'], p['port'])
            future_to_proxy[future] = p
        
        # Proses hasil yang sudah selesai
        for future in as_completed(future_to_proxy):
            p = future_to_proxy[future]
            completed += 1
            is_alive, delay, data = future.result()
            
            print(f"[{completed}/{total}] {p['ip']}:{p['port']}...", end=" ", flush=True)
            
            if is_alive:
                country = data.get('country', p['country']) if data else p['country']
                isp = data.get('isp', p['isp']) if data else p['isp']
                print(f"✅ ({delay})")
                active.append(f"{p['ip']},{p['port']},{country},{isp}")
            else:
                print(f"❌")
                dead.append(f"{p['ip']},{p['port']},{p['country']},{p['isp']}")
            
            # Update file setiap 10 proxy (kurangi overhead I/O)
            if completed % 10 == 0 or completed == total:
                with open(OUTPUT_ACTIVE, 'w') as f:
                    f.write("\n".join(active))
                with open(OUTPUT_DEAD, 'w') as f:
                    f.write("\n".join(dead))
    
    # Final write
    with open(OUTPUT_ACTIVE, 'w') as f:
        f.write("\n".join(active))
    with open(OUTPUT_DEAD, 'w') as f:
        f.write("\n".join(dead))
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*50)
    print(f"✅ Active: {len(active)}")
    print(f"❌ Dead: {len(dead)}")
    print(f"⏱️  Waktu: {elapsed:.1f} detik")
    print(f"⚡ Kecepatan: {total/elapsed:.1f} proxy/detik")
    print("="*50)
    
    session.close()

if __name__ == "__main__":
    main()
