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
import json

def select_interface_and_show():
    """Menampilkan antarmuka dan meminta pengguna memasukkan nama antarmuka dari output scapy."""
    print("[*] Mencari antarmuka jaringan yang tersedia (menggunakan Scapy)...")
    try:
        scapy.show_interfaces() # Tampilkan antarmuka versi Scapy
    except Exception as e:
        print(f"[!] Gagal menampilkan antarmuka dengan scapy: {e}")
        print("[!] Pastikan Npcap terinstal dengan benar dan Anda memiliki hak akses yang cukup.")
        print("[!] Anda mungkin perlu menjalankan 'pdm run python' dan 'from scapy.all import *; show_interfaces()' secara manual untuk debug.")
        return None
        
    print("-" * 70)
    print("[!] PERHATIKAN DAFTAR DI ATAS (dari scapy.show_interfaces()).")
    print("[!] Salin dan tempel nama antarmuka yang TEPAT (dari kolom 'Name') yang ingin Anda gunakan.")
    iface_name = input(">> Masukkan nama antarmuka dari daftar di atas: ")
    return iface_name

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
        
        if not self.interface_name:
            print("[!] Nama antarmuka tidak valid. Keluar dari thread sniffer.")
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
            if "Npcap" in str(e) or "pcap" in str(e).lower() or "WinPcap" in str(e):
                print(f"[!] Error Npcap/Pcap/WinPcap: {e}. Pastikan Npcap (atau WinPcap jika sistem lama) terinstal dengan benar dan mode kompatibilitas API WinPcap diaktifkan saat instalasi Npcap.")
            elif isinstance(e, (PermissionError, OSError)):
                print(f"[!] Error Hak Akses: {e}. Jalankan sebagai Administrator.")
            elif "Network adapter" in str(e) or "No such device" in str(e):
                print(f"[!] Error: Antarmuka jaringan '{self.interface_name}' tidak ditemukan atau tidak valid. Periksa nama antarmuka dari output 'scapy.show_interfaces()'.")
            else:
                print(f"[!] Error sniffer tak terduga: {e}")
        finally:
            print("[*] Thread sniffer telah berhenti.")
            self.stop_event.set()

    def stop(self):
        if not self.stop_event.is_set():
            print("\n[*] Menghentikan sniffer...")
            self.stop_event.set()

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
                try:
                    decoded_str = byte_val.decode('utf-8', errors='ignore')
                    if all(32 <= ord(char) <= 126 for char in decoded_str.strip()) and len(decoded_str.strip()) > 0 : 
                        value = decoded_str.strip()
                    else:
                         value = f"hex:{binascii.hexlify(byte_val).decode()}"
                except:
                    value = f"hex:{binascii.hexlify(byte_val).decode()}"
                current_offset += array_len
            else:
                break 
            
            params[param_code] = value
    except Exception:
        pass
    return params, current_offset

def extract_structured_photon_data(payload: bytes) -> list:
    parsed_commands_in_packet = []
    if not payload or len(payload) < 12:
        return parsed_commands_in_packet

    command_count = payload[3]
    current_offset = 12

    for i in range(command_count):
        if current_offset + 12 > len(payload):
            break

        cmd_type = payload[current_offset]
        cmd_len = struct.unpack(">I", payload[current_offset + 4 : current_offset + 8])[0]
        data_offset = current_offset + 12
        
        command_data = {
            "command_index_in_packet": i,
            "command_type": cmd_type,
            "command_payload_length_bytes": max(0, cmd_len - 12)
        }
        details_parsed_flag = False

        if cmd_type == 4: 
            if data_offset + 1 < len(payload) and payload[data_offset] == 0xfd: # 253
                event_params, _ = parse_photon_parameters(payload, data_offset + 1)
                custom_event_code = event_params.get(0)
                custom_event_data = event_params.get(1)
                if custom_event_code is not None:
                    command_data["event_custom_code"] = custom_event_code
                    if custom_event_data:
                        command_data["event_data"] = custom_event_data
                    details_parsed_flag = True
        
        elif cmd_type == 6 or cmd_type == 7: 
            if data_offset + 1 < len(payload) and payload[data_offset] == 0xfd: 
                event_params, _ = parse_photon_parameters(payload, data_offset + 1)
                custom_event_code = event_params.get(0)
                custom_event_data = event_params.get(1)
                if custom_event_code is not None:
                    command_data["embedded_event_custom_code"] = custom_event_code
                    if custom_event_data:
                        command_data["embedded_event_data"] = custom_event_data
                    details_parsed_flag = True
        
        elif cmd_type == 2: 
            if data_offset < len(payload):
                op_code = payload[data_offset]
                command_data["operation_code"] = op_code
                op_params, _ = parse_photon_parameters(payload, data_offset + 1)
                if op_params:
                    command_data["operation_parameters"] = op_params
                details_parsed_flag = True
        
        command_data["details_parsed_flag"] = details_parsed_flag
        parsed_commands_in_packet.append(command_data)

        current_offset += cmd_len
        if current_offset > len(payload): 
            break
            
    return parsed_commands_in_packet

