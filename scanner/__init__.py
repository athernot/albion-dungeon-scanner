import glob
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
import json
import requests
import time
import re # Untuk mengekstrak Tier dari ID

from scanner.utils.binary import Binary

DATABASE_FILE = 'database.json'
TRANSLATIONS = {} 
UPDATE_COOLDOWN_SECONDS = 24 * 60 * 60 
LAST_API_UPDATE_TIMESTAMPS = {}
API_RELEVANT_KEYWORDS = ["LOOTCHEST", "SHRINE", "BOSS", "UNCLEFROST", "ANNIVERSARY_TITAN"] 

TYPE_EVENT_BOSS = "EVENT_BOSS"
TYPE_DUNGEON_BOSS = "DUNGEON_BOSS"
TYPE_CHEST = "CHEST"
TYPE_SHRINE = "SHRINE"
TYPE_MOB = "MOB" # Untuk mob yang mungkin ingin diberi nama spesifik

def load_translations():
    global TRANSLATIONS, LAST_API_UPDATE_TIMESTAMPS
    if not os.path.exists(DATABASE_FILE):
        initial_db = {
            # Event Bosses
            "UNCLEFROST": ("Uncle Frost (Event Musim Dingin)", "🥶", TYPE_EVENT_BOSS),
            "ANNIVERSARY_TITAN": ("Titan Anniversary (Event)", "⚔️", TYPE_EVENT_BOSS),
            "RANDOM_EVENT_WINTER_STANDARD_BOSS": ("Bos Standar (Event Musim Dingin)", "☃️", TYPE_EVENT_BOSS),
            "RANDOM_EVENT_WINTER_VETERAN_BOSS": ("Bos Veteran (Event Musim Dingin)", "☃️❄️", TYPE_EVENT_BOSS),
            "RANDOM_RD_ANNIVERSARY_SOLO_BOSS": ("Bos Anniversary Solo (Event)", "🎉", TYPE_EVENT_BOSS),
            "RANDOM_RD_ANNIVERSARY_VETERAN_BOSS": ("Bos Anniversary Veteran (Event)", "🎉🏆", TYPE_EVENT_BOSS),

            # Dungeon Bosses (Contoh berdasarkan Wiki & Log)
            # Heretic
            "RANDOM_HERETIC_SOLO_MINIBOSS": ("Minibos Heretic", "💀", TYPE_DUNGEON_BOSS),
            "RANDOM_HERETIC_VETERAN_MINIBOSS": ("Minibos Heretic Veteran", "💀", TYPE_DUNGEON_BOSS),
            "RANDOM_HERETIC_SOLO_BOSS_HIGHLIGHT": ("Bos Heretic (Highlight)", "👻", TYPE_DUNGEON_BOSS),
            "RANDOM_HERETIC_VETERAN_BOSS_HIGHLIGHT": ("Bos Heretic Veteran (Highlight)", "👻", TYPE_DUNGEON_BOSS),
            "RANDOM_HERETIC_SOLO_ENDBOSS_UNCOMMON": ("Bos Akhir Heretic (Biru)", "👹", TYPE_DUNGEON_BOSS),
            "RANDOM_HERETIC_VETERAN_ENDBOSS_UNCOMMON": ("Bos Akhir Heretic Veteran (Biru)", "👹", TYPE_DUNGEON_BOSS),
            # Keeper
            "RANDOM_KEEPER_SOLO_MINIBOSS": ("Minibos Keeper", "🌿💀", TYPE_DUNGEON_BOSS),
            "RANDOM_KEEPER_VETERAN_MINIBOSS": ("Minibos Keeper Veteran", "🌿💀", TYPE_DUNGEON_BOSS),
            "RANDOM_KEEPER_SOLO_BOSS_HIGHLIGHT": ("Bos Keeper (Highlight)", "🌿👻", TYPE_DUNGEON_BOSS),
            "RANDOM_KEEPER_VETERAN_BOSS_HIGHLIGHT": ("Bos Keeper Veteran (Highlight)", "🌿👻", TYPE_DUNGEON_BOSS),
            "RANDOM_KEEPER_SOLO_ENDBOSS_RARE_CHIEFTAIN": ("Chieftain Keeper (Ungu)", "🌿👹", TYPE_DUNGEON_BOSS),
            "RANDOM_KEEPER_VETERAN_ENDBOSS_RARE_CHIEFTAIN": ("Chieftain Keeper Veteran (Ungu)", "🌿👹", TYPE_DUNGEON_BOSS),
             # Morgana
            "RANDOM_MORGANA_SOLO_MINIBOSS": ("Minibos Morgana", "⚔️💀", TYPE_DUNGEON_BOSS),
            "RANDOM_MORGANA_VETERAN_MINIBOSS": ("Minibos Morgana Veteran", "⚔️💀", TYPE_DUNGEON_BOSS),
            "RANDOM_MORGANA_SOLO_BOSS_HIGHLIGHT": ("Bos Morgana (Highlight)", "⚔️👻", TYPE_DUNGEON_BOSS),
            "RANDOM_MORGANA_VETERAN_BOSS_HIGHLIGHT": ("Bos Morgana Veteran (Highlight)", "⚔️👻", TYPE_DUNGEON_BOSS),
            "RANDOM_MORGANA_SOLO_ENDBOSS_UNCOMMON": ("Bos Akhir Morgana (Biru)", "⚔️👹", TYPE_DUNGEON_BOSS),
            "RANDOM_MORGANA_VETERAN_ENDBOSS_UNCOMMON": ("Bos Akhir Morgana Veteran (Biru)", "⚔️👹", TYPE_DUNGEON_BOSS),
            # Undead
             "RANDOM_UNDEAD_SOLO_ENDBOSS_UNCOMMON_GENERAL": ("Bos Akhir Undead (Umum)", "💀👹", TYPE_DUNGEON_BOSS),


            # Shrines (Altar)
            "SHRINE_FAME_BUFF": ("Altar Peningkatan Fame", "📈", TYPE_SHRINE), # Sebelumnya SHRINE_FAME
            "SHRINE_COMBAT_BUFF": ("Altar Kekuatan Tempur", "💥", TYPE_SHRINE),
            "SHRINE_DEFENSE_BUFF": ("Altar Pertahanan", "🛡️", TYPE_SHRINE),
            "SHRINE_ENERGY_REGEN_BUFF": ("Altar Regenerasi Energi", "⚡", TYPE_SHRINE),
            "SHRINE_HEALTH_REGEN_BUFF": ("Altar Regenerasi HP", "❤️", TYPE_SHRINE),
            "SHRINE_COOLDOWN_REDUCTION_BUFF": ("Altar Pengurangan Cooldown", "⏳", TYPE_SHRINE),
            "SHRINE_MOB_SPEED_BUFF": ("Altar Kecepatan Gerak", "🏃", TYPE_SHRINE),

            # Chests - Umum (Solo/Group bisa memiliki pola ID mirip)
            "LOOTCHEST_STANDARD": ("Peti Biasa (Hijau)", "🟩"),
            "LOOTCHEST_UNCOMMON": ("Peti Tidak Biasa (Biru)", "🟦"),
            "LOOTCHEST_RARE": ("Peti Langka (Ungu)", "🟪"),
            "LOOTCHEST_LEGENDARY": ("Peti Legendaris (Emas)", "🟨"),
            
            "LOOTCHEST_KEEPER_SOLO_UNCOMMON": ("Peti Keeper Solo (Biru)", "🟦"), # Dari log
            "LOOTCHEST_ANNIVERSARY_SOLO_LOOTCHEST_BOSS": ("Peti Boss Anniversary Solo", "🎂"), # Dari log

            # Tambahkan lebih banyak entri berdasarkan Wiki & GitHub Data jika memungkinkan
            # Contoh: T4_LOOTCHEST_GREEN_STANDARD, T5_LOOTCHEST_BLUE_STANDARD, dst.
            # Namun, karena ID dari XML sering tidak menyertakan Tier secara eksplisit di bagian yang kita parse,
            # kita mungkin lebih baik mengandalkan kata kunci umum di atas dan API.
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"translations": initial_db, "timestamps": {}}, f, indent=4, ensure_ascii=False)
        TRANSLATIONS = initial_db
        LAST_API_UPDATE_TIMESTAMPS = {}
        print(f"DEBUG: Database awal (lebih kaya) dibuat di {DATABASE_FILE}")
    else:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            TRANSLATIONS = data.get("translations", {})
            LAST_API_UPDATE_TIMESTAMPS = data.get("timestamps", {})

