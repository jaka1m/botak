import requests
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'active.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Lock untuk menulis file
write_lock = threading.Lock()
active_proxies = []
dead_proxies = []
total_checked = 0

def check_proxy(ip, port):
    """Check proxy super cepat - timeout kecil, tanpa retry"""
    url = API_URL.format(ip=ip, port=port)
    try:
        # Timeout 3 detik, stream=True untuk response cepat
        response = requests.get(url, timeout=3, stream=True)
        if response.status_code == 200:
            data = response.json()
            if data.get('status', '').upper() == 'ACTIVE':
                return True, data.get('delay', 'N/A'), data
        return False, None, None
    except:
        return False, None, None

def process_proxy(p, idx, total):
    """Proses single proxy dan update file"""
    global total_checked
    ip, port = p['ip'], p['port']
    
    is_alive, delay, data = check_proxy(ip, port)
    
    with write_lock:
        if is_alive:
            country = data.get('country', p['country']) if data else p['country']
            isp = data.get('isp', p['isp']) if data else p['isp']
            active_proxies.append(f"{ip},{port},{country},{isp}")
            status = f"✅ ({delay})"
        else:
            dead_proxies.append(f"{ip},{port},{p['country']},{p['isp']}")
            status = f"❌"
        
        total_checked += 1
        print(f"[{total_checked}/{total}] {ip}:{port}... {status}")
        
        # Tulis ke file setiap 10 proxy atau proxy terakhir
        if total_checked % 10 == 0 or total_checked == total:
            with open(OUTPUT_ACTIVE, 'w') as f:
                f.write("\n".join(active_proxies))
            with open(OUTPUT_DEAD, 'w') as f:
                f.write("\n".join(dead_proxies))
    
    return is_alive

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
    print("🚀 PROXY CHECKER - SUPER CEPAT (Concurrent)")
    print("="*50)
    print(f"⏰ Mulai: {datetime.now().strftime('%H:%M:%S')}\n")
    
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada proxy!")
        return
    
    total = len(proxies)
    start_time = time.time()
    
    # Gunakan ThreadPoolExecutor untuk concurrent checking
    # Maksimal 50 thread untuk kecepatan maksimal
    max_workers = min(50, total)
    print(f"⚡ Menggunakan {max_workers} thread concurrent\n")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit semua task
        futures = {executor.submit(process_proxy, p, idx, total): p 
                   for idx, p in enumerate(proxies, 1)}
        
        # Tunggu semua selesai
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                pass
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*50)
    print(f"✅ Active: {len(active_proxies)}")
    print(f"❌ Dead: {len(dead_proxies)}")
    print(f"⏱️  Waktu: {elapsed:.1f} detik")
    print(f"⚡ Kecepatan: {total/elapsed:.1f} proxy/detik")
    print("="*50)
    
    # Final write
    with open(OUTPUT_ACTIVE, 'w') as f:
        f.write("\n".join(active_proxies))
    with open(OUTPUT_DEAD, 'w') as f:
        f.write("\n".join(dead_proxies))

if __name__ == "__main__":
    main()
