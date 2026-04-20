import requests
import json
import time
from datetime import datetime

# Konfigurasi
IP_FILE = './cek/file.txt'
OUTPUT_ACTIVE = './cek/active.txt'
OUTPUT_DEAD = './cek/dead.txt'
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

def check_proxy(ip, port, max_retries=2):
    """Check proxy status"""
    url = API_URL.format(ip=ip, port=port)
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', '').upper()
                delay = data.get('delay', 'N/A')
                
                if status == 'ACTIVE':
                    return True, f"✓ ACTIVE | {delay}"
                else:
                    return False, f"✗ INACTIVE"
                    
            elif response.status_code == 503:
                return False, f"✗ API ERROR (503)"
            else:
                return False, f"✗ HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, f"✗ TIMEOUT"
        except requests.exceptions.ConnectionError:
            return False, f"✗ CONNECTION ERROR"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"✗ ERROR: {str(e)[:30]}"
    
    return False, f"✗ FAILED"

def read_proxies():
    """Baca proxy dari file.txt"""
    proxies = []
    try:
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
                            'raw': line
                        })
        return proxies
    except FileNotFoundError:
        print(f"❌ File {IP_FILE} tidak ditemukan!")
        return []

def save_results(active_list, dead_list):
    """Simpan hasil dengan format bersih"""
    
    # File ACTIVE - Hanya IP:PORT
    with open(OUTPUT_ACTIVE, 'w') as f:
        f.write("# PROXY AKTIF\n")
        f.write("# " + "="*40 + "\n")
        f.write(f"# Total: {len(active_list)} proxy\n")
        f.write("# " + "="*40 + "\n\n")
        for item in active_list:
            f.write(f"{item['ip']}:{item['port']}\n")
    
    # File DEAD - Hanya IP:PORT
    with open(OUTPUT_DEAD, 'w') as f:
        f.write("# PROXY MATI/TIDAK AKTIF\n")
        f.write("# " + "="*40 + "\n")
        f.write(f"# Total: {len(dead_list)} proxy\n")
        f.write("# " + "="*40 + "\n\n")
        for item in dead_list:
            f.write(f"{item['ip']}:{item['port']}\n")
    
    # File LOG lengkap untuk referensi
    with open('./cek/check_log.txt', 'w') as f:
        f.write("="*70 + "\n")
        f.write(f"HASIL PENGECEKAN PROXY\n")
        f.write(f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*70 + "\n\n")
        
        f.write("✅ PROXY AKTIF:\n")
        f.write("-"*50 + "\n")
        for item in active_list:
            f.write(f"{item['ip']}:{item['port']} | {item['country']} | {item['isp']} | {item['status']}\n")
        
        f.write("\n❌ PROXY MATI:\n")
        f.write("-"*50 + "\n")
        for item in dead_list:
            f.write(f"{item['ip']}:{item['port']} | {item['country']} | {item['isp']} | {item['status']}\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write(f"Total: {len(active_list)} aktif, {len(dead_list)} mati\n")

def main():
    print("\n" + "="*60)
    print("🚀 PROXY CHECKER")
    print("="*60)
    print(f"⏰ Mulai: {datetime.now().strftime('%H:%M:%S')}\n")
    
    # Baca proxy
    proxies = read_proxies()
    if not proxies:
        print("❌ Tidak ada proxy untuk dicek!")
        return
    
    print(f"📊 Total proxy: {len(proxies)}\n")
    print("-"*60)
    
    active = []
    dead = []
    
    # Cek satu per satu
    for idx, proxy in enumerate(proxies, 1):
        ip = proxy['ip']
        port = proxy['port']
        country = proxy['country']
        isp = proxy['isp']
        
        # Tampilkan progress
        print(f"[{idx}/{len(proxies)}] {ip}:{port} ", end="")
        
        # Cek proxy
        is_alive, status_msg = check_proxy(ip, port)
        
        if is_alive:
            print(f"✅ ACTIVE")
            active.append({
                'ip': ip,
                'port': port,
                'country': country,
                'isp': isp,
                'status': status_msg
            })
        else:
            print(f"❌ DEAD")
            dead.append({
                'ip': ip,
                'port': port,
                'country': country,
                'isp': isp,
                'status': status_msg
            })
        
        # Delay biar tidak kena rate limit
        time.sleep(0.5)
    
    # Simpan hasil
    save_results(active, dead)
    
    # Tampilkan ringkasan
    print("\n" + "="*60)
    print("📊 RINGKASAN")
    print("="*60)
    print(f"✅ ACTIVE : {len(active)} proxy → {OUTPUT_ACTIVE}")
    print(f"❌ DEAD   : {len(dead)} proxy → {OUTPUT_DEAD}")
    print(f"📝 LOG    : ./cek/check_log.txt")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
