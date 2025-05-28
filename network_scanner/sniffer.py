import scapy.all as scapy
from threading import Thread, Event
from queue import Queue
import platform
import os
import sys
import time
import struct

# --- Fungsi select_interface() tetap sama ---
def select_interface():
    ifaces_obj = scapy.conf.ifaces
    if not ifaces_obj: print("[!] Tidak dapat mendeteksi antarmuka jaringan."); return None
    interface_list = [ifaces_obj.data[guid] for guid in ifaces_obj.data]
    if not interface_list: print("[!] Daftar antarmuka kosong."); return None
    print("\n[*] Pilih antarmuka jaringan:"); display_interfaces = [iface for iface in interface_list if hasattr(iface, 'ip') and iface.ip and iface.ip != '127.0.0.1']
    if not display_interfaces: display_interfaces = [iface for iface in interface_list if hasattr(iface, 'name')]
    if not display_interfaces: print("[!] Tidak ada antarmuka."); return None
    for i, iface in enumerate(display_interfaces): print(f"  [{i}] {getattr(iface, 'name', 'N/A')} ({getattr(iface, 'description', getattr(iface, 'name', 'N/A'))}) - IP: {getattr(iface, 'ip', 'N/A')}")
    while True:
        try: choice = int(input(">> Masukkan nomor: ")); return display_interfaces[choice] if 0 <= choice < len(display_interfaces) else print("[!] Pilihan tidak valid.")
        except: print("[!] Input tidak valid."); return None

# --- Kelas PacketSniffer() tetap sama ---
class PacketSniffer(Thread):
    def __init__(self, packet_queue: Queue, bpf_filter: str, interface_name: str):
        super().__init__(daemon=True); self.packet_queue = packet_queue; self.bpf_filter = bpf_filter; self.interface_name = interface_name; self.stop_event = Event()
    def _check_privileges(self):
        if platform.system() == "Windows":
            try: return os.getuid() == 0
            except AttributeError: import ctypes; return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.getuid() == 0
    def run(self):
        if not self._check_privileges(): print("\n[!] KESALAHAN: Jalankan sebagai Administrator."); self.stop_event.set(); return
        print(f"[*] Sniffer dimulai... Antarmuka: {self.interface_name}, Filter: '{self.bpf_filter}'")
        def process_packet(packet):
            if not self.packet_queue.full(): self.packet_queue.put(bytes(packet))
        while not self.stop_event.is_set():
            try: scapy.sniff(iface=self.interface_name, filter=self.bpf_filter, prn=process_packet, store=0, stop_filter=lambda p: self.stop_event.is_set(), timeout=1)
            except Exception as e:
                if "Npcap" in str(e) or "pcap" in str(e).lower(): print(f"[!] Error Npcap: {e}."); self.stop_event.set(); break
                elif isinstance(e, (PermissionError, OSError)) and "admin" in str(e).lower(): print(f"[!] Error Hak Akses: {e}."); self.stop_event.set(); break
                else: print(f"[!] Error sniffer: {e}")
                if not self.stop_event.is_set(): self.stop_event.wait(timeout=1) 
    def stop(self):
        if not self.stop_event.is_set(): print("[*] Menghentikan sniffer..."); self.stop_event.set()

# --- Konstanta Tipe Parameter Photon ---
PHOTON_PARAM_TYPE_STRING = 0x73
PHOTON_PARAM_TYPE_BYTE = 0x62

# --- Kode Operasi Game Albion yang Dicurigai ---
GAME_OP_CHAT_MESSAGE_MARKER = b'\x62\x0e' 
GAME_OP_CONNECTION_INFO_MARKER = b'\x2a' 

def parse_photon_parameters_from_offset(payload: bytes, offset: int) -> dict:
    params = {}
    current_index = offset
    try:
        if current_index >= len(payload): return params
        num_params_expected = payload[current_index]
        current_index += 1

        for i in range(num_params_expected):
            if current_index + 1 >= len(payload): break
            param_code = payload[current_index]
            param_type = payload[current_index + 1]
            current_index += 2
            
            if param_type == PHOTON_PARAM_TYPE_STRING:
                if current_index + 2 > len(payload): break 
                str_len = struct.unpack('>H', payload[current_index : current_index + 2])[0]
                current_index += 2
                if current_index + str_len > len(payload): break
                param_value = payload[current_index : current_index + str_len].decode('utf-8', errors='replace')
                current_index += str_len
                params[param_code] = param_value
            elif param_type == PHOTON_PARAM_TYPE_BYTE:
                if current_index >= len(payload): break
                param_value = payload[current_index]
                params[param_code] = param_value
                current_index += 1
            else: break 
    except Exception: pass
    return params

