# file: gui_flet.py

import flet as ft
import threading
import configparser
import os
from collections import Counter
import time 

# Impor logika scanner Anda
from scanner import AlbionDungeonScanner, TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE, TRANSLATIONS, load_translations

CONFIG_FILE = "config.ini"

# Peta warna untuk teks di Flet (Menggunakan ft.Colors)
COLOR_MAP_FLET = {
    "LOOTCHEST_STANDARD": ft.Colors.GREEN_ACCENT_700,
    "BOOKCHEST_STANDARD": ft.Colors.GREEN_ACCENT_700,
    "LOOTCHEST_UNCOMMON": ft.Colors.BLUE_ACCENT_700,
    "BOOKCHEST_UNCOMMON": ft.Colors.BLUE_ACCENT_700,
    "LOOTCHEST_RARE": ft.Colors.PURPLE_ACCENT_700,
    "BOOKCHEST_RARE": ft.Colors.PURPLE_ACCENT_700,
    "LOOTCHEST_EPIC": ft.Colors.AMBER_ACCENT_700,
    "LOOTCHEST_LEGENDARY": ft.Colors.YELLOW_ACCENT_700,
    "LOOTCHEST_BOSS": ft.Colors.ORANGE_ACCENT_700,
    "LOOTCHEST_MINIBOSS": ft.Colors.PINK_ACCENT_700,
    "BOSS_MINIBOSS_GENERIC": ft.Colors.PINK_ACCENT_700,
    "BOSS_ENDBOSS_GENERIC": ft.Colors.DEEP_ORANGE_ACCENT_700,
    "BOSS_HIGHLIGHT_GENERIC": ft.Colors.RED_ACCENT_700,
    "BOSS_GENERIC": ft.Colors.RED_700,
    "UNCLEFROST": ft.Colors.LIGHT_BLUE_ACCENT_700,
    "ANNIVERSARY_TITAN": ft.Colors.AMBER_ACCENT_700,
    "SHRINE_NON_COMBAT_BUFF": ft.Colors.CYAN_ACCENT_700,
    "DEFAULT_ITEM_COLOR": ft.Colors.WHITE,
    "HEADER_COLOR": ft.Colors.BLUE_GREY_200,
    "CATEGORY_TITLE_COLOR": ft.Colors.BLUE_GREY_100,
}


