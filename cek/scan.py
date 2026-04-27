import asyncio
import aiohttp
import os
import time
import ipaddress
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'proxyList.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

# OPTIMASI: Kurangi concurrent limit untuk GitHub Actions
CONCURRENT_LIMIT = 50  # Turunkan dari 150 ke 50

# OPTIMASI: Hanya scan port yang paling mungkin
DEFAULT_PORTS = [443]  # Mulai dengan 443 dulu, lebih cepat

# OPTIMASI: Batasi total probe
MAX_PROBES = 5000  # Maksimal 5000 probe per run

def expand_cidr(cidr):
    """Expand CIDR dengan optimasi untuk /32"""
    try:
        # Skip /32 karena tidak efisien
        if cidr.endswith('/32'):
            return []
        
        network = ipaddress.ip_network(cidr, strict=False)
        
        # Batasi jumlah IP per CIDR
        max_ips = 256  # Maksimal /24
        ips = list(network.hosts())
        
        if len(ips) > max_ips:
            print(f"⚠️  CIDR {cidr} terlalu besar ({len(ips)} IP), dibatasi ke {max_ips}", flush=True)
            ips = ips[:max_ips]
        
        return [str(ip) for ip in ips]
    except Exception as e:
        print(f"Error expanding CIDR {cidr}: {e}")
        return []

def parse_line(line):
    """Parse line dengan filter untuk /32"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    parts = line.split(',')
    
    # Format CIDR - SKIP /32
    if '/' in parts[0] and len(parts) >= 3:
        cidr = parts[0].strip()
        
        # Skip CIDR /32 karena tidak efisien
        if cidr.endswith('/32'):
            return None
        
        ips = expand_cidr(cidr)
        if ips:
            results = []
            country = parts[1].strip() if len(parts) > 1 else 'Unknown'
            isp = parts[2].strip() if len(parts) > 2 else 'Unknown'
            
            for ip in ips:
                for port in DEFAULT_PORTS:
                    results.append({
                        'ip': ip,
                        'port': str(port),
                        'country': country,
                        'isp': isp,
                    })
            
            if results:
                print(f"📡 {cidr} → {len(ips)} IP × {len(DEFAULT_PORTS)} port = {len(results)} probe", flush=True)
            return results
        return None
    
    # Format proxy biasa
    elif len(parts) >= 2 and not '/' in parts[0]:
        try:
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
                
                # Batasi total probe
                if len(proxies) >= MAX_PROBES:
                    print(f"⚠️  Mencapai batas maksimal {MAX_PROBES} probe, berhenti membaca", flush=True)
                    break
    
    print("="*50, flush=True)
    print(f"📊 Total probe yang akan di-scan: {len(proxies)}", flush=True)
    return proxies

async def check_proxy(session, p, semaphore, timeout=5):  # Turunkan timeout ke 5 detik
    ip, port = p['ip'], p['port']
    url = API_URL.format(ip=ip, port=port)
    
    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status', '').upper() == 'ACTIVE':
                        delay = data.get('delay', 'N/A')
                        return True, p, delay
                return False, p, None
        except:
            return False, p, None

async def main():
    print("="*50, flush=True)
    print(f"🚀 STARTING SCANNER - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("="*50, flush=True)
    print(f"⚙️  Konfigurasi Optimasi:")
    print(f"   - Concurrent limit: {CONCURRENT_LIMIT}")
    print(f"   - Port yang di-scan: {DEFAULT_PORTS}")
    print(f"   - Timeout: 5 detik")
    print(f"   - Max probes: {MAX_PROBES}")
    print("="*50, flush=True)
    
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada probe untuk di-scan!", flush=True)
        return
    
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False, use_dns_cache=True)
    
    start_scan = time.time()
    completed = 0
    total = len(proxies)
    active_results = []
    dead_results = []
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, p, semaphore) for p in proxies]
        
        # Process dengan progress
        for coro in asyncio.as_completed(tasks):
            is_alive, p, delay = await coro
            completed += 1
            
            line = f"{p['ip']},{p['port']},{p['country']},{p['isp']}"
            if is_alive:
                active_results.append(f"{line},{delay}ms" if delay else line)
                print(f"✅ [{completed}/{total}] {line} | {delay}ms", flush=True)
            else:
                dead_results.append(line)
                if completed % 50 == 0:  # Print progress setiap 50 probe
                    print(f"⏳ Progress: {completed}/{total} ({completed/total*100:.1f}%)", flush=True)
    
    # Simpan hasil
    with open(OUTPUT_ACTIVE, 'w') as f: 
        f.write("\n".join(active_results))
    with open(OUTPUT_DEAD, 'w') as f: 
        f.write("\n".join(dead_results))
    
    scan_duration = time.time() - start_scan
    
    print("\n" + "="*50, flush=True)
    print(f"📊 HASIL SCAN:", flush=True)
    print(f"   ✅ Active: {len(active_results)} proxy", flush=True)
    print(f"   ❌ Dead: {len(dead_results)} proxy", flush=True)
    print(f"   ⏱️  Waktu: {scan_duration:.2f} detik", flush=True)
    print("="*50, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
