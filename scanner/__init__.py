# file: scanner/__init__.py

import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
import re
import logging

from scanner.utils.logging import logging_manager
from scanner.utils.binary import Binary

logger = logging_manager.get_logger(__name__)

# --- Konstanta ---
DATABASE_FILE = 'database.json'
TRANSLATIONS = {}
MIN_MOB_TIER_TO_SCAN = 6

# Definisi Tipe Entitas
TYPE_EVENT_BOSS = "EVENT_BOSS"
TYPE_DUNGEON_BOSS = "DUNGEON_BOSS"
TYPE_CHEST = "CHEST"
TYPE_SHRINE = "SHRINE"
TYPE_MOB = "MOB"

# Peta untuk kanonisasi bos
CANONICAL_BOSS_MAP = {
    "ENDBOSS": "BOSS_ENDBOSS_GENERIC",
    "MINIBOSS": "BOSS_MINIBOSS_GENERIC",
    "BOSS_HIGHLIGHT": "BOSS_HIGHLIGHT_GENERIC",
    "BOSS": "BOSS_GENERIC"
}

# Daftar folder, pola, dan kata kunci yang relevan
TEMPLATE_FOLDERS = ["GREEN", "YELLOW", "RED", "BLACK", "AVALON", "CORRUPTED", "HELLGATE", "EXPEDITION", "ROADS", "MISTS"]
REWARD_LAYER_PATTERNS = ["reward", "chest", "loot", "encounter", "mob", "shrine"]
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
        """Mengekstrak informasi Tier numerik dari ID item."""
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
        Mengembalikan tuple (ID generik, tipe item).
        """
        item_id_upper = clean_id.upper()

        # --- PERUBAHAN 1: Abaikan semua BOOKCHEST ---
        if "BOOKCHEST" in item_id_upper:
            return None, None

        # Cek terjemahan spesifik dulu (untuk bos bernama, dll)
        if clean_id in TRANSLATIONS:
            entry = TRANSLATIONS[clean_id]
            if len(entry) >= 3 and entry[2] != TYPE_CHEST: # Jangan gunakan ini untuk peti
                return clean_id, entry[2]

        # --- PERUBAHAN 2: Kelompokkan LOOTCHEST berdasarkan warna/rarity ---
        if "LOOTCHEST" in item_id_upper:
            if "LEGENDARY" in item_id_upper or "BOSS" in item_id_upper:
                return "CHEST_GOLD", TYPE_CHEST
            if "EPIC" in item_id_upper:
                return "CHEST_PURPLE", TYPE_CHEST
            if "RARE" in item_id_upper:
                return "CHEST_BLUE", TYPE_CHEST
            if "UNCOMMON" in item_id_upper or "STANDARD" in item_id_upper:
                return "CHEST_GREEN", TYPE_CHEST
            return "CHEST_GREEN", TYPE_CHEST # Fallback untuk peti biasa

        # Klasifikasi Bos (tidak berubah)
        if "BOSS" in item_id_upper:
            for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN", "EVENT_WINTER"]:
                if event_key in item_id_upper:
                    if clean_id in TRANSLATIONS and TRANSLATIONS[clean_id][2] == TYPE_EVENT_BOSS:
                        return clean_id, TYPE_EVENT_BOSS
                    return event_key, TYPE_EVENT_BOSS
            for key, canonical_id in CANONICAL_BOSS_MAP.items():
                if key in item_id_upper:
                    if clean_id in TRANSLATIONS and TRANSLATIONS[clean_id][2] == TYPE_DUNGEON_BOSS:
                        return clean_id, TYPE_DUNGEON_BOSS
                    return canonical_id, TYPE_DUNGEON_BOSS
            return CANONICAL_BOSS_MAP["BOSS"], TYPE_DUNGEON_BOSS

        # Klasifikasi Altar (tidak berubah)
        if "SHRINE" in item_id_upper:
            return "SHRINE_NON_COMBAT_BUFF", TYPE_SHRINE

        # Klasifikasi Mob (tidak berubah)
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
            
            if any(skip.upper() in filename.upper() for skip in ["BACKDROP", "DECORATION", "TERRAIN"]):
                logger.info(f"Melewatkan file dekoratif/latar belakang: {filename}")
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
            
            # Gunakan fungsi klasifikasi yang sudah diperbarui
            generic_id, item_type = self._classify_entity(clean_id)

            if item_type in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                results[item_type].update([generic_id])

            elif item_type == TYPE_MOB:
                tier_num = self._extract_tier_from_id(clean_id)
                if tier_num is not None and tier_num < MIN_MOB_TIER_TO_SCAN:
                    continue
                tier_str = f"T{tier_num}" if tier_num is not None else "Unknown Tier"
                if tier_str not in results["mobs_by_tier"]:
                    results["mobs_by_tier"][tier_str] = Counter()
                results["mobs_by_tier"][tier_str].update([clean_id])
            elif clean_id and generic_id is None and item_type is None:
                # Hanya log jika item tidak sengaja diabaikan (bukan bookchest)
                if "BOOKCHEST" not in clean_id.upper():
                    logger.debug(f"Entitas tidak terklasifikasi atau diabaikan: {clean_id}")
        
        logger.info(f"Pemindaian selesai. Menemukan: Bos Event({sum(results[TYPE_EVENT_BOSS].values())}), Bos Dungeon({sum(results[TYPE_DUNGEON_BOSS].values())}), Peti({sum(results[TYPE_CHEST].values())}), Altar({sum(results[TYPE_SHRINE].values())})")
        
        total_mobs_reported = sum(sum(c.values()) for c in results["mobs_by_tier"].values())
        logger.info(f"Total mob (T{MIN_MOB_TIER_TO_SCAN}+ atau Tier Tidak Diketahui) yang dilaporkan: {total_mobs_reported}")

        any_high_tier_mobs_found = False
        if results["mobs_by_tier"]:
            for tier_str_key, mob_counts in results["mobs_by_tier"].items():
                if sum(mob_counts.values()) > 0:
                    if tier_str_key == "Unknown Tier":
                        any_high_tier_mobs_found = True
                        break
                    try:
                        numeric_tier = int(tier_str_key[1:])
                        if numeric_tier >= MIN_MOB_TIER_TO_SCAN:
                            any_high_tier_mobs_found = True
                            break
                    except (ValueError, IndexError):
                        pass

        if not any_high_tier_mobs_found and sum(results[TYPE_CHEST].values()) > 0:
            logger.info(f"Tidak ada mob T{MIN_MOB_TIER_TO_SCAN}+ yang ditemukan, menyembunyikan {sum(results[TYPE_CHEST].values())} peti dari laporan.")
            results[TYPE_CHEST].clear()

        return results