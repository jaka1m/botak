import requests
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Lock untuk write file aman
write_lock = threading.Lock()

def check_proxy(ip, port):
    """Check proxy super cepat - tanpa retry, timeout kecil"""
    url = API_URL.format(ip=ip, port=port)
    try:
        # Gunakan session untuk koneksi reuse
        with requests.Session() as session:
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

def save_result(active_list, dead_list):
    """Save results ke file"""
    with write_lock:
        with open(OUTPUT_ACTIVE, 'w') as f:
            f.write("\n".join(active_list))
        with open(OUTPUT_DEAD, 'w') as f:
            f.write("\n".join(dead_list))

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
    completed = 0
    
    # Gunakan ThreadPoolExecutor dengan 50 worker
    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_proxy = {
            executor.submit(check_proxy, p['ip'], p['port']): p 
            for p in proxies
        }
        
        for future in as_completed(future_to_proxy):
            p = future_to_proxy[future]
            completed += 1
            
            try:
                is_alive, delay, data = future.result(timeout=3)
            except:
                is_alive, delay, data = False, None, None
            
            ip, port = p['ip'], p['port']
            
            if is_alive:
                print(f"[{completed}/{total}] ✅ {ip}:{port} ({delay}ms)")
                active.append(f"{ip},{port},{country},{isp}")
            else:
                print(f"[{completed}/{total}] ❌ {ip}:{port}")
                dead.append(f"{ip},{port},{p['country']},{p['isp']}")
            
            # Update file setiap 10 hasil atau di akhir
            if completed % 10 == 0 or completed == total:
                save_result(active, dead)
    
    # Save final
    save_result(active, dead)
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*50)
    print(f"✅ Active: {len(active)}")
    print(f"❌ Dead: {len(dead)}")
    print(f"⏱️  Waktu: {elapsed:.1f} detik")
    print(f"⚡ Kecepatan: {total/elapsed:.1f} proxy/detik")
    print("="*50)

if __name__ == "__main__":
    main()
