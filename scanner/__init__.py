import json
import time
from dataclasses import dataclass, field # Menggunakan dataclasses untuk struktur event
from typing import Dict, Any, Optional, Tuple, List

# Asumsikan utilitas ini sudah ada dan berfungsi dari direktori .utils
# Jika PhotonParser ada di scanner/__init__.py, maka impornya menjadi:
from .utils.binary import BinaryStream
# from .utils.config import Config # Uncomment jika Anda menggunakan Config di parser
from .utils.logging import logger # Asumsikan logger sudah dikonfigurasi

# --- Definisi Konstanta Tipe (untuk diimpor oleh gui.py) ---
TYPE_EVENT_BOSS = "EVENT_BOSS"
TYPE_DUNGEON_BOSS = "DUNGEON_BOSS"
TYPE_CHEST = "CHEST"
TYPE_SHRINE = "SHRINE"
# Anda mungkin ingin mengganti nilai string ini dengan yang lebih spesifik jika perlu

# --- Fungsi untuk Memuat Terjemahan ---
# Diasumsikan Anda memiliki file localization.json di root proyek
# atau di path yang dapat diakses.
# Struktur localization.json yang diasumsikan:
# {
#   "EN_US": { "@TAG_LOKALISASI_1": "Teks Inggris 1", ... },
#   "ID_ID": { "@TAG_LOKALISASI_1": "Teks Indonesia 1", ... }
# }
_translations = {}
_current_language = "EN_US" # Bahasa default

def load_translations(filepath="localization.json", language="EN_US"):
    """
    Memuat data terjemahan dari file JSON.
    """
    global _translations, _current_language
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            all_langs_translations = json.load(f)
            if language in all_langs_translations:
                _translations = all_langs_translations[language]
                _current_language = language
                logger.info(f"Terjemahan untuk bahasa '{language}' berhasil dimuat dari '{filepath}'. Total entri: {len(_translations)}")
            elif "EN_US" in all_langs_translations: # Fallback ke Inggris jika bahasa yang diminta tidak ada
                _translations = all_langs_translations["EN_US"]
                _current_language = "EN_US"
                logger.warning(f"Bahasa '{language}' tidak ditemukan di '{filepath}'. Menggunakan fallback EN_US. Total entri: {len(_translations)}")
            else:
                logger.error(f"Tidak ada data terjemahan untuk '{language}' atau EN_US di '{filepath}'.")
                _translations = {}
            return _translations
    except FileNotFoundError:
        logger.error(f"File lokalisasi '{filepath}' tidak ditemukan.")
        _translations = {}
        return _translations
    except json.JSONDecodeError:
        logger.error(f"Error mem-parse JSON dari file lokalisasi '{filepath}'.")
        _translations = {}
        return _translations
    except Exception as e:
        logger.error(f"Error tidak terduga saat memuat terjemahan dari '{filepath}': {e}")
        _translations = {}
        return _translations

def get_translation(tag: str, default_text: Optional[str] = None) -> str:
    """
    Mendapatkan teks terjemahan untuk tag tertentu.
    Jika tag tidak ditemukan, mengembalikan tag itu sendiri atau default_text.
    """
    if default_text is None:
        default_text = tag # Kembalikan tag jika tidak ada default dan tidak ditemukan
    return _translations.get(tag, default_text)

# Panggil load_translations saat modul diimpor untuk memuat bahasa default
# Anda mungkin ingin memindahkan path file ke config atau menentukannya secara dinamis
load_translations()


# --- Definisi Objek Event Terstruktur ---
# Sebaiknya pindahkan ini ke file terpisah, misalnya scanner/events.py, lalu impor.
@dataclass
class GameEvent:
    """Kelas dasar untuk semua event game yang dipancarkan."""
    # Semua field dengan default di kelas dasar harus keyword-only
    # jika kelas turunan akan menambahkan argumen posisi tanpa default.
    timestamp: float = field(default_factory=time.time, kw_only=True)
    raw_event_code: Optional[int] = field(default=None, kw_only=True)
    raw_parameters: Optional[Dict[int, Any]] = field(default=None, kw_only=True)

    def __str__(self):
        return f"[{self.__class__.__name__}]"

