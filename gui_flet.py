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

# Peta warna untuk teks di Flet (MENGGUNAKAN ft.Colors)
COLOR_MAP_FLET = {
    "LOOTCHEST_STANDARD": ft.colors.GREEN_ACCENT_700,
    "BOOKCHEST_STANDARD": ft.colors.GREEN_ACCENT_700,
    "LOOTCHEST_UNCOMMON": ft.colors.BLUE_ACCENT_700,
    "BOOKCHEST_UNCOMMON": ft.colors.BLUE_ACCENT_700,
    "LOOTCHEST_RARE": ft.colors.PURPLE_ACCENT_700,
    "BOOKCHEST_RARE": ft.colors.PURPLE_ACCENT_700,
    "LOOTCHEST_EPIC": ft.colors.AMBER_ACCENT_700,
    "LOOTCHEST_LEGENDARY": ft.colors.YELLOW_ACCENT_700,
    "LOOTCHEST_BOSS": ft.colors.ORANGE_ACCENT_700,
    "LOOTCHEST_MINIBOSS": ft.colors.PINK_ACCENT_700,
    "BOSS_MINIBOSS_GENERIC": ft.colors.PINK_ACCENT_700,
    "BOSS_ENDBOSS_GENERIC": ft.colors.DEEP_ORANGE_ACCENT_700,
    "BOSS_HIGHLIGHT_GENERIC": ft.colors.RED_ACCENT_700,
    "BOSS_GENERIC": ft.colors.RED_700,
    "UNCLEFROST": ft.colors.LIGHT_BLUE_ACCENT_700,
    "ANNIVERSARY_TITAN": ft.colors.AMBER_ACCENT_700,
    "SHRINE_NON_COMBAT_BUFF": ft.colors.CYAN_ACCENT_700,
    # Warna default dan header
    "DEFAULT_ITEM_COLOR": ft.colors.WHITE, # Default jika ID tidak ada di map
    "HEADER_COLOR": ft.colors.BLUE_GREY_200,
    "CATEGORY_TITLE_COLOR": ft.colors.BLUE_GREY_100,
}


