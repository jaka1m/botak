import requests
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_proxy(row, api_url_template, alive_file, dead_file):
    ip, port = row[0].strip(), row[1].strip()
    api_url = api_url_template.format(ip=ip, port=port)
    try:
        response = requests.get(api_url, timeout=60)
        response.raise_for_status()
        data = response.json()

        if data.get("status", "").lower() == "active":
            print(f"{ip}:{port} is ALIVE")
            with open(alive_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
            return True  # Proxy hidup
        else:
            print(f"{ip}:{port} is DEAD")
            with open(dead_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
            return False  # Proxy mati
    except requests.exceptions.RequestException as e:
        print(f"Error checking {ip}:{port}: {e}")
    except ValueError as ve:
        print(f"Error parsing JSON for {ip}:{port}: {ve}")
    return False

def main():
    input_file = os.getenv('IP_FILE', 'cek/file.txt')
    alive_file = 'cek/proxyList.txt'
    dead_file = 'cek/dead.txt'
    api_url_template = os.getenv('API_URL', 'https://api-check.web.id/check?ip={ip}:{port}')

    # Pastikan file output kosong sebelum menulis data baru
    open(alive_file, "w").close()
    open(dead_file, "w").close()

    try:
        with open(input_file, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        print(f"File {input_file} tidak ditemukan.")
        return

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [
            executor.submit(check_proxy, row, api_url_template, alive_file, dead_file)
            for row in rows if len(row) >= 2
        ]
        for future in as_completed(futures):
            future.result()  # Tunggu setiap proses selesai

    print(f"Semua proxy yang ALIVE telah disimpan di {alive_file}.")
    print(f"Semua proxy yang DEAD telah disimpan di {dead_file}.")

if __name__ == "__main__":
    main()
