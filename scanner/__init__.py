# file: scanner/__init__.py

import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
import re # Untuk regex

# Utilitas dari proyek (pastikan path ini benar jika struktur folder Anda berbeda)
from scanner.utils.binary import Binary

DATABASE_FILE = 'database.json'
TRANSLATIONS = {}

# Definisi Tipe Entitas (untuk kejelasan)
TYPE_EVENT_BOSS = "EVENT_BOSS"
TYPE_DUNGEON_BOSS = "DUNGEON_BOSS"
TYPE_CHEST = "CHEST"
TYPE_SHRINE = "SHRINE"
TYPE_MOB = "MOB"

# Peta untuk mengelompokkan ID Peti ke kategori standar
CANONICAL_CHEST_MAP = {
    "LOOTCHEST_LEGENDARY": "LOOTCHEST_LEGENDARY",
    "LOOTCHEST_EPIC": "LOOTCHEST_EPIC",
    "LOOTCHEST_RARE": "LOOTCHEST_RARE",
    "LOOTCHEST_UNCOMMON": "LOOTCHEST_UNCOMMON",
    "LOOTCHEST_STANDARD": "LOOTCHEST_STANDARD",
    "LOOTCHEST_BOSS": "LOOTCHEST_BOSS",
    "LOOTCHEST_MINIBOSS": "LOOTCHEST_MINIBOSS",
    "BOOKCHEST_RARE": "BOOKCHEST_RARE", 
    "BOOKCHEST_UNCOMMON": "BOOKCHEST_UNCOMMON",
    "BOOKCHEST_STANDARD": "BOOKCHEST_STANDARD",
    "BOOKCHEST": "BOOKCHEST_STANDARD", 
    "LOOTCHEST": "LOOTCHEST_STANDARD"
}

# Peta untuk mengelompokkan ID Bos ke kategori standar
CANONICAL_BOSS_MAP = {
    "ENDBOSS": "BOSS_ENDBOSS_GENERIC",
    "MINIBOSS": "BOSS_MINIBOSS_GENERIC",
    "BOSS_HIGHLIGHT": "BOSS_HIGHLIGHT_GENERIC",
    "BOSS": "BOSS_GENERIC"
}

def load_translations():
    """Memuat definisi item dari database.json."""
    global TRANSLATIONS
    if not os.path.exists(DATABASE_FILE):
        print(f"DEBUG: File '{DATABASE_FILE}' tidak ditemukan. Membuat database awal...")
        initial_db_content = {
            "translations": {
                "LOOTCHEST_STANDARD": ["Peti Standar", "🟩", TYPE_CHEST],
                "LOOTCHEST_UNCOMMON": ["Peti Tidak Umum", "🟦", TYPE_CHEST],
                "LOOTCHEST_RARE": ["Peti Langka", "🟪", TYPE_CHEST],
                "LOOTCHEST_EPIC": ["Peti Epik", "🟨", TYPE_CHEST],
                "LOOTCHEST_LEGENDARY": ["Peti Legendaris", "🌟", TYPE_CHEST],
                "LOOTCHEST_BOSS": ["Peti Boss", "👑", TYPE_CHEST],
                "LOOTCHEST_MINIBOSS": ["Peti Miniboss", "🏆", TYPE_CHEST],
                "BOOKCHEST_STANDARD": ["Peti Buku Standar", "📚", TYPE_CHEST],
                "BOOKCHEST_UNCOMMON": ["Peti Buku Tidak Umum", "📚", TYPE_CHEST],
                "BOOKCHEST_RARE": ["Peti Buku Langka", "📚", TYPE_CHEST],
                "BOSS_ENDBOSS_GENERIC": ["Endboss Generik", "💀", TYPE_DUNGEON_BOSS],
                "BOSS_MINIBOSS_GENERIC": ["Miniboss Generik", "👻", TYPE_DUNGEON_BOSS],
                "BOSS_HIGHLIGHT_GENERIC": ["Boss Highlight Generik", "👹", TYPE_DUNGEON_BOSS],
                "BOSS_GENERIC": ["Boss Generik", "☠️", TYPE_DUNGEON_BOSS],
                "SHRINE_NON_COMBAT_BUFF": ["Altar Buff Umum", "✨", TYPE_SHRINE],
                "UNCLEFROST": ["Uncle Frost (Event)", "🥶", TYPE_EVENT_BOSS],
            }
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_db_content, f, indent=4, ensure_ascii=False)
        TRANSLATIONS = initial_db_content["translations"]
        print(f"DEBUG: Database awal dibuat dan dimuat dari {DATABASE_FILE}")
    else:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            TRANSLATIONS = data.get("translations", {})
        print(f"DEBUG: Database dimuat dari {DATABASE_FILE}. Total entri: {len(TRANSLATIONS)}")

load_translations() 