def main(page: ft.Page):
    page.title = "Albion Dungeon Scanner (Flet)"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window_width = 850
    page.window_height = 800
    page.padding = 10

    # --- Font Setup ---
    assets_dir_for_fonts = "assets" # Flet akan mencari di subfolder 'assets' relatif terhadap skrip
    # Jika folder 'assets' ada di direktori yang sama dengan gui_flet.py:
    # assets_dir_for_fonts = os.path.join(os.path.dirname(__file__), "assets")
    
    page.fonts = {
        "NotoSans": os.path.join(assets_dir_for_fonts, "NotoSans-Regular.ttf"), 
        "NotoEmoji": os.path.join(assets_dir_for_fonts, "NotoEmoji-Regular.ttf") 
    }
    page.theme = ft.Theme(font_family="NotoSans")


    page.data = {
        "albion_path": "",
        "floor_count": 0,
        "findings_by_floor": [],
        "scanned_files_this_session": set(),
        "current_translations": {},
        "status_text": "Status: Siap.",
        "is_scanning": False
    }
    
    # --- Kontrol UI ---
    albion_path_field = ft.TextField(
        label="Path Albion Online",
        hint_text="Contoh: C:\\Program Files (x86)\\Steam\\...",
        expand=True,
        on_submit=lambda e: save_path_flet(page, e.control.value)
    )

    results_list_view = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=5)
    status_label = ft.Text(page.data["status_text"], style=ft.TextThemeStyle.BODY_SMALL)

    def update_ui_status(new_status: str):
        page.data["status_text"] = new_status
        status_label.value = new_status
        if page.client_storage: # Memastikan page sudah ter-render dan bisa diupdate
            page.update()
        
    def update_results_display_flet():
        results_list_view.controls.clear()
        report_data = generate_report_for_flet(page) 
        
        for text_content, text_color, item_id_for_style in report_data:
            # text_color adalah nilai warna langsung dari COLOR_MAP_FLET
            current_style = ft.TextStyle(font_family="NotoSans") # Gunakan font utama
            if text_color:
                current_style.color = text_color
            
            # Khusus untuk header, kita bisa buat lebih besar/tebal
            if item_id_for_style == "HEADER": # Menggunakan penanda khusus untuk header
                current_style.weight = ft.FontWeight.BOLD
                current_style.size = 18 # Sedikit lebih besar
            elif item_id_for_style == "CATEGORY":
                current_style.weight = ft.FontWeight.BOLD
                current_style.size = 16


            results_list_view.controls.append(
                ft.Text(text_content, style=current_style, selectable=True)
            )
        
        if not results_list_view.controls:
             results_list_view.controls.append(ft.Text("Tekan 'SCAN' untuk memulai.", style=ft.TextStyle(font_family="NotoSans")))
        if page.client_storage:
            page.update()


    def save_path_flet(p: ft.Page, path_value: str):
        config = configparser.ConfigParser()
        config['Settings'] = {'ao-dir': path_value}
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        update_ui_status(f"Status: Path disimpan -> {path_value}")
        p.data["albion_path"] = path_value

    def load_path_flet(p: ft.Page):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            path = config.get('Settings', 'ao-dir', fallback="")
            p.data["albion_path"] = path
            albion_path_field.value = path
            if path:
                update_ui_status("Status: Path dimuat. Siap memindai.")
            else:
                update_ui_status("Status: Path Albion belum diatur.")
        else:
            update_ui_status(f"Status: {CONFIG_FILE} tidak ditemukan. Atur path.")
        
        load_translations() 
        p.data["current_translations"] = TRANSLATIONS.copy()
        update_results_display_flet() 
        if p.client_storage:
             p.update()


    def pick_directory_result(e: ft.FilePickerResultEvent):
        if e.path:
            albion_path_field.value = e.path
            save_path_flet(page, e.path)
            if page.client_storage:
                 page.update()
        else:
            update_ui_status("Status: Pemilihan folder dibatalkan.")

    directory_picker = ft.FilePicker(on_result=pick_directory_result)
    page.overlay.append(directory_picker) 

    def browse_path_flet(e):
        directory_picker.get_directory_path(dialog_title="Pilih Folder Instalasi Albion Online")

    browse_button = ft.ElevatedButton("Browse", icon=ft.icons.FOLDER_OPEN, on_click=browse_path_flet, width=130, height=40, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

    def reset_session_flet(e):
        page.data["floor_count"] = 0
        page.data["findings_by_floor"] = []
        page.data["scanned_files_this_session"] = set()
        update_ui_status("Status: Sesi direset. Siap untuk dungeon baru.")
        update_results_display_flet()

    def scan_thread_worker_flet(p: ft.Page):
        p.data["is_scanning"] = True
        
        # Update UI dari main thread menggunakan page.run() atau page.run_thread_safe()
        def _update_button_state(disabled: bool, text: str):
            scan_button.disabled = disabled
            scan_button.text = text
            if p.client_storage: p.update(scan_button)

        p.run_thread_safe(_update_button_state, True, "MEMINDAI...")
        update_ui_status("Status: Sedang memindai...")
        try:
            current_path = p.data["albion_path"]
            if not current_path or not os.path.isdir(current_path):
                raise ValueError("Path Albion Online tidak valid atau belum diatur.")

            scanner_instance = AlbionDungeonScanner(ao_dir_path=current_path)
            results_from_scan = scanner_instance.run()
            
            load_translations() 
            p.data["current_translations"] = TRANSLATIONS.copy()

            notification_message = "Tidak ada temuan baru atau lantai sama."
            if results_from_scan:
                newly_scanned_files = set(results_from_scan.get("used_files", []))
                if not p.data["findings_by_floor"] or \
                   (newly_scanned_files and not newly_scanned_files.issubset(p.data["scanned_files_this_session"])):
                    p.data["floor_count"] += 1
                    p.data["scanned_files_this_session"].update(newly_scanned_files)
                    p.data["findings_by_floor"].append({
                        TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(),
                        TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(),
                        "mobs_by_tier": {}, "exits": set()
                    })
                    notification_message = f"Temuan baru di Lantai {p.data['floor_count']} ditambahkan!"
                
                current_floor_storage = p.data["findings_by_floor"][-1]
                for key, data_counter in results_from_scan.items():
                    if key in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                        current_floor_storage[key].update(data_counter)
                    elif key == "exits":
                        current_floor_storage[key].update(data_counter)
                    elif key == "mobs_by_tier":
                        for tier, mobs_counter in data_counter.items():
                            current_floor_storage["mobs_by_tier"].setdefault(tier, Counter()).update(mobs_counter)
                
                update_ui_status(f"Status: Scan lantai {p.data['floor_count']} selesai.")
                if p.client_storage:
                     p.show_snack_bar(ft.SnackBar(ft.Text(notification_message), open=True))
            else:
                update_ui_status("Status: Scan selesai. Tidak ada file dungeon aktif.")
        except Exception as err:
            update_ui_status(f"Status: Error saat scan - {err}")
            if p.client_storage:
                 p.show_snack_bar(ft.SnackBar(ft.Text(f"Error: {err}", color=ft.colors.WHITE), open=True, bgcolor=ft.colors.ERROR)) # ft.Colors.ERROR seharusnya
        
        p.data["is_scanning"] = False
        p.run_thread_safe(_update_button_state, False, "SCAN / UPDATE LANTAI")
        p.run_thread_safe(update_results_display_flet)

    def start_scan_flet(e):
        if page.data["is_scanning"]: return
        
        current_path_to_save = albion_path_field.value
        if current_path_to_save:
            save_path_flet(page, current_path_to_save)
        
        thread = threading.Thread(target=scan_thread_worker_flet, args=(page,), daemon=True)
        thread.start()

    scan_button = ft.ElevatedButton("SCAN / UPDATE LANTAI", icon=ft.icons.SEARCH, on_click=start_scan_flet, height=40, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    reset_button = ft.ElevatedButton("RESET SESI", icon=ft.icons.REFRESH, on_click=reset_session_flet, height=40, color=ft.colors.WHITE, bgcolor=ft.colors.RED_ACCENT_700, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))

    page.add(
        ft.Row(
            [albion_path_field, browse_button],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        ft.Row(
            [scan_button, reset_button],
            alignment=ft.MainAxisAlignment.CENTER, spacing=10
        ),
        ft.Divider(height=5, color=ft.colors.TRANSPARENT), 
        ft.Container(
            content=results_list_view,
            border=ft.border.all(1, ft.colors.OUTLINE), 
            border_radius=8,
            padding=10,
            expand=True, 
        ),
        status_label
    )
    
    load_path_flet(page) 

def _format_single_category_flet(p: ft.Page, category_title: str, items_counter: Counter) -> list:
    lines = [] # list of (text_content, color_value, item_id_or_category_type_for_style)
    if not items_counter: return lines
    
    lines.append((f"\n {category_title}", COLOR_MAP_FLET["CATEGORY_TITLE_COLOR"], "CATEGORY")) # "CATEGORY" untuk styling
    
    sorted_items = sorted(items_counter.items(), key=lambda item: p.data["current_translations"].get(item[0], (item[0], "❓"))[0])
    
    for item_id, count in sorted_items:
        entry = p.data["current_translations"].get(item_id)
        icon, item_name_display = "❓", f"ID: {item_id}"
        if entry:
            item_name_display = entry[0]
            icon = entry[1] if len(entry) > 1 else "❓"
        
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
    
    if not p.data["findings_by_floor"]:
        display_data.append(("\n- Tekan 'SCAN / UPDATE LANTAI' untuk memulai.", None, None))
        display_data.append(("- Pastikan Anda berada di dalam dungeon.", None, None))
        return display_data

    for i, floor_data_dict in enumerate(p.data["findings_by_floor"]):
        floor_num = i + 1
        display_data.append((f"\n═══════════ Lantai {floor_num} ═════════════", COLOR_MAP_FLET["HEADER_COLOR"], "HEADER"))
        display_data.extend(_format_single_category_flet(p, "[ Event Boss ]", floor_data_dict.get(TYPE_EVENT_BOSS, Counter())))
        display_data.extend(_format_single_category_flet(p, "[ Boss Dungeon ]", floor_data_dict.get(TYPE_DUNGEON_BOSS, Counter())))
        display_data.extend(_format_single_category_flet(p, "[ Peti ]", floor_data_dict.get(TYPE_CHEST, Counter())))
        display_data.extend(_format_single_category_flet(p, "[ Altar Buff ]", floor_data_dict.get(TYPE_SHRINE, Counter())))

    display_data.append(("\n\n\n══════ Laporan Kumulatif Total Sesi ══════", COLOR_MAP_FLET["HEADER_COLOR"], "HEADER"))
    total_cumulative = { TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(), TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(), "exits": set()}
    for floor_data_dict in p.data["findings_by_floor"]:
        for category, data in floor_data_dict.items():
            if category in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]: total_cumulative[category].update(data)
            elif category == "exits": total_cumulative["exits"].update(data)
    display_data.extend(_format_single_category_flet(p, "[ Total Event Boss ]", total_cumulative[TYPE_EVENT_BOSS]))
    display_data.extend(_format_single_category_flet(p, "[ Total Boss Dungeon ]", total_cumulative[TYPE_DUNGEON_BOSS]))
    display_data.extend(_format_single_category_flet(p, "[ Total Peti ]", total_cumulative[TYPE_CHEST]))
    display_data.extend(_format_single_category_flet(p, "[ Total Altar Buff ]", total_cumulative[TYPE_SHRINE]))
    display_data.append(("\n" + "="*57, None, None)) # Pemisah
    last_floor_exits = p.data["findings_by_floor"][-1].get("exits", set()) if p.data["findings_by_floor"] else set()
    has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
    floor_status_text = "Ada Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
    display_data.append((f" (*) Status Lantai Saat Ini ({p.data['floor_count']}): {floor_status_text}", ft.colors.LIGHT_BLUE_ACCENT_700, None)) # Perbaikan di sini juga
    return display_data

if __name__ == "__main__":
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    if not os.path.exists(assets_dir):
        try:
            os.makedirs(assets_dir)
            print(f"Folder 'assets' dibuat di: {assets_dir}")
            print("Harap letakkan file NotoSans-Regular.ttf dan NotoEmoji-Regular.ttf di sana.")
        except OSError as e:
            print(f"Gagal membuat folder 'assets': {e}")
            print("Pastikan Anda membuat folder 'assets' secara manual dan meletakkan file font di sana.")
            
    ft.app(target=main, assets_dir=assets_dir if os.path.exists(assets_dir) else os.path.dirname(__file__))