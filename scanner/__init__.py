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
TYPE_MOB = "MOB" 

def load_translations():
    global TRANSLATIONS, LAST_API_UPDATE_TIMESTAMPS
    if not os.path.exists(DATABASE_FILE):
        initial_db = {
            # Event Bosses (dari Wiki/Umum)
            "UNCLEFROST": ("Uncle Frost (Winter Event)", "🥶", TYPE_EVENT_BOSS),
            "ANNIVERSARY_TITAN": ("Anniversary Titan (Anniversary Event)", "⚔️", TYPE_EVENT_BOSS),
            "RANDOM_EVENT_WINTER_STANDARD_BOSS": ("Harbinger of Frost (Winter Event Boss)", "☃️", TYPE_EVENT_BOSS),
            "RANDOM_EVENT_WINTER_VETERAN_BOSS": ("Veteran Harbinger of Frost (Winter Event Boss)", "☃️❄️", TYPE_EVENT_BOSS),
            "RANDOM_RD_ANNIVERSARY_SOLO_BOSS": ("Anniversary Boss Solo", "🎉", TYPE_EVENT_BOSS),
            "RANDOM_RD_ANNIVERSARY_VETERAN_BOSS": ("Anniversary Boss Veteran", "🎉🏆", TYPE_EVENT_BOSS),

            # Dungeon Bosses (Contoh, inspirasi dari Wiki)
            # Anda perlu menyesuaikan ID_INTERNAL_BOSS dengan yang ditemukan pemindai
            "HERETIC_CHIEF": ("Heretic Chief", "👹", TYPE_DUNGEON_BOSS),
            "KEEPER_CHIEFTAIN": ("Keeper Chieftain", "🌿👹", TYPE_DUNGEON_BOSS),
            "MORGANA_COMMANDER": ("Morgana Commander", "⚔️👹", TYPE_DUNGEON_BOSS),
            "UNDEAD_GENERAL": ("Undead General", "💀👹", TYPE_DUNGEON_BOSS),
            "AVALONIAN_HIGH_PRIEST": ("Avalonian High Priest", "💠👹", TYPE_DUNGEON_BOSS),
            
            # Contoh ID dari log Anda yang kemungkinan Dungeon Boss
            "RANDOM_KEEPER_SOLO_BOSS_HIGHLIGHT": ("Keeper Solo Boss (Highlight)", "🌿👻", TYPE_DUNGEON_BOSS),
            "RANDOM_MORGANA_SOLO_ENDBOSS_UNCOMMON": ("Morgana Solo Endboss", "⚔️👻", TYPE_DUNGEON_BOSS),


            # Shrines (dari Wiki)
            "SHRINE_COMBAT_POWER": ("Might Shrine (Combat Power)", "💥", TYPE_SHRINE),
            "SHRINE_DEFENSE": ("Protection Shrine (Defense)", "🛡️", TYPE_SHRINE),
            "SHRINE_FAME": ("Insight Shrine (Fame Buff)", "📈", TYPE_SHRINE), # Mengganti nama agar lebih sesuai Wiki
            "SHRINE_COOLDOWN": ("Cooldown Shrine", "⏳", TYPE_SHRINE),
            "SHRINE_HEALTH": ("Regeneration Shrine (Health)", "❤️", TYPE_SHRINE),
            "SHRINE_ENERGY": ("Energy Shrine", "⚡", TYPE_SHRINE),
            "SHRINE_SPEED": ("Swiftness Shrine (Speed)", "🏃", TYPE_SHRINE), # Mengganti nama
            "SHRINE_NON_COMBAT_BUFF": ("Altar Buff Non-Tempur Umum", "✨", TYPE_SHRINE), # Dari log Anda

            # Chests (inspirasi dari Wiki, ID akan dicocokkan secara parsial)
            # Kunci di sini adalah bagian PENTING dari ID internal. Tier & variasi akan ditangani program.
            "LOOTCHEST_STANDARD": ("Peti Biasa (Hijau)", "🟩", TYPE_CHEST),
            "LOOTCHEST_UNCOMMON": ("Peti Tidak Biasa (Biru)", "🟦", TYPE_CHEST),
            "LOOTCHEST_RARE": ("Peti Langka (Ungu)", "🟪", TYPE_CHEST),
            "LOOTCHEST_EPIC": ("Peti Epik (Emas)", "🟨", TYPE_CHEST), # Dulu disebut Legendary
            "LOOTCHEST_LEGENDARY": ("Peti Legendaris (Emas Terang)", "🌟", TYPE_CHEST), # Untuk peti yang lebih tinggi lagi jika ada
            
            "LOOTCHEST_BOSS": ("Peti Boss", "👑", TYPE_CHEST), # Generik Peti Boss
            "LOOTCHEST_MINIBOSS": ("Peti Minibos", "🏆", TYPE_CHEST),

            # Contoh spesifik dari log Anda (ini bisa dihapus jika pencocokan parsial di atas sudah cukup)
            "LOOTCHEST_KEEPER_SOLO_UNCOMMON": ("Peti Keeper Solo (Biru)", "🟦", TYPE_CHEST),
            "LOOTCHEST_ANNIVERSARY_SOLO_LOOTCHEST_BOSS": ("Peti Boss Anniversary Solo", "🎂", TYPE_CHEST),
        }
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"translations": initial_db, "timestamps": {}}, f, indent=4, ensure_ascii=False)
        TRANSLATIONS = initial_db
        LAST_API_UPDATE_TIMESTAMPS = {}
        print(f"DEBUG: Database awal (berdasarkan Wiki & Log) dibuat di {DATABASE_FILE}")
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
        
        if icon_to_use == "❓": # Coba tebak ikon jika belum ada
            clean_id_upper = clean_id.upper()
            if "LOOTCHEST_STANDARD" in clean_id_upper : icon_to_use = "🟩"
            elif "LOOTCHEST_UNCOMMON" in clean_id_upper : icon_to_use = "🟦"
            elif "LOOTCHEST_RARE" in clean_id_upper : icon_to_use = "🟪"
            elif "LOOTCHEST_EPIC" in clean_id_upper or "LOOTCHEST_LEGENDARY" in clean_id_upper : icon_to_use = "🟨"
            elif "LOOTCHEST_BOSS" in clean_id_upper : icon_to_use = "👑"
            elif "LOOTCHEST" in clean_id_upper: icon_to_use = "📦" # Generik
            elif "SHRINE" in clean_id_upper: icon_to_use = "✨"
            elif any(boss_key in clean_id_upper for boss_key in API_RELEVANT_KEYWORDS if "BOSS" in boss_key): icon_to_use = "👻"


        if is_new_id_in_translations or (api_item_name != current_name_in_db and api_item_name != clean_id) :
            print(f"DEBUG API Update: Data untuk '{clean_id}' diperbarui. Nama API: '{api_item_name}', Nama DB: '{current_name_in_db}'")
            # Simpan dengan tipe jika sudah ada, jika tidak simpan tanpa tipe dulu (akan ditentukan oleh klasifikasi)
            entry_to_save = (api_item_name, icon_to_use, current_type) if current_type else (api_item_name, icon_to_use)
            TRANSLATIONS[clean_id] = entry_to_save
            LAST_API_UPDATE_TIMESTAMPS[clean_id] = current_time
            save_translations()
        elif not is_new_id_in_translations:
             LAST_API_UPDATE_TIMESTAMPS[clean_id] = current_time
             save_translations() # Simpan timestamp saja
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404: print(f"DEBUG API Info: ID '{clean_id}' tidak ditemukan di API (404). URL: {url}")
        # else: print(f"DEBUG API HTTP Error: Gagal mengambil data untuk {clean_id}. Status: {e.response.status_code}. URL: {url}")
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

    def extract_tier_from_id(self, item_id_xml_or_clean_id):
        # Mencoba mengekstrak tier seperti T4, T5, dll. dari awal ID
        # ID bisa datang dengan atau tanpa SpawnPoint_
        id_to_check = item_id_xml_or_clean_id.replace("SpawnPoint_", "")
        match = re.match(r"T(\d+)_", id_to_check.upper())
        if match:
            return f"T{match.group(1)}"
        # Cek juga format seperti MOB_KEEPER_T5...
        match_mob = re.search(r"_T(\d+)", id_to_check.upper())
        if match_mob:
            return f"T{match_mob.group(1)}"
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
        mobs_by_tier_counters = {f"T{i}": Counter() for i in range(1, 9)} 
        mobs_by_tier_counters["Unknown Tier"] = Counter()
        
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
            item_tier = self.extract_tier_from_id(clean_id) # Ekstrak tier dari clean_id

            # 1. Cek dengan entri di TRANSLATIONS (yang mungkin baru diupdate API)
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
                     mobs_by_tier_counters.setdefault(item_tier, Counter()).update([clean_id]); classified_this_id = True
                # Jika ada di TRANSLATIONS tapi tidak ada tipe, atau tipenya CHEST
                elif "LOOTCHEST" in clean_id.upper() or (item_type_from_db == TYPE_CHEST):
                     found_chests_keys.append(clean_id); classified_this_id = True
            
            # 2. Jika belum terklasifikasi, gunakan logika generik berdasarkan kata kunci di ID
            if not classified_this_id:
                if "SHRINE" in item_id_xml_upper or "ALTAR" in item_id_xml_upper:
                    found_shrines_keys.append(clean_id); classified_this_id = True
                elif "LOOTCHEST" in item_id_xml_upper:
                    found_chests_keys.append(clean_id); classified_this_id = True
                elif any(k in item_id_xml_upper for k in ["BOSS", "UNCLEFROST", "ANNIVERSARY_TITAN"]):
                    is_specific_event_boss = False
                    for event_key in ["UNCLEFROST", "ANNIVERSARY_TITAN"]: # Kunci bos event spesifik
                        if event_key in item_id_xml_upper:
                            if event_key not in found_event_bosses_keys: found_event_bosses_keys.append(event_key)
                            is_specific_event_boss = True; break
                    if not is_specific_event_boss: # Asumsikan dungeon boss
                         if clean_id not in found_dungeon_bosses_keys: found_dungeon_bosses_keys.append(clean_id)
                    classified_this_id = True
            
            # 3. Jika belum terklasifikasi, anggap sebagai mob biasa
            if not classified_this_id and ("RANDOM" in item_id_xml_upper or "MOB" in item_id_xml_upper or any(faction in item_id_xml_upper for faction in ["KEEPER", "HERETIC", "MORGANA", "UNDEAD", "AVALONIAN"])):
                mobs_by_tier_counters.setdefault(item_tier, Counter()).update([clean_id])
                # classified_this_id = True # Tidak perlu, ini defaultnya

        # Deteksi Bos dari Nama File (fallback untuk event boss jika tidak ada di XML tile)
        for file_path in self.used_files:
            filename_upper = os.path.basename(file_path).upper()
            if "UNCLEFROST" in filename_upper and "UNCLEFROST" not in found_event_bosses_keys: 
                found_event_bosses_keys.append("UNCLEFROST"); fetch_and_update_id_from_api("UNCLEFROST") 
            if "ANNIVERSARY_TITAN" in filename_upper and "ANNIVERSARY_TITAN" not in found_event_bosses_keys: 
                found_event_bosses_keys.append("ANNIVERSARY_TITAN"); fetch_and_update_id_from_api("ANNIVERSARY_TITAN")
        
        print(f"DEBUG Hasil Akhir: EventBosses: {Counter(found_event_bosses_keys)}, DungeonBosses: {Counter(found_dungeon_bosses_keys)}, Chests: {Counter(found_chests_keys)}, Shrines: {Counter(found_shrines_keys)}, MobsByTier: {mobs_by_tier_counters}, Exits: {len(found_exits_filenames)}")
        
        return {
            "event_bosses": Counter(found_event_bosses_keys),
            "dungeon_bosses": Counter(found_dungeon_bosses_keys),
            "chests": Counter(found_chests_keys),
            "shrines": Counter(found_shrines_keys),
            "mobs_by_tier": mobs_by_tier_counters, 
            "exits": found_exits_filenames,
        }