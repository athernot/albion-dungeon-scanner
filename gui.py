# file: gui.py

import tkinter
import tkinter.filedialog
import tkinter.messagebox
import customtkinter
import configparser
import os
from collections import Counter
import threading
import requests
import json
from datetime import datetime

# Impor tipe dari scanner untuk konsistensi
from scanner import TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE 

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

CONFIG_FILE = "config.ini"

# Peta warna disesuaikan dengan ID generik baru
COLOR_ID_MAP = {
    "CHEST_GREEN": "green",
    "CHEST_BLUE": "blue",
    "CHEST_PURPLE": "purple",
    "CHEST_GOLD": "gold",
    "BOSS_MINIBOSS_GENERIC": "purple",
    "BOSS_ENDBOSS_GENERIC": "gold",
    "BOSS_HIGHLIGHT_GENERIC": "gold",
    "BOSS_GENERIC": "gold",
    "UNCLEFROST": "blue", 
    "ANNIVERSARY_TITAN": "gold",
    "SHRINE_NON_COMBAT_BUFF": "blue",
}

# Peta nama tampilan untuk peti generik
GENERIC_CHEST_NAMES = {
    "CHEST_GREEN":  ["Peti Hijau (Std/Unc)", "📦"],
    "CHEST_BLUE":   ["Peti Biru (Rare)", "📦"],
    "CHEST_PURPLE": ["Peti Ungu (Epic)", "📦"],
    "CHEST_GOLD":   ["Peti Emas (Leg/Boss)", "📦"],
}