if __name__ == "__main__":
    print("[*] Mempersiapkan pemilihan antarmuka jaringan...")
    selected_iface_name = select_interface_and_show()

    if not selected_iface_name or selected_iface_name.strip() == "":
        print("[!] Tidak ada antarmuka yang dipilih atau input tidak valid. Keluar.")
        sys.exit(1)

    print(f"\n[*] Antarmuka '{selected_iface_name}' akan digunakan.\n")

    # Daftar IP Server Albion - Gabungkan semua yang sudah kita temukan
    ALBION_SERVER_IPS = [
        "5.45.187.211", "5.45.187.119", "5.45.187.30",  # Original West
        "5.45.187.213", "5.45.187.113",                # Dari resmon Anda sebelumnya
        "5.45.187.219", "5.45.187.31",                 # Dari log test_scapy Anda
        "5.45.187.49", "5.45.187.59",                  # Dari screenshot Wireshark awal
        "5.45.187.64",                                 # Dari resmon Open World & Ava
        "5.45.187.188",                                # IP BARU dari Ava Dungeon terakhir Anda
        # Tambahkan IP lain dari ResMon jika ada saat di dungeon/open world yang belum tercakup
        "193.123.235.150", "193.123.235.151" # Original East (jika masih relevan)
    ]
    # Hapus duplikat dan urutkan untuk kerapian
    ALBION_SERVER_IPS = sorted(list(set(ALBION_SERVER_IPS))) 
    
    print(f"[*] Daftar IP Server yang akan digunakan (setelah digabung dan diurutkan): {ALBION_SERVER_IPS}")
    
    host_filter = " or ".join([f"host {ip}" for ip in ALBION_SERVER_IPS])
    GAME_PORTS = [5056] 
    port_filter = " or ".join([f"port {port}" for port in GAME_PORTS])
    FINAL_BPF_FILTER = f"udp and ({host_filter}) and ({port_filter})"

    print(f"[*] Filter BPF yang akan digunakan: {FINAL_BPF_FILTER}")

    packet_processing_queue = Queue(maxsize=10000)
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
    max_entries_per_file = 5000 
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
                    if parsed_commands: 
                        current_timestamp_obj = time.time()
                        ms_timestamp = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_timestamp_obj))}.{int(current_timestamp_obj * 1000) % 1000:03d}"
                        
                        packet_info = {
                            "capture_timestamp_epoch": current_timestamp_obj,
                            "timestamp_readable": ms_timestamp,
                            "packet_size_bytes": len(payload),
                            "commands": parsed_commands
                        }
                        all_parsed_session_data.append(packet_info)
                        current_entries_in_file +=1
                        
                        has_interesting_event = any(
                            "event_custom_code" in cmd or "embedded_event_custom_code" in cmd 
                            for cmd in parsed_commands
                        )
                        if has_interesting_event:
                            print(f"[*] Paket MENARIK pada {ms_timestamp} (Total Perintah: {len(parsed_commands)}) siap disimpan.")

                        if current_entries_in_file >= max_entries_per_file:
                            current_filename = f"{output_filename_base}_{file_counter}.json"
                            with open(current_filename, 'w', encoding='utf-8') as f:
                                json.dump(all_parsed_session_data, f, indent=2, ensure_ascii=False, sort_keys=False)
                            print(f"[*] Data disimpan ke file: {current_filename} ({len(all_parsed_session_data)} entri paket)")
                            all_parsed_session_data = [] 
                            current_entries_in_file = 0
                            file_counter += 1
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[*] Perintah berhenti diterima dari pengguna.")
    finally:
        if sniffer_thread.is_alive():
            sniffer_thread.stop()
            sniffer_thread.join(timeout=5)
        
        if all_parsed_session_data:
            current_filename = f"{output_filename_base}_{file_counter}.json"
            with open(current_filename, 'w', encoding='utf-8') as f:
                json.dump(all_parsed_session_data, f, indent=2, ensure_ascii=False, sort_keys=False)
            print(f"[*] Sisa data ({len(all_parsed_session_data)} entri paket) disimpan ke: {current_filename}")
        elif file_counter == 0 and current_entries_in_file == 0:
             print("[*] Tidak ada data yang berhasil diparsing untuk disimpan.")

        print("[*] Program dihentikan.")