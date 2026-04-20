import asyncio
import aiohttp
import os
import time
from datetime import datetime

# Path otomatis menyesuaikan folder tempat script berada
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Batas request simultan (agar tidak dianggap DDoS oleh API)
CONCURRENT_LIMIT = 100 

async def check_proxy(session, p, semaphore):
    ip, port = p['ip'], p['port']
    url = API_URL.format(ip=ip, port=port)
    
    async with semaphore:
        try:
            # Timeout total 10 detik (koneksi + pembacaan)
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status', '').upper() == 'ACTIVE':
                        return True, p, data.get('delay', 'N/A')
                return False, p, None
        except:
            return False, p, None

def read_proxies():
    proxies = []
    if not os.path.exists(IP_FILE):
        print(f"❌ File sumber tidak ditemukan: {IP_FILE}")
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
    print("="*50)
    print(f"🚀 PROXY CHECKER ASYNC - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada data proxy untuk dicek.")
        return

    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    active_results = []
    dead_results = []

    # Menggunakan TCPConnector untuk mempercepat pembukaan koneksi
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, p, semaphore) for p in proxies]
        
        # Eksekusi paralel semua task
        results = await asyncio.gather(*tasks)

        for is_alive, p, delay in results:
            line = f"{p['ip']},{p['port']},{p['country']},{p['isp']}"
            if is_alive:
                active_results.append(line)
                print(f"✅ {p['ip']}:{p['port']} | Delay: {delay}ms")
            else:
                dead_results.append(line)

    # Menulis hasil ke file
    with open(OUTPUT_ACTIVE, 'w') as f:
        f.write("\n".join(active_results))
    
    with open(OUTPUT_DEAD, 'w') as f:
        f.write("\n".join(dead_results))

    print("\n" + "="*50)
    print(f"📊 HASIL AKHIR:")
    print(f"✅ Aktif: {len(active_results)}")
    print(f"❌ Mati : {len(dead_results)}")
    print("="*50)

if __name__ == "__main__":
    start_time = time.time()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    print(f"⏱️ Total Durasi: {time.time() - start_time:.2f} detik")