def save_translations():
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"translations": TRANSLATIONS, "timestamps": LAST_API_UPDATE_TIMESTAMPS}, f, indent=4, ensure_ascii=False)

def fetch_and_update_id_from_api(item_id_xml):
    global TRANSLATIONS, LAST_API_UPDATE_TIMESTAMPS
    clean_id = item_id_xml.replace("SpawnPoint_", "")
    is_relevant_for_api = any(keyword.upper() in clean_id.upper() for keyword in API_RELEVANT_KEYWORDS)
    if not is_relevant_for_api: return

    current_time = time.time()
    last_update_time = LAST_API_UPDATE_TIMESTAMPS.get(clean_id, 0)
    existing_entry = TRANSLATIONS.get(clean_id)
    is_new_id_in_translations = not existing_entry
    
    if not is_new_id_in_translations and (current_time - last_update_time < UPDATE_COOLDOWN_SECONDS):
        return

    # print(f"DEBUG API: Mencoba mengambil/memperbarui data untuk ID: {clean_id}")
    try:
        url = f"https://gameinfo.albiononline.com/api/gameinfo/items/{clean_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        api_item_name = data.get('localizedNames', {}).get('EN-US', clean_id)
        
        current_name_in_db, current_icon, current_type = None, None, None
        if existing_entry:
            if len(existing_entry) == 3: current_name_in_db, current_icon, current_type = existing_entry
            elif len(existing_entry) == 2: current_name_in_db, current_icon = existing_entry
        
        icon_to_use = current_icon if current_icon and current_icon != "❓" else "❓"
        type_to_use = current_type 

        if icon_to_use == "❓":
            clean_id_upper = clean_id.upper()
            if "LOOTCHEST" in clean_id_upper: icon_to_use = "📦"
            elif "SHRINE" in clean_id_upper: icon_to_use = "✨"
            elif any(boss_key in clean_id_upper for boss_key in API_RELEVANT_KEYWORDS if "BOSS" in boss_key): icon_to_use = "👑"

        if is_new_id_in_translations or (api_item_name != current_name_in_db and api_item_name != clean_id) :
            print(f"DEBUG API Update: Data untuk '{clean_id}' diperbarui. Nama API: '{api_item_name}', Nama DB: '{current_name_in_db}'")
            # Simpan dengan tipe jika sudah ada, jika tidak simpan tanpa tipe dulu
            entry_to_save = (api_item_name, icon_to_use, type_to_use) if type_to_use else (api_item_name, icon_to_use)
            TRANSLATIONS[clean_id] = entry_to_save
            LAST_API_UPDATE_TIMESTAMPS[clean_id] = current_time
            save_translations()
        elif not is_new_id_in_translations:
             LAST_API_UPDATE_TIMESTAMPS[clean_id] = current_time
             save_translations() # Simpan timestamp saja
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404: print(f"DEBUG API Info: ID '{clean_id}' tidak ditemukan di API (404). URL: {url}")
        else: print(f"DEBUG API HTTP Error: Gagal mengambil data untuk {clean_id}. Status: {e.response.status_code}. URL: {url}")
    except Exception as e: print(f"DEBUG API Error: Terjadi kesalahan saat memproses ID {clean_id}. Error: {type(e).__name__} - {e}. URL: {url}")

