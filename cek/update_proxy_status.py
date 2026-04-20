import requests
import json
import time
import os
import sys
from datetime import datetime

# Konfigurasi
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
            return False, f"ERROR: {str(e)[:30]}", None
    
    return False, f"FAILED", None

def read_proxies():
    """Baca proxy dari file.txt"""
    proxies = []
    
    print(f"\n📂 Mencari file: {IP_FILE}")
    
    if not os.path.exists(IP_FILE):
        print(f"❌ ERROR: File tidak ditemukan!")
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
                        })
                        print(f"  ✓ Load: {parts[0]}:{parts[1]}")
        
        print(f"✅ Total proxy: {len(proxies)}")
        return proxies
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def save_results(active_list, dead_list):
    """Simpan hasil dengan pengecekan"""
    
    print(f"\n💾 Menyimpan hasil ke: {BASE_DIR}")
    print(f"   Active: {len(active_list)} proxy")
    print(f"   Dead: {len(dead_list)} proxy")
    
    # DEBUG: Tampilkan isi active_list
    if active_list:
        print(f"\n   📝 DEBUG - Active list contents:")
        for idx, item in enumerate(active_list, 1):
            print(f"      {idx}. {item['ip']}:{item['port']}")
    
    # SAVE ACTIVE.TXT
    try:
        with open(OUTPUT_ACTIVE, 'w', encoding='utf-8') as f:
            f.write(f"# Proxy Aktif - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(active_list)}\n\n")
            
            if active_list:
                for item in active_list:
                    line = f"{item['ip']}:{item['port']}\n"
                    f.write(line)
                    print(f"   ✍️ Writing active: {line.strip()}")
            else:
                f.write("# Tidak ada proxy aktif\n")
                print(f"   ⚠️ Tidak ada proxy aktif untuk ditulis")
        
        # VERIFY: Cek apakah file berhasil ditulis
        if os.path.exists(OUTPUT_ACTIVE):
            file_size = os.path.getsize(OUTPUT_ACTIVE)
            print(f"   ✅ active.txt berhasil dibuat (size: {file_size} bytes)")
            
            # Tampilkan isi file untuk verifikasi
            with open(OUTPUT_ACTIVE, 'r') as f:
                content = f.read()
                print(f"   📄 Isi active.txt:\n{content[:200]}")
        else:
            print(f"   ❌ Gagal: active.txt tidak ditemukan setelah write!")
            
    except Exception as e:
        print(f"   ❌ ERROR write active.txt: {e}")
        import traceback
        traceback.print_exc()
    
    # SAVE DEAD.TXT
    try:
        with open(OUTPUT_DEAD, 'w', encoding='utf-8') as f:
            f.write(f"# Proxy Mati - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(dead_list)}\n\n")
            
            if dead_list:
                for item in dead_list:
                    f.write(f"{item['ip']}:{item['port']}\n")
        
        if os.path.exists(OUTPUT_DEAD):
            print(f"   ✅ dead.txt berhasil dibuat")
    except Exception as e:
        print(f"   ❌ ERROR write dead.txt: {e}")
    
    # SAVE LOG DETAIL
    log_file = os.path.join(BASE_DIR, 'check_log.txt')
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write(f"HASIL CHECK PROXY\n")
            f.write(f"Waktu: {datetime.now()}\n")
            f.write("="*60 + "\n\n")
            
            f.write("✅ ACTIVE:\n")
            if active_list:
                for item in active_list:
                    f.write(f"  {item['ip']}:{item['port']} | {item['country']} | {item['isp']} | {item['status']}\n")
            else:
                f.write("  (tidak ada)\n")
            
            f.write(f"\n❌ DEAD:\n")
            if dead_list:
                for item in dead_list:
                    f.write(f"  {item['ip']}:{item['port']} | {item['country']} | {item['isp']} | {item['status']}\n")
            else:
                f.write("  (tidak ada)\n")
        
        print(f"   ✅ check_log.txt berhasil dibuat")
    except Exception as e:
        print(f"   ❌ ERROR write log: {e}")

def main():
    print("\n" + "="*60)
    print("🚀 PROXY CHECKER")
    print("="*60)
    print(f"📁 Path: {BASE_DIR}")
    print(f"⏰ Start: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)
    
    # Baca proxy
    proxies = read_proxies()
    if not proxies:
        print("\n❌ Tidak ada proxy!")
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
        print(f"   📍 {proxy['country']} - {proxy['isp'][:30]}")
        
        is_alive, status_msg, api_data = check_proxy(ip, port)
        
        if is_alive:
            print(f"   ✅ RESULT: ACTIVE - {status_msg}")
            active.append({
                'ip': ip,
                'port': port,
                'country': proxy['country'],
                'isp': proxy['isp'],
                'status': status_msg
            })
            print(f"   📝 Added to active list (total active now: {len(active)})")
        else:
            print(f"   ❌ RESULT: DEAD - {status_msg}")
            dead.append({
                'ip': ip,
                'port': port,
                'country': proxy['country'],
                'isp': proxy['isp'],
                'status': status_msg
            })
        
        time.sleep(0.5)
    
    # Simpan hasil
    print("\n" + "-"*60)
    print("💾 MENYIMPAN HASIL")
    print("-"*60)
    save_results(active, dead)
    
    # Ringkasan
    print("\n" + "="*60)
    print("📊 RINGKASAN")
    print("="*60)
    print(f"✅ Active : {len(active)} proxy")
    print(f"❌ Dead   : {len(dead)} proxy")
    print(f"📈 Rate   : {(len(active)/len(proxies)*100):.1f}%")
    print("="*60)
    
    # Verifikasi akhir
    print("\n🔍 VERIFIKASI FILE:")
    for filename in ['active.txt', 'dead.txt', 'check_log.txt']:
        filepath = os.path.join(BASE_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"  ✅ {filename} - {size} bytes")
        else:
            print(f"  ❌ {filename} - TIDAK ADA!")
    
    print("\n✨ Selesai!\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
