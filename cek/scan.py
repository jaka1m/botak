import asyncio
import httpx
import time
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Batasi jumlah request bersamaan agar tidak kena ban/limit oleh API
MAX_CONCURRENT_REQUESTS = 50 

async def check_proxy(client, p, semaphore):
    """Mengecek proxy secara asinkron"""
    ip, port = p['ip'], p['port']
    url = API_URL.format(ip=ip, port=port)
    
    async with semaphore: # Membatasi antrean agar sistem tidak crash
        try:
            # Timeout pendek agar tidak nyangkut di proxy yang mati
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                if data.get('status', '').upper() == 'ACTIVE':
                    return True, p, data.get('delay', 'N/A')
            return False, p, None
        except:
            return False, p, None

def read_proxies():
    proxies = []
    if not os.path.exists(IP_FILE):
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

async def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("\n" + "="*50)
    print("🚀 PROXY CHECKER - ASYNC MODE (SUPER FAST)")
    print("="*50)
    
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada proxy!")
        return
    
    total = len(proxies)
    start_time = time.time()
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    # Menggunakan httpx.AsyncClient untuk efisiensi koneksi
    async with httpx.AsyncClient() as client:
        tasks = [check_proxy(client, p, semaphore) for p in proxies]
        
        active_list = []
        dead_list = []
        
        # Menjalankan semua task secara paralel
        print(f"Checking {total} proxies... Mohon tunggu.\n")
        results = await asyncio.gather(*tasks)
        
        for is_alive, p, delay in results:
            line = f"{p['ip']},{p['port']},{p['country']},{p['isp']}"
            if is_alive:
                active_list.append(line)
                print(f"✅ {p['ip']}:{p['port']} ({delay})")
            else:
                dead_list.append(line)

        # Simpan hasil akhir sekaligus (lebih cepat daripada simpan tiap loop)
        with open(OUTPUT_ACTIVE, 'w') as f:
            f.write("\n".join(active_list))
        with open(OUTPUT_DEAD, 'w') as f:
            f.write("\n".join(dead_list))

    elapsed = time.time() - start_time
    print("\n" + "="*50)
    print(f"✅ Active: {len(active_list)}")
    print(f"❌ Dead: {len(dead_list)}")
    print(f"⏱️  Waktu: {elapsed:.1f} detik")
    print("="*50)

if __name__ == "__main__":
    # Memerlukan library httpx: pip install httpx
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
