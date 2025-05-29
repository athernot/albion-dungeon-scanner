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
import json # Tambahkan import json

# --- Fungsi select_interface() sedikit disesuaikan ---
def select_interface_and_show():
    """Menampilkan antarmuka dan meminta pengguna memasukkan nama antarmuka dari output scapy."""
    print("[*] Mencari antarmuka jaringan yang tersedia (menggunakan Scapy)...")
    scapy.show_interfaces() # Tampilkan antarmuka versi Scapy
    print("-" * 70)
    print("[!] PERHATIKAN DAFTAR DI ATAS (dari scapy.show_interfaces()).")
    print("[!] Salin dan tempel nama antarmuka yang TEPAT (dari kolom 'Name') yang ingin Anda gunakan.")
    iface_name = input(">> Masukkan nama antarmuka dari daftar di atas: ")
    return iface_name

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
                return os.getuid() == 0 # type: ignore
            except AttributeError:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.getuid() == 0

    def run(self):
        if not self._check_privileges():
            print("\n[!] KESALAHAN: Jalankan skrip ini sebagai Administrator/root.")
            self.stop_event.set()
            return
        
        print(f"[*] Sniffer dimulai... Antarmuka: '{self.interface_name}', Filter: '{self.bpf_filter}'")

        def process_packet(packet):
            if not self.packet_queue.full():
                self.packet_queue.put(bytes(packet))

        try:
            scapy.sniff(
                iface=self.interface_name,
                filter=self.bpf_filter,
                prn=process_packet,
                store=0,
                stop_filter=lambda p: self.stop_event.is_set()
            )
        except Exception as e:
            if "Npcap" in str(e) or "pcap" in str(e).lower():
                print(f"[!] Error Npcap/Pcap: {e}. Pastikan Npcap terinstal dengan benar.")
            elif isinstance(e, (PermissionError, OSError)):
                print(f"[!] Error Hak Akses: {e}. Jalankan sebagai Administrator.")
            else:
                print(f"[!] Error sniffer tak terduga: {e}")
        finally:
            print("[*] Thread sniffer telah berhenti.")
            self.stop_event.set()

    def stop(self):
        if not self.stop_event.is_set():
            print("\n[*] Menghentikan sniffer...")
            self.stop_event.set()

# --- Tipe Parameter Photon (tetap sama) ---
PHOTON_PARAM_TYPE_NULL = 0x2a
PHOTON_PARAM_TYPE_DICT = 0x44 # Tidak diimplementasikan parsingnya di sini
PHOTON_PARAM_TYPE_STRING = 0x73
PHOTON_PARAM_TYPE_BYTE = 0x62
PHOTON_PARAM_TYPE_SHORT = 0x6b
PHOTON_PARAM_TYPE_INTEGER = 0x69
PHOTON_PARAM_TYPE_LONG = 0x6c
PHOTON_PARAM_TYPE_FLOAT = 0x66 # Tidak diimplementasikan parsingnya
PHOTON_PARAM_TYPE_DOUBLE = 0x64 # Tidak diimplementasikan parsingnya
PHOTON_PARAM_TYPE_BOOLEAN = 0x6f
PHOTON_PARAM_TYPE_BYTE_ARRAY = 0x78
PHOTON_PARAM_TYPE_OBJECT_ARRAY = 0x79 # Tidak diimplementasikan parsingnya

