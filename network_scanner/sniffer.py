# file: network_scanner/sniffer.py

import scapy.all as scapy
from threading import Thread, Event
from queue import Queue
import platform
import os
import sys
import time
import struct
import binascii

# --- Fungsi select_interface() tetap sama ---
def select_interface():
    ifaces_obj = scapy.conf.ifaces
    if not ifaces_obj:
        print("[!] Tidak dapat mendeteksi antarmuka jaringan.")
        return None
    interface_list = [ifaces_obj.data[guid] for guid in ifaces_obj.data]
    if not interface_list:
        print("[!] Daftar antarmuka kosong.")
        return None
    print("\n[*] Pilih antarmuka jaringan:")
    display_interfaces = [
        iface
        for iface in interface_list
        if hasattr(iface, "ip") and iface.ip and iface.ip != "127.0.0.1"
    ]
    if not display_interfaces:
        display_interfaces = [iface for iface in interface_list if hasattr(iface, "name")]
    if not display_interfaces:
        print("[!] Tidak ada antarmuka yang valid untuk ditampilkan.")
        return None
    for i, iface in enumerate(display_interfaces):
        print(
            f"  [{i}] {getattr(iface, 'name', 'N/A')} "
            f"({getattr(iface, 'description', getattr(iface, 'name', 'N/A'))}) - "
            f"IP: {getattr(iface, 'ip', 'N/A')}"
        )
    while True:
        try:
            choice = int(input(">> Masukkan nomor: "))
            if 0 <= choice < len(display_interfaces):
                return display_interfaces[choice]
            else:
                print("[!] Pilihan tidak valid.")
        except (ValueError, IndexError):
            print("[!] Input tidak valid.")
            return None

# --- Kelas PacketSniffer() tetap sama ---
class PacketSniffer(Thread):
    def __init__(self, packet_queue: Queue, bpf_filter: str, interface_name: str):
        super().__init__(daemon=True)
        self.packet_queue = packet_queue
        self.bpf_filter = bpf_filter
        self.interface_name = interface_name
        self.stop_event = Event()

    def _check_privileges(self):
        if platform.system() == "Windows":
            try:
                return os.getuid() == 0
            except AttributeError:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.getuid() == 0

    def run(self):
        if not self._check_privileges():
            print("\n[!] KESALAHAN: Jalankan skrip ini sebagai Administrator/root.")
            self.stop_event.set()
            return
        print(
            f"[*] Sniffer dimulai... Antarmuka: {self.interface_name}, Filter: '{self.bpf_filter}'"
        )

        def process_packet(packet):
            if not self.packet_queue.full():
                self.packet_queue.put(bytes(packet))

        while not self.stop_event.is_set():
            try:
                scapy.sniff(
                    iface=self.interface_name,
                    filter=self.bpf_filter,
                    prn=process_packet,
                    store=0,
                    stop_filter=lambda p: self.stop_event.is_set(),
                    timeout=1,
                )
            except Exception as e:
                if "Npcap" in str(e) or "pcap" in str(e).lower():
                    print(f"[!] Error Npcap/Pcap: {e}. Pastikan Npcap terinstal.")
                    self.stop_event.set()
                    break
                elif isinstance(e, (PermissionError, OSError)):
                    print(f"[!] Error Hak Akses: {e}. Jalankan sebagai Administrator.")
                    self.stop_event.set()
                    break
                else:
                    print(f"[!] Error sniffer: {e}")
                if not self.stop_event.is_set():
                    self.stop_event.wait(timeout=1)

    def stop(self):
        if not self.stop_event.is_set():
            print("\n[*] Menghentikan sniffer...")
            self.stop_event.set()


# --- Tipe Parameter Photon ---
# Dikutip dari berbagai sumber reverse engineering protokol Photon
PHOTON_PARAM_TYPE_NULL = 0x2a
PHOTON_PARAM_TYPE_DICT = 0x44
PHOTON_PARAM_TYPE_STRING = 0x73
PHOTON_PARAM_TYPE_BYTE = 0x62
PHOTON_PARAM_TYPE_SHORT = 0x6b
PHOTON_PARAM_TYPE_INTEGER = 0x69
PHOTON_PARAM_TYPE_LONG = 0x6c
PHOTON_PARAM_TYPE_FLOAT = 0x66
PHOTON_PARAM_TYPE_DOUBLE = 0x64
PHOTON_PARAM_TYPE_BOOLEAN = 0x6f
PHOTON_PARAM_TYPE_BYTE_ARRAY = 0x78
PHOTON_PARAM_TYPE_OBJECT_ARRAY = 0x79


