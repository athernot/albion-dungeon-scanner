import json
import os
import xml.etree.ElementTree as ET # Library standar Python untuk parsing XML

# --- Konfigurasi Sumber Data ---
MOBS_XML_FILE = 'mobs.xml'
LOOTCHESTS_JSON_FILE = 'lootchests.json'

# --- PATH KE FILE LOKALISASI NYATA ANDA ---
# GANTI INI dengan path yang benar ke file lokalisasi Albion Anda.
# Untuk demo ini, kita akan membuat file simulasi.
ACTUAL_LOCALIZATION_EN_FILE = 'simulated_albion_localization_EN.json'
ACTUAL_LOCALIZATION_ID_FILE = 'simulated_albion_localization_ID.json' # Bahasa Indonesia

# Nama file output untuk database yang dibangun
DATABASE_OUTPUT_FILE = 'database.json'

def create_simulated_actual_localization_files_if_not_exists():
    """
    Membuat file lokalisasi (simulasi) jika belum ada.
    Ini HANYA untuk demo. Ganti dengan file lokalisasi Albion Anda yang sebenarnya.
    Formatnya diasumsikan JSON dictionary: {"@TAG_LOKALISASI": "Teks Terjemahan"}
    """
    simulated_loc_en = {
        # Kunci dari mobs.xml
        "@MOB_NAME_T4_MOB_UNDEAD_SKELETON": "Undead Skeleton (Actual EN)",
        "@MOB_NAME_T5_MOB_HERETIC_BERSERKER": "Heretic Berserker (Actual EN)",
        "@MOB_NAME_T8_MOB_AVALONIAN_ARCHER": "Avalonian Archer (Actual EN)",
        "@BOSS_NAME_T6_MOB_KEEPER_BEARBOSS": "Keeper Bear Chieftain (Actual EN)",
        "@MOB_MOB_WOLF": "Wolf (Actual EN)",
        "@MOB_NAME_ROAMING_TESTMOB_LVL1": "Roaming Test Mob (Actual EN)", # Contoh tambahan

        # Kunci dari lootchests.json
        "@LOOTCHEST_NAME_STANDARD": "Standard Chest (Actual EN)",
        "@LOOTCHEST_NAME_UNCOMMON": "Uncommon Chest (Actual EN)",
        "@LOOTCHEST_NAME_RARE": "Rare Chest (Actual EN)",
        "@LOOTCHEST_NAME_LEGENDARY": "Legendary Chest (Actual EN)",
        "@LOOTCHEST_NAME_BOSS_STANDARD": "Standard Boss Chest (Actual EN)",
        "@LOOTCHEST_NAME_BOSS_GREEN": "Green Boss Chest (Actual EN)",
        "@LOOTCHEST_NAME_BOSS_BLUE": "Blue Boss Chest (Actual EN)",
        "@LOOTCHEST_NAME_BOSS_PURPLE": "Purple Boss Chest (Actual EN)",
        "@LOOTCHEST_NAME_BOSS_GOLD": "Gold Boss Chest (Actual EN)",
        # Tambahkan lebih banyak contoh tag yang mungkin ada di mobs.xml/lootchests.json Anda
        "@MOB_NAME_T1_MOB_HIDE_RABBIT": "Rabbit (Actual EN)",
        "@MOB_NAME_T3_MOB_STONE_ROCK_ELEMENTAL": "Rock Elemental (Actual EN)"
    }
    simulated_loc_id = {
        "@MOB_NAME_T4_MOB_UNDEAD_SKELETON": "Tengkorak Hidup (Aktual ID)",
        "@MOB_NAME_T5_MOB_HERETIC_BERSERKER": "Pengamuk Bidaah (Aktual ID)",
        "@MOB_NAME_T8_MOB_AVALONIAN_ARCHER": "Pemanah Avalon (Aktual ID)",
        "@BOSS_NAME_T6_MOB_KEEPER_BEARBOSS": "Kepala Suku Beruang Penjaga (Aktual ID)",
        "@MOB_MOB_WOLF": "Serigala (Aktual ID)",
        "@MOB_NAME_ROAMING_TESTMOB_LVL1": "Mob Tes Keliling (Aktual ID)",

        "@LOOTCHEST_NAME_STANDARD": "Peti Standar (Aktual ID)",
        "@LOOTCHEST_NAME_UNCOMMON": "Peti Tidak Umum (Aktual ID)",
        "@LOOTCHEST_NAME_RARE": "Peti Langka (Aktual ID)",
        "@LOOTCHEST_NAME_LEGENDARY": "Peti Legendaris (Aktual ID)",
        "@LOOTCHEST_NAME_BOSS_STANDARD": "Peti Bos Standar (Aktual ID)",
        "@LOOTCHEST_NAME_BOSS_GREEN": "Peti Bos Hijau (Aktual ID)",
        "@LOOTCHEST_NAME_BOSS_BLUE": "Peti Bos Biru (Aktual ID)",
        "@LOOTCHEST_NAME_BOSS_PURPLE": "Peti Bos Ungu (Aktual ID)",
        "@LOOTCHEST_NAME_BOSS_GOLD": "Peti Bos Emas (Aktual ID)",
        "@MOB_NAME_T1_MOB_HIDE_RABBIT": "Kelinci (Aktual ID)",
        "@MOB_NAME_T3_MOB_STONE_ROCK_ELEMENTAL": "Elemental Batu (Aktual ID)"
    }

    files_to_create = {
        ACTUAL_LOCALIZATION_EN_FILE: simulated_loc_en,
        ACTUAL_LOCALIZATION_ID_FILE: simulated_loc_id
    }

    for filename, data_content in files_to_create.items():
        if not os.path.exists(filename):
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data_content, f, indent=4, ensure_ascii=False)
                print(f"File lokalisasi simulasi '{filename}' telah dibuat.")
            except IOError as e:
                print(f"Error saat membuat file simulasi '{filename}': {e}")
        else:
            print(f"File lokalisasi simulasi '{filename}' sudah ada.")