REWARD_LAYER_PATTERNS = ["reward", "chest", "loot", "encounter", "mob", "shrine"]
TEMPLATE_FOLDERS = ["GREEN", "YELLOW", "RED", "BLACK", "AVALON", "CORRUPTED", "HELLGATE", "EXPEDITION", "ROADS", "MISTS"]

class AlbionDungeonScanner:
    """Kelas utama untuk logika pemindaian dungeon."""
    def __init__(self, ao_dir_path: str) -> None:
        self.used_files = []
        self.base_path = ao_dir_path
        self.templates_base_path = os.path.join(self.base_path, r"Albion-Online_Data\StreamingAssets\GameData\templates")
        if not ao_dir_path or not os.path.isdir(ao_dir_path):
            raise ValueError(f"Path direktori Albion tidak valid atau tidak ditemukan: {ao_dir_path}")

    def get_dungeon_dirs(self):
        """Mendapatkan daftar direktori dungeon yang valid."""
        existing_dirs = []
        for folder_name in TEMPLATE_FOLDERS:
            path = os.path.join(self.templates_base_path, folder_name)
            if os.path.isdir(path):
                existing_dirs.append(path)
        if not existing_dirs:
            raise FileNotFoundError(f"Tidak ada folder template ({', '.join(TEMPLATE_FOLDERS)}) yang ditemukan di {self.templates_base_path}")
        return existing_dirs

    def check_and_restore_files(self, dungeon_dir: str):
        """Mendeteksi file yang digunakan dengan mencoba memindahkannya, lalu mengembalikannya."""
        temp_path = os.path.join(dungeon_dir, ".temp_scanner_check")
        if os.path.exists(temp_path):
            try:
                shutil.rmtree(temp_path)
            except OSError as e:
                print(f"DEBUG: Gagal menghapus folder temp lama: {e}")
        try:
            os.makedirs(temp_path, exist_ok=True)
        except OSError as e:
            print(f"DEBUG: Gagal membuat folder temp: {e}")
            return

        files_in_dir = glob.glob(os.path.join(dungeon_dir, "*.bin"))
        for file_path in files_in_dir:
            filename = os.path.basename(file_path)
            temp_file_path = os.path.join(temp_path, filename)
            try:
                shutil.move(file_path, temp_file_path)
                shutil.move(temp_file_path, file_path)
            except IOError: 
                self.used_files.append(file_path)
            except Exception as e:
                print(f"DEBUG: Error saat memeriksa file {filename}: {e}")
                if os.path.exists(temp_file_path) and not os.path.exists(file_path):
                    try:
                        shutil.move(temp_file_path, file_path)
                    except Exception as e_restore:
                         print(f"DEBUG: Gagal mengembalikan file {filename} dari temp: {e_restore}")
        try:
            shutil.rmtree(temp_path, ignore_errors=True)
        except OSError as e:
            print(f"DEBUG: Gagal menghapus folder temp akhir: {e}")

    def extract_tier_from_id(self, item_id: str) -> str:
        """Mengekstrak informasi Tier (misal: T4, T5) dari ID item."""
        clean_id = item_id.replace("SpawnPoint_", "").upper()
        match = re.match(r"T(\d+)_", clean_id)
        if match:
            return f"T{match.group(1)}"
        return "Unknown Tier"

    def classify_id(self, clean_id: str, item_id_upper_raw: str) -> tuple[str | None, str | None]:
        """Mengklasifikasikan ID bersih dan mengembalikan ID kanonis serta tipenya."""
        if clean_id in TRANSLATIONS:
            entry_type = TRANSLATIONS[clean_id][2] if len(TRANSLATIONS[clean_id]) == 3 else None
            if entry_type not in [TYPE_CHEST, TYPE_DUNGEON_BOSS, TYPE_EVENT_BOSS]:
                return clean_id, entry_type

        if "LOOTCHEST" in item_id_upper_raw or "BOOKCHEST" in item_id_upper_raw:
            for key, canonical_id in CANONICAL_CHEST_MAP.items():
                if key in item_id_upper_raw:
                    return canonical_id, TYPE_CHEST
            return CANONICAL_CHEST_MAP.get("LOOTCHEST" if "LOOTCHEST" in item_id_upper_raw else "BOOKCHEST"), TYPE_CHEST

        for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN"]:
            if event_key in item_id_upper_raw and event_key in TRANSLATIONS:
                return event_key, TYPE_EVENT_BOSS
        
        if "BOSS" in item_id_upper_raw:
            for key, canonical_id in CANONICAL_BOSS_MAP.items():
                if key in item_id_upper_raw:
                    return canonical_id, TYPE_DUNGEON_BOSS
            return CANONICAL_BOSS_MAP["BOSS"], TYPE_DUNGEON_BOSS

        if "SHRINE" in item_id_upper_raw:
            for db_id, entry_data in TRANSLATIONS.items():
                if len(entry_data) == 3 and entry_data[2] == TYPE_SHRINE and db_id in item_id_upper_raw:
                    return db_id, TYPE_SHRINE
            return "SHRINE_NON_COMBAT_BUFF", TYPE_SHRINE

        return None, None

    def run(self) -> dict | None:
        """Menjalankan proses pemindaian utama."""
        print("\nDEBUG: Memulai Pemindaian Baru (Mode Database Lokal)...")
        self.used_files = []
        for dir_path in self.get_dungeon_dirs():
            self.check_and_restore_files(dir_path)

        if not self.used_files:
            print("DEBUG: Tidak ada file yang digunakan terdeteksi (Tidak ada di dalam dungeon aktif?).")
            return None

        results = {
            TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(),
            TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(),
            "mobs_by_tier": {f"T{i}": Counter() for i in range(1, 9)},
            "exits": set()
        }
        results["mobs_by_tier"]["Unknown Tier"] = Counter()
        all_item_ids_from_xml = set()

        for file_path in self.used_files:
            filename = os.path.basename(file_path)
            if "EXIT" in filename.upper(): 
                results["exits"].add(filename)
            if any(skip.upper() in filename.upper() for skip in ["BACKDROP", "MASTER", "EXIT", "LIGHT", "DECORATION", "TERRAIN"]):
                continue
            try:
                decrypted_str = Binary().decrypter.decrypt_binary_file(file_path).decode("utf-8", errors='replace')
                root = ET.fromstring(decrypted_str)
                for layer_node in root.findall(".//layer"):
                    layer_name = layer_node.attrib.get("name", "").lower()
                    if any(pattern in layer_name for pattern in REWARD_LAYER_PATTERNS):
                        for tile in layer_node.findall(".//tile[@name]"):
                            item_id_xml = tile.attrib["name"]
                            if item_id_xml.startswith("SpawnPoint_"):
                                all_item_ids_from_xml.add(item_id_xml)
            except ET.ParseError as e_xml:
                print(f"DEBUG: XML Parse Error di {file_path}: {e_xml}")
            except Exception as e:
                print(f"DEBUG: Error saat memproses file {file_path}: {e}")
        
        if not all_item_ids_from_xml:
            print("DEBUG: Tidak ada ID SpawnPoint yang relevan ditemukan dari file XML.")
        else:
            print(f"DEBUG: Total ID unik dari XML ({len(all_item_ids_from_xml)}): {sorted(list(all_item_ids_from_xml))}")

        for item_id_xml in all_item_ids_from_xml:
            clean_id = item_id_xml.replace("SpawnPoint_", "")
            item_id_upper_raw = clean_id.upper()

            canonical_id, item_type = self.classify_id(clean_id, item_id_upper_raw)

            if item_type and canonical_id:
                if item_type in results:
                    results[item_type].update([canonical_id])
            # --- PERBAIKAN SYNTAX ERROR DI SINI ---
            elif any(faction in item_id_upper_raw for faction in ["RANDOM", "MOB", "KEEPER", "HERETIC", "MORGANA", "UNDEAD", "AVALONIAN"]):
                tier = self.extract_tier_from_id(clean_id)
                results["mobs_by_tier"].setdefault(tier, Counter()).update([clean_id])
            else:
                pass

        for file_path in self.used_files:
            fn_upper = os.path.basename(file_path).upper()
            if "UNCLEFROST" in fn_upper and "UNCLEFROST" not in results[TYPE_EVENT_BOSS] and "UNCLEFROST" in TRANSLATIONS:
                results[TYPE_EVENT_BOSS].update(["UNCLEFROST"])
            if "ANNIVERSARY_TITAN" in fn_upper and "ANNIVERSARY_TITAN" not in results[TYPE_EVENT_BOSS] and "ANNIVERSARY_TITAN" in TRANSLATIONS:
                results[TYPE_EVENT_BOSS].update(["ANNIVERSARY_TITAN"])
        
        print(f"DEBUG Hasil Akhir: EventBosses: {results[TYPE_EVENT_BOSS]}, DungeonBosses: {results[TYPE_DUNGEON_BOSS]}, Chests: {results[TYPE_CHEST]}, Shrines: {results[TYPE_SHRINE]}, MobsByTier: {results['mobs_by_tier']}, Exits: {len(results['exits'])}")
        
        final_results = {
            "event_bosses": results[TYPE_EVENT_BOSS],
            "dungeon_bosses": results[TYPE_DUNGEON_BOSS],
            "chests": results[TYPE_CHEST],
            "shrines": results[TYPE_SHRINE],
            "mobs_by_tier": results["mobs_by_tier"],
            "exits": results["exits"],
            "used_files": self.used_files,
        }
        return final_results