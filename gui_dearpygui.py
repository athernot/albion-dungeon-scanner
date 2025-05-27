# file: gui_dearpygui.py

import dearpygui.dearpygui as dpg
import threading
import configparser
import os
from collections import Counter

# Impor logika scanner Anda
from scanner import AlbionDungeonScanner, TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE, TRANSLATIONS, load_translations

CONFIG_FILE = "config.ini"

# --- Variabel Global untuk State UI ---
albion_path_input = ""
status_text = "Status: Siap."
floor_count = 0
findings_by_floor = []
scanned_files_this_session = set()
current_translations_dpg = {}

# Peta warna untuk teks (RGB tuple untuk Dear PyGui)
COLOR_MAP_DPG = {
    "LOOTCHEST_STANDARD": (0, 180, 0), "BOOKCHEST_STANDARD": (0, 180, 0),
    "LOOTCHEST_UNCOMMON": (30, 144, 255), "BOOKCHEST_UNCOMMON": (30, 144, 255),
    "LOOTCHEST_RARE": (186, 85, 211), "BOOKCHEST_RARE": (186, 85, 211),
    "LOOTCHEST_EPIC": (255, 193, 7), "LOOTCHEST_LEGENDARY": (255, 215, 0),
    "LOOTCHEST_BOSS": (255, 165, 0), "LOOTCHEST_MINIBOSS": (218, 112, 214),
    "BOSS_MINIBOSS_GENERIC": (218, 112, 214), "BOSS_ENDBOSS_GENERIC": (255, 127, 80),
    "BOSS_HIGHLIGHT_GENERIC": (255, 99, 71), "BOSS_GENERIC": (240, 128, 128),
    "UNCLEFROST": (173, 216, 230), "ANNIVERSARY_TITAN": (255, 215, 0),
    "SHRINE_NON_COMBAT_BUFF": (123, 104, 238),
}

# (Fungsi save_path_dpg, load_path_dpg, browse_albion_path_callback, reset_session_dpg, 
#  _format_single_category_dpg, generate_report_for_dpg, update_scan_results_display,
#  scan_thread_worker, start_scan_thread tetap sama persis seperti di respons saya sebelumnya
#  yang menyarankan Solusi 1 untuk masalah font. 
#  Salin versi fungsi-fungsi tersebut dari sana.)
# --- Salin fungsi-fungsi yang tidak berubah dari respons sebelumnya ke sini ---
# Contoh:
def save_path_dpg(path_value: str):
    global status_text
    config = configparser.ConfigParser()
    config['Settings'] = {'ao-dir': path_value}
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    status_text = f"Status: Path disimpan -> {path_value}"
    if dpg.is_dearpygui_running() and dpg.does_item_exist("status_label"): # Cek jika DPG running
        dpg.set_value("status_label", status_text)

def load_path_dpg():
    global albion_path_input, status_text, current_translations_dpg
    if os.path.exists(CONFIG_FILE):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        path = config.get('Settings', 'ao-dir', fallback="")
        albion_path_input = path # Simpan ke variabel global
        if dpg.is_dearpygui_running() and dpg.does_item_exist("albion_path_input"):
            dpg.set_value("albion_path_input", path)
        if path:
            status_text = "Status: Path dimuat. Siap memindai."
        else:
            status_text = "Status: Path belum diatur."
    else:
        status_text = f"Status: {CONFIG_FILE} tidak ditemukan. Atur path."
    if dpg.is_dearpygui_running() and dpg.does_item_exist("status_label"):
        dpg.set_value("status_label", status_text)
    
    load_translations() # Dari scanner
    current_translations_dpg = TRANSLATIONS.copy()


