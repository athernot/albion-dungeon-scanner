# file: scanner/__init__.py

import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
import re # Pastikan re diimpor
import logging

# Impor instance manager dan dapatkan logger untuk modul ini
from scanner.utils.logging import logging_manager
from scanner.utils.binary import Binary

logger = logging_manager.get_logger(__name__)

# --- Konstanta ---
DATABASE_FILE = 'database.json'
TRANSLATIONS = {}
MIN_MOB_TIER_TO_SCAN = 6 # Hanya proses mob Tier 6 ke atas

# Definisi Tipe Entitas
TYPE_EVENT_BOSS = "EVENT_BOSS"
TYPE_DUNGEON_BOSS = "DUNGEON_BOSS"
TYPE_CHEST = "CHEST"
TYPE_SHRINE = "SHRINE"
TYPE_MOB = "MOB"

# Peta untuk kanonisasi ID (membuat ID generik dari ID spesifik)
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

CANONICAL_BOSS_MAP = {
    "ENDBOSS": "BOSS_ENDBOSS_GENERIC",
    "MINIBOSS": "BOSS_MINIBOSS_GENERIC",
    "BOSS_HIGHLIGHT": "BOSS_HIGHLIGHT_GENERIC",
    "BOSS": "BOSS_GENERIC"
}

# Daftar folder template yang akan dipindai
TEMPLATE_FOLDERS = ["GREEN", "YELLOW", "RED", "BLACK", "AVALON", "CORRUPTED", "HELLGATE", "EXPEDITION", "ROADS", "MISTS"]
# Daftar kata kunci untuk layer yang relevan di dalam file XML
REWARD_LAYER_PATTERNS = ["reward", "chest", "loot", "encounter", "mob", "shrine"]
# Daftar faksi mob untuk klasifikasi fallback
MOB_FACTION_KEYWORDS = ["RANDOM", "MOB", "KEEPER", "HERETIC", "MORGANA", "UNDEAD", "AVALON", "AVALONIAN"]


def load_translations():
    """Memuat definisi item dari database.json ke dalam memori."""
    global TRANSLATIONS
    if not os.path.exists(DATABASE_FILE):
        logger.warning(f"File '{DATABASE_FILE}' tidak ditemukan. Beberapa nama item mungkin tidak tampil.")
        TRANSLATIONS = {}
        return

    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            TRANSLATIONS = data.get("translations", {})
        logger.info(f"Database dimuat dari {DATABASE_FILE}. Total entri: {len(TRANSLATIONS)}")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Gagal memuat atau membaca file database '{DATABASE_FILE}': {e}")
        TRANSLATIONS = {}

load_translations()


