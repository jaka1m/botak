import asyncio
import aiohttp
import os
import time
import ipaddress
from datetime import datetime

# Path otomatis
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# Limit simultan (100-200 aman untuk GitHub Actions)
CONCURRENT_LIMIT = 150

# Default ports untuk CIDR
DEFAULT_PORTS = [80, 443, 8443]

def expand_cidr(cidr):
    """Expand CIDR notation to individual IPs"""
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        return [str(ip) for ip in network.hosts()]
    except Exception as e:
        print(f"Error expanding CIDR {cidr}: {e}")
        return []

def parse_line(line):
    """Parse different line formats:
    Format 1 (proxy): IP,Port,Country,ISP
    Format 2 (CIDR): CIDR,Country,Region,City
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    parts = line.split(',')
    
    # Format CIDR: 14.1.64.0/24,PH,PH-00,Manila,
    if '/' in parts[0] and len(parts) >= 3:
        cidr = parts[0].strip()
        ips = expand_cidr(cidr)
        if ips:
            results = []
            country = parts[1].strip() if len(parts) > 1 else 'Unknown'
            isp = parts[2].strip() if len(parts) > 2 else 'Unknown'
            
            # Buat entri untuk setiap IP dengan semua port default
            for ip in ips:
                for port in DEFAULT_PORTS:
                    results.append({
                        'ip': ip,
                        'port': str(port),
                        'country': country,
                        'isp': isp,
                        'original_cidr': cidr  # Untuk tracking
                    })
            print(f"📡 CIDR {cidr} → {len(ips)} IP × {len(DEFAULT_PORTS)} port = {len(results)} probe", flush=True)
            return results
        return None
    
    # Format proxy: IP,Port,Country,ISP
    elif len(parts) >= 2 and not '/' in parts[0]:
        try:
            # Validate IP format
            ipaddress.ip_address(parts[0].strip())
            return [{
                'ip': parts[0].strip(),
                'port': parts[1].strip(),
                'country': parts[2].strip() if len(parts) > 2 else 'Unknown',
                'isp': parts[3].strip() if len(parts) > 3 else 'Unknown',
            }]
        except:
            return None
    
    return None

def read_proxies():
    proxies = []
    if not os.path.exists(IP_FILE):
        print(f"❌ File {IP_FILE} tidak ditemukan!", flush=True)
        return []
    
    print(f"\n📖 Membaca file: {IP_FILE}", flush=True)
    print("="*50, flush=True)
    
    with open(IP_FILE, 'r') as f:
        for line in f:
            result = parse_line(line)
            if result:
                proxies.extend(result)
    
    print("="*50, flush=True)
    print(f"📊 Total probe yang akan di-scan: {len(proxies)}", flush=True)
    print(f"   (Ini adalah jumlah IP × port yang akan diuji)", flush=True)
    return proxies

async def check_proxy(session, p, semaphore, timeout=7):
    ip, port = p['ip'], p['port']
    url = API_URL.format(ip=ip, port=port)
    
    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status', '').upper() == 'ACTIVE':
                        delay = data.get('delay', 'N/A')
                        print(f"✅ {ip}:{port} | {delay}ms | {p['country']} | {p['isp']}", flush=True)
                        return True, p, delay
                
                # Jika tidak aktif (tapi respon 200) atau status bukan ACTIVE
                print(f"❌ {ip}:{port} | Status: {response.status}", flush=True)
                return False, p, None
        except asyncio.TimeoutError:
            print(f"⏰ {ip}:{port} | Timeout ({timeout}s)", flush=True)
            return False, p, None
        except Exception as e:
            print(f"❌ {ip}:{port} | Error: {str(e)[:30]}", flush=True)
            return False, p, None

async def main():
    print("="*50, flush=True)
    print(f"🚀 STARTING SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("="*50, flush=True)
    print(f"⚙️  Konfigurasi:")
    print(f"   - Concurrent limit: {CONCURRENT_LIMIT}")
    print(f"   - Default ports CIDR: {DEFAULT_PORTS}")
    print(f"   - Timeout per probe: 7 detik")
    print("="*50, flush=True)
    
    proxies = read_proxies()
    if not proxies:
        print("❌ File sumber kosong atau format tidak valid!", flush=True)
        return

    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False, use_dns_cache=True)
    
    start_scan = time.time()
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, p, semaphore) for p in proxies]
        results = await asyncio.gather(*tasks)

        active_results = []
        dead_results = []
        
        for is_alive, p, delay in results:
            line = f"{p['ip']},{p['port']},{p['country']},{p['isp']}"
            if is_alive:
                # Tambahkan delay jika ingin melihat kecepatan
                active_results.append(f"{line},{delay}ms" if delay else line)
            else:
                dead_results.append(line)

    # Simpan hasil akhir
    with open(OUTPUT_ACTIVE, 'w') as f: 
        f.write("\n".join(active_results))
    with open(OUTPUT_DEAD, 'w') as f: 
        f.write("\n".join(dead_results))

    scan_duration = time.time() - start_scan
    
    print("\n" + "="*50, flush=True)
    print(f"📊 HASIL SCAN:", flush=True)
    print(f"   ✅ Active: {len(active_results)} proxy", flush=True)
    print(f"   ❌ Dead: {len(dead_results)} proxy", flush=True)
    print(f"   📈 Success rate: {(len(active_results)/len(proxies)*100):.1f}%", flush=True)
    print(f"   ⏱️  Waktu scan: {scan_duration:.2f} detik", flush=True)
    print(f"   🚀 Kecepatan: {(len(proxies)/scan_duration):.1f} probe/detik", flush=True)
    print(f"\n📁 Output files:", flush=True)
    print(f"   Active: {OUTPUT_ACTIVE}", flush=True)
    print(f"   Dead: {OUTPUT_DEAD}", flush=True)
    print("="*50, flush=True)

if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main())
    print(f"\n✨ Total waktu eksekusi: {time.time() - start_time:.2f} detik", flush=True)