def browse_albion_path_callback():
    def callback(sender, app_data):
        if "file_path_name" in app_data and app_data["file_path_name"]:
            selected_path = app_data["file_path_name"]
            dpg.set_value("albion_path_input", selected_path)
            save_path_dpg(selected_path) 
        else:
            print("Pemilihan path dibatalkan atau tidak ada path yang dipilih.")
        if dpg.does_item_exist("file_dialog_id"):
            dpg.delete_item("file_dialog_id")

    if not dpg.does_item_exist("file_dialog_id"):
        with dpg.file_dialog(
            directory_selector=True, show=True, callback=callback, tag="file_dialog_id",
            width=700, height=400, modal=True, label="Pilih Folder Instalasi Albion Online"
        ):
            pass 
    else:
         dpg.configure_item("file_dialog_id", show=True)


def reset_session_dpg():
    global floor_count, findings_by_floor, scanned_files_this_session, status_text
    floor_count = 0
    findings_by_floor = []
    scanned_files_this_session = set()
    status_text = "Status: Sesi direset. Siap untuk dungeon baru."
    
    update_scan_results_display()
    if dpg.is_dearpygui_running() and dpg.does_item_exist("status_label"):
        dpg.set_value("status_label", status_text)

def _format_single_category_dpg(category_title: str, items_counter: Counter) -> list:
    lines_with_color = []
    if not items_counter: return lines_with_color
    lines_with_color.append((f"\n {category_title}", (220,220,220) ))
    sorted_items = sorted(items_counter.items(), key=lambda item: current_translations_dpg.get(item[0], (item[0], "❓"))[0])
    for item_id, count in sorted_items:
        entry = current_translations_dpg.get(item_id)
        icon, item_name_display = "❓", f"ID: {item_id}"
        if entry: item_name_display, icon = entry[0], entry[1] if len(entry) > 1 else "❓"
        line_text = f"  {icon} {item_name_display}"
        formatted_count = f"(x{count})"
        target_len, current_len = 65, len(line_text) + len(formatted_count)
        padding_needed = max(1, target_len - current_len)
        line_text = f"{line_text}{' ' * padding_needed}{formatted_count}"
        lines_with_color.append((line_text, COLOR_MAP_DPG.get(item_id)))
    return lines_with_color

def generate_report_for_dpg() -> list:
    display_data = []
    header_color = (200, 200, 50)
    if not findings_by_floor:
        display_data.append(("\n- Tekan 'SCAN / UPDATE LANTAI' untuk memulai.", None))
        display_data.append(("- Pastikan Anda berada di dalam dungeon.", None))
        return display_data
    for i, floor_data_dict in enumerate(findings_by_floor):
        floor_num = i + 1
        display_data.append((f"\n═══════════ Lantai {floor_num} ═════════════", header_color))
        display_data.extend(_format_single_category_dpg("[ Event Boss ]", floor_data_dict.get(TYPE_EVENT_BOSS, Counter())))
        display_data.extend(_format_single_category_dpg("[ Boss Dungeon ]", floor_data_dict.get(TYPE_DUNGEON_BOSS, Counter())))
        display_data.extend(_format_single_category_dpg("[ Peti ]", floor_data_dict.get(TYPE_CHEST, Counter())))
        display_data.extend(_format_single_category_dpg("[ Altar Buff ]", floor_data_dict.get(TYPE_SHRINE, Counter())))
    display_data.append(("\n\n\n══════ Laporan Kumulatif Total Sesi ══════", header_color))
    total_cumulative = {TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(), TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(), "exits": set()}
    for floor_data_dict in findings_by_floor:
        for category, data in floor_data_dict.items():
            if category in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]: total_cumulative[category].update(data)
            elif category == "exits": total_cumulative["exits"].update(data)
    display_data.extend(_format_single_category_dpg("[ Total Event Boss ]", total_cumulative[TYPE_EVENT_BOSS]))
    display_data.extend(_format_single_category_dpg("[ Total Boss Dungeon ]", total_cumulative[TYPE_DUNGEON_BOSS]))
    display_data.extend(_format_single_category_dpg("[ Total Peti ]", total_cumulative[TYPE_CHEST]))
    display_data.extend(_format_single_category_dpg("[ Total Altar Buff ]", total_cumulative[TYPE_SHRINE]))
    display_data.append(("\n" + "="*57, None))
    last_floor_exits = findings_by_floor[-1].get("exits", set()) if findings_by_floor else set()
    has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
    floor_status_text = "Ada Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
    display_data.append((f" 🚪 Status Lantai Saat Ini ({floor_count}): {floor_status_text}", (173, 216, 230)))
    return display_data

