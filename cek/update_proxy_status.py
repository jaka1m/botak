import requests
import json
import time
import os
import sys
from datetime import datetime

# Konfigurasi - Path untuk repo botak/cek/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Ini akan jadi .../botak/cek/
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'active.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
API_URL = 'https://api-check.web.id/check?ip={ip}:{port}'

def check_proxy(ip, port, max_retries=2):
    """Check proxy status"""
    url = API_URL.format(ip=ip, port=port)
    
    for attempt in range(max_retries):
        try:
            print(f"  🌐 API: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', '').upper()
                delay = data.get('delay', 'N/A')
                
                if status == 'ACTIVE':
                    return True, f"ACTIVE ({delay})"
                else:
                    return False, f"INACTIVE"
                    
            elif response.status_code == 503:
                return False, f"API ERROR (503)"
            else:
                return False, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"TIMEOUT"
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"CONNECTION ERROR"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"ERROR"
    
    return False, f"FAILED"

def read_proxies():
    """Baca proxy dari file.txt"""
    proxies = []
    
    print(f"\n📂 Mencari file: {IP_FILE}")
    
    if not os.path.exists(IP_FILE):
        print(f"❌ ERROR: File tidak ditemukan!")
        print(f"📝 Harusnya ada di: {IP_FILE}")
        
        # Cek isi direktori
        print(f"\n📁 Isi direktori {BASE_DIR}:")
        for file in os.listdir(BASE_DIR):
            print(f"   - {file}")
        return []
    
    try:
        with open(IP_FILE, 'r') as f:
            lines = f.readlines()
            print(f"📄 Membaca file: {len(lines)} baris")
            
            for line_num, line in enumerate(lines, 1):
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
                        print(f"  ✓ {parts[0]}:{parts[1]} - {parts[2] if len(parts)>2 else 'Unknown'}")
                    else:
                        print(f"  ⚠️ Baris {line_num}: Format salah")
        
        print(f"\n✅ Total proxy: {len(proxies)}")
        return proxies
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def save_results(active_list, dead_list):
    """Simpan hasil"""
    
    print(f"\n💾 Menyimpan ke: {BASE_DIR}")
    
    # File ACTIVE
    with open(OUTPUT_ACTIVE, 'w') as f:
        f.write(f"# Proxy Aktif - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total: {len(active_list)}\n\n")
        for item in active_list:
            f.write(f"{item['ip']}:{item['port']}\n")
    print(f"  ✅ active.txt ({len(active_list)} proxy)")
    
    # File DEAD
    with open(OUTPUT_DEAD, 'w') as f:
        f.write(f"# Proxy Mati - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total: {len(dead_list)}\n\n")
        for item in dead_list:
            f.write(f"{item['ip']}:{item['port']}\n")
    print(f"  ✅ dead.txt ({len(dead_list)} proxy)")
    
    # File LOG
    log_file = os.path.join(BASE_DIR, 'result_log.txt')
    with open(log_file, 'w') as f:
        f.write("="*60 + "\n")
        f.write(f"HASIL CHECK PROXY\n")
        f.write(f"Waktu: {datetime.now()}\n")
        f.write("="*60 + "\n\n")
        
        f.write("✅ ACTIVE:\n")
        for item in active_list:
            f.write(f"  {item['ip']}:{item['port']} | {item['country']} | {item['isp']} | {item['status']}\n")
        
        f.write(f"\n❌ DEAD:\n")
        for item in dead_list:
            f.write(f"  {item['ip']}:{item['port']} | {item['country']} | {item['isp']} | {item['status']}\n")
    
    print(f"  ✅ result_log.txt")

def main():
    print("\n" + "="*60)
    print("🚀 PROXY CHECKER - botak/cek/")
    print("="*60)
    print(f"📁 Path: {BASE_DIR}")
    print(f"⏰ Start: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)
    
    # Baca proxy
    proxies = read_proxies()
    if not proxies:
        print("\n❌ Tidak ada proxy! Buat file.txt dengan format:")
        print("   IP,Port,Country,ISP")
        print("   Contoh: 89.31.120.79,56531,AE,M247 Europe")
        return
    
    print("\n" + "-"*60)
    print("🔍 MULAI PENGECEKAN")
    print("-"*60)
    
    active = []
    dead = []
    
    for idx, proxy in enumerate(proxies, 1):
        ip = proxy['ip']
        port = proxy['port']
        
        print(f"\n[{idx}/{len(proxies)}] 📡 {ip}:{port}")
        
        is_alive, status_msg = check_proxy(ip, port)
        
        if is_alive:
            print(f"   ✅ ACTIVE - {status_msg}")
            active.append({
                'ip': ip,
                'port': port,
                'country': proxy['country'],
                'isp': proxy['isp'],
                'status': status_msg
            })
        else:
            print(f"   ❌ DEAD - {status_msg}")
            dead.append({
                'ip': ip,
                'port': port,
                'country': proxy['country'],
                'isp': proxy['isp'],
                'status': status_msg
            })
        
        time.sleep(0.5)  # Delay
    
    # Simpan hasil
    print("\n" + "-"*60)
    save_results(active, dead)
    
    # Ringkasan
    print("\n" + "="*60)
    print("📊 RINGKASAN")
    print("="*60)
    print(f"✅ Active: {len(active)} proxy")
    print(f"❌ Dead  : {len(dead)} proxy")
    print(f"📈 Rate  : {(len(active)/len(proxies)*100):.1f}%")
    print("="*60)
    
    # Tampilkan isi file
    if active:
        print(f"\n📄 active.txt:")
        for item in active[:3]:
            print(f"   {item['ip']}:{item['port']}")
    
    print("\n✨ Selesai!\n")

if __name__ == "__main__":
    main()