@dataclass
class UnknownEvent(GameEvent):
    """Event untuk kode yang tidak dikenal atau tidak ada handlernya."""
    event_code: int # Argumen posisi, tanpa default
    parameters: Dict[int, Any] # Argumen posisi, tanpa default

    def __str__(self):
        return f"[{self.__class__.__name__}] Code: {self.event_code}, Params: {self.parameters}"

@dataclass
class MobSpawnedEvent(GameEvent):
    entity_id: int
    type_id: str # Type ID dari database.json (kunci internal_id)
    name: str    # Nama dari database.json (misalnya, name_en)
    position: Tuple[float, float]
    # Field berikut adalah opsional dan memiliki nilai default, jadi tidak masalah urutannya
    # setelah field non-default di atas.
    max_health: Optional[float] = None
    current_health: Optional[float] = None
    category: Optional[str] = None # MOB, BOSS, MINIBOSS
    faction: Optional[str] = None
    tier: Optional[str] = None

    def __str__(self):
        return f"[{self.__class__.__name__}] ID: {self.entity_id}, Type: {self.type_id}, Name: '{self.name}', Cat: {self.category}, Pos: {self.position}"

@dataclass
class EntityDeathEvent(GameEvent):
    victim_id: int # Argumen posisi, tanpa default
    # Field berikut opsional
    victim_name: Optional[str] = None
    victim_category: Optional[str] = None 
    killer_id: Optional[int] = None
    killer_name: Optional[str] = None
    
    def __str__(self):
        return f"[{self.__class__.__name__}] Victim: {self.victim_id} ({self.victim_name or 'N/A'}) killed by Killer: {self.killer_id} ({self.killer_name or 'N/A'})"

@dataclass
class ChestEvent(GameEvent): 
    chest_id: int # Argumen posisi, tanpa default
    chest_type_id: str # Argumen posisi, tanpa default
    chest_name: str # Argumen posisi, tanpa default
    # Field berikut opsional
    chest_quality: Optional[str] = None
    chest_category: Optional[str] = None 
    position: Optional[Tuple[float, float]] = None
    opener_id: Optional[int] = None 

    def __str__(self):
        action = "Opened" if self.opener_id else "Appeared"
        return f"[{self.__class__.__name__}] {action}: ID {self.chest_id}, Name '{self.chest_name}', Quality: {self.chest_quality}"

# --- Kode Event Albion Online (SANGAT PENTING: INI HANYA CONTOH PLACEHOLDER!) ---
ALBION_EVENT_CODES = {
    "NewCharacter": 2,
    "CharacterEquipmentChanged": 7,
    "HealthUpdate": 9,
    "PlayerMovement": 15,
    "NewObject": 23,
    "CharacterDeath": 102,
    "NewLootObject": 156,
    "ChestOpened": 157,
}