class AlbionDungeonScanner:
    """Kelas utama untuk logika pemindaian dungeon."""
    def __init__(self, ao_dir_path: str) -> None:
        if not ao_dir_path or not os.path.isdir(ao_dir_path):
            raise ValueError(f"Path direktori Albion tidak valid: {ao_dir_path}")
        self.base_path = ao_dir_path
        self.templates_base_path = os.path.join(self.base_path, r"Albion-Online_Data\StreamingAssets\GameData\templates")
        self.used_files = []
        self.binary_decrypter = Binary().decrypter

    def _get_dungeon_dirs(self) -> list[str]:
        """Mendapatkan daftar direktori dungeon yang ada berdasarkan TEMPLATE_FOLDERS."""
        existing_dirs = [os.path.join(self.templates_base_path, folder) for folder in TEMPLATE_FOLDERS if os.path.isdir(os.path.join(self.templates_base_path, folder))]
        if not existing_dirs:
            raise FileNotFoundError(f"Tidak ada folder template yang ditemukan di {self.templates_base_path}")
        return existing_dirs

    def _find_active_dungeon_files(self):
        """Mendeteksi file dungeon yang aktif dengan mencoba memindahkannya."""
        self.used_files = []
        for dungeon_dir in self._get_dungeon_dirs():
            temp_path = os.path.join(dungeon_dir, ".temp_scanner_check")
            os.makedirs(temp_path, exist_ok=True)

            bin_files = glob.glob(os.path.join(dungeon_dir, "*.bin"))
            for file_path in bin_files:
                filename = os.path.basename(file_path)
                temp_file_path = os.path.join(temp_path, filename)
                try:
                    shutil.move(file_path, temp_file_path)
                    shutil.move(temp_file_path, file_path)
                except IOError:
                    self.used_files.append(file_path)
                    logger.info(f"File aktif terdeteksi: {filename}")
                except Exception as e:
                    logger.error(f"Error saat memeriksa file {filename}: {e}")
                    if os.path.exists(temp_file_path) and not os.path.exists(file_path):
                        shutil.move(temp_file_path, file_path)
            
            shutil.rmtree(temp_path, ignore_errors=True)

    def _extract_tier_from_id(self, item_id: str) -> int | None:
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

    def _classify_entity(self, clean_id: str) -> tuple[str | None, str | None]:
        """
        Mengklasifikasikan entitas berdasarkan ID-nya.
        Mengembalikan tuple (canonical_id, item_type).
        """
        item_id_upper = clean_id.upper()

        if clean_id in TRANSLATIONS:
            entry = TRANSLATIONS[clean_id]
            if len(entry) >= 3:
                return clean_id, entry[2] 

        if "LOOTCHEST" in item_id_upper or "BOOKCHEST" in item_id_upper:
            for key, canonical_id in CANONICAL_CHEST_MAP.items():
                if key in item_id_upper:
                    return canonical_id, TYPE_CHEST
            return CANONICAL_CHEST_MAP.get("LOOTCHEST"), TYPE_CHEST

        if "BOSS" in item_id_upper:
            for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN", "EVENT_WINTER"]: # Tambahkan event key jika perlu
                if event_key in item_id_upper:
                    # Coba dapatkan nama yang lebih spesifik jika ada di TRANSLATIONS
                    if clean_id in TRANSLATIONS and TRANSLATIONS[clean_id][2] == TYPE_EVENT_BOSS:
                        return clean_id, TYPE_EVENT_BOSS
                    return event_key, TYPE_EVENT_BOSS # Fallback ke key generik event
            
            for key, canonical_id in CANONICAL_BOSS_MAP.items():
                if key in item_id_upper:
                     # Coba dapatkan nama yang lebih spesifik jika ada di TRANSLATIONS
                    if clean_id in TRANSLATIONS and TRANSLATIONS[clean_id][2] == TYPE_DUNGEON_BOSS:
                        return clean_id, TYPE_DUNGEON_BOSS
                    return canonical_id, TYPE_DUNGEON_BOSS
            return CANONICAL_BOSS_MAP["BOSS"], TYPE_DUNGEON_BOSS

        if "SHRINE" in item_id_upper:
            return "SHRINE_NON_COMBAT_BUFF", TYPE_SHRINE

        if any(faction in item_id_upper for faction in MOB_FACTION_KEYWORDS):
            return clean_id, TYPE_MOB

        return None, None

    def run(self) -> dict | None:
        """Menjalankan proses pemindaian utama."""
        logger.info("Memulai pemindaian baru...")
        self._find_active_dungeon_files()

        if not self.used_files:
            logger.warning("Tidak ada file dungeon aktif terdeteksi. Pastikan Anda berada di dalam dungeon.")
            return None

        results = {
            TYPE_EVENT_BOSS: Counter(),
            TYPE_DUNGEON_BOSS: Counter(),
            TYPE_CHEST: Counter(),
            TYPE_SHRINE: Counter(),
            "mobs_by_tier": {},
            "exits": set(),
            "used_files": self.used_files,
        }
        all_item_ids_from_xml = set()

        for file_path in self.used_files:
            filename = os.path.basename(file_path)
            if "EXIT" in filename.upper() or "ENTER" in filename.upper():
                results["exits"].add(filename)
            
            if any(skip.upper() in filename.upper() for skip in ["BACKDROP", "MASTER", "EXIT", "ENTER", "LIGHT", "DECORATION", "TERRAIN"]):
                continue

            try:
                decrypted_bytes = self.binary_decrypter.decrypt_binary_file(file_path)
                decrypted_str = decrypted_bytes.decode("utf-8", errors='ignore')
                root = ET.fromstring(decrypted_str)
                
                for layer_node in root.findall(".//layer"):
                    layer_name = layer_node.attrib.get("name", "").lower()
                    if any(pattern in layer_name for pattern in REWARD_LAYER_PATTERNS):
                        for tile in layer_node.findall(".//tile[@name]"):
                            if tile.attrib["name"].startswith("SpawnPoint_"):
                                all_item_ids_from_xml.add(tile.attrib["name"])
            except Exception as e:
                logger.error(f"Gagal memproses file {file_path}: {e}")

        for item_id_xml in all_item_ids_from_xml:
            clean_id = item_id_xml.replace("SpawnPoint_", "")
            
            canonical_id, item_type = self._classify_entity(clean_id)

            if item_type in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                # Jika canonical_id adalah ID spesifik dari TRANSLATIONS, gunakan itu.
                # Jika tidak, gunakan hasil dari CANONICAL_MAP.
                # Ini memastikan bos dengan nama spesifik tidak dioverwrite oleh ID generik.
                final_id_to_store = canonical_id 
                if clean_id in TRANSLATIONS and TRANSLATIONS[clean_id][2] == item_type:
                    final_id_to_store = clean_id

                results[item_type].update([final_id_to_store])

            elif item_type == TYPE_MOB:
                tier_num = self._extract_tier_from_id(clean_id)
                
                # Filter mob berdasarkan Tier
                if tier_num is not None and tier_num < MIN_MOB_TIER_TO_SCAN:
                    logger.debug(f"Mob {clean_id} (Tier T{tier_num}) dilewati karena di bawah T{MIN_MOB_TIER_TO_SCAN}.")
                    continue # Lewati mob jika Tier-nya di bawah minimum

                # Jika tier_num None (tidak ada info Tier di ID) atau >= MIN_MOB_TIER_TO_SCAN, proses mob
                tier_str = f"T{tier_num}" if tier_num is not None else "Unknown Tier"
                
                if tier_str not in results["mobs_by_tier"]:
                    results["mobs_by_tier"][tier_str] = Counter()
                results["mobs_by_tier"][tier_str].update([clean_id])
            elif clean_id: # Hanya log jika clean_id ada isinya
                logger.debug(f"Entitas tidak terklasifikasi: {clean_id}")
        
        logger.info(f"Pemindaian selesai. Menemukan: Bos Event({sum(results[TYPE_EVENT_BOSS].values())}), Bos Dungeon({sum(results[TYPE_DUNGEON_BOSS].values())}), Peti({sum(results[TYPE_CHEST].values())}), Altar({sum(results[TYPE_SHRINE].values())})")
        
        # Hitung total mob yang dilaporkan
        total_mobs_reported = 0
        for tier_counter in results["mobs_by_tier"].values():
            total_mobs_reported += sum(tier_counter.values())
        logger.info(f"Total mob (T{MIN_MOB_TIER_TO_SCAN}+ atau Tier Tidak Diketahui) yang dilaporkan: {total_mobs_reported}")

        # Logika baru: Sesuaikan informasi peti berdasarkan keberadaan mob T6+
        any_high_tier_mobs_found = False
        if results["mobs_by_tier"]: # Periksa apakah ada entri mob sama sekali
            for tier_str_key, mob_counts in results["mobs_by_tier"].items():
                if sum(mob_counts.values()) > 0: # Jika ada mob di tier ini (setelah filter)
                    # Asumsikan tier_str_key adalah "TX" atau "Unknown Tier"
                    # Jika "Unknown Tier", kita anggap itu bisa jadi relevan
                    # Jika "TX", kita periksa apakah X >= MIN_MOB_TIER_TO_SCAN
                    if tier_str_key == "Unknown Tier":
                        any_high_tier_mobs_found = True
                        break
                    try:
                        numeric_tier = int(tier_str_key[1:]) # Ambil angka dari "TX"
                        if numeric_tier >= MIN_MOB_TIER_TO_SCAN:
                            any_high_tier_mobs_found = True
                            break
                    except ValueError: # Jika format tier_str_key bukan "TX"
                        logger.warning(f"Format tier tidak dikenal di mobs_by_tier: {tier_str_key}")
                        # Anda bisa memutuskan apakah ini dihitung sebagai 'high_tier_mob_found'
                        # Untuk sekarang, kita anggap tidak jika formatnya aneh.
                        pass


        if not any_high_tier_mobs_found and sum(results[TYPE_CHEST].values()) > 0:
            logger.info(f"Tidak ada mob T{MIN_MOB_TIER_TO_SCAN}+ yang ditemukan dalam pemindaian ini. Menyembunyikan {sum(results[TYPE_CHEST].values())} peti dari laporan.")
            results[TYPE_CHEST].clear() # Kosongkan peti jika tidak ada mob T6+

        return results