def main(page: ft.Page):
    page.title = "Albion Dungeon Scanner (Flet)"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH 
    page.window_width = 850
    page.window_height = 800
    page.padding = ft.padding.all(10)

    script_dir = os.path.dirname(__file__)
    assets_dir_for_fonts = os.path.join(script_dir, "assets")
    noto_sans_path = os.path.join(assets_dir_for_fonts, "NotoSans-Regular.ttf")
    noto_emoji_path = os.path.join(assets_dir_for_fonts, "NotoEmoji-Regular.ttf")

    page.fonts = {}
    font_family_to_use = "Roboto" 

    if os.path.exists(noto_sans_path):
        page.fonts["NotoSans"] = noto_sans_path
        font_family_to_use = "NotoSans"
        print(f"DEBUG: NotoSans ditemukan di: {noto_sans_path}")
    else:
        print(f"WARNING: NotoSans-Regular.ttf tidak ditemukan di {noto_sans_path}. Menggunakan font sistem.")

    if os.path.exists(noto_emoji_path):
        page.fonts["NotoEmoji"] = noto_emoji_path 
        print(f"DEBUG: NotoEmoji ditemukan di: {noto_emoji_path}")
    else:
        print(f"WARNING: NotoEmoji-Regular.ttf tidak ditemukan di {noto_emoji_path}. Emoji mungkin tidak tampil dengan benar.")
        
    page.theme = ft.Theme(font_family=font_family_to_use)
    
    # Definisikan properti style dasar di sini untuk referensi
    # Ukuran font bisa disesuaikan di sini
    page.data = { 
        "font_family": font_family_to_use,
        "default_font_size": 14,
        "header_font_size": 18,
        "category_font_size": 16,
        "albion_path": "", "floor_count": 0, "findings_by_floor": [],
        "scanned_files_this_session": set(), "current_translations": {},
        "status_text": "Status: Siap.", "is_scanning": False
    }
    
    page.snack_bar = ft.SnackBar(content=ft.Text(""), open=False)
    page.overlay.append(page.snack_bar) 

    albion_path_field = ft.TextField(
        label="Path Albion Online", hint_text="Contoh: C:\\Program Files (x86)\\Steam\\...",
        expand=True, on_change=lambda e: save_path_flet(page, e.control.value)
    )
    results_list_view = ft.ListView(expand=True, spacing=1, auto_scroll=True, padding=ft.padding.symmetric(horizontal=5))
    status_label = ft.Text(page.data["status_text"], style=ft.TextThemeStyle.BODY_SMALL, font_family=page.data["font_family"])

    scan_button = ft.ElevatedButton(
        "SCAN / UPDATE LANTAI", icon=ft.Icons.SEARCH,
        on_click=lambda e: start_scan_flet(e, page), height=40, 
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )
    reset_button = ft.ElevatedButton(
        "RESET SESI", icon=ft.Icons.REFRESH, 
        on_click=lambda e: reset_session_flet(e, page), height=40, 
        color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_ACCENT_700, 
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    def update_ui_status(p: ft.Page, new_status: str):
        p.data["status_text"] = new_status
        status_label.value = new_status
        status_label.font_family = p.data["font_family"]
        if p.client_storage: p.update(status_label)
        
    def update_results_display_flet(p: ft.Page):
        results_list_view.controls.clear()
        report_data = generate_report_for_flet(p) 
        
        font_fam = p.data["font_family"]
        default_size = p.data["default_font_size"]
        header_size = p.data["header_font_size"]
        category_size = p.data["category_font_size"]

        for text_content, text_color, item_id_or_style_type in report_data:
            # --- PERBAIKAN UTAMA: Buat TextStyle baru setiap kali ---
            current_font_family_val = font_fam
            current_size_val = default_size
            current_weight_val = ft.FontWeight.NORMAL
            current_color_val = text_color 

            if item_id_or_style_type == "HEADER": 
                current_size_val = header_size
                current_weight_val = ft.FontWeight.BOLD
                if not current_color_val: current_color_val = COLOR_MAP_FLET.get("HEADER_COLOR", ft.Colors.WHITE)
            elif item_id_or_style_type == "CATEGORY":
                current_size_val = category_size
                current_weight_val = ft.FontWeight.BOLD 
                if not current_color_val: current_color_val = COLOR_MAP_FLET.get("CATEGORY_TITLE_COLOR", ft.Colors.WHITE)
            
            results_list_view.controls.append(
                ft.Text(
                    text_content, 
                    style=ft.TextStyle(
                        font_family=current_font_family_val,
                        size=current_size_val,
                        weight=current_weight_val,
                        color=current_color_val
                    ), 
                    selectable=True
                )
            )
        
        if not results_list_view.controls:
             results_list_view.controls.append(ft.Text("Tekan 'SCAN' untuk memulai.", style=ft.TextStyle(font_family=font_fam, size=default_size)))
        if p.client_storage: p.update(results_list_view)

    def save_path_flet(p: ft.Page, path_value: str):
        if path_value == p.data.get("albion_path"): return
        config = configparser.ConfigParser(); config['Settings'] = {'ao-dir': path_value}
        with open(CONFIG_FILE, 'w') as configfile: config.write(configfile)
        update_ui_status(p, f"Status: Path disimpan -> {path_value}")
        p.data["albion_path"] = path_value

    def load_path_flet(p: ft.Page):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser(); config.read(CONFIG_FILE)
            path = config.get('Settings', 'ao-dir', fallback="")
            p.data["albion_path"] = path; albion_path_field.value = path
            if path: update_ui_status(p, "Status: Path dimuat. Siap memindai.")
            else: update_ui_status(p, "Status: Path Albion belum diatur.")
        else: update_ui_status(p, f"Status: {CONFIG_FILE} tidak ditemukan. Atur path.")
        load_translations(); p.data["current_translations"] = TRANSLATIONS.copy()
        update_results_display_flet(p) 
        if p.client_storage: p.update(albion_path_field)

    def pick_directory_result(e: ft.FilePickerResultEvent, p: ft.Page):
        if e.path:
            albion_path_field.value = e.path
            save_path_flet(p, e.path) 
            if p.client_storage: p.update(albion_path_field)
        else: update_ui_status(p, "Status: Pemilihan folder dibatalkan.")

    directory_picker = ft.FilePicker(on_result=lambda e: pick_directory_result(e, page))
    page.overlay.append(directory_picker) 

    def browse_path_flet(e): 
        directory_picker.get_directory_path(dialog_title="Pilih Folder Instalasi Albion Online")

    browse_button = ft.ElevatedButton("Browse", icon=ft.Icons.FOLDER_OPEN, on_click=browse_path_flet, width=130, height=40, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

    def reset_session_flet(e, p: ft.Page): 
        p.data["floor_count"] = 0; p.data["findings_by_floor"] = []
        p.data["scanned_files_this_session"] = set()
        update_ui_status(p, "Status: Sesi direset. Siap untuk dungeon baru.")
        update_results_display_flet(p)

    def scan_thread_worker_flet(p: ft.Page):
        p.data["is_scanning"] = True
        scan_button.disabled = True; scan_button.text = "MEMINDAI..."
        if p.client_storage: p.update(scan_button) 
        update_ui_status(p, "Status: Sedang memindai...")
        try:
            current_path = p.data["albion_path"]
            if not current_path or not os.path.isdir(current_path): raise ValueError("Path Albion Online tidak valid atau belum diatur.")
            scanner_instance = AlbionDungeonScanner(ao_dir_path=current_path)
            results_from_scan = scanner_instance.run()
            load_translations(); p.data["current_translations"] = TRANSLATIONS.copy()
            notification_message = "Tidak ada temuan baru atau lantai sama."
            if results_from_scan:
                newly_scanned_files = set(results_from_scan.get("used_files", []))
                if not p.data["findings_by_floor"] or \
                   (newly_scanned_files and not newly_scanned_files.issubset(p.data["scanned_files_this_session"])):
                    p.data["floor_count"] += 1
                    p.data["scanned_files_this_session"].update(newly_scanned_files)
                    p.data["findings_by_floor"].append({
                        TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(), TYPE_CHEST: Counter(), 
                        TYPE_SHRINE: Counter(), "mobs_by_tier": {}, "exits": set()
                    })
                    notification_message = f"Temuan baru di Lantai {p.data['floor_count']} ditambahkan!"
                current_floor_storage = p.data["findings_by_floor"][-1]
                for key, data_counter in results_from_scan.items():
                    if key in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]: current_floor_storage[key].update(data_counter)
                    elif key == "exits": current_floor_storage[key].update(data_counter)
                    elif key == "mobs_by_tier":
                        for tier, mobs_counter in data_counter.items(): current_floor_storage["mobs_by_tier"].setdefault(tier, Counter()).update(mobs_counter)
                update_ui_status(p, f"Status: Scan lantai {p.data['floor_count']} selesai.")
                if p.client_storage: 
                    p.snack_bar.content = ft.Text(notification_message); p.snack_bar.bgcolor = None 
                    p.snack_bar.open = True; p.update() 
            else: update_ui_status(p, "Status: Scan selesai. Tidak ada file dungeon aktif.")
        except Exception as err:
            update_ui_status(p, f"Status: Error saat scan - {err}")
            if p.client_storage: 
                p.snack_bar.content = ft.Text(f"Error: {err}", color=ft.Colors.WHITE)
                p.snack_bar.bgcolor = ft.Colors.RED_ACCENT_700; p.snack_bar.open = True; p.update()
        p.data["is_scanning"] = False
        scan_button.disabled = False; scan_button.text = "SCAN / UPDATE LANTAI"
        if p.client_storage: p.update(scan_button)
        update_results_display_flet(p) 

    def start_scan_flet(e, p: ft.Page): 
        if p.data["is_scanning"]: return
        current_path_to_save = albion_path_field.value
        if current_path_to_save: save_path_flet(p, current_path_to_save)
        thread = threading.Thread(target=scan_thread_worker_flet, args=(p,), daemon=True); thread.start()

    page.add(
        ft.Column( 
            [
                ft.Row([albion_path_field, browse_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([scan_button, reset_button], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                ft.Divider(height=5, color=ft.Colors.TRANSPARENT), 
                ft.Container(content=results_list_view, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=8, padding=10, expand=True),
                status_label 
            ],
            expand=True 
        )
    )
    load_path_flet(page) 

def _format_single_category_flet(p: ft.Page, category_title: str, items_counter: Counter) -> list:
    lines = [] 
    font_fam = p.data["font_family"]
    if not items_counter: return lines
    lines.append((f"\n {category_title}", COLOR_MAP_FLET["CATEGORY_TITLE_COLOR"], "CATEGORY")) 
    sorted_items = sorted(items_counter.items(), key=lambda item: p.data["current_translations"].get(item[0], (item[0], "❓"))[0])
    for item_id, count in sorted_items:
        entry = p.data["current_translations"].get(item_id)
        icon, item_name_display = "❓", f"ID: {item_id}"
        if entry: item_name_display, icon = entry[0], entry[1] if len(entry) > 1 else "❓"
        icon_display = icon 
        line_text = f"  {icon_display} {item_name_display}"
        formatted_count = f"(x{count})"
        target_len, current_len = 60, len(line_text) + len(formatted_count) 
        padding_needed = max(1, target_len - current_len)
        line_text = f"{line_text}{' ' * padding_needed}{formatted_count}"
        lines.append((line_text, COLOR_MAP_FLET.get(item_id, COLOR_MAP_FLET["DEFAULT_ITEM_COLOR"]), item_id))
    return lines

def generate_report_for_flet(p: ft.Page) -> list:
    display_data = [] 
    font_fam = p.data["font_family"]
    if not p.data["findings_by_floor"]:
        display_data.append(("\n- Tekan 'SCAN / UPDATE LANTAI' untuk memulai.", None, None))
        display_data.append(("- Pastikan Anda berada di dalam dungeon.", None, None))
        return display_data
    for i, floor_data_dict in enumerate(p.data["findings_by_floor"]):
        floor_num = i + 1
        display_data.append((f"\n----- Lantai {floor_num} -----", COLOR_MAP_FLET["HEADER_COLOR"], "HEADER"))
        display_data.extend(_format_single_category_flet(p, "[ Event Boss ]", floor_data_dict.get(TYPE_EVENT_BOSS, Counter())))
        display_data.extend(_format_single_category_flet(p, "[ Boss Dungeon ]", floor_data_dict.get(TYPE_DUNGEON_BOSS, Counter())))
        display_data.extend(_format_single_category_flet(p, "[ Peti ]", floor_data_dict.get(TYPE_CHEST, Counter())))
        display_data.extend(_format_single_category_flet(p, "[ Altar Buff ]", floor_data_dict.get(TYPE_SHRINE, Counter())))
    display_data.append(("\n\n\n----- Laporan Kumulatif Total Sesi -----", COLOR_MAP_FLET["HEADER_COLOR"], "HEADER"))
    total_cumulative = { TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(), TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(), "exits": set()}
    for floor_data_dict in p.data["findings_by_floor"]:
        for category, data in floor_data_dict.items():
            if category in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]: total_cumulative[category].update(data)
            elif category == "exits": total_cumulative["exits"].update(data)
    display_data.extend(_format_single_category_flet(p, "[ Total Event Boss ]", total_cumulative[TYPE_EVENT_BOSS]))
    display_data.extend(_format_single_category_flet(p, "[ Total Boss Dungeon ]", total_cumulative[TYPE_DUNGEON_BOSS]))
    display_data.extend(_format_single_category_flet(p, "[ Total Peti ]", total_cumulative[TYPE_CHEST]))
    display_data.extend(_format_single_category_flet(p, "[ Total Altar Buff ]", total_cumulative[TYPE_SHRINE]))
    display_data.append(("\n" + "---------------------------------------------------------", None, None)) 
    last_floor_exits = p.data["findings_by_floor"][-1].get("exits", set()) if p.data["findings_by_floor"] else set()
    has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
    floor_status_text = "Ada Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
    display_data.append((f" (*) Status Lantai Saat Ini ({p.data['floor_count']}): {floor_status_text}", ft.Colors.LIGHT_BLUE_ACCENT_700, None))
    return display_data

if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(script_dir, "assets")
    if not os.path.exists(assets_dir):
        try:
            os.makedirs(assets_dir)
            print(f"Folder 'assets' dibuat di: {assets_dir}")
            print(f"Harap letakkan NotoSans-Regular.ttf dan NotoEmoji-Regular.ttf di {assets_dir}")
        except OSError as e:
            print(f"Gagal membuat folder 'assets': {e}")
            print(f"Pastikan Anda membuat folder 'assets' secara manual di {script_dir} dan meletakkan file font di sana.")
            
    ft.app(target=main, assets_dir=assets_dir if os.path.exists(assets_dir) else script_dir)