def update_scan_results_display():
    if not dpg.is_dearpygui_running() or not dpg.does_item_exist("scan_results_group_content"): return
    dpg.delete_item("scan_results_group_content", children_only=True)
    report_data = generate_report_for_dpg()
    for line_text, color_tuple in report_data:
        if color_tuple: dpg.add_text(line_text, color=color_tuple, parent="scan_results_group_content")
        else: dpg.add_text(line_text, parent="scan_results_group_content")

def scan_thread_worker():
    global status_text, floor_count, findings_by_floor, scanned_files_this_session, current_translations_dpg
    if dpg.is_dearpygui_running() and dpg.does_item_exist("status_label"): dpg.set_value("status_label", "Status: Sedang memindai...")
    if dpg.is_dearpygui_running() and dpg.does_item_exist("scan_button"): dpg.configure_item("scan_button", enabled=False, label="MEMINDAI...")
    try:
        current_path = dpg.get_value("albion_path_input") if dpg.is_dearpygui_running() else albion_path_input 
        if not current_path or not os.path.isdir(current_path): raise ValueError("Path Albion Online tidak valid atau belum diatur.")
        scanner_instance = AlbionDungeonScanner(ao_dir_path=current_path)
        results_from_scan = scanner_instance.run()
        load_translations(); current_translations_dpg = TRANSLATIONS.copy()
        notification_message = "Tidak ada file dungeon aktif baru terdeteksi atau lantai sama."
        if results_from_scan:
            newly_scanned_files = set(results_from_scan.get("used_files", []))
            if not findings_by_floor or (newly_scanned_files and not newly_scanned_files.issubset(scanned_files_this_session)):
                floor_count += 1; scanned_files_this_session.update(newly_scanned_files)
                findings_by_floor.append({TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(), TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(), "mobs_by_tier": {}, "exits": set()})
                notification_message = f"Temuan baru di Lantai {floor_count} telah ditambahkan!"
            else: notification_message = "Scan selesai. Data untuk lantai saat ini diperbarui."
            current_floor_storage = findings_by_floor[-1]
            for key, data_counter in results_from_scan.items():
                if key in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]: current_floor_storage[key].update(data_counter)
                elif key == "exits": current_floor_storage[key].update(data_counter)
                elif key == "mobs_by_tier":
                    for tier, mobs_counter in data_counter.items(): current_floor_storage["mobs_by_tier"].setdefault(tier, Counter()).update(mobs_counter)
            status_text = f"Status: Scan lantai {floor_count} selesai."
            print(f"UI Notifikasi: {notification_message}")
        else: status_text = "Status: Scan selesai. Tidak ada file dungeon aktif."
    except Exception as e: status_text = f"Status: Error saat scan - {e}"; print(f"ERROR SCAN: {e}")
    if dpg.is_dearpygui_running() and dpg.does_item_exist("status_label"): dpg.set_value("status_label", status_text)
    if dpg.is_dearpygui_running() : update_scan_results_display() 
    if dpg.is_dearpygui_running() and dpg.does_item_exist("scan_button"): dpg.configure_item("scan_button", enabled=True, label="SCAN / UPDATE LANTAI")

def start_scan_thread():
    current_path_to_save = dpg.get_value("albion_path_input") if dpg.is_dearpygui_running() else albion_path_input
    if current_path_to_save: save_path_dpg(current_path_to_save)
    scan_thread = threading.Thread(target=scan_thread_worker); scan_thread.daemon = True; scan_thread.start()
# --- Akhir dari fungsi-fungsi yang tidak berubah ---


