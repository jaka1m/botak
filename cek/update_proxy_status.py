import requests
import time
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

def check_proxy(ip, port):
    """Check proxy - tanpa retry, timeout kecil"""
    url = API_URL.format(ip=ip, port=port)
    try:
        response = requests.get(url, timeout=2)  # Timeout 2 detik
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
    print("🚀 PROXY CHECKER - SUPER CEPAT")
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
    
    for idx, p in enumerate(proxies, 1):
        ip, port = p['ip'], p['port']
        print(f"[{idx}/{total}] {ip}:{port}...", end=" ", flush=True)
        
        is_alive, delay, data = check_proxy(ip, port)
        
        if is_alive:
            country = data.get('country', p['country']) if data else p['country']
            isp = data.get('isp', p['isp']) if data else p['isp']
            print(f"✅ ({delay})")
            active.append(f"{ip},{port},{country},{isp}")
        else:
            print(f"❌")
            dead.append(f"{ip},{port},{p['country']},{p['isp']}")
        
        # Update file setiap saat
        with open(OUTPUT_ACTIVE, 'w') as f:
            f.write("\n".join(active))
        with open(OUTPUT_DEAD, 'w') as f:
            f.write("\n".join(dead))
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*50)
    print(f"✅ Active: {len(active)}")
    print(f"❌ Dead: {len(dead)}")
    print(f"⏱️  Waktu: {elapsed:.1f} detik")
    print("="*50)

if __name__ == "__main__":
    main()
