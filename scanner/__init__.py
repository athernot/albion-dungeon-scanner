# file: scanner/__init__.py

import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
# import requests # Dihapus karena API tidak digunakan lagi
import time # Tetap digunakan untuk struktur database, bisa dihapus jika tidak ingin timestamp
import re

from scanner.utils.binary import Binary

DATABASE_FILE = 'database.json'
TRANSLATIONS = {}
# UPDATE_COOLDOWN_SECONDS = 24 * 60 * 60 # Dihapus
# LAST_API_UPDATE_TIMESTAMPS = {} # Dihapus
# API_RELEVANT_KEYWORDS = ["LOOTCHEST", "SHRINE", "BOSS", "UNCLEFROST", "ANNIVERSARY_TITAN"] # Dihapus

TYPE_EVENT_BOSS = "EVENT_BOSS"
TYPE_DUNGEON_BOSS = "DUNGEON_BOSS"
TYPE_CHEST = "CHEST"
TYPE_SHRINE = "SHRINE"
TYPE_MOB = "MOB"

CANONICAL_CHEST_MAP = {
    "LOOTCHEST_LEGENDARY": "LOOTCHEST_LEGENDARY",
    "LOOTCHEST_EPIC": "LOOTCHEST_EPIC",
    "LOOTCHEST_RARE": "LOOTCHEST_RARE",
    "LOOTCHEST_UNCOMMON": "LOOTCHEST_UNCOMMON",
    "LOOTCHEST_STANDARD": "LOOTCHEST_STANDARD",
    "LOOTCHEST_BOSS": "LOOTCHEST_BOSS",
    "LOOTCHEST_MINIBOSS": "LOOTCHEST_MINIBOSS",
    "LOOTCHEST": "LOOTCHEST_STANDARD"
}

CANONICAL_BOSS_MAP = {
    "ENDBOSS": "BOSS_ENDBOSS_GENERIC",
    "MINIBOSS": "BOSS_MINIBOSS_GENERIC",
    "BOSS_HIGHLIGHT": "BOSS_HIGHLIGHT_GENERIC",
    "BOSS": "BOSS_GENERIC"
}

def load_translations():
    global TRANSLATIONS # LAST_API_UPDATE_TIMESTAMPS Dihapus
    if not os.path.exists(DATABASE_FILE):
        initial_db_content = {
            "translations": {
                # Contoh entri awal, sesuaikan dengan yang Anda inginkan
                "UNCLEFROST": ["Uncle Frost (Winter Event)", "🥶", "EVENT_BOSS"],
                "ANNIVERSARY_TITAN": ["Anniversary Titan (Anniversary Event)", "⚔️", "EVENT_BOSS"],
                "LOOTCHEST_STANDARD": ["Peti Biasa", "🟩", "CHEST"],
                "LOOTCHEST_UNCOMMON": ["Peti Tidak Biasa", "🟦", "CHEST"],
                "LOOTCHEST_RARE": ["Peti Langka", "🟪", "CHEST"],
                "LOOTCHEST_EPIC": ["Peti Epik", "🟨", "CHEST"],
                "LOOTCHEST_LEGENDARY": ["Peti Legendaris", "🌟", "CHEST"],
                "LOOTCHEST_BOSS": ["Peti Boss", "👑", "CHEST"],
                "LOOTCHEST_MINIBOSS": ["Peti Miniboss", "🏆", "CHEST"],
                "BOSS_MINIBOSS_GENERIC": ["Miniboss", "👻", "DUNGEON_BOSS"],
                "BOSS_ENDBOSS_GENERIC": ["Endboss", "💀", "DUNGEON_BOSS"],
                "BOSS_HIGHLIGHT_GENERIC": ["Boss (Highlight)", "👹", "DUNGEON_BOSS"],
                "BOSS_GENERIC": ["Boss", "☠️", "DUNGEON_BOSS"],
                "SHRINE_NON_COMBAT_BUFF": ["Altar Buff Non-Tempur Umum", "✨", "SHRINE"]
                # Tambahkan ID kanonis lainnya dan ID penting di sini
            }
            # "timestamps": {} # Timestamps tidak lagi relevan jika API tidak digunakan
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_db_content, f, indent=4, ensure_ascii=False)
        TRANSLATIONS = initial_db_content["translations"]
        # LAST_API_UPDATE_TIMESTAMPS = initial_db_content.get("timestamps", {}) # Dihapus
        print(f"DEBUG: Database awal dibuat di {DATABASE_FILE}")
    else:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            TRANSLATIONS = data.get("translations", {})
            # LAST_API_UPDATE_TIMESTAMPS = data.get("timestamps", {}) # Dihapus
        print(f"DEBUG: Database dimuat dari {DATABASE_FILE}")

def save_translations(): # Fungsi ini bisa jadi tidak diperlukan lagi jika database hanya di-load
    # Namun, kita biarkan jika ada rencana pengembangan lain
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        # Hanya simpan translations, tanpa timestamps
        json.dump({"translations": TRANSLATIONS}, f, indent=4, ensure_ascii=False)

