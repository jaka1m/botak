import requests
import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

alive_lock = threading.Lock()
dead_lock = threading.Lock()

def check_proxy(ip, port):
    """Cek apakah proxy aktif"""
    api_url = f"https://api-check.web.id/check?ip={ip}:{port}"
    
    try:
        response = requests.get(api_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "").lower()
            
            if status == "active":
                return True
            else:
                return False
        else:
            return False
            
    except Exception:
        return False

def main():
    input_file = "file.txt"
    alive_file = "proxyList.txt"
    dead_file = "dead.txt"
    
    # Kosongkan file output
    open(alive_file, "w").close()
    open(dead_file, "w").close()
    
    # Baca daftar proxy dari file.txt
    proxies = []
    try:
        with open(input_file, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 4:  # IP, Port, Country, Provider
                    ip = row[0].strip()
                    port = row[1].strip()
                    proxies.append((ip, port, row))  # Simpan row lengkap
    except FileNotFoundError:
        print(f"Error: File {input_file} tidak ditemukan!")
        return
    
    if not proxies:
        print("Tidak ada proxy yang ditemukan di file.txt")
        return
    
    print(f"Total proxy ditemukan: {len(proxies)}")
    print("Memeriksa proxy...\n")
    
    alive_count = 0
    dead_count = 0
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {
            executor.submit(check_proxy, ip, port): (ip, port, row)
            for ip, port, row in proxies
        }
        
        for i, future in enumerate(as_completed(future_to_proxy), 1):
            ip, port, row = future_to_proxy[future]
            is_alive = future.result()
            
            if is_alive:
                # Simpan ke proxyList.txt (format CSV lengkap)
                with alive_lock:
                    with open(alive_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                print(f"✓ [{i}/{len(proxies)}] {ip}:{port} - ALIVE")
                alive_count += 1
            else:
                # Simpan ke dead.txt (format CSV lengkap)
                with dead_lock:
                    with open(dead_file, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                print(f"✗ [{i}/{len(proxies)}] {ip}:{port} - DEAD")
                dead_count += 1
    
    print(f"\n===== HASIL ======")
    print(f"✓ ALIVE: {alive_count} proxy -> {alive_file}")
    print(f"✗ DEAD:  {dead_count} proxy -> {dead_file}")
    print(f"Total: {len(proxies)} proxy")

if __name__ == "__main__":
    main()