def parse_albion_localization_file(filepath, language_code=""):
    """
    Mem-parse file lokalisasi Albion.
    Saat ini mengasumsikan format JSON dictionary sederhana: {"@TAG": "Teks"}.
    ANDA MUNGKIN PERLU MENGUBAH FUNGSI INI jika format file lokalisasi Anda berbeda
    (misalnya, CSV, XML, atau format teks kustom lainnya).
    """
    print(f"Memuat data lokalisasi {language_code.upper()} dari '{filepath}'...")
    if not os.path.exists(filepath):
        print(f"  Peringatan: File lokalisasi '{filepath}' tidak ditemukan.")
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Jika file Anda bukan JSON dictionary sederhana, ubah logika parsing di sini
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"  Error: Format file lokalisasi '{filepath}' bukan dictionary JSON yang diharapkan.")
                return {}
            # Pastikan semua kunci adalah string dan dimulai dengan '@' untuk konsistensi
            # (Ini opsional, tapi bisa membantu standarisasi)
            # return {str(k).upper(): v for k, v in data.items() if str(k).startswith("@")}
            return {str(k): v for k, v in data.items()} # Biarkan kunci apa adanya untuk pencocokan
            
    except json.JSONDecodeError as e:
        print(f"  Error: Gagal mem-parse JSON dari file lokalisasi '{filepath}'. Detail: {e}")
        return {}
    except Exception as e:
        print(f"  Error saat memuat file lokalisasi '{filepath}': {e}")
        return {}

def load_json_from_file(filepath, file_description="data"): # Untuk lootchests.json
    if not os.path.exists(filepath):
        print(f"Peringatan: File {file_description} '{filepath}' tidak ditemukan.")
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Gagal mem-parse JSON dari file {file_description} '{filepath}'. Detail: {e}")
        return {}
    except Exception as e:
        print(f"Error saat memuat file {file_description} '{filepath}': {e}")
        return {}