def parse_photon_parameters(payload: bytes, offset: int) -> tuple[dict, int]:
    """
    Membongkar parameter dari payload Photon.
    Mengembalikan dictionary parameter dan offset akhir.
    """
    params = {}
    current_offset = offset
    try:
        # 2 byte pertama setelah header adalah jumlah parameter
        param_count = struct.unpack(">H", payload[current_offset : current_offset + 2])[0]
        current_offset += 2

        for _ in range(param_count):
            # 1 byte kode parameter, 1 byte tipe data
            param_code = payload[current_offset]
            param_type = payload[current_offset + 1]
            current_offset += 2
            
            value = None
            if param_type == PHOTON_PARAM_TYPE_STRING:
                str_len = struct.unpack(">H", payload[current_offset : current_offset + 2])[0]
                current_offset += 2
                value = payload[current_offset : current_offset + str_len].decode("utf-8", errors="replace")
                current_offset += str_len
            elif param_type == PHOTON_PARAM_TYPE_BYTE:
                value = payload[current_offset]
                current_offset += 1
            elif param_type == PHOTON_PARAM_TYPE_SHORT:
                value = struct.unpack(">h", payload[current_offset : current_offset + 2])[0]
                current_offset += 2
            elif param_type == PHOTON_PARAM_TYPE_INTEGER:
                value = struct.unpack(">i", payload[current_offset : current_offset + 4])[0]
                current_offset += 4
            elif param_type == PHOTON_PARAM_TYPE_LONG:
                value = struct.unpack(">q", payload[current_offset : current_offset + 8])[0]
                current_offset += 8
            elif param_type == PHOTON_PARAM_TYPE_BOOLEAN:
                value = payload[current_offset] != 0
                current_offset += 1
            elif param_type == PHOTON_PARAM_TYPE_NULL:
                value = None # Tidak ada data untuk dibaca
            elif param_type == PHOTON_PARAM_TYPE_BYTE_ARRAY:
                array_len = struct.unpack(">i", payload[current_offset : current_offset + 4])[0]
                current_offset += 4
                value = payload[current_offset : current_offset + array_len]
                current_offset += array_len
            # Tipe data lain seperti Dictionary dan Array bisa ditambahkan di sini jika perlu
            else:
                # Tipe tidak dikenal, kita hentikan parsing untuk parameter ini
                break
            
            params[param_code] = value
    except Exception:
        # Gagal parsing, kembalikan apa yang sudah didapat
        pass
    return params, current_offset


def analyze_photon_payload(payload: bytes):
    """
    Menganalisis payload Photon dan mencoba mencetak informasi yang relevan.
    Fokus utama adalah pada EventData (kode f=253).
    """
    if not payload or len(payload) < 12:
        return

    # Header Photon: 2 byte (peer id?), 1 byte (flags), 1 byte (command count)
    # 4 byte (timestamp), 4 byte (challenge)
    command_count = payload[3]
    current_offset = 12

    for i in range(command_count):
        if current_offset >= len(payload):
            break

        # Header Perintah: 1 byte (tipe), 1 byte (channel id), 1 byte (flags)
        # 1 byte (reserved), 4 byte (panjang), 4 byte (seq number)
        cmd_type = payload[current_offset]
        cmd_len = struct.unpack(">I", payload[current_offset + 4 : current_offset + 8])[0]
        
        # Pointer ke data di dalam perintah
        data_offset = current_offset + 12
        
        print("-" * 35 + f" Perintah #{i+1} " + "-" * 35)
        print(f"  [>] Tipe Perintah: {cmd_type} | Panjang: {cmd_len - 12} bytes")

        if cmd_type == 4: # Tipe 4 biasanya untuk EventData
            # Header Event: 1 byte (kode operasi), 1 byte (reserved/count?), 2 byte (param count)
            event_code = payload[data_offset + 1] # Photon V2 Operation Code
            if event_code == 253: # f=253 -> EventData
                # Di dalam EventData, kode event sebenarnya ada di parameter 0
                event_params, _ = parse_photon_parameters(payload, data_offset + 2)
                
                # '0' adalah kode parameter untuk Kode Event Kustom
                custom_event_code = event_params.get(0)
                # '1' adalah kode parameter untuk data event kustom
                custom_event_data = event_params.get(1)
                
                print(f"  [EVENT] Kode Event Kustom: {custom_event_code}")
                
                if isinstance(custom_event_data, dict):
                    print("  [DATA EVENT]")
                    for key, val in custom_event_data.items():
                        # Coba decode byte array menjadi string, sangat berguna untuk ID entitas
                        if isinstance(val, bytes):
                             print(f"    - Key: {key}, Val: {val.decode('utf-8', errors='replace')} ({binascii.hexlify(val).decode()})")
                        else:
                             print(f"    - Key: {key}, Val: {val}")
                else:
                    print(f"  [DATA EVENT] {custom_event_data}")
        elif cmd_type == 2: # Tipe 2 biasanya untuk OperationRequest
            op_code = payload[data_offset + 1]
            print(f"  [REQUEST] Kode Operasi: {op_code}")
            op_params, _ = parse_photon_parameters(payload, data_offset + 2)
            if op_params:
                print("  [PARAMETER REQUEST]")
                for key, val in op_params.items():
                    print(f"    - Key: {key}, Val: {val}")

        # Pindah ke perintah berikutnya
        current_offset += cmd_len