def parse_photon_parameters(payload: bytes, offset: int) -> tuple[dict, int]:
    params = {}
    current_offset = offset
    try:
        param_count = struct.unpack(">H", payload[current_offset : current_offset + 2])[0]
        current_offset += 2
        for _ in range(param_count):
            if current_offset + 1 >= len(payload): break
            param_code = payload[current_offset]
            param_type = payload[current_offset + 1]
            current_offset += 2
            value = None
            original_bytes_val = None # Untuk menyimpan representasi byte array

            if param_type == PHOTON_PARAM_TYPE_STRING:
                if current_offset + 2 > len(payload): break
                str_len = struct.unpack(">H", payload[current_offset : current_offset + 2])[0]
                current_offset += 2
                if current_offset + str_len > len(payload): break
                value = payload[current_offset : current_offset + str_len].decode("utf-8", errors="replace")
                current_offset += str_len
            elif param_type == PHOTON_PARAM_TYPE_BYTE:
                if current_offset >= len(payload): break
                value = payload[current_offset]
                current_offset += 1
            elif param_type == PHOTON_PARAM_TYPE_SHORT:
                if current_offset + 2 > len(payload): break
                value = struct.unpack(">h", payload[current_offset : current_offset + 2])[0]
                current_offset += 2
            elif param_type == PHOTON_PARAM_TYPE_INTEGER:
                if current_offset + 4 > len(payload): break
                value = struct.unpack(">i", payload[current_offset : current_offset + 4])[0]
                current_offset += 4
            elif param_type == PHOTON_PARAM_TYPE_LONG:
                if current_offset + 8 > len(payload): break
                value = struct.unpack(">q", payload[current_offset : current_offset + 8])[0]
                current_offset += 8
            elif param_type == PHOTON_PARAM_TYPE_BOOLEAN:
                if current_offset >= len(payload): break
                value = payload[current_offset] != 0
                current_offset += 1
            elif param_type == PHOTON_PARAM_TYPE_NULL:
                value = None
            elif param_type == PHOTON_PARAM_TYPE_BYTE_ARRAY:
                if current_offset + 4 > len(payload): break
                array_len = struct.unpack(">i", payload[current_offset : current_offset + 4])[0]
                current_offset += 4
                if current_offset + array_len > len(payload): break
                byte_val = payload[current_offset : current_offset + array_len]
                # Coba decode sebagai string, jika gagal, simpan sebagai hex
                try:
                    value = byte_val.decode('utf-8', errors='ignore')
                    if not value.isprintable() or len(value.strip()) == 0: # Jika tidak bisa dicetak atau string kosong
                         value = f"hex:{binascii.hexlify(byte_val).decode()}"
                except:
                    value = f"hex:{binascii.hexlify(byte_val).decode()}"
                current_offset += array_len
            else: # Tipe tidak dikenal atau tidak dihandle
                # Untuk tipe yang tidak kita parse nilainya secara spesifik,
                # kita bisa mencoba lewati berdasarkan perkiraan ukuran umum atau hentikan.
                # Untuk saat ini kita hentikan saja agar tidak salah parse.
                # print(f"  [Debug] Tipe parameter tidak dikenal: {hex(param_type)} pada offset {current_offset-2}")
                break 
            
            params[param_code] = value
    except Exception as e:
        # print(f"  [Debug] Exception saat parsing parameter: {e} pada offset {current_offset}")
        pass
    return params, current_offset