def parse_mobs_xml(xml_filepath):
    parsed_entities = {}
    if not os.path.exists(xml_filepath):
        print(f"Error: File '{xml_filepath}' tidak ditemukan.")
        return parsed_entities
    try:
        tree = ET.parse(xml_filepath)
        root = tree.getroot()
        mob_elements = root.findall('.//Mob')
        if not mob_elements: mob_elements = root.findall('Mob')
        print(f"Menemukan {len(mob_elements)} elemen <Mob> di '{xml_filepath}'.")

        for mob_element in mob_elements:
            uniquename = mob_element.get('uniquename')
            if not uniquename: continue

            namelocatag = mob_element.get('namelocatag', '') # Jangan di-uppercase di sini, biarkan apa adanya untuk pencocokan
            faction = mob_element.get('faction', 'UNKNOWN_FACTION').upper()
            tier = mob_element.get('tier', '0')
            fame = mob_element.get('fame', '0')
            mobtypecategory = mob_element.get('mobtypecategory', '').lower()
            dangerstate = mob_element.get('dangerstate', '').lower()

            category = "MOB"
            if dangerstate == "boss" or dangerstate == "worldboss": category = "BOSS"
            elif dangerstate == "elite" or "elite" in mobtypecategory: category = "MINIBOSS"
            elif dangerstate == "champion" or "champion" in mobtypecategory: category = "CHAMPION_MOB"
            elif "boss" in mobtypecategory or "boss" in uniquename.lower() or (namelocatag and "boss" in namelocatag.lower()): category = "BOSS"
            elif "miniboss" in mobtypecategory: category = "MINIBOSS"
            
            display_type = uniquename
            if namelocatag and namelocatag.startswith("@"):
                temp_display_type = namelocatag.split('_')[-1] # Coba ambil bagian akhir dari tag
                # Heuristik sederhana untuk membersihkan display_type dari namelocatag
                if temp_display_type and not temp_display_type.isupper(): # Jika bukan semua huruf besar (seperti FACTION)
                    display_type = temp_display_type.replace("MOB", "").replace("BOSS", "").replace("NAME", "").replace("KEEPER", "Keeper").strip().title()
                if not display_type or len(display_type) < 3 : # Jika hasil aneh, fallback
                     parts = uniquename.split('_')
                     display_type = " ".join(p.capitalize() for p in parts[-2:]) if len(parts) > 1 else parts[0].capitalize()

            else:
                parts = uniquename.split('_')
                idx = -1
                for keyword in ["MOB", "BOSS", "TR", "SK", "FX", "QUEST"]: # Kata kunci yang mungkin mendahului nama sebenarnya
                    if keyword in parts:
                        try:
                            idx = parts.index(keyword)
                            break
                        except ValueError:
                            pass
                
                if idx != -1 and idx + 1 < len(parts):
                    display_type_parts = parts[idx+1:]
                    if display_type_parts[0].startswith("T") and display_type_parts[0][1:].isdigit() and len(display_type_parts) > 1:
                        display_type_parts = display_type_parts[1:]
                    display_type = " ".join(p.capitalize() for p in display_type_parts if not p.startswith("LVL"))
                elif len(parts) > 0:
                    display_type = parts[-1].capitalize()
            
            if not display_type: display_type = uniquename # Fallback terakhir

            parsed_entities[uniquename] = {
                "ingame_id_key": namelocatag, "category": category, "faction": faction,
                "tier": tier, "fame": fame, "display_type": display_type,
                "source_file": "mobs.xml", "raw_mobtypecategory": mobtypecategory,
                "raw_dangerstate": dangerstate,
            }
    except ET.ParseError as e: print(f"Error parsing XML '{xml_filepath}': {e}")
    except Exception as e: print(f"Error tidak terduga saat memproses '{xml_filepath}': {e}")
    return parsed_entities