def setup_dpg_ui():
    global albion_path_input

    dpg.create_context()

    # --- REVISI BAGIAN FONT ---
    font_primary_path = "NotoSans-Regular.ttf" 
    font_emoji_path = "NotoEmoji-Regular.ttf" 
    font_size_ui = 18 # Anda bisa sesuaikan ukuran ini

    with dpg.font_registry():
        try:
            if os.path.exists(font_primary_path):
                # 1. Muat font utama (NotoSans)
                default_font = dpg.add_font(font_primary_path, font_size_ui)
                print(f"DEBUG: Font utama '{font_primary_path}' dimuat dengan handle: {default_font}")
                
                # 2. Tambahkan range karakter standar ke font utama ini
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default, parent=default_font)
                # Jika perlu, tambahkan hint untuk bahasa lain seperti Indonesia
                # dpg.add_font_range_hint(dpg.mvFontRangeHint_Indonesian, parent=default_font)

                # 3. Jika font emoji ada, tambahkan karakter emoji ke font utama
                #    dengan mengambil glyph dari file font emoji
                if os.path.exists(font_emoji_path):
                    # Definisikan karakter atau range emoji yang ingin ditambahkan
                    # ke 'default_font' dan diambil dari 'font_emoji_path'
                    # Ini adalah cara Dear PyGui menggabungkan glyph dari file font berbeda ke satu font handle.
                    dpg.add_font_chars(
                        chars=[0x1F600, 0x1F64F, 0x1F300, 0x1F5FF, 0x1F900, 0x1F9FF, 0x2600, 0x26FF, 0x2700, 0x27BF], # Contoh beberapa kode emoji
                        char_count=10, # Sesuaikan dengan jumlah di atas
                        glyph_source_font_file=font_emoji_path, 
                        parent=default_font
                    )
                    # Alternatif: Jika ingin seluruh range (lebih berat)
                    # dpg.add_font_range(0x1F600, 0x1F64F, parent=default_font, source_font_file=font_emoji_path) # Tidak ada arg 'source_font_file'
                    # Cara yang lebih umum adalah menggunakan add_font_chars dengan daftar karakter spesifik
                    # atau memuat NotoEmoji sebagai font terpisah dan membiarkan DPG melakukan fallback.
                    # Untuk penggabungan eksplisit:
                    # Buat daftar semua karakter emoji yang ingin Anda dukung.
                    # Contoh untuk emoji pintu 🚪 (U+1F6AA) dan peti 👑 (U+1F451), dll.
                    emoji_chars_to_add = [
                        0x1F6AA, # 🚪
                        0x1F451, # 👑
                        0x1F383, # 🎃
                        0x1F47E, # 👾
                        0x1F43B, # 🐻
                        0x1F43A, # 🐺
                        0x1F417, # 🐗
                        0x1F4DA, # 📚
                        0x1F98A, # 🦊
                        0x1F98C, # 🦌
                        0x1F40F, # 🐏 (mirip tupai/marmot)
                        0x1F407, # 🐇
                        0x1F418, # 🐘
                        0x1F426, # 🐦
                        0x1F98F, # 🦏
                        0x1F409, # 🐉
                        0x1F40D, # 🐍
                        0x1F438, # 🐸
                        0x1F98E, # 🦎
                        0x2753,  #❓
                        0x2728,  #✨
                        0x1F976, #🥶
                        0x2694,  #⚔️
                        0x1F389, #🎉
                        0x1F3C6, #🏆
                        0x1F479, #👹
                        0x1F33F, #🌿 (untuk keeper)
                        0x1F480, #💀
                        0x1F52E, #💠 (Avalonian)
                        0x1F3C3, #🏃
                        0x23F3,  #⏳
                        0x1F525, #🔥 (mungkin untuk Ballista atau Mortar)
                        0x26CF,  #⛏️
                        0x1F6E1, #🛡️
                        0x1F4A5, #💥
                        0x2764, # ❤️
                        0x26A1, # ⚡
                        0x1F4C8, # 📈
                        0x1F504, # 🔄 (Placeholder untuk cooldown atau tipe lain)
                        0x1F4E6, # 📦 (Untuk peti generik)
                        0x1F384, # 🎄 (Contoh untuk Winter Event)
                        0x2744,  # ❄️ (Contoh untuk Winter Event)
                        0x1F382, # 🎂 (Anniversary)
                    ]
                    dpg.add_font_chars(chars=emoji_chars_to_add, char_count=len(emoji_chars_to_add), 
                                       parent=default_font, 
                                       # Untuk mengambil glyph dari file lain, Anda perlu
                                       # memuat font emoji itu secara terpisah, lalu membuat char remaps.
                                       # Atau, cara yang lebih sederhana adalah membiarkan DPG melakukan fallback.

                                       # Pilihan 1: Biarkan DPG fallback (metode sebelumnya)
                                       #   - Muat font emoji secara terpisah (seperti di versi lalu)
                                       #   - dan DPG akan otomatis menggunakan jika glyph tidak ada di default_font.

                                       # Pilihan 2: Jika ingin menggabungkan glyph secara eksplisit ke default_font
                                       # Ini lebih rumit dan mungkin tidak perlu jika fallback bekerja.
                                       # Biasanya, jika font emoji sudah dimuat di registry, fallback sudah cukup.
                                       # Kita akan kembali ke metode fallback untuk kesederhanaan dan keandalan.
                                       )
                    print(f"DEBUG: Karakter emoji dari '{font_emoji_path}' akan coba digabungkan/fallback.")
                else:
                    print(f"WARNING: File font emoji '{font_emoji_path}' tidak ditemukan.")

                dpg.bind_font(default_font)
                print("DEBUG: Font utama di-bind.")

            else: # Fallback jika font utama tidak ada
                default_font = dpg.add_font(dpg.mvFont_Default, font_size_ui) 
                dpg.bind_font(default_font)
                print(f"WARNING: Font utama '{font_primary_path}' tidak ditemukan. Menggunakan font default DPG.")

        except Exception as e:
            print(f"ERROR saat memuat atau mengikat font: {e}. Menggunakan font default Dear PyGui.")
            if 'default_font' not in locals() or not default_font :
                 try:
                    font_to_bind = dpg.add_font(dpg.mvFont_Default, font_size_ui) # Muat font default DPG
                    dpg.bind_font(font_to_bind)
                    print("DEBUG: Fallback ke font default DPG karena error.")
                 except Exception as e_fallback:
                     print(f"ERROR saat mencoba fallback ke font default DPG: {e_fallback}")
    # --- AKHIR REVISI BAGIAN FONT ---

    with dpg.window(label="Albion Dungeon Scanner DPG", tag="main_window", width=850, height=750):
        # ... (Sisa UI window tetap sama seperti sebelumnya) ...
        with dpg.group(horizontal=True):
            dpg.add_text("Path Albion:")
            dpg.add_input_text(tag="albion_path_input", default_value=albion_path_input, width=-150, 
                               callback=lambda s,d,u: save_path_dpg(d), on_enter=True)
            dpg.add_button(label="Browse", callback=browse_albion_path_callback, width=100)
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="SCAN / UPDATE LANTAI", tag="scan_button", callback=start_scan_thread, width=-220, height=40)
            dpg.add_button(label="RESET SESI DUNGEON", callback=reset_session_dpg, width=200, height=40)

        dpg.add_separator()
        
        with dpg.child_window(tag="results_child_window", border=True, height=-50):
             with dpg.group(tag="scan_results_group_content", horizontal=False):
                pass 

        dpg.add_separator()
        dpg.add_text(status_text, tag="status_label")


    dpg.create_viewport(title='Albion Dungeon Scanner DPG', width=870, height=790, resizable=True)
    dpg.setup_dearpygui()
    
    load_path_dpg() 
    update_scan_results_display() 

    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    setup_dpg_ui()