class PhotonParser:
    def __init__(self, database_path='database.json'):
        self._entity_database = self._load_entity_database(database_path)
        self._unknown_event_codes_logged = set()
        self._unknown_response_opcodes_logged = set()

        self.event_handlers = {
            ALBION_EVENT_CODES.get("NewCharacter"): self._handle_new_character,
            ALBION_EVENT_CODES.get("CharacterDeath"): self._handle_character_death,
            ALBION_EVENT_CODES.get("NewObject"): self._handle_new_object,
            ALBION_EVENT_CODES.get("ChestOpened"): self._handle_chest_opened,
        }
        self.response_handlers = {}

    def _load_entity_database(self, db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                db = json.load(f)
                logger.info(f"Database entitas berhasil dimuat dari '{db_path}'. Total entitas: {len(db)}")
                return db
        except FileNotFoundError:
            logger.error(f"PENTING: File database '{db_path}' tidak ditemukan. Jalankan build_database.py terlebih dahulu.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error mem-parse database dari '{db_path}'.")
            return {}

    def _get_entity_details(self, internal_id_key: str) -> Optional[Dict[str, Any]]:
        return self._entity_database.get(str(internal_id_key))

    def parse_message(self, body: bytes) -> Optional[GameEvent]:
        if not body:
            logger.warning("Menerima body pesan kosong.")
            return None
        
        stream = BinaryStream(body)
        try:
            msg_type = stream.read_byte()
            
            if msg_type == 2: # OperationRequest
                op_code = stream.read_byte()
                parameters = self._deserialize_parameter_table(stream)
                # Tidak menghasilkan GameEvent untuk request saat ini
                return None 
            elif msg_type == 3: # OperationResponse
                op_code = stream.read_byte()
                return_code = stream.read_short()
                debug_message_val = self._deserialize_photon_value(stream) 
                debug_message = str(debug_message_val) if debug_message_val is not None else None
                parameters = self._deserialize_parameter_table(stream)
                return self._handle_operation_response(op_code, return_code, debug_message, parameters, raw_params=parameters)
            elif msg_type == 4: # EventData
                event_code = stream.read_byte() 
                parameters = self._deserialize_parameter_table(stream)
                return self._handle_event_data(event_code, parameters, raw_params=parameters)
            else:
                logger.warning(f"Tipe pesan Photon tidak dikenal: {msg_type} pada awal stream. Body: {body[:20].hex()}")
                return None
        except IndexError: # Lebih spesifik dari Exception umum
            logger.error(f"Stream berakhir prematur saat parsing tipe pesan Photon. Body: {body[:20].hex()}")
            return None
        except ValueError as ve: # Dari _deserialize_photon_value jika tipe tidak dikenal
             logger.error(f"ValueError saat parsing pesan Photon: {ve}. Body Awal: {body[:30].hex()}")
             return None
        except Exception as e: # Tangkap semua exception lain
            logger.error(f"Error umum saat parsing pesan Photon: {e}, Body Awal: {body[:30].hex()}")
            return None

    def _handle_event_data(self, event_code: int, parameters: Dict[int, Any], raw_params) -> Optional[GameEvent]:
        handler = self.event_handlers.get(event_code)
        # Membuat instance GameEvent dengan kw_only args
        base_event_kwargs = {'raw_event_code': event_code, 'raw_parameters': raw_params}
        if handler:
            try:
                # Handler sekarang harus menerima **kwargs dan meneruskannya ke konstruktor eventnya
                return handler(parameters, **base_event_kwargs)
            except Exception as e:
                logger.error(f"Error di handler untuk event code {event_code}: {e}. Params: {parameters}")
                self._log_unknown_event_details(event_code, parameters, error=str(e))
                return UnknownEvent(event_code=event_code, parameters=parameters, **base_event_kwargs)
        else:
            if event_code not in self._unknown_event_codes_logged:
                logger.info(f"Tidak ada handler untuk event code: {event_code}. Params: {parameters}")
                self._unknown_event_codes_logged.add(event_code)
                self._log_unknown_event_details(event_code, parameters)
            return UnknownEvent(event_code=event_code, parameters=parameters, **base_event_kwargs)

    def _handle_operation_response(self, op_code: int, return_code: int, debug_message: Optional[str], parameters: Dict[int, Any], raw_params) -> Optional[GameEvent]:
        handler = self.response_handlers.get(op_code)
        base_event_kwargs = {'raw_event_code': op_code, 'raw_parameters': raw_params} # op_code sebagai raw_event_code
        if handler:
            try:
                return handler(return_code, debug_message, parameters, **base_event_kwargs)
            except Exception as e:
                logger.error(f"Error di handler response untuk OpCode {op_code}: {e}. Params: {parameters}")
                self._log_unknown_response_details(op_code, return_code, debug_message, parameters, error=str(e))
                return None 
        else:
            if op_code not in self._unknown_response_opcodes_logged:
                logger.info(f"Tidak ada handler spesifik untuk response OpCode: {op_code}, RC: {return_code}. Params: {parameters}")
                self._unknown_response_opcodes_logged.add(op_code)
                self._log_unknown_response_details(op_code, return_code, debug_message, parameters)
            return None

    def _handle_new_character(self, parameters: Dict[int, Any], **kwargs) -> Optional[MobSpawnedEvent]:
        try:
            entity_id = int(parameters.get(0))
            type_id_key = str(parameters.get(1)) 

            pos_x = parameters.get(7) 
            pos_z = parameters.get(9) 
            position = (float(pos_x), float(pos_z)) if pos_x is not None and pos_z is not None else (0.0, 0.0)

            health_array = parameters.get(15)
            current_health, max_health = None, None
            if isinstance(health_array, list) and len(health_array) >= 2:
                current_health = float(health_array[0])
                max_health = float(health_array[1])
            
            if entity_id is None or not type_id_key:
                logger.warning(f"Parameter ID atau TypeIDKey hilang di NewCharacter: {parameters}")
                return None

            entity_details = self._get_entity_details(type_id_key)
            name_from_db, category_from_db, faction_from_db, tier_from_db = "Unknown Entity", "UNKNOWN", "UNKNOWN", "0"

            if entity_details:
                name_from_db = entity_details.get('name_en', type_id_key) # Gunakan name_en dari database
                category_from_db = entity_details.get('category', "UNKNOWN")
                faction_from_db = entity_details.get('faction', "UNKNOWN")
                tier_from_db = entity_details.get('tier', "0")
            else:
                logger.warning(f"TypeIDKey '{type_id_key}' tidak ditemukan di database untuk NewCharacter id {entity_id}.")

            name_from_event = parameters.get(2) 
            # Prioritaskan nama dari database jika ada, kecuali jika kategori bukan MOB/BOSS
            # atau jika nama dari event lebih spesifik (misalnya, nama pemain)
            final_name = name_from_db
            if category_from_db not in ["MOB", "BOSS", "MINIBOSS", "CHAMPION_MOB"] and name_from_event:
                 final_name = str(name_from_event)
            elif not entity_details and name_from_event: # Jika tidak ada di DB tapi ada nama di event
                 final_name = str(name_from_event)


            if category_from_db in ["MOB", "BOSS", "MINIBOSS", "CHAMPION_MOB"]:
                # Gunakan get_translation untuk nama yang akan ditampilkan jika perlu
                # translated_name = get_translation(entity_details.get('ingame_id_key'), final_name) if entity_details else final_name
                # logger.info(f"MOB/BOSS SPAWNED: ID={entity_id}, TypeKey={type_id_key}, Name='{translated_name}', Cat={category_from_db}, Pos={position}, HP={current_health}/{max_health}")
                return MobSpawnedEvent(
                    entity_id=entity_id, type_id=type_id_key, name=final_name, # Simpan nama EN di event object
                    position=position, max_health=max_health, current_health=current_health,
                    category=category_from_db, faction=faction_from_db, tier=tier_from_db,
                    **kwargs 
                )
            else:
                return None
        except Exception as e:
            logger.error(f"Error parsing NewCharacter (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)


    def _handle_character_death(self, parameters: Dict[int, Any], **kwargs) -> Optional[EntityDeathEvent]:
        try:
            victim_id = int(parameters.get(0))
            killer_id_param = parameters.get(1)
            killer_id = int(killer_id_param) if killer_id_param is not None else None

            victim_name_param = parameters.get(4)
            killer_name_param = parameters.get(5)

            victim_name = str(victim_name_param) if victim_name_param else None
            killer_name = str(killer_name_param) if killer_name_param else None
            
            victim_category = None # TODO: Dapatkan ini dari pelacakan entitas aktif

            # logger.info(f"DEATH: VictimID={victim_id} ({victim_name or 'N/A'}), KillerID={killer_id} ({killer_name or 'N/A'})")
            return EntityDeathEvent(
                victim_id=victim_id, victim_name=victim_name, victim_category=victim_category,
                killer_id=killer_id, killer_name=killer_name,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error parsing CharacterDeath (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)

    def _handle_new_object(self, parameters: Dict[int, Any], **kwargs) -> Optional[GameEvent]:
        try:
            object_id = int(parameters.get(0))
            type_id_key = str(parameters.get(1))

            pos_array = parameters.get(2)
            position = (float(pos_array[0]), float(pos_array[1])) if isinstance(pos_array, (list, tuple)) and len(pos_array) >= 2 else None

            if object_id is None or not type_id_key:
                logger.warning(f"Parameter ID atau TypeIDKey hilang di NewObject: {parameters}")
                return None

            entity_details = self._get_entity_details(type_id_key)
            name, category, quality = "Unknown Object", "UNKNOWN_OBJECT", None

            if entity_details:
                name = entity_details.get('name_en', type_id_key) # Gunakan name_en dari database
                category = entity_details.get('category', "UNKNOWN_OBJECT")
                quality = entity_details.get('quality')
            else:
                logger.warning(f"TypeIDKey '{type_id_key}' tidak ditemukan di database untuk NewObject id {object_id}.")

            if category and category.startswith("CHEST_"):
                # translated_name = get_translation(entity_details.get('ingame_id_key'), name) if entity_details else name
                # logger.info(f"CHEST SPAWNED (via NewObject): ID={object_id}, TypeKey={type_id_key}, Name='{translated_name}', Cat={category}, Quality={quality}, Pos={position}")
                return ChestEvent(
                    chest_id=object_id, chest_type_id=type_id_key, chest_name=name, # Simpan name_en
                    chest_quality=quality, chest_category=category, position=position,
                    **kwargs
                )
            else: # Objek lain yang mungkin tidak kita pedulikan untuk saat ini
                return None
        except Exception as e:
            logger.error(f"Error parsing NewObject (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)

    def _handle_chest_opened(self, parameters: Dict[int, Any], **kwargs) -> Optional[ChestEvent]:
        try:
            chest_id = int(parameters.get(0))
            opener_id = int(parameters.get(1))
            chest_type_id_key = str(parameters.get(2)) if parameters.get(2) else None # Mungkin tidak selalu ada
            
            chest_name, chest_quality, chest_category = "Unknown Chest", None, None

            if chest_type_id_key:
                entity_details = self._get_entity_details(chest_type_id_key)
                if entity_details:
                    chest_name = entity_details.get('name_en', chest_type_id_key) # Gunakan name_en
                    chest_quality = entity_details.get('quality')
                    chest_category = entity_details.get('category')
                else:
                    logger.warning(f"TypeIDKey '{chest_type_id_key}' tidak ditemukan di database untuk ChestOpened id {chest_id}.")
            else:
                # Jika type_id_key tidak ada di event buka, kita mungkin perlu melacaknya dari saat spawn.
                # Untuk sekarang, kita tandai sebagai tidak diketahui jika tidak ada di event.
                logger.warning(f"ChestOpened event untuk ID {chest_id} tanpa TypeIDKey di parameter. Info peti mungkin tidak lengkap.")
                # Anda bisa mencoba mencari chest_id di daftar peti yang aktif/terlihat yang dilacak oleh DungeonTracker.

            # translated_name = get_translation(entity_details.get('ingame_id_key'), chest_name) if chest_type_id_key and entity_details else chest_name
            # logger.info(f"CHEST OPENED: ID={chest_id}, Name='{translated_name}', OpenerID={opener_id}, Quality={chest_quality}")
            return ChestEvent(
                chest_id=chest_id, chest_type_id=chest_type_id_key or "UNKNOWN_CHEST_TYPE", 
                chest_name=chest_name, # Simpan name_en
                chest_quality=chest_quality, chest_category=chest_category,
                opener_id=opener_id,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error parsing ChestOpened (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)

    def _deserialize_parameter_table(self, stream: BinaryStream) -> Dict[int, Any]:
        param_count = stream.read_short()
        parameters = {}
        for _ in range(param_count):
            key = stream.read_byte() 
            value = self._deserialize_photon_value(stream)
            parameters[key] = value
        return parameters

    def _deserialize_photon_value(self, stream: BinaryStream) -> Any:
        type_code = stream.read_byte()
        if type_code == 0: return None
        elif type_code == 42: return self._deserialize_parameter_table(stream)
        elif type_code == 68: return stream.read_double()
        elif type_code == 97:
            size = stream.read_int() 
            return stream.read_bytes(size)
        elif type_code == 98: return stream.read_byte()
        elif type_code == 100: return stream.read_double()
        elif type_code == 102: return stream.read_float()
        elif type_code == 104: return self._deserialize_parameter_table(stream)
        elif type_code == 105: return stream.read_int()
        elif type_code == 107: return stream.read_short()
        elif type_code == 108: return stream.read_long()
        elif type_code == 110:
            size = stream.read_int()
            return [stream.read_int() for _ in range(size)]
        elif type_code == 111: return stream.read_bool()
        elif type_code == 115: return stream.read_string() 
        elif type_code == 118:
            size = stream.read_short()
            arr = [self._deserialize_photon_value(stream) for _ in range(size)]
            return arr
        elif type_code == 120:
            size = stream.read_int()
            return [stream.read_long() for _ in range(size)]
        elif type_code == 121:
            size = stream.read_short() 
            return [stream.read_string() for _ in range(size)]
        else:
            logger.error(f"Tipe data Photon TIDAK DIKENAL dalam parameter: {type_code} at stream pos {stream.tell()-1}. Sisa stream mungkin tidak valid.")
            raise ValueError(f"Tipe data Photon tidak dikenal: {type_code} at stream pos {stream.tell()-1}")

    def _log_unknown_event_details(self, event_code, parameters, error=None):
        log_entry = f"--- Unknown/Unhandled Event or Error ---\n"
        log_entry += f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        log_entry += f"EventCode: {event_code}\n"
        log_entry += f"Parameters: {json.dumps(parameters, default=lambda o: f'<bytes len={len(o)}>' if isinstance(o, bytes) else repr(o), indent=2)}\n"
        if error: log_entry += f"Error: {error}\n"
        log_entry += f"--------------------------------------\n\n"
        try:
            with open('unknown_ids.txt', 'a', encoding='utf-8') as f: f.write(log_entry)
        except IOError: logger.error("Gagal menulis ke unknown_ids.txt")

    def _log_unknown_response_details(self, op_code, return_code, debug_message, parameters, error=None):
        log_entry = f"--- Unknown/Unhandled Response or Error ---\n"
        log_entry += f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        log_entry += f"OperationCode: {op_code}\n"
        log_entry += f"ReturnCode: {return_code}\n"
        log_entry += f"DebugMessage: {debug_message}\n"
        log_entry += f"Parameters: {json.dumps(parameters, default=lambda o: f'<bytes len={len(o)}>' if isinstance(o, bytes) else repr(o), indent=2)}\n"
        if error: log_entry += f"Error: {error}\n"
        log_entry += f"--------------------------------------\n\n"
        try:
            with open('unknown_ids.txt', 'a', encoding='utf-8') as f: f.write(log_entry)
        except IOError: logger.error("Gagal menulis ke unknown_ids.txt")