load_translations()

REWARD_LAYER_PATTERNS = ["reward_solo", "reward_group", "reward_avalonian", "chest", "loot", "reward", "encounter", "mob", "shrine"]
TEMPLATE_FOLDERS = ["GREEN", "YELLOW", "RED", "BLACK", "AVALON", "CORRUPTED", "HELLGATE", "EXPEDITION", "ROADS"]

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
            if os.path.isdir(path): existing_dirs.append(path)
        if not existing_dirs: raise FileNotFoundError(f"Tidak ada folder template yang ditemukan di {self.templates_base_path}")
        return existing_dirs

    def check_and_restore_files(self, dungeon_dir):
        temp_path = os.path.join(dungeon_dir, ".temp")
        if os.path.exists(temp_path): shutil.rmtree(temp_path)
        os.makedirs(temp_path, exist_ok=True)
        files_in_dir = glob.glob(os.path.join(dungeon_dir, "*.bin"))
        for file_path in files_in_dir:
            filename = os.path.basename(file_path)
            try: shutil.move(file_path, os.path.join(temp_path, filename))
            except IOError: self.used_files.append(file_path)
            except Exception: pass 
            if os.path.exists(os.path.join(temp_path, filename)):
                try: shutil.move(os.path.join(temp_path, filename), file_path)
                except Exception: pass 
        shutil.rmtree(temp_path, ignore_errors=True)

    def extract_tier_from_id(self, item_id_xml):
        # Mencoba mengekstrak tier seperti T4, T5, dll. dari awal ID
        match = re.match(r"T(\d+)_", item_id_xml.upper())
        if match:
            return f"T{match.group(1)}"
        return "Unknown Tier"

    def run(self) -> dict:
        print("\nDEBUG: Memulai Pemindaian Baru...")
        self.used_files = [] 
        dungeon_dirs_to_scan = self.get_dungeon_dirs()
        for dir_path in dungeon_dirs_to_scan:
            self.check_and_restore_files(dir_path)

        if not self.used_files:
            print("DEBUG: Tidak ada file yang digunakan terdeteksi.")
            return None

        found_event_bosses_keys = []
        found_dungeon_bosses_keys = []
        found_chests_keys = []
        found_shrines_keys = []
        # Ubah found_generic_mobs_ids menjadi kamus untuk menyimpan hitungan per tier
        # Format: {"T4": Counter(), "T5": Counter(), "Unknown Tier": Counter()}
        mobs_by_tier = {f"T{i}": Counter() for i in range(1, 9)} 
        mobs_by_tier["Unknown Tier"] = Counter()
        
        found_exits_filenames = []
        all_item_ids_from_xml = set()

        for file_path in self.used_files:
            filename = os.path.basename(file_path)
            if "EXIT" in filename.upper():
                found_exits_filenames.append(filename)
            if not any(skip.upper() in filename.upper() for skip in ["BACKDROP", "MASTER", "EXIT"]):
                try:
                    binary_instance = Binary()
                    decrypted_bytes = binary_instance.decrypter.decrypt_binary_file(file_path)
                    decrypted_str = decrypted_bytes.decode("utf-8", errors='ignore')
                    root = ET.fromstring(decrypted_str)
                    for layer_node in root.findall(".//layer"):
                        layer_name = layer_node.attrib.get("name", "").lower()
                        if any(pattern in layer_name for pattern in REWARD_LAYER_PATTERNS):
                            for tile in layer_node.findall(".//tile"):
                                item_id_xml = tile.attrib.get("name", "")
                                if item_id_xml: all_item_ids_from_xml.add(item_id_xml)
                except Exception: pass
        
        if all_item_ids_from_xml:
             print(f"DEBUG: Daftar ID unik dari XML ({len(all_item_ids_from_xml)}): {sorted(list(all_item_ids_from_xml))}")

        for item_id_xml in all_item_ids_from_xml:
            if not item_id_xml: continue
            
            fetch_and_update_id_from_api(item_id_xml) 
            
            item_id_xml_upper = item_id_xml.upper() 
            clean_id = item_id_xml.replace("SpawnPoint_", "")
            classified_this_id = False
            item_tier = self.extract_tier_from_id(item_id_xml) # Ekstrak tier

            if clean_id in TRANSLATIONS:
                entry = TRANSLATIONS[clean_id]
                item_type_from_db = entry[2] if len(entry) == 3 else None 

                if item_type_from_db == TYPE_EVENT_BOSS:
                    found_event_bosses_keys.append(clean_id); classified_this_id = True
                elif item_type_from_db == TYPE_DUNGEON_BOSS:
                    found_dungeon_bosses_keys.append(clean_id); classified_this_id = True
                elif item_type_from_db == TYPE_SHRINE:
                    found_shrines_keys.append(clean_id); classified_this_id = True
                elif item_type_from_db == TYPE_MOB:
                     mobs_by_tier.setdefault(item_tier, Counter()).update([clean_id]); classified_this_id = True
                elif "LOOTCHEST" in clean_id.upper(): 
                     found_chests_keys.append(clean_id); classified_this_id = True
            
            if not classified_this_id:
                if "SHRINE" in item_id_xml_upper or "ALTAR" in item_id_xml_upper:
                    found_shrines_keys.append(clean_id); classified_this_id = True
                elif "LOOTCHEST" in item_id_xml_upper:
                    found_chests_keys.append(clean_id); classified_this_id = True
                elif any(k in item_id_xml_upper for k in ["BOSS", "UNCLEFROST", "ANNIVERSARY_TITAN"]):
                    is_specific_event_boss = False
                    for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN"]:
                        if event_key in item_id_xml_upper:
                            if event_key not in found_event_bosses_keys: found_event_bosses_keys.append(event_key)
                            is_specific_event_boss = True; break
                    if not is_specific_event_boss:
                         if clean_id not in found_dungeon_bosses_keys: found_dungeon_bosses_keys.append(clean_id)
                    classified_this_id = True
            
            if not classified_this_id and ("RANDOM" in item_id_xml_upper or "MOB" in item_id_xml_upper or any(faction in item_id_xml_upper for faction in ["KEEPER", "HERETIC", "MORGANA", "UNDEAD"])):
                mobs_by_tier.setdefault(item_tier, Counter()).update([clean_id])
                # classified_this_id = True # Tidak perlu, ini adalah kategori 'lainnya'

        # Deteksi Bos dari Nama File
        current_event_boss_set = set(found_event_bosses_keys) 
        for file_path in self.used_files:
            filename_upper = os.path.basename(file_path).upper()
            if "UNCLEFROST" in filename_upper and "UNCLEFROST" not in current_event_boss_set: 
                found_event_bosses_keys.append("UNCLEFROST"); fetch_and_update_id_from_api("UNCLEFROST") 
            if "ANNIVERSARY_TITAN" in filename_upper and "ANNIVERSARY_TITAN" not in current_event_boss_set: 
                found_event_bosses_keys.append("ANNIVERSARY_TITAN"); fetch_and_update_id_from_api("ANNIVERSARY_TITAN")

        # Hitung total mob biasa dari semua tier
        total_generic_mobs = sum(sum(tier_counter.values()) for tier_counter in mobs_by_tier.values())

        print(f"DEBUG Hasil Akhir: EventBosses: {Counter(found_event_bosses_keys)}, DungeonBosses: {Counter(found_dungeon_bosses_keys)}, Chests: {Counter(found_chests_keys)}, Shrines: {Counter(found_shrines_keys)}, TotalGenericMobs: {total_generic_mobs}, Exits: {len(found_exits_filenames)}")
        
        return {
            "event_bosses": Counter(found_event_bosses_keys),
            "dungeon_bosses": Counter(found_dungeon_bosses_keys),
            "chests": Counter(found_chests_keys),
            "shrines": Counter(found_shrines_keys),
            "mobs_by_tier": mobs_by_tier, # Kirim data mob per tier
            "exits": found_exits_filenames,
        }