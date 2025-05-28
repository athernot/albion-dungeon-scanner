# file: build_database.py

import os
import glob
import json
import xml.etree.ElementTree as ET
import configparser
import re # Import modul regex

# Import decrypter dari scanner yang sudah ada
from scanner.utils.binary import Binary
from scanner import TEMPLATE_FOLDERS # Menggunakan konstanta folder yang sudah ada

print("=========================================")
print("=== Albion Dungeon Database Builder ===")
print("=========================================")

CONFIG_FILE = "config.ini"
DATABASE_FILE = "database.json"
MIN_TIER_TO_REPORT = 6 # Hanya laporkan ID baru untuk Tier 6 ke atas

def get_albion_path():
    """Membaca path Albion dari config.ini."""
    if not os.path.exists(CONFIG_FILE):
        print(f"\n[ERROR] File '{CONFIG_FILE}' tidak ditemukan.")
        print("Harap jalankan GUI setidaknya sekali untuk membuat file ini dan mengatur path Albion.")
        return None
    
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    path = config.get('Settings', 'ao-dir', fallback=None)
    if not path or not os.path.isdir(path):
        print(f"\n[ERROR] Path Albion di '{CONFIG_FILE}' tidak valid.")
        print(f"Path saat ini: {path}")
        return None
    
    return path

def extract_tier_from_id(item_id: str) -> int | None:
    """
    Mengekstrak informasi Tier numerik dari ID item.
    Contoh: "T6_MOB_..." akan mengembalikan 6.
    Mengembalikan None jika tidak ada pola Tier yang ditemukan.
    """
    match = re.match(r"T(\d+)_", item_id.upper())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None

