# file: build_database.py

import os
import glob
import json
import xml.etree.ElementTree as ET
import configparser
from collections import Counter

# Import decrypter dari scanner yang sudah ada
from scanner.utils.binary import Binary
from scanner import TEMPLATE_FOLDERS # Menggunakan konstanta folder yang sudah ada

print("=========================================")
print("=== Albion Dungeon Database Builder ===")
print("=========================================")

CONFIG_FILE = "config.ini"
DATABASE_FILE = "database.json"

def get_albion_path():
    """Membaca path Albion dari config.ini."""
    if not os.path.exists(CONFIG_FILE):
        print(f"\n[ERROR] File '{CONFIG_FILE}' tidak ditemukan.")
        print("Harap jalankan gui.py setidaknya sekali untuk membuat file ini dan mengatur path Albion.")
        return None
    
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    path = config.get('Settings', 'ao-dir', fallback=None)
    if not path or not os.path.isdir(path):
        print(f"\n[ERROR] Path Albion di '{CONFIG_FILE}' tidak valid.")
        print(f"Path saat ini: {path}")
        return None
    
    return path

def main():
    albion_path = get_albion_path()
    if not albion_path:
        return

    templates_base_path = os.path.join(albion_path, r"Albion-Online_Data\StreamingAssets\GameData\templates")
    
    if not os.path.isdir(templates_base_path):
        print(f"\n[ERROR] Folder templates tidak ditemukan di: {templates_base_path}")
        return

    print(f"\n[*] Memulai pemindaian file game di: {templates_base_path}")
    
    all_game_ids = set()
    binary_decrypter = Binary().decrypter

    # Memindai semua folder template (GREEN, YELLOW, RED, dll.) untuk data yang lebih lengkap
    for folder in TEMPLATE_FOLDERS:
        dungeon_dir = os.path.join(templates_base_path, folder)
        if not os.path.isdir(dungeon_dir):
            continue

        print(f"    - Memindai folder '{folder}'...")
        bin_files = glob.glob(os.path.join(dungeon_dir, "*.bin"))

        for file_path in bin_files:
            try:
                decrypted_bytes = binary_decrypter.decrypt_binary_file(file_path)
                decrypted_str = decrypted_bytes.decode("utf-8", errors='ignore')
                root = ET.fromstring(decrypted_str)
                
                # Menemukan semua 'tile' yang memiliki atribut 'name'
                for tile in root.findall(".//tile[@name]"):
                    item_id_xml = tile.attrib.get("name", "")
                    if item_id_xml.startswith("SpawnPoint_"):
                        clean_id = item_id_xml.replace("SpawnPoint_", "")
                        all_game_ids.add(clean_id)

            except Exception as e:
                # Mengabaikan file yang tidak bisa didekripsi (misal: file master)
                pass

    if not all_game_ids:
        print("\n[ERROR] Tidak ada ID yang berhasil diekstrak dari file game.")
        return

    print(f"\n[*] Selesai! Ditemukan total {len(all_game_ids)} ID unik di semua file game.")

    # Membandingkan dengan database.json yang ada
    known_db_ids = set()
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            known_db_ids = set(data.get("translations", {}).keys())
        print(f"[*] Ditemukan {len(known_db_ids)} ID di file {DATABASE_FILE} saat ini.")
    else:
        print(f"[WARNING] File {DATABASE_FILE} tidak ditemukan. Semua ID akan dianggap baru.")

    newly_found_ids = all_game_ids - known_db_ids

    if not newly_found_ids:
        print("\n[SUCCESS] Selamat! Database Anda sudah sinkron dengan file game. Tidak ada ID baru yang ditemukan.")
        return

    print("\n-----------------------------------------")
    print(f"*** Ditemukan {len(newly_found_ids)} ID BARU yang belum ada di database.json: ***")
    
    # Kelompokkan berdasarkan tipe untuk memudahkan
    new_ids_by_type = {"CHEST": [], "BOSS": [], "MOB": [], "SHRINE": [], "OTHER": []}
    for new_id in sorted(list(newly_found_ids)):
        if "LOOTCHEST" in new_id:
            new_ids_by_type["CHEST"].append(new_id)
        elif "BOSS" in new_id:
            new_ids_by_type["BOSS"].append(new_id)
        elif "SHRINE" in new_id:
            new_ids_by_type["SHRINE"].append(new_id)
        elif "RANDOM" in new_id or "MOB" in new_id:
             new_ids_by_type["MOB"].append(new_id)
        else:
            new_ids_by_type["OTHER"].append(new_id)

    for type, ids in new_ids_by_type.items():
        if ids:
            print(f"\n--- Tipe: {type} ---")
            for id_to_add in ids:
                print(id_to_add)

    print("\n-----------------------------------------")
    print("\n[AKSI DIPERLUKAN]")
    print(f"Salin ID baru di atas dan tambahkan ke file '{DATABASE_FILE}' Anda di dalam objek 'translations'.")
    print("Gunakan format berikut untuk setiap ID:")
    print('\n"ID_BARU_DARI_SINI": ["Nama Tampilan", "❓", "TIPE"],')
    print("\nContoh:")
    print('"RANDOM_HERETIC_SOLO_GATHERER_ORE": ["Heretic Ore Gatherer", "⛏️", "MOB"],')
    print('\nTIP: Ganti TIPE dengan "CHEST", "DUNGEON_BOSS", "EVENT_BOSS", "SHRINE", atau "MOB".')


if __name__ == "__main__":
    main()