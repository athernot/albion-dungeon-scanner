import struct
import io

class BinaryStream:
    """
    Kelas untuk membaca tipe data biner dari stream byte (misalnya, dari payload paket jaringan).
    Menggunakan format little-endian secara default untuk sebagian besar tipe data,
    sesuai dengan yang umum digunakan dalam protokol jaringan game.
    """
    def __init__(self, base_stream_bytes: bytes):
        """
        Inisialisasi BinaryStream dengan byte array.
        :param base_stream_bytes: Bytes yang akan dibaca.
        """
        self._stream = io.BytesIO(base_stream_bytes)

    def read_byte(self) -> int:
        """Membaca 1 byte sebagai integer unsigned."""
        return struct.unpack('<B', self._stream.read(1))[0]

    def read_signed_byte(self) -> int:
        """Membaca 1 byte sebagai integer signed."""
        return struct.unpack('<b', self._stream.read(1))[0]

    def read_bool(self) -> bool:
        """Membaca 1 byte dan menginterpretasikannya sebagai boolean (0=False, lainnya=True)."""
        return self.read_byte() != 0

    def read_short(self) -> int:
        """Membaca 2 byte sebagai short integer signed (little-endian)."""
        return struct.unpack('<h', self._stream.read(2))[0]

    def read_unsigned_short(self) -> int:
        """Membaca 2 byte sebagai short integer unsigned (little-endian)."""
        return struct.unpack('<H', self._stream.read(2))[0]

    def read_int(self) -> int:
        """Membaca 4 byte sebagai integer signed (little-endian)."""
        return struct.unpack('<i', self._stream.read(4))[0]

    def read_unsigned_int(self) -> int:
        """Membaca 4 byte sebagai integer unsigned (little-endian)."""
        return struct.unpack('<I', self._stream.read(4))[0]

    def read_long(self) -> int:
        """Membaca 8 byte sebagai long integer signed (little-endian)."""
        return struct.unpack('<q', self._stream.read(8))[0]

    def read_unsigned_long(self) -> int:
        """Membaca 8 byte sebagai long integer unsigned (little-endian)."""
        return struct.unpack('<Q', self._stream.read(8))[0]

    def read_float(self) -> float:
        """Membaca 4 byte sebagai float (little-endian)."""
        return struct.unpack('<f', self._stream.read(4))[0]

    def read_double(self) -> float:
        """Membaca 8 byte sebagai double (little-endian)."""
        return struct.unpack('<d', self._stream.read(8))[0]

    def read_string(self, encoding='utf-8') -> str:
        """
        Membaca string yang diawali dengan panjang string (short).
        Ini adalah format umum untuk string dalam protokol Photon.
        Panjang string dibaca sebagai unsigned short.
        """
        try:
            length = self.read_unsigned_short()
            if length == 0:
                return ""
            # Batasi panjang untuk menghindari masalah memori jika ada data korup
            if length > 8192: # Batas wajar, bisa disesuaikan
                raise ValueError(f"Panjang string terlalu besar: {length}")
            return self._stream.read(length).decode(encoding)
        except struct.error as e:
            # Terjadi jika stream berakhir sebelum panjang string bisa dibaca sepenuhnya
            raise EOFError(f"Gagal membaca panjang string atau string itu sendiri: {e}")
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(f"Gagal men-decode string dengan encoding {encoding}: {e}")

    def read_string_safe(self, encoding='utf-8', default_on_error="") -> str:
        """
        Versi aman dari read_string, mengembalikan default jika terjadi error.
        """
        current_pos = self._stream.tell()
        try:
            return self.read_string(encoding)
        except (EOFError, ValueError, UnicodeDecodeError) as e:
            # Kembalikan stream ke posisi sebelum mencoba membaca string
            self._stream.seek(current_pos)
            # Baca byte tipe data string (biasanya 's' atau 115 untuk Photon) jika belum terbaca
            # dan pastikan kita melewati panjang string jika ada.
            # Ini adalah bagian yang rumit jika kita tidak tahu pasti struktur errornya.
            # Untuk saat ini, kita hanya log dan return default.
            # logger.warning(f"read_string_safe gagal: {e}, mengembalikan default.")
            return default_on_error


    def read_bytes(self, length: int) -> bytes:
        """Membaca sejumlah byte tertentu dari stream."""
        if length < 0:
            raise ValueError("Panjang byte tidak boleh negatif.")
        return self._stream.read(length)

    def read_guid(self) -> str:
        """Membaca 16 byte dan mengonversinya menjadi string GUID/UUID."""
        guid_bytes = self.read_bytes(16)
        # Format GUID standar: 8-4-4-4-12 hex digits
        # Bytes di .NET GUID tidak selalu dalam urutan yang sama dengan representasi string standar.
        # Urutan umum: Data1 (4 byte, LE), Data2 (2 byte, LE), Data3 (2 byte, LE), Data4 (8 byte, BE)
        # Untuk Python uuid, kita bisa construct dari bytes langsung jika urutannya sesuai.
        # Namun, seringkali lebih mudah memformatnya secara manual jika ada perbedaan endianness per field.
        # Contoh sederhana (asumsi urutan byte cocok dengan representasi hex string standar, mungkin perlu penyesuaian):
        return "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}".format(
            guid_bytes[3], guid_bytes[2], guid_bytes[1], guid_bytes[0],  # Data1 (LE)
            guid_bytes[5], guid_bytes[4],  # Data2 (LE)
            guid_bytes[7], guid_bytes[6],  # Data3 (LE)
            guid_bytes[8], guid_bytes[9],  # Data4[0-1] (BE)
            guid_bytes[10], guid_bytes[11], guid_bytes[12], guid_bytes[13], guid_bytes[14], guid_bytes[15] # Data4[2-7] (BE)
        )
        # Atau menggunakan library uuid jika format byte-nya standar
        # import uuid
        # return str(uuid.UUID(bytes_le=guid_bytes)) # Jika semua little-endian

    def is_eof(self) -> bool:
        """Memeriksa apakah akhir stream telah tercapai."""
        return self._stream.tell() >= len(self._stream.getbuffer())

    def tell(self) -> int:
        """Mengembalikan posisi saat ini dalam stream."""
        return self._stream.tell()

    def seek(self, offset: int, whence: int = 0):
        """Mengubah posisi stream."""
        self._stream.seek(offset, whence)

    def get_bytes_left(self) -> int:
        """Mengembalikan jumlah byte yang tersisa untuk dibaca."""
        return len(self._stream.getbuffer()) - self._stream.tell()

    def get_remaining_bytes(self) -> bytes:
        """Mengembalikan semua byte yang tersisa di stream."""
        return self._stream.read()

