import requests
import json
import time
import os
import sys
from datetime import datetime

# Konfigurasi - Path untuk repo botak/cek/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IP_FILE = os.path.join(BASE_DIR, 'file.txt')
OUTPUT_ACTIVE = os.path.join(BASE_DIR, 'active.txt')
OUTPUT_DEAD = os.path.join(BASE_DIR, 'dead.txt')
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
                    return True, f"ACTIVE ({delay})", data
                else:
                    return False, f"INACTIVE", data
                    
            elif response.status_code == 503:
                return False, f"API ERROR (503)", None
            else:
                return False, f"HTTP {response.status_code}", None
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"TIMEOUT", None
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"CONNECTION ERROR", None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return False, f"ERROR", None
    
    return False, f"FAILED", None

def read_proxies():
    """Baca proxy dari file.txt dengan format: IP,Port,Country,ISP"""
    proxies = []
    
    print(f"\n📂 Mencari file: {IP_FILE}")
    
    if not os.path.exists(IP_FILE):
        print(f"❌ ERROR: File tidak ditemukan!")
        print(f"📝 Buat file di: {IP_FILE}")
        return []
    
    try:
        with open(IP_FILE, 'r') as f:
            lines = f.readlines()
            
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
                            'raw': line
                        })
        
        print(f"✅ Membaca {len(proxies)} proxy dari file.txt")
        return proxies
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def save_active_proxy(active_list):
    """Simpan active.txt dengan format CSV: IP,Port,Country,ISP"""
    with open(OUTPUT_ACTIVE, 'w') as f:
        for item in active_list:
            f.write(f"{item['ip']},{item['port']},{item['country']},{item['isp']}\n")

def save_dead_proxy(dead_list):
    """Simpan dead.txt dengan format CSV: IP,Port,Country,ISP"""
    with open(OUTPUT_DEAD, 'w') as f:
        for item in dead_list:
            f.write(f"{item['ip']},{item['port']},{item['country']},{item['isp']}\n")

def main():
    # Clear screen untuk tampilan lebih bersih
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("\n" + "="*70)
    print("🚀 PROXY CHECKER - botak/cek/")
    print("="*70)
    print(f"📁 Path: {BASE_DIR}")
    print(f"⏰ Mulai: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Baca proxy
    proxies = read_proxies()
    if not proxies:
        print("\n❌ Tidak ada proxy untuk dicek!")
        return
    
    print(f"\n📊 Total proxy: {len(proxies)}")
    print("\n" + "="*70)
    print("🔍 PROSES SCAN (1 per 1)")
    print("="*70 + "\n")
    
    active = []
    dead = []
    
    # Scan satu per satu dengan tampilan realtime
    for idx, proxy in enumerate(proxies, 1):
        ip = proxy['ip']
        port = proxy['port']
        country = proxy['country']
        isp = proxy['isp']
        
        # Tampilkan proses scanning
        print(f"[{idx}/{len(proxies)}] 🔍 Scanning: {ip}:{port} [{country}] - {isp[:30]}")
        print(f"    ⏳ Mengecek...", end=" ", flush=True)
        
        # Panggil API
        is_alive, status_msg, api_data = check_proxy(ip, port)
        
        if is_alive:
            # Gunakan data dari API jika ada (country, isp lebih akurat)
            final_country = api_data.get('country', country) if api_data else country
            final_isp = api_data.get('isp', isp) if api_data else isp
            delay = api_data.get('delay', 'N/A') if api_data else 'N/A'
            
            print(f"✅ ACTIVE! (delay: {delay})")
            
            active.append({
                'ip': ip,
                'port': port,
                'country': final_country,
                'isp': final_isp
            })
            
            # Langsung simpan ke file setiap kali dapat proxy aktif (realtime)
            save_active_proxy(active)
            
        else:
            print(f"❌ DEAD! ({status_msg})")
            
            dead.append({
                'ip': ip,
                'port': port,
                'country': country,
                'isp': isp
            })
            
            # Langsung simpan ke file setiap kali dapat proxy mati (realtime)
            save_dead_proxy(dead)
        
        # Tampilkan statistik sementara
        print(f"    📊 Sementara: {len(active)} aktif, {len(dead)} mati")
        print()
        
        # Delay untuk menghindari rate limit
        if idx < len(proxies):
            time.sleep(1)
    
    # Final save
    save_active_proxy(active)
    save_dead_proxy(dead)
    
    # Tampilkan ringkasan akhir
    print("="*70)
    print("📊 RINGKASAN AKHIR")
    print("="*70)
    print(f"✅ ACTIVE : {len(active)} proxy")
    print(f"❌ DEAD   : {len(dead)} proxy")
    print(f"📈 Rate   : {(len(active)/len(proxies)*100):.1f}% aktif")
    print("="*70)
    
    # Tampilkan preview active.txt
    print(f"\n📄 Preview {OUTPUT_ACTIVE}:")
    print("-"*50)
    with open(OUTPUT_ACTIVE, 'r') as f:
        content = f.read()
        print(content[:500] if len(content) > 500 else content)
    
    print("\n✨ Selesai!\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Proses dihentikan user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