class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Albion Dungeon Scanner")
        self.geometry(f"{850}x750") 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self.webhook_url = None
        
        self.top_controls_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self.top_controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.top_controls_frame.grid_columnconfigure(1, weight=1)

        self.label_path = customtkinter.CTkLabel(self.top_controls_frame, text="Path Albion:")
        self.label_path.grid(row=0, column=0, padx=(10,5), pady=10, sticky="w")
        self.entry_path = customtkinter.CTkEntry(self.top_controls_frame, placeholder_text="Contoh: C:\\Program Files (x86)\\Steam\\...")
        self.entry_path.grid(row=0, column=1, sticky="ew", padx=0, pady=10)
        self.button_browse = customtkinter.CTkButton(self.top_controls_frame, text="Browse", command=self.browse_directory, width=100)
        self.button_browse.grid(row=0, column=2, padx=(5,10), pady=10, sticky="e")

        self.action_buttons_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self.action_buttons_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,5))
        self.action_buttons_frame.grid_columnconfigure((0,1), weight=1)

        self.button_scan = customtkinter.CTkButton(self.action_buttons_frame, text="SCAN / UPDATE LANTAI", command=self.scan_dungeon_thread, height=35)
        self.button_scan.grid(row=0, column=0, padx=(0,5), pady=10, sticky="ew")
        self.button_reset = customtkinter.CTkButton(self.action_buttons_frame, text="RESET SESI DUNGEON", command=self.reset_session, fg_color="#D32F2F", hover_color="#B71C1C", height=35)
        self.button_reset.grid(row=0, column=1, padx=(5,0), pady=10, sticky="ew")
        
        self.textbox_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self.textbox_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0,5))
        self.textbox_frame.grid_rowconfigure(0, weight=1)
        self.textbox_frame.grid_columnconfigure(0, weight=1)

        self.textbox = customtkinter.CTkTextbox(self.textbox_frame, wrap="none", font=("Consolas", 13))
        self.textbox.grid(row=0, column=0, sticky="nsew")
        
        label_text_colors = customtkinter.ThemeManager.theme["CTkLabel"]["text_color"]
        current_label_text_color = label_text_colors[0] if customtkinter.get_appearance_mode().lower() == "dark" else label_text_colors[1]

        self.textbox.tag_config("green", foreground="#66BB6A") 
        self.textbox.tag_config("blue", foreground="#42A5F5")  
        self.textbox.tag_config("purple", foreground="#AB47BC")
        self.textbox.tag_config("gold", foreground="#FFA726")
        self.textbox.tag_config("header", foreground=current_label_text_color, underline=True) 
        self.textbox.tag_config("category_title", foreground=current_label_text_color, underline=True)
        
        self.textbox.configure(state="disabled")

        self.status_label = customtkinter.CTkLabel(self, text="Status: Siap.", anchor="w", font=("Segoe UI", 12))
        self.status_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.current_translations = {} 
        self.reset_session() 
        self.load_path()

    def reset_session(self):
        self.floor_count = 0
        self.scanned_files_this_session = set()
        self.findings_by_floor = [] 
        if hasattr(self, 'status_label'): 
            self.status_label.configure(text="Status: Sesi direset. Siap untuk dungeon baru.")
        if hasattr(self, 'textbox'): 
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", "Tekan 'SCAN / UPDATE LANTAI' untuk memulai.\nPastikan Anda berada di dalam dungeon.")
            self.textbox.configure(state="disabled")
        self.update_display_content()

    def browse_directory(self):
        directory = tkinter.filedialog.askdirectory(title="Pilih Folder Utama Albion Online")
        if directory: 
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, directory)
            self.save_path()
        
    def save_path(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
        if not config.has_section('Settings'):
            config.add_section('Settings')
        config.set('Settings', 'ao-dir', self.entry_path.get())
        if not config.has_section('Discord'):
            config.add_section('Discord')
            if not config.has_option('Discord', 'webhook_url'):
                 config.set('Discord', 'webhook_url', "")
        with open(CONFIG_FILE, 'w') as configfile: 
            config.write(configfile)
        self.status_label.configure(text=f"Status: Path disimpan -> {self.entry_path.get()}")
        
    def load_path(self):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            if path := config.get('Settings', 'ao-dir', fallback=None):
                self.entry_path.insert(0, path)
                self.status_label.configure(text="Status: Path dimuat. Siap memindai.")
            self.webhook_url = config.get('Discord', 'webhook_url', fallback=None)
            if not self.webhook_url or "MASUKKAN_URL_WEBHOOK" in self.webhook_url.upper():
                self.webhook_url = None 
        else:
            self.status_label.configure(text=f"Status: {CONFIG_FILE} tidak ditemukan. Atur path.")
        
        from scanner import TRANSLATIONS, load_translations
        if not TRANSLATIONS:
            load_translations()
        self.current_translations = TRANSLATIONS.copy()
        self.update_display_content() 
        
    def scan_dungeon_thread(self):
        self.button_scan.configure(state="disabled", text="MEMINDAI...")
        self.status_label.configure(text="Status: Sedang memindai lantai saat ini...")
        scan_thread = threading.Thread(target=self._scan_logic_worker)
        scan_thread.daemon = True
        scan_thread.start()
        
    def _scan_logic_worker(self):
        try:
            from scanner import AlbionDungeonScanner
            ao_path = self.entry_path.get()
            if not ao_path or not os.path.isdir(ao_path):
                raise ValueError("Path Albion Online tidak valid atau belum diatur.")
            scanner_instance = AlbionDungeonScanner(ao_dir_path=ao_path)
            current_results_from_scan = scanner_instance.run()
            self.after(0, self.merge_and_update_ui_post_scan, current_results_from_scan)
        except Exception as e:
            self.after(0, self.handle_scan_error, e)

    def merge_and_update_ui_post_scan(self, current_scan_results: dict | None):
        notification_title = "Scan Selesai"
        notification_message = "Tidak ada file dungeon aktif baru terdeteksi atau lantai sama."
        if current_scan_results:
            newly_scanned_files = set(current_scan_results.get("used_files", []))
            is_new_floor_detected = False
            if not self.findings_by_floor or (newly_scanned_files and not newly_scanned_files.issubset(self.scanned_files_this_session)):
                is_new_floor_detected = True
                self.floor_count += 1
                self.scanned_files_this_session.update(newly_scanned_files)
                self.findings_by_floor.append({
                    TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(),
                    TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(),
                    "mobs_by_tier": {}, "exits": set()
                })
                notification_message = f"Temuan baru di Lantai {self.floor_count} telah ditambahkan!"
            else:
                if self.findings_by_floor:
                    self.findings_by_floor[-1] = {
                        TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(),
                        TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(),
                        "mobs_by_tier": {}, "exits": set()
                    }
                notification_message = "Scan selesai. Data untuk lantai saat ini diperbarui."
            
            current_floor_storage = self.findings_by_floor[-1]
            for key_type in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                if key_type in current_scan_results:
                    current_floor_storage[key_type].update(current_scan_results[key_type])
            if "exits" in current_scan_results:
                current_floor_storage["exits"].update(current_scan_results["exits"])
            if "mobs_by_tier" in current_scan_results:
                for tier, mobs_in_tier_counter in current_scan_results["mobs_by_tier"].items():
                    current_floor_storage["mobs_by_tier"].setdefault(tier, Counter()).update(mobs_in_tier_counter)
            
            if is_new_floor_detected and self.webhook_url:
                # --- PERUBAHAN DI SINI: Mengirim objek embed, bukan teks biasa ---
                discord_embed = self._format_for_discord_embed(current_floor_storage, self.floor_count)
                threading.Thread(target=self._send_to_discord, args=(discord_embed,), daemon=True).start()
            
            self.status_label.configure(text=f"Status: Scan lantai {self.floor_count} selesai.")
        else:
            self.status_label.configure(text="Status: Scan selesai. Tidak ada file dungeon aktif.")
            
        self.update_display_content()
        self.button_scan.configure(state="normal", text="SCAN / UPDATE LANTAI")
        if current_scan_results:
             tkinter.messagebox.showinfo(notification_title, notification_message)

    def _format_for_discord_embed(self, floor_data: dict, floor_num: int) -> dict:
        """
        Memformat data dari satu lantai menjadi objek embed Discord.
        """
        embed_fields = []
        
        # Gabungkan semua jenis bos
        all_bosses = floor_data.get(TYPE_DUNGEON_BOSS, Counter()) + floor_data.get(TYPE_EVENT_BOSS, Counter())
        
        # Proses Bos
        if all_bosses:
            boss_lines = []
            for item_id, count in all_bosses.items():
                # Ambil nama dan ikon dari database terjemahan
                display_name, icon = self.current_translations.get(item_id, (item_id.replace("_", " ").title(), "❓"))[:2]
                count_str = f" (x{count})" if count > 1 else ""
                boss_lines.append(f"{icon} {display_name}{count_str}")
            embed_fields.append({
                "name": "Boss Terdeteksi",
                "value": "\n".join(boss_lines),
                "inline": False
            })

        # Proses Peti
        all_chests = floor_data.get(TYPE_CHEST, Counter())
        if all_chests:
            chest_lines = []
            # Urutkan berdasarkan kelangkaan
            color_order = {"CHEST_GREEN": 0, "CHEST_BLUE": 1, "CHEST_PURPLE": 2, "CHEST_GOLD": 3}
            sorted_chests = sorted(all_chests.items(), key=lambda item: color_order.get(item[0], 99))
            
            for item_id, count in sorted_chests:
                display_name, icon = GENERIC_CHEST_NAMES.get(item_id, ("Peti Tidak Dikenal", "❓"))
                chest_lines.append(f"{icon} {display_name} **(x{count})**")
            embed_fields.append({
                "name": "Peti Ditemukan",
                "value": "\n".join(chest_lines),
                "inline": False
            })

        # Proses Mob
        total_mobs = sum(sum(c.values()) for c in floor_data.get("mobs_by_tier", {}).values())
        if total_mobs > 0:
            embed_fields.append({
                "name": "Total Mob (T6+/?)",
                "value": f"👾 Terdapat **{total_mobs}** spawn point mob.",
                "inline": False
            })
            
        # Membuat struktur embed lengkap
        embed = {
            "title": f"Laporan Dungeon - Lantai {floor_num}",
            "color": 3447003,  # Warna biru
            "fields": embed_fields,
            "footer": {
                "text": f"Albion Dungeon Scanner | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        return embed

    def _send_to_discord(self, embed_data: dict):
        """Mengirim pesan embed ke URL webhook Discord."""
        if not self.webhook_url: return
        
        # Cek jika tidak ada field yang berarti (tidak ada bos/peti/mob)
        if not embed_data.get("fields"):
            print("Pesan Discord tidak dikirim (tidak ada konten).")
            return

        headers = {"Content-Type": "application/json"}
        # Webhook payload untuk embed berbeda
        payload = {
            "username": "Dungeon Scanner",
            "avatar_url": "https://i.imgur.com/K3e6F4f.png", # Contoh ikon
            "embeds": [embed_data]
        }
        
        try:
            response = requests.post(self.webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
            if response.status_code >= 400:
                print(f"Error mengirim ke Discord (Status {response.status_code}): {response.text}")
        except requests.RequestException as e:
            print(f"Gagal mengirim pesan ke Discord: {e}")

    def _format_single_category_lines(self, category_title: str, items_counter: Counter) -> list:
        lines = []
        if not items_counter: return lines
        
        lines.append((f"\n {category_title}", "category_title", None))
        
        is_chest_category = (category_title == "[ Peti ]")
        
        if is_chest_category:
            color_order = {"CHEST_GREEN": 0, "CHEST_BLUE": 1, "CHEST_PURPLE": 2, "CHEST_GOLD": 3}
            sorted_items = sorted(items_counter.items(), key=lambda item: color_order.get(item[0], 99))
        else:
            sorted_items = sorted(items_counter.items(), key=lambda item: self.current_translations.get(item[0], (item[0], "❓"))[0])
        
        for item_id, count in sorted_items:
            if is_chest_category:
                item_name_display, icon = GENERIC_CHEST_NAMES.get(item_id, ("Peti Tidak Dikenal", "❓"))
            else:
                entry = self.current_translations.get(item_id)
                icon, item_name_display = ("❓", f"ID: {item_id}")
                if entry:
                    item_name_display = entry[0]
                    icon = entry[1] if len(entry) > 1 else "❓"
            
            line_text = f"  {icon} {item_name_display}"
            padding = 55 - len(line_text) 
            if padding < 1 : padding = 1
            line_text += " " * padding + f"(x{count})"
            lines.append((line_text, "item", item_id))
        return lines

    def generate_report_data_for_display(self) -> list:
        """Menghasilkan list data HANYA untuk laporan per lantai."""
        display_lines_with_tags = [] 

        if not self.findings_by_floor:
            display_lines_with_tags.append(("\n- Belum ada temuan. Tekan SCAN saat di dalam dungeon.", "item", None))
            return display_lines_with_tags

        for i, floor_data_dict in enumerate(self.findings_by_floor):
            floor_num = i + 1
            display_lines_with_tags.append((f"\n═══════════ Lantai {floor_num} ═════════════", "header", None))
            
            display_lines_with_tags.extend(self._format_single_category_lines("[ Event Boss ]", floor_data_dict.get(TYPE_EVENT_BOSS, Counter())))
            display_lines_with_tags.extend(self._format_single_category_lines("[ Boss Dungeon ]", floor_data_dict.get(TYPE_DUNGEON_BOSS, Counter())))
            display_lines_with_tags.extend(self._format_single_category_lines("[ Peti ]", floor_data_dict.get(TYPE_CHEST, Counter())))
            display_lines_with_tags.extend(self._format_single_category_lines("[ Altar Buff ]", floor_data_dict.get(TYPE_SHRINE, Counter())))
            
        display_lines_with_tags.append(("\n" + "="*57, "item", None)) 
        last_floor_exits = self.findings_by_floor[-1].get("exits", set()) if self.findings_by_floor else set()
        has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
        floor_status_text = "Ada Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
        display_lines_with_tags.append((f" 🚪 Lantai Saat Ini: {self.floor_count} | Status: {floor_status_text}", "item", None))
        
        return display_lines_with_tags

    def update_display_content(self):
        if not hasattr(self, 'textbox') or self.textbox is None: return

        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        
        if not self.findings_by_floor and self.floor_count == 0 :
            self.textbox.insert("1.0", "Tekan 'SCAN / UPDATE LANTAI' untuk memulai.\nPastikan Anda berada di dalam dungeon.")
            self.textbox.configure(state="disabled")
            return

        report_data_for_display = self.generate_report_data_for_display()
        
        for text_line, line_tag_type, item_id_for_color in report_data_for_display:
            tags_to_apply = []
            if line_tag_type == "header":
                tags_to_apply.append("header")
            elif line_tag_type == "category_title":
                tags_to_apply.append("category_title")
            elif line_tag_type == "item" and item_id_for_color: 
                color_tag_name = COLOR_ID_MAP.get(item_id_for_color)
                if color_tag_name:
                    tags_to_apply.append(color_tag_name)
            
            self.textbox.insert("end", text_line + "\n", tuple(tags_to_apply) if tags_to_apply else None)
            
        self.textbox.configure(state="disabled")
        self.textbox.see("1.0")

    def handle_scan_error(self, error_obj: Exception):
        error_message = f"TERJADI ERROR SAAT SCAN:\n\n{type(error_obj).__name__}: {error_obj}\n\nPastikan path Albion Online sudah benar."
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", error_message)
        self.textbox.configure(state="disabled")
        self.button_scan.configure(state="normal", text="SCAN / UPDATE LANTAI")
        self.status_label.configure(text="Status: Error saat scan. Periksa path & coba lagi.")
        tkinter.messagebox.showerror("Error Scan", f"Terjadi kesalahan:\n{error_obj}")

if __name__ == "__main__":
    from scanner import load_translations
    load_translations()
    app = App()
    app.mainloop()