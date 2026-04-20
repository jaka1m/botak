import requests
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# File configuration
INPUT_FILE = 'cek/file.txt'
ALIVE_FILE = 'cek/proxyList.txt'
DEAD_FILE = 'cek/dead.txt'
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

def check_proxy(ip, port):
    """Check if proxy is active"""
    try:
        api_url = API_URL.format(ip=ip, port=port)
        response = requests.get(api_url, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "").lower()
            return status == "active"
        return False
    except Exception as e:
        print(f"Error checking {ip}:{port}: {str(e)[:50]}")
        return False

def main():
    print(f"🚀 Starting proxy checker at {datetime.now()}")
    print(f"📁 Input file: {INPUT_FILE}")
    
    # Check if input file exists
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} tidak ditemukan!")
        sys.exit(1)
    
    # Read proxies from file.txt
    proxies = []
    try:
        with open(INPUT_FILE, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:  # At least IP and port
                    ip = row[0].strip()
                    port = row[1].strip()
                    proxies.append(row)  # Keep full row
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)
    
    if not proxies:
        print("⚠️ Tidak ada proxy yang ditemukan di file.txt")
        sys.exit(0)
    
    print(f"📊 Total proxy ditemukan: {len(proxies)}")
    print("🔄 Memeriksa proxy...\n")
    
    # Clear output files
    open(ALIVE_FILE, 'w').close()
    open(DEAD_FILE, 'w').close()
    
    alive_count = 0
    dead_count = 0
    
    # Check proxies with multithreading
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {
            executor.submit(check_proxy, row[0].strip(), row[1].strip()): row
            for row in proxies
        }
        
        for i, future in enumerate(as_completed(future_to_proxy), 1):
            row = future_to_proxy[future]
            ip = row[0]
            port = row[1]
            is_alive = future.result()
            
            if is_alive:
                with open(ALIVE_FILE, 'a', newline='') as f:
                    csv.writer(f).writerow(row)
                print(f"✓ [{i}/{len(proxies)}] {ip}:{port} - ALIVE")
                alive_count += 1
            else:
                with open(DEAD_FILE, 'a', newline='') as f:
                    csv.writer(f).writerow(row)
                print(f"✗ [{i}/{len(proxies)}] {ip}:{port} - DEAD")
                dead_count += 1
    
    print(f"\n{'='*50}")
    print(f"✅ HASIL AKHIR:")
    print(f"   ✓ ALIVE: {alive_count} proxy -> {ALIVE_FILE}")
    print(f"   ✗ DEAD:  {dead_count} proxy -> {DEAD_FILE}")
    print(f"   📊 Total: {len(proxies)} proxy")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