def extract_structured_photon_data(payload: bytes) -> list:
    """
    Menganalisis payload Photon dan MENGEMBALIKAN LIST berisi data terstruktur
    dari perintah yang berhasil diparsing.
    """
    parsed_commands_in_packet = []
    if not payload or len(payload) < 12: # Minimal panjang header photon
        return parsed_commands_in_packet

    # Header Photon Global:
    # peer_id = struct.unpack(">H", payload[0:2])[0]
    # flags = payload[2]
    command_count = payload[3]
    # server_time_stamp = struct.unpack(">I", payload[4:8])[0]
    # challenge = struct.unpack(">I", payload[8:12])[0]
    current_offset = 12

    for _ in range(command_count):
        if current_offset + 12 > len(payload): # Minimal panjang header perintah
            break

        cmd_type = payload[current_offset]
        # channel_id = payload[current_offset + 1]
        # cmd_flags = payload[current_offset + 2]
        # reserved_byte = payload[current_offset + 3]
        cmd_len = struct.unpack(">I", payload[current_offset + 4 : current_offset + 8])[0]
        # sequence_number = struct.unpack(">I", payload[current_offset + 8 : current_offset + 12])[0]
        
        data_offset = current_offset + 12 # Awal dari data aktual di dalam perintah
        
        command_data = {"command_type": cmd_type}

        if cmd_type == 4: # EventData (f=253)
            if data_offset + 2 <= len(payload): # Cek panjang minimal untuk kode event & param count
                # Photon V2 Operation Code -> di byte pertama setelah payload header perintah
                op_code_f253 = payload[data_offset] # harusnya 0xfd atau 253
                if op_code_f253 == 0xfd: # 253 (EventData)
                    event_params, _ = parse_photon_parameters(payload, data_offset + 1) # Parameter dimulai setelah op_code 0xfd
                    custom_event_code = event_params.get(0) # Kode Event Kustom di param key 0
                    custom_event_data = event_params.get(1) # Data Event Kustom di param key 1
                    
                    if custom_event_code is not None:
                        command_data["event_custom_code"] = custom_event_code
                        if custom_event_data:
                             command_data["event_data"] = custom_event_data
                        parsed_commands_in_packet.append(command_data)

        elif cmd_type == 6 or cmd_type == 7: # SendReliable / SendUnreliable
            # Terkadang EventData dibungkus di dalam ini.
            # Strukturnya: [0xfd (253)] [param_code_event_id (biasanya 0)] [param_type_event_id] [event_id_val]
            #                 [param_code_data (biasanya 1)] [param_type_data] [data_val]
            if data_offset + 1 < len(payload) and payload[data_offset] == 0xfd: # 253 (EventData)
                event_params, _ = parse_photon_parameters(payload, data_offset + 1)
                custom_event_code = event_params.get(0)
                custom_event_data = event_params.get(1)

                if custom_event_code is not None:
                    command_data["event_custom_code"] = custom_event_code
                    if custom_event_data:
                        command_data["event_data"] = custom_event_data
                    parsed_commands_in_packet.append(command_data)
        
        elif cmd_type == 2: # OperationRequest
            if data_offset + 1 <= len(payload): # Cek panjang minimal untuk kode operasi
                op_code = payload[data_offset]
                command_data["operation_code"] = op_code
                op_params, _ = parse_photon_parameters(payload, data_offset + 1) # Parameter dimulai setelah op_code
                if op_params:
                    command_data["operation_parameters"] = op_params
                parsed_commands_in_packet.append(command_data)

        current_offset += cmd_len
        if current_offset > len(payload): # Pencegahan jika cmd_len salah
            break
            
    return parsed_commands_in_packet