def parse_lootchests_json(json_filepath):
    parsed_entities = {}
    chest_data_root = load_json_from_file(json_filepath, "loot chests")
    if not chest_data_root: return parsed_entities

    loot_chest_list = []
    if isinstance(chest_data_root, dict):
        if "LootChests" in chest_data_root and "LootChest" in chest_data_root["LootChests"]:
            loot_chest_list = chest_data_root["LootChests"]["LootChest"]
        elif "LootChest" in chest_data_root: loot_chest_list = chest_data_root["LootChest"]
    elif isinstance(chest_data_root, list): loot_chest_list = chest_data_root

    if not isinstance(loot_chest_list, list):
        print(f"Peringatan: Tidak menemukan list 'LootChest' yang valid di '{json_filepath}'.")
        return parsed_entities
        
    print(f"Menemukan {len(loot_chest_list)} entri peti di '{json_filepath}'.")

    for chest_entry in loot_chest_list:
        if not isinstance(chest_entry, dict): continue
        uniquename = chest_entry.get('@uniquename')
        if not uniquename: continue

        namelocatag = chest_entry.get('@namelocatag', '') # Biarkan apa adanya untuk pencocokan
        
        quality = "UNKNOWN"
        dangerstate = chest_entry.get('@dangerstate', '').lower()
        # File lootchests.json Anda memiliki 'RareStateMappings' yang bisa jadi lebih akurat.
        # Namun, untuk kesederhanaan, kita gunakan heuristik dari uniquename/dangerstate dulu.
        # Anda bisa memperbaikinya dengan mem-parse RareStateMappings dan mencocokkan @rarity
        if "legendary" in uniquename.lower() or "gold" in uniquename.lower() or dangerstate == "legendary": quality = "GOLD"
        elif "epic" in uniquename.lower() or "purple" in uniquename.lower() or dangerstate == "rare": quality = "PURPLE" # 'rare' di dangerstate seringkali berarti ungu
        elif "rare" in uniquename.lower() or "blue" in uniquename.lower() or dangerstate == "uncommon": quality = "BLUE" # 'uncommon' di dangerstate seringkali berarti biru
        elif "uncommon" in uniquename.lower() or "green" in uniquename.lower() or dangerstate == "standard": quality = "GREEN" # 'standard' di dangerstate seringkali berarti hijau
        elif "standard" in uniquename.lower() or "wood" in uniquename.lower() or dangerstate == "normal" or dangerstate == "none": quality = "WOOD"
        
        category = "CHEST_UNKNOWN"
        if "boss" in uniquename.lower() or (namelocatag and "boss" in namelocatag.lower()) or "boss" in dangerstate :
            category = f"CHEST_BOSS_{quality}" if quality != "UNKNOWN" else "CHEST_BOSS"
        else: # Anggap peti biasa
            category = f"CHEST_STANDARD_{quality}" if quality != "UNKNOWN" else "CHEST_STANDARD"

        display_type = namelocatag
        if namelocatag and namelocatag.startswith("@"):
            display_type = namelocatag.replace("@LOOTCHEST_NAME_", "").replace("_", " ").title()
        if not display_type or display_type.startswith("@"): # Fallback
            display_type = uniquename.replace("_", " ").title()


        parsed_entities[uniquename] = {
            "ingame_id_key": namelocatag, "category": category, "quality": quality,
            "display_type": display_type, "faction": chest_entry.get('@faction', 'NEUTRAL').upper(),
            "tier": chest_entry.get('@tier', '0'), "source_file": "lootchests.json"
        }
    return parsed_entities

