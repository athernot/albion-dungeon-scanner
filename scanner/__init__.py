# file: scanner/__init__.py

import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
import re
import logging

# Impor instance manager dan dapatkan logger untuk modul ini
from scanner.utils.logging import logging_manager
from scanner.utils.binary import Binary

logger = logging_manager.get_logger(__name__)

# --- Konstanta ---
DATABASE_FILE = 'database.json'
TRANSLATIONS = {}

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
        # PANGGILAN YANG BENAR SEKARANG MENGGUNAKAN LOGGER YANG VALID
        logger.info(f"Database dimuat dari {DATABASE_FILE}. Total entri: {len(TRANSLATIONS)}")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Gagal memuat atau membaca file database '{DATABASE_FILE}': {e}")
        TRANSLATIONS = {}

# Memuat terjemahan saat modul diimpor
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
                    # File yang tidak bisa dipindah berarti sedang digunakan oleh game
                    shutil.move(file_path, temp_file_path)
                    shutil.move(temp_file_path, file_path)
                except IOError:
                    self.used_files.append(file_path)
                    logger.info(f"File aktif terdeteksi: {filename}")
                except Exception as e:
                    logger.error(f"Error saat memeriksa file {filename}: {e}")
                    # Pastikan file dikembalikan jika terjadi error setelah berhasil dipindah
                    if os.path.exists(temp_file_path) and not os.path.exists(file_path):
                        shutil.move(temp_file_path, file_path)
            
            # Hapus folder temporary
            shutil.rmtree(temp_path, ignore_errors=True)

    def _extract_tier_from_id(self, item_id: str) -> str:
        """Mengekstrak informasi Tier (misal: T4) dari ID item."""
        match = re.match(r"T(\d+)_", item_id.upper())
        return f"T{match.group(1)}" if match else "Unknown Tier"

    def _classify_entity(self, clean_id: str) -> tuple[str | None, str | None]:
        """
        Mengklasifikasikan entitas berdasarkan ID-nya.
        Mengembalikan tuple (canonical_id, item_type).
        """
        item_id_upper = clean_id.upper()

        # 1. Cek database untuk klasifikasi eksplisit
        if clean_id in TRANSLATIONS:
            entry = TRANSLATIONS[clean_id]
            if len(entry) >= 3:
                return clean_id, entry[2] # Return ID asli dan tipenya dari DB

        # 2. Jika tidak ada di DB, coba klasifikasi berdasarkan kata kunci
        if "LOOTCHEST" in item_id_upper or "BOOKCHEST" in item_id_upper:
            for key, canonical_id in CANONICAL_CHEST_MAP.items():
                if key in item_id_upper:
                    return canonical_id, TYPE_CHEST
            return CANONICAL_CHEST_MAP.get("LOOTCHEST"), TYPE_CHEST

        if "BOSS" in item_id_upper:
            for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN"]:
                if event_key in item_id_upper:
                    return event_key, TYPE_EVENT_BOSS
            
            for key, canonical_id in CANONICAL_BOSS_MAP.items():
                if key in item_id_upper:
                    return canonical_id, TYPE_DUNGEON_BOSS
            return CANONICAL_BOSS_MAP["BOSS"], TYPE_DUNGEON_BOSS

        if "SHRINE" in item_id_upper:
            return "SHRINE_NON_COMBAT_BUFF", TYPE_SHRINE

        # 3. Fallback ke klasifikasi sebagai MOB jika mengandung kata kunci faksi
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

            if item_type in results:
                results[item_type].update([canonical_id])
            elif item_type == TYPE_MOB:
                tier = self._extract_tier_from_id(clean_id)
                if tier not in results["mobs_by_tier"]:
                    results["mobs_by_tier"][tier] = Counter()
                results["mobs_by_tier"][tier].update([clean_id])
            elif clean_id:
                logger.debug(f"Entitas tidak terklasifikasi: {clean_id}")
        
        logger.info(f"Pemindaian selesai. Menemukan: Bos Event({sum(results[TYPE_EVENT_BOSS].values())}), Bos Dungeon({sum(results[TYPE_DUNGEON_BOSS].values())}), Peti({sum(results[TYPE_CHEST].values())}), Altar({sum(results[TYPE_SHRINE].values())})")

        # PERBAIKAN: Kembalikan dictionary dengan kunci berupa konstanta yang diharapkan oleh GUI
        return {
            TYPE_EVENT_BOSS: results[TYPE_EVENT_BOSS],
            TYPE_DUNGEON_BOSS: results[TYPE_DUNGEON_BOSS],
            TYPE_CHEST: results[TYPE_CHEST],
            TYPE_SHRINE: results[TYPE_SHRINE],
            "mobs_by_tier": results["mobs_by_tier"],
            "exits": results["exits"],
            "used_files": results["used_files"],
        }