import tkinter
import tkinter.filedialog
import customtkinter
import configparser
import os
from collections import Counter
# Import dinamis akan dilakukan di dalam fungsi yang memerlukan versi terbaru

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

CONFIG_FILE = "config.ini"

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("Albion Dungeon Scanner (Advanced v2)")
        self.geometry(f"{700}x650") # Perbesar sedikit lagi untuk detail mob
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.top_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.label_path = customtkinter.CTkLabel(self.top_frame, text="Albion Path:")
        self.label_path.grid(row=0, column=0, padx=10, pady=10)
        self.entry_path = customtkinter.CTkEntry(self.top_frame, placeholder_text="C:\\Program Files (x86)\\Steam\\...")
        self.entry_path.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        self.button_browse = customtkinter.CTkButton(self.top_frame, text="Browse", command=self.browse_directory)
        self.button_browse.grid(row=0, column=2, padx=10, pady=10)

        self.button_frame = customtkinter.CTkFrame(self.top_frame)
        self.button_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)
        
        self.button_scan = customtkinter.CTkButton(self.button_frame, text="SCAN / UPDATE", command=self.scan_dungeon_thread)
        self.button_scan.grid(row=0, column=0, padx=(0,5), sticky="ew")
        self.button_reset = customtkinter.CTkButton(self.button_frame, text="RESET SESSION", command=self.reset_session, fg_color="red", hover_color="darkred")
        self.button_reset.grid(row=0, column=1, padx=(5,0), sticky="ew")
        
        self.textbox = customtkinter.CTkTextbox(self, width=250)
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,10))
        self.textbox.configure(state="disabled", font=("Courier New", 14))
        
        self.status_label = customtkinter.CTkLabel(self, text="Ready.", anchor="w")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.current_translations = {} 

        self.reset_session() 
        self.load_path()

    def reset_session(self):
        self.session_findings = {
            "event_bosses": Counter(),
            "dungeon_bosses": Counter(),
            "chests": Counter(),
            "shrines": Counter(),
            "mobs_by_tier": {f"T{i}": Counter() for i in range(1, 9)}, # Inisialisasi mobs_by_tier
            "exits": set()
        }
        if 'mobs_by_tier' not in self.session_findings: self.session_findings['mobs_by_tier'] = {}
        self.session_findings['mobs_by_tier'].setdefault("Unknown Tier", Counter())

        if hasattr(self, 'status_label'): 
            self.status_label.configure(text="Sesi direset. Siap untuk dungeon baru.")
        
        from scanner import load_translations, TRANSLATIONS
        load_translations() 
        self.current_translations = TRANSLATIONS.copy() 
        self.update_display()
            
    def browse_directory(self):
        directory = tkinter.filedialog.askdirectory(title="Pilih Folder Utama Albion Online")
        if directory:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, directory)
            self.save_path()

    def save_path(self):
        config = configparser.ConfigParser()
        config['Settings'] = {'ao-dir': self.entry_path.get()}
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        self.status_label.configure(text=f"Path disimpan: {self.entry_path.get()}")
            
    def load_path(self):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            path = config.get('Settings', 'ao-dir', fallback=None)
            if path:
                self.entry_path.insert(0, path)
                self.status_label.configure(text=f"Path dimuat. Siap memindai.")
        
        from scanner import load_translations, TRANSLATIONS
        load_translations()
        self.current_translations = TRANSLATIONS.copy()
        self.update_display()

    def scan_dungeon_thread(self):
        import threading
        self.button_scan.configure(state="disabled", text="Scanning...")
        self.status_label.configure(text="Scanning... (Mungkin perlu waktu jika mengambil data dari API)")
        
        def run_scan():
            try:
                from scanner import AlbionDungeonScanner, load_translations, TRANSLATIONS
                
                scanner_instance = AlbionDungeonScanner(ao_dir_path=self.entry_path.get())
                current_results = scanner_instance.run()
                
                load_translations() 
                self.current_translations = TRANSLATIONS.copy() 
                
                self.after(0, self.merge_and_update_ui, current_results)
            except Exception as e:
                self.after(0, self.update_ui_with_error, e)
        
        scan_thread = threading.Thread(target=run_scan)
        scan_thread.daemon = True
        scan_thread.start()
        
    def merge_and_update_ui(self, current_results):
        if current_results:
            self.session_findings["event_bosses"].update(current_results["event_bosses"])
            self.session_findings["dungeon_bosses"].update(current_results["dungeon_bosses"])
            self.session_findings["chests"].update(current_results["chests"])
            self.session_findings["shrines"].update(current_results["shrines"])
            self.session_findings["exits"].update(current_results["exits"])

            # Gabungkan mobs_by_tier
            if "mobs_by_tier" in current_results:
                for tier, tier_counter in current_results["mobs_by_tier"].items():
                    self.session_findings["mobs_by_tier"].setdefault(tier, Counter()).update(tier_counter)
            
            self.status_label.configure(text="Scan complete. Temuan telah digabungkan.")
        else:
            self.status_label.configure(text="Scan complete. Tidak ada file dungeon aktif baru yang ditemukan.")
            
        self.update_display()
        self.button_scan.configure(state="normal", text="SCAN / UPDATE")

    def format_results_to_string(self) -> str:
        output_lines = ["===== Laporan Dungeon Kumulatif ====="]
        active_translations = self.current_translations

        def format_category_counters(title, items_counter):
            if not items_counter: return
            output_lines.append(f"\n{title}")
            for item_id, count in sorted(items_counter.items()):
                entry = active_translations.get(item_id)
                item_name, icon = f"ID Tidak Dikenal: {item_id}", "❓"
                if entry:
                    item_name = entry[0]
                    icon = entry[1] if len(entry) > 1 else "❓"
                output_lines.append(f"{icon} {item_name:<60} (x{count})")
        
        format_category_counters("[ EVENT BOSS TERLIHAT ]", self.session_findings["event_bosses"])
        format_category_counters("[ BOSS DUNGEON TERLIHAT ]", self.session_findings["dungeon_bosses"])
        format_category_counters("[ ALTAR BUFF TERLIHAT ]", self.session_findings["shrines"])
        format_category_counters("[ PETI TERLIHAT (TOTAL SPAWN POINT) ]", self.session_findings["chests"])
        
        # Tampilkan jumlah mob per tier
        total_mobs = 0
        if self.session_findings.get("mobs_by_tier"):
            mob_tier_lines = []
            for tier in sorted(self.session_findings["mobs_by_tier"].keys()):
                tier_counter = self.session_findings["mobs_by_tier"][tier]
                if tier_counter:
                    tier_total = sum(tier_counter.values())
                    total_mobs += tier_total
                    mob_tier_lines.append(f"  - {tier}: {tier_total} spawn point")
            
            if mob_tier_lines:
                output_lines.append(f"\n[ MOB BIASA TERDETEKSI (PER TIER) ]")
                output_lines.extend(mob_tier_lines)
                output_lines.append(f"👾 Total Spawn Point Mob Biasa: {total_mobs}")


        is_empty = True # Cek apakah ada temuan signifikan
        for key, category_data in self.session_findings.items():
            if key == "exits": continue
            if key == "mobs_by_tier":
                if any(tier_data for tier_data in category_data.values()):
                    is_empty = False; break
            elif category_data: 
                is_empty = False; break
        if is_empty:
             output_lines.append("\n- Belum ada item, bos, peti, atau mob yang signifikan ditemukan.")

        output_lines.append("\n" + "="*42)
        has_next_floor_exit = any("EXIT" in e and "ENTER" not in e and "HELL" not in e for e in self.session_findings["exits"])
        floor_status = "Terdapat Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
        output_lines.append(f"🚪 Status Lantai: {floor_status}")
        
        return "\n".join(output_lines)

    def update_display(self):
        report = self.format_results_to_string()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", report)
        self.textbox.configure(state="disabled")

    def update_ui_with_error(self, error):
        error_message = f"TERJADI ERROR:\n\n{type(error).__name__}: {error}"
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", error_message)
        self.textbox.configure(state="disabled")
        self.button_scan.configure(state="normal", text="SCAN / UPDATE")
        self.status_label.configure(text="Error occurred. Please check the path and try again.")

if __name__ == "__main__":
    app = App()
    app.mainloop()