if __name__ == "__main__":
    print("[*] Mempersiapkan pemilihan antarmuka jaringan...")
    selected_iface_obj = select_interface()
    if not selected_iface_obj:
        sys.exit(1)

    iface_name_for_scapy = getattr(
        selected_iface_obj,
        "name",
        getattr(selected_iface_obj, "description", getattr(selected_iface_obj, "guid", None)),
    )
    if not iface_name_for_scapy:
        print(f"[!] Tidak dapat menentukan nama antarmuka dari objek: {selected_iface_obj}")
        sys.exit(1)

    print(f"\n[*] Antarmuka '{iface_name_for_scapy}' akan digunakan.\n")

    # IP Server Albion, bisa diperbarui jika perlu
    # Anda bisa mendapatkannya dari resource monitor saat bermain
    ALBION_SERVER_IPS = [
        "5.45.187.211", # West
        "5.45.187.119", # West
        "5.45.187.30",  # West
        "5.45.187.213", # West - IP Baru dari Resmon
        "5.45.187.113", # West - IP Baru dari Resmon
        "193.123.235.150", # East
        "193.123.235.151", # East
    ]
    host_filter = " or ".join([f"host {ip}" for ip in ALBION_SERVER_IPS])
    GAME_PORTS = [5056]  # Port utama untuk event game
    port_filter = " or ".join([f"port {port}" for port in GAME_PORTS])
    FINAL_BPF_FILTER = f"udp and ({host_filter}) and ({port_filter})"

    print(f"[*] Filter BPF yang akan digunakan: {FINAL_BPF_FILTER}")

    packet_processing_queue = Queue(maxsize=5000)
    sniffer_thread = PacketSniffer(
        packet_processing_queue, FINAL_BPF_FILTER, interface_name=iface_name_for_scapy
    )
    sniffer_thread.start()

    if not sniffer_thread.is_alive() and sniffer_thread.stop_event.is_set():
        print("[!] Gagal memulai thread sniffer. Periksa hak akses dan instalasi Npcap.")
        sys.exit(1)

    print("[*] Thread utama berjalan. Tekan Ctrl+C untuk berhenti.")
    print("[*] Menganalisis paket Photon (UDP)...")
    print("[!] Lakukan aksi di dalam game (masuk dungeon, dekati peti/mob) untuk melihat event.")

    try:
        while sniffer_thread.is_alive() or not packet_processing_queue.empty():
            if not packet_processing_queue.empty():
                packet_data_raw = packet_processing_queue.get()
                payload = b""
                try:
                    # Asumsi paket mentah adalah Ethernet Frame
                    eth_frame = scapy.Ether(packet_data_raw)
                    if eth_frame.haslayer(scapy.IP) and eth_frame.haslayer(scapy.UDP):
                        payload = bytes(eth_frame[scapy.UDP].payload)
                except Exception:
                    # Jika gagal, asumsikan data mentah adalah payload UDP
                    payload = packet_data_raw

                if payload:
                    print("\n" + "=" * 80)
                    print(f"| Paket Diterima pada {time.strftime('%H:%M:%S')} | Ukuran Payload: {len(payload)} bytes |")
                    print("=" * 80)
                    scapy.hexdump(payload)
                    print("-" * 80)
                    analyze_photon_payload(payload)
                    print("=" * 80)

            else:
                time.sleep(0.01) # Hindari busy-waiting
    except KeyboardInterrupt:
        print("\n[*] Perintah berhenti diterima dari pengguna.")
    finally:
        if sniffer_thread.is_alive():
            sniffer_thread.stop()
            sniffer_thread.join()
        print("[*] Program dihentikan.")