import requests
import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Lock untuk menulis ke file secara aman
alive_lock = threading.Lock()
dead_lock = threading.Lock()

def check_proxy(row, api_url_template, alive_file, dead_file):
    if len(row) < 2:
        return False
    
    ip, port = row[0].strip(), row[1].strip()
    
    # Validasi port
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            print(f"Port tidak valid untuk {ip}:{port}")
            return False
    except ValueError:
        print(f"Port bukan angka untuk {ip}:{port}")
        return False
    
    api_url = api_url_template.format(ip=ip, port=port)
    
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("status", "").lower() == "active":
            print(f"✓ {ip}:{port} is ALIVE")
            with alive_lock:
                with open(alive_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([ip, port])
            return True
        else:
            print(f"✗ {ip}:{port} is DEAD (status: {data.get('status', 'unknown')})")
            with dead_lock:
                with open(dead_file, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([ip, port])
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱ Timeout checking {ip}:{port}")
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection error for {ip}:{port}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking {ip}:{port}: {type(e).__name__}")
    except ValueError as ve:
        print(f"📄 Error parsing JSON for {ip}:{port}: {ve}")
    
    return False

def main():
    # Konfigurasi
    input_file = os.getenv('IP_FILE', 'cek/file.txt')
    alive_file = os.getenv('ALIVE_FILE', 'cek/proxyList.txt')
    dead_file = os.getenv('DEAD_FILE', 'cek/dead.txt')
    api_url_template = os.getenv('API_URL', 'https://api-check.web.id/check?ip={ip}:{port}')
    max_workers = int(os.getenv('MAX_WORKERS', '50'))
    timeout = int(os.getenv('TIMEOUT', '30'))

    # Buat direktori jika belum ada
    os.makedirs(os.path.dirname(alive_file), exist_ok=True)

    # Kosongkan file output
    open(alive_file, "w").close()
    open(dead_file, "w").close()

    # Baca input file
    try:
        with open(input_file, "r") as f:
            reader = csv.reader(f)
            rows = [row for row in reader if row and len(row) >= 2]
    except FileNotFoundError:
        print(f"❌ File {input_file} tidak ditemukan.")
        return
    except Exception as e:
        print(f"❌ Error membaca file: {e}")
        return

    if not rows:
        print("⚠️ Tidak ada data proxy yang valid di file.")
        return

    print(f"📊 Memeriksa {len(rows)} proxy dengan {max_workers} thread...")
    print("-" * 50)

    # Eksekusi pengecekan
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(check_proxy, row, api_url_template, alive_file, dead_file)
            for row in rows
        ]
        
        # Optional: tracking progress
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 10 == 0:
                print(f"📈 Progress: {completed}/{len(rows)}")

    print("-" * 50)
    print(f"✅ Selesai! Hasil pengecekan {len(rows)} proxy:")
    print(f"   • ALIVE: {alive_file}")
    print(f"   • DEAD:  {dead_file}")

if __name__ == "__main__":
    main()
