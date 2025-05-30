import json
import time
from dataclasses import dataclass, field # Menggunakan dataclasses untuk struktur event
from typing import Dict, Any, Optional, Tuple, List

# Asumsikan utilitas ini sudah ada dan berfungsi dari direktori .utils
# Jika PhotonParser ada di scanner/__init__.py, maka impornya menjadi:
from .utils.binary import BinaryStream
# from .utils.config import Config # Uncomment jika Anda menggunakan Config di parser
from .utils.logging import logger # Asumsikan logger sudah dikonfigurasi

# --- Definisi Objek Event Terstruktur ---
# Sebaiknya pindahkan ini ke file terpisah, misalnya scanner/events.py, lalu impor.
@dataclass
class GameEvent:
    """Kelas dasar untuk semua event game yang dipancarkan."""
    timestamp: float = field(default_factory=time.time)
    raw_event_code: Optional[int] = None # Untuk debugging, simpan kode event asli
    raw_parameters: Optional[Dict[int, Any]] = None # Untuk debugging

    def __str__(self):
        return f"[{self.__class__.__name__}]"

@dataclass
class UnknownEvent(GameEvent):
    """Event untuk kode yang tidak dikenal atau tidak ada handlernya."""
    event_code: int
    parameters: Dict[int, Any]

    def __str__(self):
        return f"[{self.__class__.__name__}] Code: {self.event_code}, Params: {self.parameters}"

@dataclass
class MobSpawnedEvent(GameEvent):
    entity_id: int
    type_id: str # Type ID dari database.json (kunci internal_id)
    name: str    # Nama dari database.json (misalnya, name_en)
    position: Tuple[float, float]
    max_health: Optional[float] = None
    current_health: Optional[float] = None
    category: Optional[str] = None # MOB, BOSS, MINIBOSS
    faction: Optional[str] = None
    tier: Optional[str] = None

    def __str__(self):
        return f"[{self.__class__.__name__}] ID: {self.entity_id}, Type: {self.type_id}, Name: '{self.name}', Cat: {self.category}, Pos: {self.position}"

@dataclass
class EntityDeathEvent(GameEvent):
    victim_id: int
    victim_name: Optional[str] = None
    victim_category: Optional[str] = None # Untuk membedakan apakah mob/boss yang mati
    killer_id: Optional[int] = None
    killer_name: Optional[str] = None
    
    def __str__(self):
        return f"[{self.__class__.__name__}] Victim: {self.victim_id} ({self.victim_name or 'N/A'}) killed by Killer: {self.killer_id} ({self.killer_name or 'N/A'})"

@dataclass
class ChestEvent(GameEvent): # Bisa jadi ChestSpawned atau ChestOpened
    chest_id: int
    chest_type_id: str # Type ID peti dari database.json
    chest_name: str
    chest_quality: Optional[str] = None
    chest_category: Optional[str] = None # Misal CHEST_BOSS_GOLD
    position: Optional[Tuple[float, float]] = None
    opener_id: Optional[int] = None # Jika ini event ChestOpened

    def __str__(self):
        action = "Opened" if self.opener_id else "Appeared"
        return f"[{self.__class__.__name__}] {action}: ID {self.chest_id}, Name '{self.chest_name}', Quality: {self.chest_quality}"

# --- Kode Event Albion Online (SANGAT PENTING: INI HANYA CONTOH PLACEHOLDER!) ---
# Anda HARUS mengganti ini dengan kode numerik yang benar dari riset Anda
# menggunakan Albion_Op-EvCodes_Checker atau analisis log.
# Nama variabel di sini hanya untuk keterbacaan.
ALBION_EVENT_CODES = {
    "NewCharacter": 2,          # Placeholder -> GANTI DENGAN KODE SEBENARNYA
    "CharacterEquipmentChanged": 7, # Placeholder
    "HealthUpdate": 9,          # Placeholder
    "PlayerMovement": 15,       # Placeholder
    "NewObject": 23,            # Placeholder (bisa jadi peti atau objek lain)
    "CharacterDeath": 102,      # Placeholder
    "NewLootObject": 156,       # Placeholder (mungkin untuk loot bag di tanah)
    "ChestOpened": 157,         # Placeholder (atau mungkin NewObject dengan parameter tertentu)
    # Tambahkan event lain yang relevan untuk dungeon...
    # Misal: Event masuk dungeon, event interaksi dengan shrine, event bos muncul, dll.
}


