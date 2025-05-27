# file: gui.py

import tkinter
import tkinter.filedialog
import tkinter.messagebox
import customtkinter
import configparser
import os
from collections import Counter

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

CONFIG_FILE = "config.ini"

# Peta untuk memberi warna pada teks (sementara tidak digunakan)
COLOR_ID_MAP = {
    "LOOTCHEST_STANDARD": "green",
    "LOOTCHEST_UNCOMMON": "blue",
    "LOOTCHEST_RARE": "purple",
    "LOOTCHEST_EPIC": "gold",
    "LOOTCHEST_LEGENDARY": "gold",
    "LOOTCHEST_BOSS": "gold",
    "LOOTCHEST_MINIBOSS": "purple",
    "BOSS_MINIBOSS_GENERIC": "purple",
    "BOSS_ENDBOSS_GENERIC": "gold",
    "BOSS_HIGHLIGHT_GENERIC": "gold",
    "BOSS_GENERIC": "gold",
    "UNCLEFROST": "blue",
    "ANNIVERSARY_TITAN": "gold",
    "RANDOM_EVENT_WINTER_STANDARD_BOSS": "blue",
    "RANDOM_RD_ANNIVERSARY_SOLO_BOSS": "purple",
}

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Albion Dungeon Scanner (Wiki-Enhanced)")
        self.geometry(f"{800}x800")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0); self.top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10); self.top_frame.grid_columnconfigure(1, weight=1)
        self.label_path = customtkinter.CTkLabel(self.top_frame, text="Albion Path:"); self.label_path.grid(row=0, column=0, padx=10, pady=10)
        self.entry_path = customtkinter.CTkEntry(self.top_frame, placeholder_text="C:\\Program Files (x86)\\Steam\\..."); self.entry_path.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        self.button_browse = customtkinter.CTkButton(self.top_frame, text="Browse", command=self.browse_directory); self.button_browse.grid(row=0, column=2, padx=10, pady=10)
        self.button_frame = customtkinter.CTkFrame(self.top_frame); self.button_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew"); self.button_frame.grid_columnconfigure(0, weight=1); self.button_frame.grid_columnconfigure(1, weight=1)
        self.button_scan = customtkinter.CTkButton(self.button_frame, text="SCAN / UPDATE", command=self.scan_dungeon_thread); self.button_scan.grid(row=0, column=0, padx=(0,5), sticky="ew")
        self.button_reset = customtkinter.CTkButton(self.button_frame, text="RESET SESSION", command=self.reset_session, fg_color="red", hover_color="darkred"); self.button_reset.grid(row=0, column=1, padx=(5,0), sticky="ew")
        
        self.textbox = customtkinter.CTkTextbox(self, width=250) # Menggunakan font default CTk
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        
        # --- DIAGNOSTIK: SEMUA tag_config dikomentari ---
        # self.textbox.tag_config("green", foreground="#34a853")
        # self.textbox.tag_config("blue", foreground="#65a6ff")
        # self.textbox.tag_config("purple", foreground="#c36dff")
        # self.textbox.tag_config("gold", foreground="#fbbc05")
        
        self.textbox.configure(state="disabled")

        self.status_label = customtkinter.CTkLabel(self, text="Ready.", anchor="w"); self.status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
        self.current_translations = {} 
        self.reset_session() 
        self.load_path()

    def reset_session(self):
        self.floor_count = 0
        self.scanned_files_this_session = set()
        self.findings_by_floor = [] 

        if hasattr(self, 'status_label'): 
            self.status_label.configure(text="Sesi direset. Siap untuk dungeon baru.")
        
        from scanner import load_translations, TRANSLATIONS
        load_translations() 
        self.current_translations = TRANSLATIONS.copy() 
        self.update_display()

    def browse_directory(self):
        directory = tkinter.filedialog.askdirectory(title="Pilih Folder Utama Albion Online")
        if directory: self.entry_path.delete(0, "end"); self.entry_path.insert(0, directory); self.save_path()
        
    def save_path(self):
        config = configparser.ConfigParser(); config['Settings'] = {'ao-dir': self.entry_path.get()}
        with open(CONFIG_FILE, 'w') as configfile: config.write(configfile)
        self.status_label.configure(text=f"Path disimpan: {self.entry_path.get()}")
        
    def load_path(self):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser(); config.read(CONFIG_FILE)
            if path := config.get('Settings', 'ao-dir', fallback=None):
                self.entry_path.insert(0, path); self.status_label.configure(text=f"Path dimuat. Siap memindai.")
        from scanner import load_translations, TRANSLATIONS
        load_translations(); self.current_translations = TRANSLATIONS.copy(); self.update_display()
        
    def scan_dungeon_thread(self):
        import threading
        self.button_scan.configure(state="disabled", text="Scanning...")
        self.status_label.configure(text="Scanning... (Mungkin perlu waktu jika mengambil data dari API)")
        def run_scan():
            try:
                from scanner import AlbionDungeonScanner, load_translations, TRANSLATIONS
                scanner_instance = AlbionDungeonScanner(ao_dir_path=self.entry_path.get())
                current_results = scanner_instance.run()
                load_translations(); self.current_translations = TRANSLATIONS.copy() 
                self.after(0, self.merge_and_update_ui, current_results)
            except Exception as e: self.after(0, self.update_ui_with_error, e)
        scan_thread = threading.Thread(target=run_scan); scan_thread.daemon = True; scan_thread.start()
        
    def merge_and_update_ui(self, current_results):
        notification_title = "Scan Selesai"; notification_message = "Tidak ada file dungeon aktif baru yang ditemukan."
        if current_results:
            newly_scanned_files = set(current_results.get("used_files", []))
            
            is_new_floor = False
            if not self.findings_by_floor or (newly_scanned_files and not newly_scanned_files.issubset(self.scanned_files_this_session)):
                is_new_floor = True
                self.floor_count += 1
                self.scanned_files_this_session.update(newly_scanned_files)
                self.findings_by_floor.append({
                    "event_bosses": Counter(), "dungeon_bosses": Counter(),
                    "chests": Counter(), "shrines": Counter(),
                    "mobs_by_tier": {}, "exits": set()
                })
                notification_message = f"Temuan baru di Lantai {self.floor_count} telah ditambahkan!"
            else:
                 notification_message = "Scan selesai, data diperbarui. Tidak ada lantai baru terdeteksi."

            current_floor_data = self.findings_by_floor[-1]

            current_floor_data["event_bosses"].update(current_results.get("event_bosses", Counter()))
            current_floor_data["dungeon_bosses"].update(current_results.get("dungeon_bosses", Counter()))
            current_floor_data["chests"].update(current_results.get("chests", Counter()))
            current_floor_data["shrines"].update(current_results.get("shrines", Counter()))
            current_floor_data["exits"].update(current_results.get("exits", set()))
            
            if "mobs_by_tier" in current_results:
                for tier, tier_counter in current_results["mobs_by_tier"].items():
                    if tier not in current_floor_data["mobs_by_tier"]:
                        current_floor_data["mobs_by_tier"][tier] = Counter()
                    current_floor_data["mobs_by_tier"][tier].update(tier_counter)

            self.status_label.configure(text="Scan complete. Temuan telah digabungkan.")
        else:
            self.status_label.configure(text="Scan complete. Tidak ada file dungeon aktif baru ditemukan.")
            
        self.update_display()
        self.button_scan.configure(state="normal", text="SCAN / UPDATE")
        tkinter.messagebox.showinfo(notification_title, notification_message)

    def generate_report_lines(self) -> list:
        report_data = []
        active_translations = self.current_translations

        def format_category(title, items_counter, parent_list):
            if not items_counter: return
            parent_list.append((f"\n{title}", None)) # item_id_or_type menjadi None untuk judul kategori
            sorted_items = sorted(items_counter.items(), key=lambda item: active_translations.get(item[0], (item[0],))[0])
            for item_id, count in sorted_items:
                entry = active_translations.get(item_id, (f"ID: {item_id}", "❓"))
                item_name, icon = entry[0], entry[1] if len(entry) > 1 else "❓"
                line_text = f" {icon} {item_name:<25}" 
                line_text = f"{line_text:<50} (x{count})"
                parent_list.append((line_text, item_id))

        if not self.findings_by_floor:
            report_data.append(("\n- Belum ada item signifikan yang ditemukan.", None))
        else:
            for i, floor_data in enumerate(self.findings_by_floor):
                floor_num = i + 1
                report_data.append((f"\n═══════════════ Lantai {floor_num} ═══════════════", "header")) # type "header"
                format_category("[ Event Boss ]", floor_data.get("event_bosses", Counter()), report_data)
                format_category("[ Boss Dungeon ]", floor_data.get("dungeon_bosses", Counter()), report_data)
                format_category("[ Peti ]", floor_data.get("chests", Counter()), report_data)
                format_category("[ Altar Buff ]", floor_data.get("shrines", Counter()), report_data)

        report_data.append(("\n\n\n══════ Laporan Kumulatif Total ══════", "header"))
        
        total_findings = {"event_bosses": Counter(), "dungeon_bosses": Counter(), "chests": Counter(), "shrines": Counter(), "exits": set()}
        for floor_data in self.findings_by_floor:
            for category, data in floor_data.items():
                if category in total_findings and category != "exits": # Pastikan kategori ada di total_findings
                    total_findings[category].update(data)
            total_findings["exits"].update(floor_data.get("exits", set()))
        
        format_category("[ Total Event Boss ]", total_findings["event_bosses"], report_data)
        format_category("[ Total Boss Dungeon ]", total_findings["dungeon_bosses"], report_data)
        format_category("[ Total Peti ]", total_findings["chests"], report_data)
        format_category("[ Total Altar Buff ]", total_findings["shrines"], report_data)

        report_data.append(("\n" + "="*57, None))
        last_floor_exits = self.findings_by_floor[-1].get("exits", set()) if self.findings_by_floor else set()
        has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
        floor_status = "Terdapat Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
        report_data.append((f" 🚪 Status Lantai Saat Ini: {floor_status}", None))
        
        return report_data

    def update_display(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        report_lines = self.generate_report_lines()
        for text, item_id_or_type in report_lines:
            # --- DIAGNOSTIK: Pewarnaan dinonaktifkan sementara ---
            # tag_to_apply = None
            # if item_id_or_type == "header":
            #     pass 
            # elif item_id_or_type: # Ini adalah item_id
            #     tag_to_apply = COLOR_ID_MAP.get(item_id_or_type)
            # self.textbox.insert("end", text + "\n", (tag_to_apply,) if tag_to_apply else None)
            self.textbox.insert("end", text + "\n") # Insert tanpa tag untuk diagnostik

        self.textbox.configure(state="disabled")

    def update_ui_with_error(self, error):
        error_message = f"TERJADI ERROR:\n\n{type(error).__name__}: {error}"
        self.textbox.configure(state="normal"); self.textbox.delete("1.0", "end"); self.textbox.insert("1.0", error_message); self.textbox.configure(state="disabled")
        self.button_scan.configure(state="normal", text="SCAN / UPDATE"); self.status_label.configure(text="Error occurred. Please check the path and try again.")
        tkinter.messagebox.showerror("Error", f"Terjadi kesalahan saat memindai:\n{error}")

if __name__ == "__main__":
    app = App()
    app.mainloop()