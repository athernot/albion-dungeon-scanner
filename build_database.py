import json
import os

# --- Konfigurasi Sumber Data (Simulasi) ---
# Dalam implementasi nyata, ini bisa berupa URL atau path ke file yang diunduh
# dari ao-bin-dumps dan AlbionLocalization.
# Kita akan membuat file dummy untuk contoh ini.

DUMMY_MOB_DATA_FILE = 'dummy_mob_data.json'
DUMMY_LOCALIZATION_EN_FILE = 'dummy_localization_en.json'
DUMMY_LOCALIZATION_ID_FILE = 'dummy_localization_id.json' # Contoh untuk Bahasa Indonesia

DATABASE_OUTPUT_FILE = 'database.json'

# --- Fungsi Helper (Simulasi Parsing) ---

def create_dummy_data_files():
    """
    Membuat file data dummy untuk simulasi.
    Di dunia nyata, Anda akan mengunduh dan mem-parse data dari ao-bin-dumps/AlbionLocalization.
    """
    # Contoh data dari ao-bin-dumps (misalnya, monster)
    mob_data = {
        "UNIQUE_MOB_ID_AVALONIAN_ARCHER": {
            "ingame_id": "@MOB_AVALONIAN_ARCHER_T8", # Ini adalah kunci untuk lokalisasi
            "category": "MOB",
            "faction": "AVALONIAN",
            "display_type": "Archer" # Tipe umum untuk tampilan
        },
        "UNIQUE_MOB_ID_AVALONIAN_SPEARMAN": {
            "ingame_id": "@MOB_AVALONIAN_SPEARMAN_T8",
            "category": "MOB",
            "faction": "AVALONIAN",
            "display_type": "Spearman"
        },
        "UNIQUE_BOSS_ID_BASILISK": {
            "ingame_id": "@BOSS_AVALONIAN_BASILISK",
            "category": "BOSS",
            "faction": "AVALONIAN",
            "display_type": "Basilisk" # Bos bisa memiliki display_type sendiri
        },
        "CHEST_GREEN_STATIC_ID": { # Contoh ID untuk peti
            "ingame_id": "@CHEST_GREEN_STATIC", # Kunci lokalisasi untuk nama peti
            "category": "CHEST_NORMAL",
            "quality": "GREEN",
            "display_type": "Green Chest"
        }
    }
    with open(DUMMY_MOB_DATA_FILE, 'w') as f:
        json.dump(mob_data, f, indent=2)
    print(f"File dummy '{DUMMY_MOB_DATA_FILE}' telah dibuat.")

    # Contoh data dari AlbionLocalization (Inggris)
    localization_en = {
        "@MOB_AVALONIAN_ARCHER_T8": "Avalonian Archer",
        "@MOB_AVALONIAN_SPEARMAN_T8": "Avalonian Spearman",
        "@BOSS_AVALONIAN_BASILISK": "Basilisk",
        "@CHEST_GREEN_STATIC": "Green Chest"
    }
    with open(DUMMY_LOCALIZATION_EN_FILE, 'w') as f:
        json.dump(localization_en, f, indent=2)
    print(f"File dummy '{DUMMY_LOCALIZATION_EN_FILE}' telah dibuat.")

    # Contoh data dari AlbionLocalization (Bahasa Indonesia)
    localization_id = {
        "@MOB_AVALONIAN_ARCHER_T8": "Pemanah Avalon",
        "@MOB_AVALONIAN_SPEARMAN_T8": "Prajurit Tombak Avalon",
        "@BOSS_AVALONIAN_BASILISK": "Basilisk",
        "@CHEST_GREEN_STATIC": "Peti Hijau"
    }
    with open(DUMMY_LOCALIZATION_ID_FILE, 'w') as f:
        json.dump(localization_id, f, indent=2)
    print(f"File dummy '{DUMMY_LOCALIZATION_ID_FILE}' telah dibuat.")


