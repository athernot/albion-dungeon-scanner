# file: gui.py

import tkinter
import tkinter.filedialog
import tkinter.messagebox
import customtkinter
import configparser
import os
from collections import Counter

# Impor tipe dari scanner untuk konsistensi
from scanner import TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE 

customtkinter.set_appearance_mode("System") # Atau "Light", "Dark"
customtkinter.set_default_color_theme("blue") # Atau "green", "dark-blue"

CONFIG_FILE = "config.ini"

# Peta warna untuk teks di laporan
# Kunci adalah ID KANONIS atau TIPE
COLOR_ID_MAP = {
    # Peti berdasarkan ID kanonis
    "LOOTCHEST_STANDARD": "green", "BOOKCHEST_STANDARD": "green",
    "LOOTCHEST_UNCOMMON": "blue", "BOOKCHEST_UNCOMMON": "blue",
    "LOOTCHEST_RARE": "purple", "BOOKCHEST_RARE": "purple",
    "LOOTCHEST_EPIC": "gold",
    "LOOTCHEST_LEGENDARY": "gold",
    "LOOTCHEST_BOSS": "gold",
    "LOOTCHEST_MINIBOSS": "purple",
    # Bos berdasarkan ID kanonis atau ID spesifik dari database
    "BOSS_MINIBOSS_GENERIC": "purple",
    "BOSS_ENDBOSS_GENERIC": "gold",
    "BOSS_HIGHLIGHT_GENERIC": "gold",
    "BOSS_GENERIC": "gold",
    "UNCLEFROST": "blue", # Contoh event boss
    "ANNIVERSARY_TITAN": "gold",
    # Altar (bisa ditambahkan jika ada variasi warna)
    "SHRINE_NON_COMBAT_BUFF": "blue",
}

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Albion Dungeon Scanner")
        self.geometry(f"{850}x750") # Sedikit lebih lebar dan tinggi
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Frame utama untuk output teks
        
        # Frame untuk input path dan tombol
        self.top_controls_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self.top_controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.top_controls_frame.grid_columnconfigure(1, weight=1) # Agar entry path bisa expand

        self.label_path = customtkinter.CTkLabel(self.top_controls_frame, text="Path Albion:")
        self.label_path.grid(row=0, column=0, padx=(10,5), pady=10, sticky="w")
        self.entry_path = customtkinter.CTkEntry(self.top_controls_frame, placeholder_text="Contoh: C:\\Program Files (x86)\\Steam\\...")
        self.entry_path.grid(row=0, column=1, sticky="ew", padx=0, pady=10)
        self.button_browse = customtkinter.CTkButton(self.top_controls_frame, text="Browse", command=self.browse_directory, width=100)
        self.button_browse.grid(row=0, column=2, padx=(5,10), pady=10, sticky="e")

        # Frame untuk tombol Scan dan Reset (dipisahkan agar lebih rapi)
        self.action_buttons_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self.action_buttons_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,5))
        self.action_buttons_frame.grid_columnconfigure((0,1), weight=1) # Kedua tombol sama lebar

        self.button_scan = customtkinter.CTkButton(self.action_buttons_frame, text="SCAN / UPDATE LANTAI", command=self.scan_dungeon_thread, height=35)
        self.button_scan.grid(row=0, column=0, padx=(0,5), pady=10, sticky="ew")
        self.button_reset = customtkinter.CTkButton(self.action_buttons_frame, text="RESET SESI DUNGEON", command=self.reset_session, fg_color="#D32F2F", hover_color="#B71C1C", height=35)
        self.button_reset.grid(row=0, column=1, padx=(5,0), pady=10, sticky="ew")
        
        # Textbox untuk output hasil scan
        self.textbox_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self.textbox_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0,5))
        self.textbox_frame.grid_rowconfigure(0, weight=1)
        self.textbox_frame.grid_columnconfigure(0, weight=1)

        self.textbox = customtkinter.CTkTextbox(self.textbox_frame, wrap="none", font=("Consolas", 13)) # Font monospace agar rapi
        self.textbox.grid(row=0, column=0, sticky="nsew")
        
        # Konfigurasi tag warna (tanpa mengubah font per tag)
        self.textbox.tag_config("green", foreground="#66BB6A") # Hijau lebih lembut
        self.textbox.tag_config("blue", foreground="#42A5F5")  # Biru lebih lembut
        self.textbox.tag_config("purple", foreground="#AB47BC")# Ungu lebih lembut
        self.textbox.tag_config("gold", foreground="#FFA726")  # Oranye/Emas
        self.textbox.tag_config("header", foreground=customtkinter.ThemeManager.theme["CTkLabel"]["text_color"], font=("Consolas", 14, "bold"))
        self.textbox.tag_config("category_title", foreground=customtkinter.ThemeManager.theme["CTkLabel"]["text_color"], font=("Consolas", 13, "underline"))
        
        self.textbox.configure(state="disabled")

        # Status label di bawah
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
        if hasattr(self, 'textbox'): # Pastikan textbox sudah ada
            self.textbox.configure(state="normal")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", "Tekan 'SCAN / UPDATE LANTAI' untuk memulai.\nPastikan Anda berada di dalam dungeon.")
            self.textbox.configure(state="disabled")
        
        # Muat ulang terjemahan jika diperlukan (opsional, tergantung apakah TRANSLATIONS bisa berubah runtime)
        # from scanner import load_translations # Jika ingin memastikan TRANSLATIONS selalu fresh
        # load_translations()
        # self.current_translations = scanner.TRANSLATIONS.copy()
        
        # Cukup panggil update_display jika TRANSLATIONS tidak berubah
        self.update_display_content()


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
        self.status_label.configure(text=f"Status: Path disimpan -> {self.entry_path.get()}")
        
    def load_path(self):
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            if path := config.get('Settings', 'ao-dir', fallback=None):
                self.entry_path.insert(0, path)
                self.status_label.configure(text="Status: Path dimuat. Siap memindai.")
        from scanner import TRANSLATIONS # Cukup ambil dari global yang sudah di-load
        self.current_translations = TRANSLATIONS.copy()
        self.update_display_content() # Panggil update display setelah path dimuat
        
    def scan_dungeon_thread(self):
        import threading
        self.button_scan.configure(state="disabled", text="MEMINDAI...")
        self.status_label.configure(text="Status: Sedang memindai lantai saat ini...")
        
        def run_scan_logic():
            try:
                from scanner import AlbionDungeonScanner # Impor scanner di sini
                # Pastikan TRANSLATIONS global sudah terisi dari scanner.load_translations()
                # Jika instance scanner mengubah TRANSLATIONS, kita perlu load ulang
                # Untuk saat ini, kita asumsikan TRANSLATIONS stabil setelah load awal
                scanner_instance = AlbionDungeonScanner(ao_dir_path=self.entry_path.get())
                current_results_from_scan = scanner_instance.run()
                
                # Tidak perlu load_translations() di sini jika tidak ada perubahan pada file database saat runtime
                # self.current_translations = scanner.TRANSLATIONS.copy() 
                
                self.after(0, self.merge_and_update_ui_post_scan, current_results_from_scan)
            except Exception as e:
                self.after(0, self.handle_scan_error, e)
        
        scan_thread = threading.Thread(target=run_scan_logic)
        scan_thread.daemon = True
        scan_thread.start()
        
    def merge_and_update_ui_post_scan(self, current_scan_results: dict | None):
        """Menggabungkan hasil scan ke data sesi dan memperbarui UI."""
        notification_title = "Scan Selesai"
        notification_message = "Tidak ada file dungeon aktif baru terdeteksi atau lantai sama."

        if current_scan_results:
            newly_scanned_files = set(current_scan_results.get("used_files", []))
            
            is_new_floor_detected = False
            # Logika deteksi lantai baru yang lebih baik:
            # Lantai baru jika ini scan pertama ATAU jika ada file baru yang belum pernah dipindai di sesi ini
            if not self.findings_by_floor or (newly_scanned_files and not newly_scanned_files.issubset(self.scanned_files_this_session)):
                is_new_floor_detected = True
                self.floor_count += 1
                self.scanned_files_this_session.update(newly_scanned_files)
                # Tambahkan struktur data baru untuk lantai ini
                self.findings_by_floor.append({
                    "event_bosses": Counter(), "dungeon_bosses": Counter(),
                    "chests": Counter(), "shrines": Counter(),
                    "mobs_by_tier": {}, "exits": set() # mobs_by_tier adalah dict of Counters
                })
                notification_message = f"Temuan baru di Lantai {self.floor_count} telah ditambahkan!"
            else:
                 notification_message = "Scan selesai. Data untuk lantai saat ini diperbarui (jika ada perubahan)."

            # Ambil data untuk lantai saat ini (yang terakhir ditambahkan atau lantai pertama)
            current_floor_storage = self.findings_by_floor[-1]

            # Gabungkan hasil scan ke lantai saat ini
            for key, counter_data in current_scan_results.items():
                if key in ["event_bosses", "dungeon_bosses", "chests", "shrines"]:
                    current_floor_storage[key].update(counter_data)
                elif key == "exits":
                    current_floor_storage[key].update(counter_data)
                elif key == "mobs_by_tier": # mobs_by_tier adalah dict of Counters
                    for tier, mobs_in_tier_counter in counter_data.items():
                        current_floor_storage["mobs_by_tier"].setdefault(tier, Counter()).update(mobs_in_tier_counter)
            
            self.status_label.configure(text=f"Status: Scan lantai {self.floor_count} selesai. Temuan digabungkan.")
        else:
            self.status_label.configure(text="Status: Scan selesai. Tidak ada file dungeon aktif.")
            
        self.update_display_content()
        self.button_scan.configure(state="normal", text="SCAN / UPDATE LANTAI")
        tkinter.messagebox.showinfo(notification_title, notification_message)

    def _format_single_category_lines(self, category_title: str, items_counter: Counter) -> list:
        """Helper untuk memformat satu kategori menjadi list of tuples (text, item_id_or_tagtype)."""
        lines = []
        if not items_counter: return lines
        
        lines.append((f"\n {category_title}", "category_title", None)) # Tag untuk judul kategori
        
        # Mengurutkan item agar tampilan konsisten
        # Ambil nama dari translations; jika tidak ada, gunakan item_id itu sendiri
        sorted_items = sorted(
            items_counter.items(),
            key=lambda item: self.current_translations.get(item[0], (item[0], "❓"))[0]
        )
        
        for item_id, count in sorted_items:
            entry = self.current_translations.get(item_id)
            icon, item_name_display = "❓", f"ID: {item_id}" # Default jika ID tidak ada di database
            if entry:
                item_name_display = entry[0]
                icon = entry[1] if len(entry) > 1 else "❓"
            
            # Format baris yang lebih rapi dengan padding dinamis sederhana
            line_text = f"  {icon} {item_name_display}"
            # Padding agar (x_count) rata kanan. Angka 60 adalah estimasi lebar.
            # Anda mungkin perlu menyesuaikannya berdasarkan font dan lebar rata-rata nama.
            padding = 55 - len(line_text) 
            if padding < 1 : padding = 1
            line_text += " " * padding + f"(x{count})"
            lines.append((line_text, "item", item_id))
        return lines

    def generate_report_data_for_display(self) -> list:
        """Menghasilkan list data yang akan ditampilkan, termasuk pemisah lantai."""
        display_lines_with_tags = [] # List of (text_line, tag_type, item_id_for_color)

        if not self.findings_by_floor:
            display_lines_with_tags.append(("\n- Belum ada temuan. Tekan SCAN saat di dalam dungeon.", "item", None))
            return display_lines_with_tags

        # --- LAPORAN PER LANTAI ---
        for i, floor_data_dict in enumerate(self.findings_by_floor):
            floor_num = i + 1
            display_lines_with_tags.append((f"\n═══════════ Lantai {floor_num} ═════════════", "header", None))
            
            display_lines_with_tags.extend(self._format_single_category_lines("[ Event Boss ]", floor_data_dict.get(TYPE_EVENT_BOSS, Counter())))
            display_lines_with_tags.extend(self._format_single_category_lines("[ Boss Dungeon ]", floor_data_dict.get(TYPE_DUNGEON_BOSS, Counter())))
            display_lines_with_tags.extend(self._format_single_category_lines("[ Peti ]", floor_data_dict.get(TYPE_CHEST, Counter())))
            display_lines_with_tags.extend(self._format_single_category_lines("[ Altar Buff ]", floor_data_dict.get(TYPE_SHRINE, Counter())))
            
            # Menampilkan Mob per Tier untuk lantai ini
            mobs_on_floor = floor_data_dict.get("mobs_by_tier", {})
            if any(mobs_on_floor.values()): # Cek apakah ada mob di tier manapun
                display_lines_with_tags.append(("\n [ Mob Biasa di Lantai Ini (Per Tier) ]", "category_title", None))
                total_mobs_on_floor = 0
                # Urutkan tier
                sorted_tiers = sorted(mobs_on_floor.keys(), key=lambda t: (t.startswith("T"), int(t[1:]) if t[1:].isdigit() else float('inf'), t))
                for tier in sorted_tiers:
                    if tier_counter := mobs_on_floor[tier]: # Jika ada mob di tier ini
                        tier_total_count = sum(tier_counter.values())
                        total_mobs_on_floor += tier_total_count
                        # Di sini kita hanya tampilkan jumlah, bukan detail setiap mob per tier di per-lantai
                        display_lines_with_tags.append((f"   - Spawn Point Mob {tier}: {tier_total_count}", "item", None))
                display_lines_with_tags.append((f"   👾 Total Mob Biasa di Lantai Ini: {total_mobs_on_floor}", "item", None))


        # --- LAPORAN KUMULATIF TOTAL ---
        display_lines_with_tags.append(("\n\n\n══════ Laporan Kumulatif Total Sesi ══════", "header", None))
        
        total_cumulative_findings = {
            TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(),
            TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(), "exits": set()
        }
        total_mobs_by_tier_cumulative = {}

        for floor_data_dict in self.findings_by_floor:
            for category, data in floor_data_dict.items():
                if category in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                    total_cumulative_findings[category].update(data)
                elif category == "exits":
                    total_cumulative_findings["exits"].update(data)
                elif category == "mobs_by_tier":
                    for tier, mobs_in_tier_counter in data.items():
                        total_mobs_by_tier_cumulative.setdefault(tier, Counter()).update(mobs_in_tier_counter)
        
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Event Boss ]", total_cumulative_findings[TYPE_EVENT_BOSS]))
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Boss Dungeon ]", total_cumulative_findings[TYPE_DUNGEON_BOSS]))
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Peti ]", total_cumulative_findings[TYPE_CHEST]))
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Altar Buff ]", total_cumulative_findings[TYPE_SHRINE]))

        # Menampilkan Total Mob Kumulatif per Tier
        if any(total_mobs_by_tier_cumulative.values()):
            display_lines_with_tags.append(("\n [ Total Mob Biasa Sesi Ini (Per Tier) ]", "category_title", None))
            grand_total_mobs = 0
            sorted_tiers_total = sorted(total_mobs_by_tier_cumulative.keys(), key=lambda t: (t.startswith("T"), int(t[1:]) if t[1:].isdigit() else float('inf'), t))
            for tier in sorted_tiers_total:
                 if tier_counter := total_mobs_by_tier_cumulative[tier]:
                    tier_total_count = sum(tier_counter.values())
                    grand_total_mobs += tier_total_count
                    display_lines_with_tags.append((f"   - Spawn Point Mob {tier}: {tier_total_count}", "item", None))
            display_lines_with_tags.append((f"   👾 Total Semua Spawn Point Mob Biasa Sesi Ini: {grand_total_mobs}", "item", None))


        # --- Status Pintu Keluar (dari lantai terakhir yang dipindai) ---
        display_lines_with_tags.append(("\n" + "="*57, "item", None)) # Pemisah
        last_floor_exits = self.findings_by_floor[-1].get("exits", set()) if self.findings_by_floor else set()
        has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
        floor_status_text = "Ada Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
        display_lines_with_tags.append((f" 🚪 Status Lantai Saat Ini ({self.floor_count}): {floor_status_text}", "item", None))
        
        return display_lines_with_tags

    def update_display_content(self):
        """Memperbarui konten textbox dengan data yang diformat."""
        # Cegah error jika textbox belum siap sepenuhnya
        if not hasattr(self, 'textbox') or self.textbox is None:
            return

        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        
        # Jika belum ada scan, tampilkan pesan awal
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
            elif line_tag_type == "item" and item_id_for_color: # Ini adalah item_id
                color_tag_name = COLOR_ID_MAP.get(item_id_for_color)
                if color_tag_name:
                    tags_to_apply.append(color_tag_name)
            
            self.textbox.insert("end", text_line + "\n", tuple(tags_to_apply) if tags_to_apply else None)
            
        self.textbox.configure(state="disabled")

    def handle_scan_error(self, error_obj: Exception):
        """Menangani error yang terjadi selama proses scan."""
        error_message = f"TERJADI ERROR SAAT SCAN:\n\n{type(error_obj).__name__}: {error_obj}"
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", error_message)
        self.textbox.configure(state="disabled")
        self.button_scan.configure(state="normal", text="SCAN / UPDATE LANTAI")
        self.status_label.configure(text="Status: Error saat scan. Periksa path & coba lagi.")
        tkinter.messagebox.showerror("Error Scan", f"Terjadi kesalahan:\n{error_obj}")

# Blok utama untuk menjalankan aplikasi
if __name__ == "__main__":
    # Pastikan TRANSLATIONS dimuat sebelum App dibuat jika App bergantung padanya saat init
    # Namun, load_path() di __init__ App akan memuatnya.
    app = App()
    app.mainloop()