def analyze_photon_payload(payload: bytes):
    if not payload: print("    Payload kosong."); return
    
    print("--- Analisis Isi Payload Photon ---")
    
    chat_header_index = payload.find(GAME_OP_CHAT_MESSAGE_MARKER)
    if chat_header_index != -1:
        print(f"    -> Terdeteksi Pola Header CHAT (0x{GAME_OP_CHAT_MESSAGE_MARKER.hex()}) pada index payload {chat_header_index}")
        params_offset = chat_header_index + len(GAME_OP_CHAT_MESSAGE_MARKER)
        chat_params = parse_photon_parameters_from_offset(payload, params_offset)
        
        sender = chat_params.get(1) 
        message = chat_params.get(2)
        channel = chat_params.get(3)
        
        print(f"       Pengirim (0x01): {sender if sender is not None else 'N/A'}")
        print(f"       Isi Pesan (0x02): {message if message is not None else 'N/A'}")
        if channel is not None: print(f"       Channel/Info (0x03): {channel if isinstance(channel, int) else channel.hex() if isinstance(channel, bytes) else channel }")
        if len(chat_params) > 3:
            other_params = {k:v for k,v in chat_params.items() if k not in [1,2,3]}
            if other_params: print(f"       Parameter Lain: {other_params}")
        return True

    conn_info_header_index = payload.find(GAME_OP_CONNECTION_INFO_MARKER)
    if conn_info_header_index != -1:
        if conn_info_header_index + 2 < len(payload) and payload[conn_info_header_index + 1] == 0x00 and payload[conn_info_header_index + 2] == 0x03:
            print(f"    -> Terdeteksi Pola Header INFO KONEKSI (0x{GAME_OP_CONNECTION_INFO_MARKER.hex()} 00 03) pada index {conn_info_header_index}")
            params_offset = conn_info_header_index + 3 
            if params_offset < len(payload) and payload[params_offset] == PHOTON_PARAM_TYPE_STRING:
                params_offset +=1 
                if params_offset + 2 <= len(payload):
                    str_len = struct.unpack('>H', payload[params_offset : params_offset + 2])[0]
                    params_offset += 2
                    if params_offset + str_len <= len(payload):
                        server_address = payload[params_offset : params_offset + str_len].decode('utf-8', errors='replace')
                        print(f"       Info Alamat (Param 0x03): {server_address}")
                    else: print("       Gagal parse string alamat info koneksi (panjang tidak cukup).")
                else: print("       Gagal parse panjang string info koneksi.")
            else: print("       Parameter alamat info koneksi tidak bertipe string setelah header 0x2A0003.")
            return True
        elif conn_info_header_index + 1 < len(payload) :
             print(f"    -> Terdeteksi Pola Header INFO KONEKSI (0x{GAME_OP_CONNECTION_INFO_MARKER.hex()}) pada index {conn_info_header_index} (parsing umum)")
             params_offset = conn_info_header_index + 1
             conn_params = parse_photon_parameters_from_offset(payload, params_offset)
             if conn_params : print(f"       Parameter Info Koneksi: {conn_params}")
             else: print("       Gagal parse parameter info koneksi (umum).")
             return True

    print(f"    Byte pertama payload (potensi kode operasi Photon global): 0x{payload[0]:02x}")
    if len(payload) > 1: print(f"    Byte kedua payload: 0x{payload[1]:02x}")
    if len(payload) > 2: print(f"    Byte ketiga payload: 0x{payload[2]:02x}")
    
    print("    String Umum yang Terdeteksi (UTF-8 dari keseluruhan payload):")
    try:
        decoded_text = payload.decode('utf-8', errors='replace')
        meaningful_strings = []
        current_word = []
        printable_chars_count = 0
        for char_code in payload:
            char = chr(char_code) if 32 <= char_code <= 126 else '' 
            if char:
                current_word.append(char)
                if not char.isspace(): printable_chars_count += 1
            else:
                if current_word:
                    word = "".join(current_word).strip()
                    if len(word) >= 4 and printable_chars_count >= 2 and any(c.isalpha() for c in word):
                        meaningful_strings.append(word)
                current_word = []; printable_chars_count = 0
        if current_word:
            word = "".join(current_word).strip()
            if len(word) >= 4 and printable_chars_count >= 2 and any(c.isalpha() for c in word):
                meaningful_strings.append(word)
        if meaningful_strings:
            for s in meaningful_strings: print(f"      -> \"{s}\"")
        else: print("    (Tidak ada string UTF-8 signifikan terdeteksi)")
    except Exception: pass
    return False

