import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
import requests

DATABASE_FILE = 'database.json'
TRANSLATIONS = {} 

def load_translations():
    global TRANSLATIONS
    if not os.path.exists(DATABASE_FILE):
        initial_db = {
            "UNCLEFROST": ("Uncle Frost (Event)", "🥶"),
            "ANNIVERSARY_TITAN": ("Anniversary Titan (Event)", "⚔️"),
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_db, f, indent=4, ensure_ascii=False)
        TRANSLATIONS = initial_db
    else:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            TRANSLATIONS = json.load(f)

def fetch_and_update_id_from_api(item_id):
    global TRANSLATIONS
    clean_id = item_id.replace("SpawnPoint_", "")
    
    if any(key in clean_id for key in TRANSLATIONS.keys()):
        return

    try:
        url = f"https://gameinfo.albiononline.com/api/gameinfo/items/{clean_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            item_name = data.get('localizedNames', {}).get('EN-US', clean_id)
            
            icon = "❓"
            if "LOOTCHEST" in clean_id: icon = "📦"
            if "SHRINE" in clean_id: icon = "✨"
            if "BOSS" in clean_id: icon = "👑"
            
            print(f"API Success: Menemukan nama untuk '{clean_id}': '{item_name}'")
            
            TRANSLATIONS[clean_id] = (item_name, icon)
            with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(TRANSLATIONS, f, indent=4, ensure_ascii=False)

    except requests.exceptions.RequestException as e:
        print(f"API Error: Gagal menghubungi API untuk ID {clean_id}. Error: {e}")

load_translations()

REWARD_LAYER_PATTERNS = ["reward_solo", "reward_group", "reward_avalonian"]
TEMPLATE_FOLDERS = ["GREEN", "YELLOW", "RED", "BLACK", "AVALON", "CORRUPTED", "HELLGATE"]

class AlbionDungeonScanner:
    def __init__(self, ao_dir_path: str) -> None:
        self.used_files = []
        if not ao_dir_path or not os.path.isdir(ao_dir_path):
            raise ValueError(f"Path direktori Albion tidak valid atau tidak ditemukan: {ao_dir_path}")
        self.base_path = ao_dir_path
        self.templates_base_path = os.path.join(self.base_path, r"Albion-Online_Data\StreamingAssets\GameData\templates")

    def get_dungeon_dirs(self):
        existing_dirs = []
        for folder in TEMPLATE_FOLDERS:
            path = os.path.join(self.templates_base_path, folder)
            if os.path.isdir(path):
                existing_dirs.append(path)
        if not existing_dirs:
            raise FileNotFoundError(f"Tidak ada folder template (GREEN, AVALON, dll.) yang ditemukan di {self.templates_base_path}")
        return existing_dirs

    def check_and_restore_files(self, dungeon_dir):
        temp_path = os.path.join(dungeon_dir, ".temp")
        if os.path.exists(temp_path): shutil.rmtree(temp_path)
        os.mkdir(temp_path)
        files_in_dir = glob.glob(os.path.join(dungeon_dir, "*.bin"))
        for file_path in files_in_dir:
            filename = os.path.basename(file_path)
            try: shutil.move(file_path, os.path.join(temp_path, filename))
            except IOError: self.used_files.append(file_path)
            try: shutil.move(os.path.join(temp_path, filename), file_path)
            except Exception: pass
        shutil.rmtree(temp_path, ignore_errors=True)

    def run(self) -> dict:
        self.used_files = []
        dungeon_dirs_to_scan = self.get_dungeon_dirs()
        for dir_path in dungeon_dirs_to_scan:
            self.check_and_restore_files(dir_path)

        if not self.used_files:
            return None

        found_bosses, found_chests_ids, found_shrines_ids, found_exits = [], [], [], []
        all_item_ids = set()
        for file_path in self.used_files:
            filename = os.path.basename(file_path)
            if "EXIT" in filename: found_exits.append(filename)
            if not any(skip in filename for skip in ["BACKDROP", "MASTER", "EXIT"]):
                try:
                    binary = Binary()
                    decrypted_bytes = binary.decrypter.decrypt_binary_file(file_path)
                    decrypted_str = decrypted_bytes.decode("utf-8", errors='ignore')
                    root = ET.fromstring(decrypted_str)
                    for layer_node in root.findall(".//layer"):
                        layer_name = layer_node.attrib.get("name", "").lower()
                        if any(pattern in layer_name for pattern in REWARD_LAYER_PATTERNS) or "mob" in layer_name:
                            for tile in layer_node.findall(".//tile"):
                                all_item_ids.add(tile.attrib.get("name", ""))
                except Exception: pass
        
        
        
        for item_id in all_item_ids:
            if not item_id: continue
            fetch_and_update_id_from_api(item_id)
            item_id_upper = item_id.upper()
            clean_id = item_id.replace("SpawnPoint_", "")
            if "SHRINE" in item_id_upper: found_shrines_ids.append(clean_id)
            elif "LOOTCHEST" in item_id_upper: found_chests_ids.append(clean_id)
            elif "BOSS" in item_id_upper: found_bosses.append(clean_id)
            elif "UNCLEFROST" in item_id_upper: found_bosses.append("UNCLEFROST")
            elif "ANNIVERSARY_TITAN" in item_id_upper: found_bosses.append("ANNIVERSARY_TITAN")

        return {
            "bosses": Counter(found_bosses),
            "chests": Counter(found_chests_ids),
            "shrines": Counter(found_shrines_ids),
            "exits": found_exits,
        }