def build_database_with_actual_localization():
    print("Memulai proses build database dengan parser lokalisasi nyata (simulasi)...")

    # 1. Buat file lokalisasi simulasi jika belum ada (HANYA UNTUK DEMO)
    create_simulated_actual_localization_files_if_not_exists()
    print("-" * 30)

    # 2. Parse mobs.xml
    mob_entities = parse_mobs_xml(MOBS_XML_FILE)

    # 3. Parse lootchests.json
    chest_entities = parse_lootchests_json(LOOTCHESTS_JSON_FILE)

    # 4. Gabungkan semua entitas
    all_parsed_entities = {}
    all_parsed_entities.update(mob_entities)
    all_parsed_entities.update(chest_entities)

    # 5. Muat data lokalisasi menggunakan parser baru
    #    GANTI ACTUAL_LOCALIZATION_EN_FILE dan ACTUAL_LOCALIZATION_ID_FILE
    #    dengan path ke file lokalisasi Albion Anda yang sebenarnya.
    localization_en = parse_albion_localization_file(ACTUAL_LOCALIZATION_EN_FILE, "EN")
    localization_id = parse_albion_localization_file(ACTUAL_LOCALIZATION_ID_FILE, "ID")

    if not all_parsed_entities:
        print("Kritis: Tidak ada data entitas yang berhasil di-parse. Proses build database dibatalkan.")
        return
    if not localization_en and not localization_id:
        print("Peringatan: Tidak ada data lokalisasi yang berhasil dimuat. Nama akan menjadi generik.")


    # 6. Proses dan gabungkan data untuk membuat database output
    output_database = {}
    print("\nMemproses entitas untuk database output dengan lokalisasi...")
    processed_count = 0

    for internal_id, properties in all_parsed_entities.items():
        # `ingame_id_key` adalah `namelocatag` dari file XML/JSON sumber
        ingame_localization_key = properties.get("ingame_id_key", "")

        # Dapatkan nama dari data lokalisasi yang sudah di-parse
        # Penting: Pastikan `ingame_localization_key` (misalnya, "@MOB_NAME_...")
        # cocok dengan kunci di file lokalisasi Anda.
        name_en = localization_en.get(ingame_localization_key)
        name_id = localization_id.get(ingame_localization_key)

        # Fallback jika nama tidak ditemukan di lokalisasi
        if name_en is None:
            name_en = properties.get("display_type", internal_id) # Gunakan display_type atau ID
            if ingame_localization_key: # Hanya cetak jika ada key tapi tidak ketemu
                 print(f"  Peringatan EN: Lokalisasi tidak ditemukan untuk kunci '{ingame_localization_key}' (ID: {internal_id}). Menggunakan '{name_en}'.")
        if name_id is None:
            name_id = name_en # Fallback ke nama Inggris jika Bahasa Indonesia tidak ada
            if ingame_localization_key and localization_id: # Hanya cetak jika ada key tapi tidak ketemu di ID
                 print(f"  Peringatan ID: Lokalisasi tidak ditemukan untuk kunci '{ingame_localization_key}' (ID: {internal_id}). Menggunakan '{name_id}'.")


        output_database[internal_id] = {
            "internal_id": internal_id,
            "name_en": name_en,
            "name_id": name_id,
            "category": properties.get("category", "UNKNOWN").upper(),
            "display_type": properties.get("display_type", name_en), # display_type bisa juga nama EN jika lebih baik
            "faction": properties.get("faction", "UNKNOWN").upper(),
            "tier": properties.get("tier", "0"),
        }
        # Tambahkan field spesifik
        if "fame" in properties: output_database[internal_id]["fame"] = properties["fame"]
        if "quality" in properties: output_database[internal_id]["quality"] = properties["quality"].upper()
        if "source_file" in properties: output_database[internal_id]["source_file"] = properties["source_file"]
        # Untuk debugging, Anda bisa menyimpan ingame_localization_key juga
        # output_database[internal_id]["loc_key"] = ingame_localization_key


        processed_count += 1
        if processed_count <= 10 or processed_count % 500 == 0: # Kurangi frekuensi cetak
             source = output_database[internal_id].get('source_file', 'N/A')
             print(f"  Diproses: [{source}] {internal_id} -> {output_database[internal_id]['category']} '{name_en}' / '{name_id}'")

    # 7. Tulis hasil ke file database.json
    try:
        with open(DATABASE_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_database, f, indent=4, ensure_ascii=False)
        print(f"\nDatabase berhasil dibangun dan disimpan di '{DATABASE_OUTPUT_FILE}'")
        print(f"Total entitas dalam database: {len(output_database)}")
    except IOError as e: print(f"Error: Gagal menulis database ke '{DATABASE_OUTPUT_FILE}'. Detail: {e}")
    except Exception as e: print(f"Error tidak terduga saat menulis database: {e}")

if __name__ == "__main__":
    build_database_with_actual_localization()
    print("\nProses build database selesai.")
