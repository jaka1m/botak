import asyncio
import aiohttp
import os
import time
from datetime import datetime

# Path otomatis
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Limit simultan (100-200 aman untuk GitHub Actions)
CONCURRENT_LIMIT = 150 

async def check_proxy(session, p, semaphore):
    ip, port = p['ip'], p['port']
    url = API_URL.format(ip=ip, port=port)
    
    async with semaphore:
        try:
            # Timeout diperketat ke 7 detik agar tidak terlalu lama menggantung
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=7)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status', '').upper() == 'ACTIVE':
                        delay = data.get('delay', 'N/A')
                        print(f"✅ {ip}:{port} | {delay}ms", flush=True)
                        return True, p, delay
                
                # Jika tidak aktif (tapi respon 200) atau status bukan ACTIVE
                print(f"❌ {ip}:{port} | Status: {response.status}", flush=True)
                return False, p, None
        except Exception:
            # Print minimal agar log tetap berjalan meski error/timeout
            print(f"❌ {ip}:{port} | Timeout/Error", flush=True)
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
    print("="*50, flush=True)
    print(f"🚀 STARTING SCANNER - {datetime.now().strftime('%H:%M:%S')}", flush=True)
    print("="*50, flush=True)
    
    proxies = read_proxies()
    if not proxies:
        print("❌ File sumber kosong!", flush=True)
        return

    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    
    # Optimasi: Matikan verifikasi SSL & gunakan DNS cache agar tidak 'stuck'
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False, use_dns_cache=True)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, p, semaphore) for p in proxies]
        results = await asyncio.gather(*tasks)

        active_results = []
        dead_results = []
        
        for is_alive, p, delay in results:
            line = f"{p['ip']},{p['port']},{p['country']},{p['isp']}"
            if is_alive:
                active_results.append(line)
            else:
                dead_results.append(line)

    # Simpan hasil akhir
    with open(OUTPUT_ACTIVE, 'w') as f: f.write("\n".join(active_results))
    with open(OUTPUT_DEAD, 'w') as f: f.write("\n".join(dead_results))

    print("\n" + "="*50, flush=True)
    print(f"📊 HASIL: ✅ {len(active_results)} | ❌ {len(dead_results)}", flush=True)
    print("="*50, flush=True)

if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main())
    print(f"⏱️ Selesai dalam {time.time() - start_time:.2f} detik", flush=True)