class PhotonParser:
    def __init__(self, database_path='database.json'):
        # self.config = Config() # Jika Anda menggunakannya untuk konfigurasi parser
        self._entity_database = self._load_entity_database(database_path)
        self._unknown_event_codes_logged = set()
        self._unknown_response_opcodes_logged = set()

        # Registrasi handler untuk event code spesifik
        # Kunci adalah KODE NUMERIK EVENT yang sebenarnya.
        self.event_handlers = {
            ALBION_EVENT_CODES.get("NewCharacter"): self._handle_new_character,
            # ALBION_EVENT_CODES.get("HealthUpdate"): self._handle_health_update,
            ALBION_EVENT_CODES.get("CharacterDeath"): self._handle_character_death,
            ALBION_EVENT_CODES.get("NewObject"): self._handle_new_object, # Bisa untuk peti atau objek lain
            ALBION_EVENT_CODES.get("ChestOpened"): self._handle_chest_opened, # Jika ada event spesifik
            # Daftarkan handler lain di sini sesuai dengan ALBION_EVENT_CODES yang Anda temukan
        }
        # Untuk Operation Responses, Anda juga bisa membuat handler serupa jika perlu
        self.response_handlers = {
            # Contoh: OP_CODE_JOIN_MAP_RESPONSE: self._handle_join_map_response,
        }

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
        """Mendapatkan detail entitas dari database menggunakan internal_id (uniquename)."""
        return self._entity_database.get(str(internal_id_key))

    def parse_message(self, body: bytes) -> Optional[GameEvent]:
        """
        Titik masuk utama untuk mem-parse pesan Photon.
        'body' diasumsikan sebagai payload dari satu Photon Command (Request, Response, atau Event)
        yang dimulai dengan byte tipe pesan.
        """
        if not body:
            logger.warning("Menerima body pesan kosong.")
            return None
        
        stream = BinaryStream(body)
        try:
            msg_type = stream.read_byte() # Tipe pesan Photon (Request, Response, Event dari ExitGames)
            
            if msg_type == 2: # OperationRequest
                op_code = stream.read_byte()
                parameters = self._deserialize_parameter_table(stream)
                # logger.debug(f"Photon OperationRequest: OpCode={op_code}, Params={parameters}")
                # Anda bisa membuat event khusus untuk request jika perlu dilacak
                return None 
            elif msg_type == 3: # OperationResponse
                op_code = stream.read_byte()
                return_code = stream.read_short()
                # Debug message bisa string atau null, perlu ditangani dengan hati-hati
                debug_message_val = self._deserialize_photon_value(stream) 
                debug_message = str(debug_message_val) if debug_message_val is not None else None
                parameters = self._deserialize_parameter_table(stream)
                return self._handle_operation_response(op_code, return_code, debug_message, parameters, raw_params=parameters)
            elif msg_type == 4: # EventData
                event_code = stream.read_byte() 
                # AktorNum (byte) mungkin ada di sini sebelum parameter, tergantung konfigurasi server Photon
                # Jika ada, stream.read_byte() lagi. Untuk Albion, seringkali langsung parameter.
                parameters = self._deserialize_parameter_table(stream)
                return self._handle_event_data(event_code, parameters, raw_params=parameters)
            else:
                logger.warning(f"Tipe pesan Photon tidak dikenal: {msg_type} pada awal stream. Body: {body[:20].hex()}")
                return None
        except IndexError:
            logger.error(f"Stream berakhir prematur saat parsing tipe pesan Photon. Body: {body[:20].hex()}")
            return None
        except Exception as e:
            logger.error(f"Error umum saat parsing pesan Photon: {e}, Body Awal: {body[:20].hex()}")
            return None

    def _handle_event_data(self, event_code: int, parameters: Dict[int, Any], raw_params) -> Optional[GameEvent]:
        handler = self.event_handlers.get(event_code)
        if handler:
            try:
                # Menyertakan raw_event_code dan raw_parameters ke semua event turunan GameEvent
                return handler(parameters, raw_event_code=event_code, raw_parameters=raw_params)
            except Exception as e:
                logger.error(f"Error di handler untuk event code {event_code}: {e}. Params: {parameters}")
                self._log_unknown_event_details(event_code, parameters, error=str(e))
                return UnknownEvent(event_code=event_code, parameters=parameters, raw_event_code=event_code, raw_parameters=raw_params)
        else:
            if event_code not in self._unknown_event_codes_logged:
                logger.info(f"Tidak ada handler untuk event code: {event_code}. Params: {parameters}")
                self._unknown_event_codes_logged.add(event_code)
                self._log_unknown_event_details(event_code, parameters)
            return UnknownEvent(event_code=event_code, parameters=parameters, raw_event_code=event_code, raw_parameters=raw_params)

    def _handle_operation_response(self, op_code: int, return_code: int, debug_message: Optional[str], parameters: Dict[int, Any], raw_params) -> Optional[GameEvent]:
        # logger.debug(f"Response - OpCode: {op_code}, RC: {return_code}, Debug: {debug_message}, Params: {parameters}")
        handler = self.response_handlers.get(op_code)
        if handler:
            try:
                return handler(return_code, debug_message, parameters, raw_event_code=op_code, raw_parameters=raw_params) # OpCode jadi "event_code"
            except Exception as e:
                logger.error(f"Error di handler response untuk OpCode {op_code}: {e}. Params: {parameters}")
                self._log_unknown_response_details(op_code, return_code, debug_message, parameters, error=str(e))
                return None # Atau UnknownResponseEvent
        else:
            if op_code not in self._unknown_response_opcodes_logged:
                logger.info(f"Tidak ada handler spesifik untuk response OpCode: {op_code}, RC: {return_code}. Params: {parameters}")
                self._unknown_response_opcodes_logged.add(op_code)
                self._log_unknown_response_details(op_code, return_code, debug_message, parameters)
            return None # Atau UnknownResponseEvent

    # --- Contoh Handler Spesifik untuk Event Code (PERLU PENYESUAIAN PARAMETER!) ---

    def _handle_new_character(self, parameters: Dict[int, Any], **kwargs) -> Optional[MobSpawnedEvent]:
        """
        Handler untuk event spawn karakter baru (bisa mob atau pemain).
        Kunci parameter (byte) dan tipe datanya HARUS diverifikasi dari riset Anda.
        """
        try:
            # --- ASUMSI PEMETAAN PARAMETER (GANTI DENGAN YANG BENAR!) ---
            # Key 0: ID unik runtime entitas (int)
            # Key 1: Type ID entitas (string unikname dari database.json)
            # Key 2: Nama entitas (string) - jika ada langsung di event, jika tidak ambil dari DB
            # Key 7: Posisi X (float) - Albion map X
            # Key 9: Posisi Y (float) - Albion map Z (Y di game adalah ketinggian)
            # Key 15: Array floats [currentHealth, maxHealth] atau dua parameter terpisah
            # Key 18: Faction ID (byte/int)
            # Key 20: Guild ID (string)
            # Key 22: Tier (byte)
            # Key 46: Enchantment level (byte)
            # ... dan seterusnya ...

            entity_id = int(parameters.get(0))
            type_id_key = str(parameters.get(1)) # Ini harusnya uniquename dari database.json

            pos_x = parameters.get(7) # Contoh
            pos_z = parameters.get(9) # Contoh (Y di game adalah ketinggian)
            position = (float(pos_x), float(pos_z)) if pos_x is not None and pos_z is not None else (0.0, 0.0)

            # Contoh jika HP ada dalam array di parameter 15
            health_array = parameters.get(15)
            current_health, max_health = None, None
            if isinstance(health_array, list) and len(health_array) >= 2:
                current_health = float(health_array[0])
                max_health = float(health_array[1])
            # Atau jika HP adalah parameter terpisah (misal 15 untuk current, 16 untuk max)
            # current_health = float(parameters.get(15, 0.0))
            # max_health = float(parameters.get(16, 0.0))


            if entity_id is None or not type_id_key:
                logger.warning(f"Parameter ID atau TypeIDKey hilang di NewCharacter: {parameters}")
                return None

            entity_details = self._get_entity_details(type_id_key)
            name_from_db = "Unknown Entity"
            category_from_db = "UNKNOWN"
            faction_from_db = "UNKNOWN"
            tier_from_db = "0"

            if entity_details:
                name_from_db = entity_details.get('name_en', type_id_key)
                category_from_db = entity_details.get('category', "UNKNOWN")
                faction_from_db = entity_details.get('faction', "UNKNOWN")
                tier_from_db = entity_details.get('tier', "0")
            else:
                logger.warning(f"TypeIDKey '{type_id_key}' tidak ditemukan di database untuk NewCharacter id {entity_id}.")

            # Nama bisa juga datang dari parameter event (misalnya untuk pemain)
            name_from_event = parameters.get(2) # Contoh parameter nama
            final_name = str(name_from_event) if name_from_event else name_from_db
            
            # Fokus pada MOB dan BOSS untuk scanner dungeon
            if category_from_db in ["MOB", "BOSS", "MINIBOSS", "CHAMPION_MOB"]:
                logger.info(f"MOB/BOSS SPAWNED: ID={entity_id}, TypeKey={type_id_key}, Name='{final_name}', Cat={category_from_db}, Pos={position}, HP={current_health}/{max_health}")
                return MobSpawnedEvent(
                    entity_id=entity_id, type_id=type_id_key, name=final_name,
                    position=position, max_health=max_health, current_health=current_health,
                    category=category_from_db, faction=faction_from_db, tier=tier_from_db,
                    **kwargs # Meneruskan raw_event_code dan raw_parameters
                )
            else:
                # logger.debug(f"NewCharacter (non-mob): ID={entity_id}, TypeKey={type_id_key}, Name='{final_name}', Cat={category_from_db}")
                return None
        except Exception as e:
            logger.error(f"Error parsing NewCharacter (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)


    def _handle_character_death(self, parameters: Dict[int, Any], **kwargs) -> Optional[EntityDeathEvent]:
        try:
            # --- ASUMSI PEMETAAN PARAMETER (GANTI DENGAN YANG BENAR!) ---
            # Key 0: ID entitas yang mati (int)
            # Key 1: ID entitas pembunuh (int, bisa 0 atau tidak ada)
            # Key 4: Nama entitas yang mati (string, opsional) - jika dari pemain
            # Key 5: Nama pembunuh (string, opsional) - jika dari pemain
            # Key 8: Total fame yang didapat pembunuh (int) - jika relevan
            
            victim_id = int(parameters.get(0))
            killer_id_param = parameters.get(1)
            killer_id = int(killer_id_param) if killer_id_param is not None else None

            # Nama mungkin tidak selalu ada di event kematian untuk mob.
            # Kita mungkin perlu melacak entitas aktif untuk mendapatkan nama/kategori korban.
            # Untuk sekarang, kita coba ambil dari parameter jika ada.
            victim_name_param = parameters.get(4)
            killer_name_param = parameters.get(5)

            victim_name = str(victim_name_param) if victim_name_param else None
            killer_name = str(killer_name_param) if killer_name_param else None
            
            # TODO: Dapatkan kategori korban dari state yang dilacak (misalnya, DungeonTracker)
            # Untuk sekarang, kita tidak tahu kategorinya dari event ini saja.
            victim_category = None 

            logger.info(f"DEATH: VictimID={victim_id} ({victim_name or 'N/A'}), KillerID={killer_id} ({killer_name or 'N/A'})")
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
        """ Handler untuk objek baru, bisa jadi peti atau lainnya. """
        try:
            # --- ASUMSI PEMETAAN PARAMETER (GANTI DENGAN YANG BENAR!) ---
            # Key 0: ID unik runtime objek (int)
            # Key 1: Type ID objek (string uniquename dari database.json)
            # Key 2: Posisi (array float [x, y] atau [x, y, z])
            
            object_id = int(parameters.get(0))
            type_id_key = str(parameters.get(1))

            pos_array = parameters.get(2)
            position = (float(pos_array[0]), float(pos_array[1])) if isinstance(pos_array, (list, tuple)) and len(pos_array) >= 2 else None

            if object_id is None or not type_id_key:
                logger.warning(f"Parameter ID atau TypeIDKey hilang di NewObject: {parameters}")
                return None

            entity_details = self._get_entity_details(type_id_key)
            name = "Unknown Object"
            category = "UNKNOWN_OBJECT"
            quality = None

            if entity_details:
                name = entity_details.get('name_en', type_id_key)
                category = entity_details.get('category', "UNKNOWN_OBJECT")
                quality = entity_details.get('quality') # Untuk peti
            else:
                logger.warning(f"TypeIDKey '{type_id_key}' tidak ditemukan di database untuk NewObject id {object_id}.")

            if category and category.startswith("CHEST_"):
                logger.info(f"CHEST SPAWNED (via NewObject): ID={object_id}, TypeKey={type_id_key}, Name='{name}', Cat={category}, Quality={quality}, Pos={position}")
                return ChestEvent(
                    chest_id=object_id, chest_type_id=type_id_key, chest_name=name,
                    chest_quality=quality, chest_category=category, position=position,
                    **kwargs
                )
            else:
                # logger.debug(f"NewObject (non-chest): ID={object_id}, TypeKey={type_id_key}, Name='{name}', Cat={category}")
                return None # Atau event generik jika perlu
        except Exception as e:
            logger.error(f"Error parsing NewObject (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)

    def _handle_chest_opened(self, parameters: Dict[int, Any], **kwargs) -> Optional[ChestEvent]:
        """ Handler spesifik jika ada event ChestOpened. """
        try:
            # --- ASUMSI PEMETAAN PARAMETER (GANTI DENGAN YANG BENAR!) ---
            # Key 0: ID runtime peti yang dibuka (int)
            # Key 1: ID pemain yang membuka (int)
            # Key 2: Type ID peti (string uniquename dari database.json) - mungkin tidak selalu ada di event buka
            
            chest_id = int(parameters.get(0))
            opener_id = int(parameters.get(1))
            
            # Jika event buka tidak menyertakan type_id peti, Anda perlu mendapatkannya dari
            # state yang dilacak (misalnya, saat peti itu spawn via NewObject).
            # Untuk sekarang, kita asumsikan bisa ada di parameter 2.
            chest_type_id_key = str(parameters.get(2)) if parameters.get(2) else None
            
            chest_name = "Unknown Chest"
            chest_quality = None
            chest_category = None

            if chest_type_id_key:
                entity_details = self._get_entity_details(chest_type_id_key)
                if entity_details:
                    chest_name = entity_details.get('name_en', chest_type_id_key)
                    chest_quality = entity_details.get('quality')
                    chest_category = entity_details.get('category')
                else:
                    logger.warning(f"TypeIDKey '{chest_type_id_key}' tidak ditemukan di database untuk ChestOpened id {chest_id}.")
            else:
                # Jika tidak ada type_id_key, kita perlu cara lain untuk mengidentifikasi peti ini
                # Mungkin dari ID runtime yang sudah dilacak saat spawn.
                logger.warning(f"ChestOpened event untuk ID {chest_id} tanpa TypeIDKey di parameter.")
                # Anda bisa mencoba mencari chest_id di daftar peti yang aktif/terlihat.

            logger.info(f"CHEST OPENED: ID={chest_id}, Name='{chest_name}', OpenerID={opener_id}, Quality={chest_quality}")
            return ChestEvent(
                chest_id=chest_id, chest_type_id=chest_type_id_key or "UNKNOWN_CHEST_TYPE", 
                chest_name=chest_name, chest_quality=chest_quality, chest_category=chest_category,
                opener_id=opener_id,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error parsing ChestOpened (EvCode {kwargs.get('raw_event_code')}): {e}. Params: {parameters}")
            self._log_unknown_event_details(kwargs.get('raw_event_code'), parameters, error=str(e))
            return UnknownEvent(event_code=kwargs.get('raw_event_code'), parameters=parameters, **kwargs)


    # --- Metode Deserialisasi Parameter (dari contoh sebelumnya, sedikit disesuaikan) ---
    def _deserialize_parameter_table(self, stream: BinaryStream) -> Dict[int, Any]:
        param_count = stream.read_short()
        parameters = {}
        for _ in range(param_count):
            key = stream.read_byte() # Kunci parameter adalah byte
            value = self._deserialize_photon_value(stream)
            parameters[key] = value
        return parameters

    def _deserialize_photon_value(self, stream: BinaryStream) -> Any:
        type_code = stream.read_byte()
        # logger.debug(f"Deserializing Photon Value with TypeCode: {type_code} at pos {stream.tell()-1}")
        if type_code == 0:    # null
            return None
        elif type_code == 42: # Dictionary (ParameterTable)
            return self._deserialize_parameter_table(stream)
        elif type_code == 68: # double (alias untuk 100 di beberapa versi Photon?)
            return stream.read_double()
        elif type_code == 97: # array byte[]
            size = stream.read_int() 
            return stream.read_bytes(size)
        elif type_code == 98: # byte
            return stream.read_byte()
        elif type_code == 100: # double
            return stream.read_double()
        elif type_code == 102: # float
            return stream.read_float()
        elif type_code == 104: # Hashtable (dianggap sama dengan Dictionary untuk parsing ini)
            return self._deserialize_parameter_table(stream)
        elif type_code == 105: # int (Photon int = 4 bytes, signed)
            return stream.read_int()
        elif type_code == 107: # short (Photon short = 2 bytes, signed)
            return stream.read_short()
        elif type_code == 108: # long (Photon long = 8 bytes, signed)
            return stream.read_long()
        elif type_code == 110: # array int[]
            size = stream.read_int()
            return [stream.read_int() for _ in range(size)]
        elif type_code == 111: # boolean
            return stream.read_bool()
        elif type_code == 115: # string
            return stream.read_string() 
        elif type_code == 118: # array object[] (tipe heterogen)
            size = stream.read_short()
            arr = []
            for _ in range(size):
                arr.append(self._deserialize_photon_value(stream)) # Rekursif
            return arr
        elif type_code == 120: # array long[]
            size = stream.read_int()
            return [stream.read_long() for _ in range(size)]
        elif type_code == 121: # array string[]
            size = stream.read_short() 
            return [stream.read_string() for _ in range(size)]
        # Tambahkan tipe lain jika Anda menemukannya dari analisis atau dokumentasi Photon
        # seperti array float[], array short[], array bool[], Custom Types (type_code > 127 atau sesuai registrasi)
        else:
            # Ini adalah fallback yang sangat penting. Jika Anda menemui ini,
            # Anda HARUS menambahkan handler untuk type_code tersebut atau stream akan rusak.
            logger.error(f"Tipe data Photon TIDAK DIKENAL dalam parameter: {type_code} at stream pos {stream.tell()-1}. Sisa stream mungkin tidak valid.")
            # Mengembalikan string placeholder bisa menyebabkan error tipe data di handler.
            # Lebih baik raise error atau return None dan tangani di pemanggil.
            # Untuk debugging, kita bisa return string.
            # return f"UNSUPPORTED_TYPE({type_code})"
            raise ValueError(f"Tipe data Photon tidak dikenal: {type_code} at stream pos {stream.tell()-1}")


    def _log_unknown_event_details(self, event_code, parameters, error=None):
        """Mencatat detail event yang tidak dikenal atau error parsing ke unknown_ids.txt."""
        log_entry = f"--- Unknown/Unhandled Event or Error ---\n"
        log_entry += f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        log_entry += f"EventCode: {event_code}\n"
        log_entry += f"Parameters: {json.dumps(parameters, default=lambda o: f'<bytes len={len(o)}>' if isinstance(o, bytes) else repr(o), indent=2)}\n"
        if error:
            log_entry += f"Error: {error}\n"
        log_entry += f"--------------------------------------\n\n"
        try:
            with open('unknown_ids.txt', 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except IOError:
            logger.error("Gagal menulis ke unknown_ids.txt")

    def _log_unknown_response_details(self, op_code, return_code, debug_message, parameters, error=None):
        """Mencatat detail response yang tidak dikenal atau error parsing ke unknown_ids.txt."""
        log_entry = f"--- Unknown/Unhandled Response or Error ---\n"
        log_entry += f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        log_entry += f"OperationCode: {op_code}\n"
        log_entry += f"ReturnCode: {return_code}\n"
        log_entry += f"DebugMessage: {debug_message}\n"
        log_entry += f"Parameters: {json.dumps(parameters, default=lambda o: f'<bytes len={len(o)}>' if isinstance(o, bytes) else repr(o), indent=2)}\n"
        if error:
            log_entry += f"Error: {error}\n"
        log_entry += f"--------------------------------------\n\n"
        try:
            with open('unknown_ids.txt', 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except IOError:
            logger.error("Gagal menulis ke unknown_ids.txt")