def generate_suggested_name(clean_id: str) -> str:
    """
    Menghasilkan nama tampilan yang disarankan dari ID yang bersih.
    Contoh: RANDOM_AVALON_ELITE_BOSS_CRYSTAL_BASILISK -> Avalon Elite Boss Crystal Basilisk
    """
    name = clean_id
    # Hapus prefiks umum yang tidak deskriptif
    if name.startswith("RANDOM_"):
        name = name[7:]
    
    # Hapus prefiks Tier karena Tier akan ditangani secara terpisah
    name = re.sub(r"^T\d+_", "", name)

    # Ganti garis bawah dengan spasi
    name = name.replace("_", " ")

    # Ubah menjadi Title Case (huruf kapital di awal setiap kata)
    name = name.title()
    
    # Perbaikan untuk akronim umum atau istilah spesifik
    name = name.replace(" Cd ", " CD ") # Contoh: Corrupted Dungeon
    name = name.replace(" Hce ", " HCE ") # Contoh: Hardcore Expedition
    name = name.replace(" Rd ", " RD ")   # Contoh: Randomized Dungeon
    name = name.replace(" Poi ", " POI ") # Contoh: Point of Interest

    # Hapus spasi berlebih yang mungkin muncul
    name = ' '.join(name.split())
    
    return name

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
                
                for tile in root.findall(".//tile[@name]"):
                    item_id_xml = tile.attrib.get("name", "")
                    if item_id_xml.startswith("SpawnPoint_"):
                        clean_id = item_id_xml.replace("SpawnPoint_", "")
                        all_game_ids.add(clean_id)
            except Exception:
                pass # Abaikan file yang gagal diproses

    if not all_game_ids:
        print("\n[ERROR] Tidak ada ID yang berhasil diekstrak dari file game.")
        return

    print(f"\n[*] Selesai! Ditemukan total {len(all_game_ids)} ID unik di semua file game.")

    known_db_ids = set()
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                known_db_ids = set(data.get("translations", {}).keys())
            except json.JSONDecodeError:
                print(f"[WARNING] Gagal membaca {DATABASE_FILE}. File mungkin korup.")
        print(f"[*] Ditemukan {len(known_db_ids)} ID di file {DATABASE_FILE} saat ini.")
    else:
        print(f"[WARNING] File {DATABASE_FILE} tidak ditemukan. Semua ID akan dianggap baru.")

    newly_found_ids_unfiltered = all_game_ids - known_db_ids
    
    if not newly_found_ids_unfiltered:
        print("\n[SUCCESS] Database Anda sudah sinkron. Tidak ada ID baru yang ditemukan.")
        return

    print(f"\n[*] Total ID baru yang belum difilter: {len(newly_found_ids_unfiltered)}")
    print(f"[*] Menerapkan filter untuk Tier {MIN_TIER_TO_REPORT} ke atas (atau tanpa info Tier eksplisit pada ID)...")

    newly_found_ids_filtered = set()
    for new_id in newly_found_ids_unfiltered:
        tier = extract_tier_from_id(new_id)
        # Sertakan ID jika tidak ada info Tier eksplisit ATAU jika Tier >= MIN_TIER_TO_REPORT
        if tier is None or tier >= MIN_TIER_TO_REPORT:
            newly_found_ids_filtered.add(new_id)
    
    if not newly_found_ids_filtered:
        print(f"\n[INFO] Tidak ada ID baru yang memenuhi kriteria Tier {MIN_TIER_TO_REPORT}+ (atau tanpa info Tier).")
        return

    print("\n--------------------------------------------------------------------------")
    print(f"*** Ditemukan {len(newly_found_ids_filtered)} ID BARU (Tier {MIN_TIER_TO_REPORT}+ atau Tanpa Info Tier) yang belum ada di {DATABASE_FILE}: ***")
    
    new_ids_by_type_for_display = {"CHEST": [], "BOSS": [], "MOB": [], "SHRINE": [], "OTHER": []}
    
    for new_id in sorted(list(newly_found_ids_filtered)):
        suggested_name = generate_suggested_name(new_id)
        tier_num = extract_tier_from_id(new_id)
        tier_str = f" (Tier: T{tier_num})" if tier_num is not None else " (Tier: N/A)"
        
        display_entry = (new_id, suggested_name, tier_str)

        if "LOOTCHEST" in new_id.upper() or "BOOKCHEST" in new_id.upper():
            new_ids_by_type_for_display["CHEST"].append(display_entry)
        elif "BOSS" in new_id.upper() or "ENDBOSS" in new_id.upper() or "MINIBOSS" in new_id.upper():
            new_ids_by_type_for_display["BOSS"].append(display_entry)
        elif "SHRINE" in new_id.upper():
            new_ids_by_type_for_display["SHRINE"].append(display_entry)
        elif "MOB" in new_id.upper() or "RANDOM" in new_id.upper() or "KEEPER" in new_id.upper() or "HERETIC" in new_id.upper() or "MORGANA" in new_id.upper() or "UNDEAD" in new_id.upper() or "AVALON" in new_id.upper():
            new_ids_by_type_for_display["MOB"].append(display_entry)
        else:
            new_ids_by_type_for_display["OTHER"].append(display_entry)

    for type_category, id_entries in new_ids_by_type_for_display.items():
        if id_entries:
            print(f"\n--- Tipe Kategori: {type_category} ---")
            for id_val, name_val, tier_info in id_entries:
                print(f"ID          : {id_val}")
                print(f"Nama Saran  : {name_val}{tier_info}")
                print(f"Contoh JSON : \"{id_val}\": [\"{name_val}\", \"❓\", \"{type_category if type_category != 'OTHER' else 'MOB'}\"],")
                print("-" * 40)


    print("\n--------------------------------------------------------------------------")
    print("\n[AKSI DIPERLUKAN]")
    print(f"Salin ID baru di atas dan tambahkan ke file '{DATABASE_FILE}' Anda di dalam objek 'translations'.")
    print("Gunakan format JSON yang disarankan untuk setiap ID.")
    print("Sesuaikan \"Nama Saran\", ikon \"❓\", dan \"TIPE_KATEGORI\" jika diperlukan.")
    print('\nTIP: Tipe yang umum adalah "CHEST", "DUNGEON_BOSS", "EVENT_BOSS", "SHRINE", atau "MOB".')

if __name__ == "__main__":
    main()