# Fungsi fetch_and_update_id_from_api DIHAPUS SELURUHNYA

load_translations()

REWARD_LAYER_PATTERNS = ["reward_solo", "reward_group", "reward_avalonian", "chest", "loot", "reward", "encounter", "mob", "shrine"]
TEMPLATE_FOLDERS = ["GREEN", "YELLOW", "RED", "BLACK", "AVALON", "CORRUPTED", "HELLGATE", "EXPEDITION", "ROADS"]

class AlbionDungeonScanner:
    def __init__(self, ao_dir_path: str) -> None:
        self.used_files = []
        self.base_path = ao_dir_path
        self.templates_base_path = os.path.join(self.base_path, r"Albion-Online_Data\StreamingAssets\GameData\templates")
        if not ao_dir_path or not os.path.isdir(ao_dir_path):
            raise ValueError(f"Path direktori Albion tidak valid atau tidak ditemukan: {ao_dir_path}")

    def get_dungeon_dirs(self):
        existing_dirs = []
        for folder in TEMPLATE_FOLDERS:
            path = os.path.join(self.templates_base_path, folder)
            if os.path.isdir(path):
                existing_dirs.append(path)
        if not existing_dirs:
            raise FileNotFoundError(f"Tidak ada folder template yang ditemukan di {self.templates_base_path}")
        return existing_dirs

    def check_and_restore_files(self, dungeon_dir):
        temp_path = os.path.join(dungeon_dir, ".temp")
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path)
        os.makedirs(temp_path, exist_ok=True)
        files_in_dir = glob.glob(os.path.join(dungeon_dir, "*.bin"))
        for file_path in files_in_dir:
            filename = os.path.basename(file_path)
            try:
                shutil.move(file_path, os.path.join(temp_path, filename))
            except IOError:
                self.used_files.append(file_path)
            except Exception:
                pass
            if os.path.exists(os.path.join(temp_path, filename)):
                try:
                    shutil.move(os.path.join(temp_path, filename), file_path)
                except Exception:
                    pass
        shutil.rmtree(temp_path, ignore_errors=True)

    def extract_tier_from_id(self, item_id_xml_or_clean_id):
        id_to_check = item_id_xml_or_clean_id.replace("SpawnPoint_", "")
        match = re.match(r"T(\d+)_", id_to_check.upper())
        if match:
            return f"T{match.group(1)}"
        match_mob = re.search(r"_T(\d+)", id_to_check.upper())
        if match_mob:
            return f"T{match_mob.group(1)}"
        return "Unknown Tier"

    def run(self) -> dict:
        print("\nDEBUG: Memulai Pemindaian Baru (Mode Database Lokal)...")
        self.used_files = []
        for dir_path in self.get_dungeon_dirs():
            self.check_and_restore_files(dir_path)

        if not self.used_files:
            print("DEBUG: Tidak ada file yang digunakan terdeteksi.")
            return None

        found_event_bosses, found_dungeon_bosses, found_chests, found_shrines = [], [], [], []
        mobs_by_tier_counters = {f"T{i}": Counter() for i in range(1, 9)}
        mobs_by_tier_counters["Unknown Tier"] = Counter()
        found_exits_filenames, all_item_ids_from_xml = [], set()

        for file_path in self.used_files:
            filename = os.path.basename(file_path)
            if "EXIT" in filename.upper():
                found_exits_filenames.append(filename)
            if any(skip.upper() in filename.upper() for skip in ["BACKDROP", "MASTER", "EXIT"]):
                continue
            try:
                decrypted_str = Binary().decrypter.decrypt_binary_file(file_path).decode("utf-8", errors='ignore')
                root = ET.fromstring(decrypted_str)
                for layer_node in root.findall(".//layer"):
                    if any(p in layer_node.attrib.get("name", "").lower() for p in REWARD_LAYER_PATTERNS):
                        for tile in layer_node.findall(".//tile"):
                            if item_id_xml := tile.attrib.get("name"):
                                all_item_ids_from_xml.add(item_id_xml)
            except Exception:
                pass
        
        if all_item_ids_from_xml:
             print(f"DEBUG: Daftar ID unik dari XML ({len(all_item_ids_from_xml)}): {sorted(list(all_item_ids_from_xml))}")

        for item_id_xml in all_item_ids_from_xml:
            if not item_id_xml:
                continue
            
            # Panggilan ke fetch_and_update_id_from_api DIHAPUS
            
            clean_id = item_id_xml.replace("SpawnPoint_", "")
            item_id_upper = item_id_xml.upper().replace("SPAWNPOINT_", "") # Gunakan item_id_xml untuk cek kata kunci
            classified = False

            if clean_id in TRANSLATIONS:
                entry = TRANSLATIONS[clean_id]
                item_type = entry[2] if len(entry) == 3 else None
                if item_type == TYPE_EVENT_BOSS:
                    found_event_bosses.append(clean_id); classified = True
                elif item_type == TYPE_DUNGEON_BOSS:
                    found_dungeon_bosses.append(clean_id); classified = True
                elif item_type == TYPE_SHRINE:
                    found_shrines.append(clean_id); classified = True
                elif item_type == TYPE_CHEST:
                    # Langsung gunakan clean_id karena sudah pasti ada di TRANSLATIONS
                    # Atau, jika ingin tetap menggunakan pemetaan kanonis untuk konsistensi internal:
                    mapped_to_canonical = False
                    for key_map, canonical_id_map in CANONICAL_CHEST_MAP.items():
                        if key_map in item_id_upper: # Cek item_id_upper (dari SpawnPoint_...)
                            found_chests.append(canonical_id_map)
                            mapped_to_canonical = True
                            break
                    if not mapped_to_canonical: # Fallback jika ID ada di DB tapi tidak cocok map kanonis
                         found_chests.append(clean_id) # Atau CANONICAL_CHEST_MAP["LOOTCHEST"]
                    classified = True
            if classified:
                continue

            if "LOOTCHEST" in item_id_upper:
                for key, cid in CANONICAL_CHEST_MAP.items():
                    if key in item_id_upper:
                        found_chests.append(cid); classified = True; break
                if classified: continue
            
            if "SHRINE" in item_id_upper:
                # Cek apakah ada ID shrine spesifik di DB
                shrine_id_to_add = "SHRINE_NON_COMBAT_BUFF" # Default
                for db_shrine_id, (name, icon, type_val) in TRANSLATIONS.items():
                    if type_val == TYPE_SHRINE and db_shrine_id in item_id_upper:
                        shrine_id_to_add = db_shrine_id
                        break
                found_shrines.append(shrine_id_to_add)
                classified = True; continue

            if "BOSS" in item_id_upper: # Termasuk MINIBOSS, ENDBOSS, dll.
                boss_id_to_add = clean_id # Default jika tidak ada pemetaan
                # Cek event boss spesifik dulu
                is_event_boss = False
                for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN"]: # Tambahkan ID event boss spesifik lain jika ada
                    if event_key in item_id_upper:
                        if event_key in TRANSLATIONS: # Pastikan ada di DB
                           found_event_bosses.append(event_key)
                           is_event_boss = True; classified = True; break
                if is_event_boss: continue

                # Jika bukan event boss, coba peta kanonis dungeon boss
                for key, cid in CANONICAL_BOSS_MAP.items():
                    if key in item_id_upper:
                        if cid in TRANSLATIONS: # Pastikan ID kanonis ada di DB
                            found_dungeon_bosses.append(cid)
                            classified = True; break
                if not classified: # Jika tidak ada di peta kanonis, tambahkan sebagai ID unik (akan jadi "ID: clean_id")
                    if clean_id not in TRANSLATIONS: # Hanya jika benar2 baru dan tidak dikenal
                         print(f"DEBUG: Dungeon Boss ID tidak dikenal & tidak ada di DB: {clean_id}")
                    found_dungeon_bosses.append(clean_id) # Akan ditampilkan sbg "ID: xxx" jika tdk di DB
                    classified = True # Tetap diklasifikasikan sebagai dungeon boss
                if classified: continue
            
            if not classified and any(f in item_id_upper for f in ["RANDOM", "MOB", "KEEPER", "HERETIC", "MORGANA", "UNDEAD", "AVALONIAN"]):
                mobs_by_tier_counters.setdefault(self.extract_tier_from_id(clean_id), Counter()).update([clean_id])

        for file_path in self.used_files:
            fn_upper = os.path.basename(file_path).upper()
            if "UNCLEFROST" in fn_upper and "UNCLEFROST" not in found_event_bosses and "UNCLEFROST" in TRANSLATIONS:
                found_event_bosses.append("UNCLEFROST")
            if "ANNIVERSARY_TITAN" in fn_upper and "ANNIVERSARY_TITAN" not in found_event_bosses and "ANNIVERSARY_TITAN" in TRANSLATIONS:
                found_event_bosses.append("ANNIVERSARY_TITAN")
        
        print(f"DEBUG Hasil Akhir: EventBosses: {Counter(found_event_bosses)}, DungeonBosses: {Counter(found_dungeon_bosses)}, Chests: {Counter(found_chests)}, Shrines: {Counter(found_shrines)}, MobsByTier: {mobs_by_tier_counters}, Exits: {len(found_exits_filenames)}")
        
        return {
            "event_bosses": Counter(found_event_bosses), "dungeon_bosses": Counter(found_dungeon_bosses),
            "chests": Counter(found_chests), "shrines": Counter(found_shrines),
            "mobs_by_tier": mobs_by_tier_counters, "exits": set(found_exits_filenames),
            "used_files": self.used_files,
        }