def load_json_data(filepath):
    """Memuat data dari file JSON."""
    if not os.path.exists(filepath):
        print(f"Peringatan: File data '{filepath}' tidak ditemukan.")
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Gagal mem-parse JSON dari '{filepath}'.")
        return {}
    except Exception as e:
        print(f"Error saat memuat '{filepath}': {e}")
        return {}

# --- Logika Utama build_database.py ---

def build_database():
    """
    Membangun database.json dari sumber data yang telah diproses.
    """
    # Buat file dummy jika belum ada (hanya untuk keperluan demo ini)
    if not (os.path.exists(DUMMY_MOB_DATA_FILE) and \
            os.path.exists(DUMMY_LOCALIZATION_EN_FILE) and \
            os.path.exists(DUMMY_LOCALIZATION_ID_FILE)):
        print("Membuat file data dummy untuk pertama kali...")
        create_dummy_data_files()
        print("-" * 30)

    # 1. Muat data dari sumber (simulasi)
    #    Dalam implementasi nyata, ini akan melibatkan parsing XML/JSON dari ao-bin-dumps
    #    dan file lokalisasi.
    print(f"Memuat data master dari '{DUMMY_MOB_DATA_FILE}'...")
    master_data = load_json_data(DUMMY_MOB_DATA_FILE)

    print(f"Memuat lokalisasi EN dari '{DUMMY_LOCALIZATION_EN_FILE}'...")
    loc_en_data = load_json_data(DUMMY_LOCALIZATION_EN_FILE)

    print(f"Memuat lokalisasi ID dari '{DUMMY_LOCALIZATION_ID_FILE}'...")
    loc_id_data = load_json_data(DUMMY_LOCALIZATION_ID_FILE)

    if not master_data:
        print("Error: Data master tidak bisa dimuat. Proses build database dibatalkan.")
        return

    # 2. Proses dan gabungkan data
    output_database = {}
    print("\nMemproses entitas...")

    for internal_id, entity_props in master_data.items():
        ingame_loc_key = entity_props.get("ingame_id") # Kunci untuk mencari di file lokalisasi

        name_en = "Unknown"
        name_id = "Tidak Diketahui" # Default untuk Bahasa Indonesia

        if ingame_loc_key:
            name_en = loc_en_data.get(ingame_loc_key, f"Name not found for {ingame_loc_key}")
            name_id = loc_id_data.get(ingame_loc_key, f"Nama tidak ditemukan untuk {ingame_loc_key}")
        else:
            print(f"Peringatan: Entitas '{internal_id}' tidak memiliki 'ingame_id' untuk lokalisasi.")


        output_database[internal_id] = {
            "internal_id": internal_id,
            "name_en": name_en,
            "name_id": name_id,
            "category": entity_props.get("category", "UNKNOWN_CATEGORY"),
            "display_type": entity_props.get("display_type", name_en), # Default ke nama jika tidak ada display_type
            "faction": entity_props.get("faction", "UNKNOWN_FACTION"),
            # Tambahkan properti lain yang relevan jika ada
            # Misalnya, "quality" untuk peti, dll.
        }
        if "quality" in entity_props: # Khusus untuk entitas seperti peti
            output_database[internal_id]["quality"] = entity_props["quality"]

        print(f"  Processed: {internal_id} -> {name_en} / {name_id}")


    # 3. Tulis ke database.json
    try:
        with open(DATABASE_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_database, f, indent=2, ensure_ascii=False) # ensure_ascii=False untuk karakter non-ASCII
        print(f"\nDatabase berhasil dibangun dan disimpan di '{DATABASE_OUTPUT_FILE}'")
        print(f"Total entitas diproses: {len(output_database)}")
    except IOError:
        print(f"Error: Gagal menulis database ke '{DATABASE_OUTPUT_FILE}'.")
    except Exception as e:
        print(f"Error tidak terduga saat menulis database: {e}")


if __name__ == "__main__":
    print("Memulai proses build database...")
    build_database()
    print("\nProses build database selesai.")