if __name__ == '__main__':
    print("[*] Mempersiapkan pemilihan antarmuka jaringan...")
    selected_iface_obj = select_interface()
    if not selected_iface_obj: sys.exit(1)
    
    iface_name_for_scapy = getattr(selected_iface_obj, 'name', getattr(selected_iface_obj, 'description', getattr(selected_iface_obj, 'guid', None)))
    if not iface_name_for_scapy: print(f"[!] Tidak dapat menentukan nama antarmuka: {selected_iface_obj}"); sys.exit(1)

    print(f"\n[*] Antarmuka '{iface_name_for_scapy}' akan digunakan.\n")

    ALBION_SERVER_IPS = ["5.45.187.211", "5.45.187.119", "5.45.187.30"]
    host_filter = " or ".join([f"host {ip}" for ip in ALBION_SERVER_IPS])
    GAME_PORTS = [4535, 5055, 5056] 
    port_filter = " or ".join([f"port {port}" for port in GAME_PORTS])
    FINAL_BPF_FILTER = f"udp and ({host_filter}) and ({port_filter})"
    print(f"[*] Filter BPF yang akan digunakan: {FINAL_BPF_FILTER}")

    packet_processing_queue = Queue(maxsize=2000)
    sniffer_thread = PacketSniffer(packet_processing_queue, FINAL_BPF_FILTER, interface_name=iface_name_for_scapy)
    sniffer_thread.start()

    if not sniffer_thread.is_alive() and sniffer_thread.stop_event.is_set():
        print("[!] Gagal memulai thread sniffer."); sys.exit(1)

    print("[*] Thread utama berjalan. Tekan Ctrl+C untuk berhenti.")
    print("[*] Menganalisis payload Photon...")
    
    try:
        packet_count = 0; analyzed_packet_count = 0; start_time = time.time()
        
        while sniffer_thread.is_alive() or not packet_processing_queue.empty():
            if not packet_processing_queue.empty():
                packet_data_raw = packet_processing_queue.get(); packet_count += 1
                payload = b''; udp_sport, udp_dport, ip_src, ip_dst = 'N/A', 'N/A', 'N/A', 'N/A'
                try:
                    eth_frame = scapy.Ether(packet_data_raw)
                    if eth_frame.haslayer(scapy.IP):
                        ip_layer = eth_frame[scapy.IP]; ip_src, ip_dst = ip_layer.src, ip_layer.dst
                        if ip_layer.haslayer(scapy.UDP):
                            udp_layer = ip_layer[scapy.UDP]; udp_sport, udp_dport = udp_layer.sport, udp_layer.dport
                            if udp_layer.payload: payload = bytes(udp_layer.payload)
                except Exception: payload = packet_data_raw

                if payload: 
                    analyzed_packet_count +=1
                    print("=" * 70)
                    print(f"| Paket #{packet_count} ({ip_src}:{udp_sport} -> {ip_dst}:{udp_dport}) | Payload: {len(payload)} bytes |")
                    print("=" * 70)
                    
                    scapy.hexdump(payload) 
                    # ===============================================
                    # PERBAIKAN NAMEERROR DI SINI
                    # ===============================================
                    analyze_photon_payload(payload) 
                    # ===============================================
                    
                    print("=" * 70 + "\n")
                
                if analyzed_packet_count >= 200 or (time.time() - start_time > 120 and analyzed_packet_count > 0) : 
                    print(f"[*] Batas analisis paket ({analyzed_packet_count} paket atau >120 detik) tercapai."); break
            else:
                if not sniffer_thread.is_alive() and packet_processing_queue.empty(): print("[*] Sniffer berhenti, antrian kosong."); break
                time.sleep(0.01)
                if analyzed_packet_count == 0 and time.time() - start_time > 75: print("[!] Tidak ada paket dianalisis setelah 75 detik."); break
    except KeyboardInterrupt: print("\n[*] Perintah berhenti diterima.")
    finally:
        if sniffer_thread.is_alive(): sniffer_thread.stop(); sniffer_thread.join()
        print(f"[*] Total paket yang dianalisis: {analyzed_packet_count}"); print("[*] Program dihentikan.")