if __name__ == "__main__":
    print("[*] Mempersiapkan pemilihan antarmuka jaringan...")
    selected_iface_name = select_interface_and_show()

    if not selected_iface_name:
        print("[!] Tidak ada antarmuka yang dipilih atau input tidak valid. Keluar.")
        sys.exit(1)

    print(f"\n[*] Antarmuka '{selected_iface_name}' akan digunakan.\n")

    ALBION_SERVER_IPS = [
        "5.45.187.211", "5.45.187.119", "5.45.187.30",
        "5.45.187.213", "5.45.187.113", "5.45.187.219", "5.45.187.31", # Tambahan dari tes Anda
        "193.123.235.150", "193.123.235.151" # East
    ]
    host_filter = " or ".join([f"host {ip}" for ip in ALBION_SERVER_IPS])
    GAME_PORTS = [5056]
    port_filter = " or ".join([f"port {port}" for port in GAME_PORTS])
    FINAL_BPF_FILTER = f"udp and ({host_filter}) and ({port_filter})"

    print(f"[*] Filter BPF yang akan digunakan: {FINAL_BPF_FILTER}")

    packet_processing_queue = Queue(maxsize=10000) # Tingkatkan ukuran queue
    sniffer_thread = PacketSniffer(
        packet_processing_queue, FINAL_BPF_FILTER, interface_name=selected_iface_name
    )
    sniffer_thread.start()

    if not sniffer_thread.is_alive() and not sniffer_thread.stop_event.is_set():
        print("[!] Gagal memulai thread sniffer. Periksa hak akses dan instalasi Npcap.")
        sys.exit(1)

    print("[*] Thread utama berjalan. Tekan Ctrl+C untuk berhenti.")
    print("[*] Menganalisis paket Photon (UDP)...")
    print("[!] Lakukan aksi di dalam game (masuk dungeon, dekati peti/mob) untuk melihat event.")
    
    all_parsed_session_data = []
    output_filename_base = f"parsed_photon_log_{time.strftime('%Y%m%d_%H%M%S')}"
    file_counter = 0
    max_entries_per_file = 5000 # Simpan setiap 5000 entri paket (bukan perintah)
    current_entries_in_file = 0

    try:
        while sniffer_thread.is_alive() or not packet_processing_queue.empty():
            if not packet_processing_queue.empty():
                packet_data_raw = packet_processing_queue.get()
                payload = b""
                try:
                    eth_frame = scapy.Ether(packet_data_raw)
                    if eth_frame.haslayer(scapy.IP) and eth_frame.haslayer(scapy.UDP):
                        payload = bytes(eth_frame[scapy.UDP].payload)
                except Exception:
                    payload = packet_data_raw

                if payload:
                    parsed_commands = extract_structured_photon_data(payload)
                    if parsed_commands: # Hanya proses jika ada perintah yang berhasil diparsing
                        current_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        ms_timestamp = f"{current_timestamp}.{int(time.time()*1000)%1000:03d}" # Tambah milidetik
                        
                        packet_info = {
                            "timestamp": ms_timestamp,
                            "packet_size_bytes": len(payload),
                            "commands": parsed_commands
                        }
                        all_parsed_session_data.append(packet_info)
                        current_entries_in_file +=1
                        print(f"[*] Data dari paket pada {ms_timestamp} (Total Perintah: {len(parsed_commands)}) siap disimpan.")

                        # Opsi untuk menampilkan live di console (bisa di-comment jika terlalu berisik)
                        # print("\n" + "=" * 80)
                        # print(f"| Paket Diterima pada {ms_timestamp} | Ukuran Payload: {len(payload)} bytes |")
                        # print("=" * 80)
                        # for cmd_idx, cmd in enumerate(parsed_commands):
                        #     print(f"--- Perintah #{cmd_idx + 1} ---")
                        #     for key, val in cmd.items():
                        #         print(f"  {key}: {val}")
                        # print("=" * 80)

                        if current_entries_in_file >= max_entries_per_file:
                            current_filename = f"{output_filename_base}_{file_counter}.json"
                            with open(current_filename, 'w', encoding='utf-8') as f:
                                json.dump(all_parsed_session_data, f, indent=2, ensure_ascii=False)
                            print(f"[*] Data disimpan ke file: {current_filename} ({len(all_parsed_session_data)} entri paket)")
                            all_parsed_session_data = [] # Reset untuk file berikutnya
                            current_entries_in_file = 0
                            file_counter += 1
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[*] Perintah berhenti diterima dari pengguna.")
    finally:
        if sniffer_thread.is_alive():
            sniffer_thread.stop()
            sniffer_thread.join(timeout=5) # Beri waktu thread untuk berhenti
        
        # Simpan sisa data yang belum disimpan
        if all_parsed_session_data:
            current_filename = f"{output_filename_base}_{file_counter}.json"
            with open(current_filename, 'w', encoding='utf-8') as f:
                json.dump(all_parsed_session_data, f, indent=2, ensure_ascii=False)
            print(f"[*] Sisa data ({len(all_parsed_session_data)} entri paket) disimpan ke: {current_filename}")
        elif file_counter == 0: # Jika tidak ada data sama sekali yang disimpan
             print("[*] Tidak ada data yang berhasil diparsing untuk disimpan.")

        print("[*] Program dihentikan.")