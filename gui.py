# file: gui.py

import tkinter
import tkinter.filedialog
import tkinter.messagebox
import customtkinter
import configparser
import os
from collections import Counter
import threading # Untuk menjalankan pengiriman webhook di thread terpisah
import requests # Untuk mengirim HTTP request ke webhook
import json # Untuk memformat payload JSON

# Impor tipe dari scanner untuk konsistensi
from scanner import TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE 

customtkinter.set_appearance_mode("System") # Atau "Light", "Dark"
customtkinter.set_default_color_theme("blue") # Atau "green", "dark-blue"

CONFIG_FILE = "config.ini"

# Peta warna untuk teks di laporan GUI (bisa disesuaikan)
COLOR_ID_MAP = {
    "LOOTCHEST_STANDARD": "green", "BOOKCHEST_STANDARD": "green",
    "LOOTCHEST_UNCOMMON": "green", "BOOKCHEST_UNCOMMON": "green",
    "LOOTCHEST_RARE": "blue", "BOOKCHEST_RARE": "blue",
    "LOOTCHEST_EPIC": "purple",
    "LOOTCHEST_LEGENDARY": "gold",
    "LOOTCHEST_BOSS": "gold", # Peti dari bos utama
    "LOOTCHEST_MINIBOSS": "purple", # Peti dari miniboss
    "BOSS_MINIBOSS_GENERIC": "purple",
    "BOSS_ENDBOSS_GENERIC": "gold",
    "BOSS_HIGHLIGHT_GENERIC": "gold",
    "BOSS_GENERIC": "gold",
    "UNCLEFROST": "blue", 
    "ANNIVERSARY_TITAN": "gold",
    "SHRINE_NON_COMBAT_BUFF": "blue",
}

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Albion Dungeon Scanner")
        self.geometry(f"{850}x750") 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Baris untuk textbox dibuat expandable
        
        # --- Atribut untuk Webhook ---
        self.webhook_url = None
        
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

        # Frame untuk tombol Scan dan Reset
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

        # Atur font dasar untuk seluruh CTkTextbox di sini
        self.textbox = customtkinter.CTkTextbox(self.textbox_frame, wrap="none", font=("Consolas", 13))
        self.textbox.grid(row=0, column=0, sticky="nsew")
        
        # --- PERBAIKAN UNTUK WARNA TAG ---
        # Dapatkan warna teks label yang sesuai dengan mode tampilan saat ini
        # customtkinter.ThemeManager.theme["CTkLabel"]["text_color"] adalah tuple: (dark_mode_color, light_mode_color)
        label_text_colors = customtkinter.ThemeManager.theme["CTkLabel"]["text_color"]
        current_label_text_color = ""
        if customtkinter.get_appearance_mode().lower() == "dark":
            current_label_text_color = label_text_colors[0] # Warna untuk mode gelap
        else:
            current_label_text_color = label_text_colors[1] # Warna untuk mode terang

        self.textbox.tag_config("green", foreground="#66BB6A") 
        self.textbox.tag_config("blue", foreground="#42A5F5")  
        self.textbox.tag_config("purple", foreground="#AB47BC")
        self.textbox.tag_config("gold", foreground="#FFA726")  
        self.textbox.tag_config("header", foreground=current_label_text_color) 
        self.textbox.tag_config("category_title", foreground=current_label_text_color, underline=True)
        # --- AKHIR PERBAIKAN ---
        
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
        # Baca dulu config yang ada untuk mempertahankan bagian lain jika ada
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
        
        if not config.has_section('Settings'):
            config.add_section('Settings')
        config.set('Settings', 'ao-dir', self.entry_path.get())
        
        # Pastikan bagian Discord ada saat menyimpan, meskipun URLnya mungkin belum diisi
        if not config.has_section('Discord'):
            config.add_section('Discord')
            if not config.has_option('Discord', 'webhook_url'):
                 config.set('Discord', 'webhook_url', "MASUKKAN_URL_WEBHOOK_ANDA_DI_SINI")
        
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
            
            # Memuat URL Webhook
            self.webhook_url = config.get('Discord', 'webhook_url', fallback=None)
            if not self.webhook_url or "MASUKKAN_URL_WEBHOOK" in self.webhook_url.upper(): # Cek placeholder
                self.webhook_url = None 
                print("PERINGATAN: Discord webhook_url belum diatur dengan benar di config.ini")
        else:
            self.status_label.configure(text=f"Status: {CONFIG_FILE} tidak ditemukan. Atur path.")

        # Muat terjemahan dari scanner
        from scanner import TRANSLATIONS, load_translations
        if not TRANSLATIONS: # Jika belum dimuat oleh scanner
            load_translations()
        self.current_translations = TRANSLATIONS.copy()
        self.update_display_content() 
        
    def scan_dungeon_thread(self):
        # Menggunakan lambda untuk memastikan UI update berjalan di main thread via self.after
        self.button_scan.configure(state="disabled", text="MEMINDAI...")
        self.status_label.configure(text="Status: Sedang memindai lantai saat ini...")
        
        # Jalankan logika scan di thread terpisah agar GUI tidak freeze
        scan_thread = threading.Thread(target=self._scan_logic_worker)
        scan_thread.daemon = True # Thread akan berhenti jika aplikasi utama ditutup
        scan_thread.start()
        
    def _scan_logic_worker(self):
        """Wrapper untuk logika scan yang berjalan di thread terpisah."""
        try:
            from scanner import AlbionDungeonScanner # Impor di sini untuk thread-safety atau reload
            
            # Pastikan path valid sebelum membuat instance scanner
            ao_path = self.entry_path.get()
            if not ao_path or not os.path.isdir(ao_path):
                raise ValueError("Path Albion Online tidak valid atau belum diatur.")

            scanner_instance = AlbionDungeonScanner(ao_dir_path=ao_path)
            current_results_from_scan = scanner_instance.run()
            
            # Kirim hasil ke main thread untuk update UI
            self.after(0, self.merge_and_update_ui_post_scan, current_results_from_scan)
        except Exception as e:
            # Kirim error ke main thread untuk ditampilkan
            self.after(0, self.handle_scan_error, e)

    def merge_and_update_ui_post_scan(self, current_scan_results: dict | None):
        """Menggabungkan hasil scan ke data sesi dan memperbarui UI."""
        notification_title = "Scan Selesai"
        notification_message = "Tidak ada file dungeon aktif baru terdeteksi atau lantai sama."

        if current_scan_results:
            newly_scanned_files = set(current_scan_results.get("used_files", []))
            
            is_new_floor_detected = False
            if not self.findings_by_floor or \
               (newly_scanned_files and not newly_scanned_files.issubset(self.scanned_files_this_session)):
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
                 notification_message = "Scan selesai. Data untuk lantai saat ini diperbarui (jika ada perubahan)."

            current_floor_storage = self.findings_by_floor[-1]

            # Menggabungkan data dari hasil scan ke penyimpanan sesi
            for key_type in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                if key_type in current_scan_results:
                    current_floor_storage[key_type].update(current_scan_results[key_type])
            
            if "exits" in current_scan_results:
                current_floor_storage["exits"].update(current_scan_results["exits"])

            if "mobs_by_tier" in current_scan_results:
                for tier, mobs_in_tier_counter in current_scan_results["mobs_by_tier"].items():
                    current_floor_storage["mobs_by_tier"].setdefault(tier, Counter()).update(mobs_in_tier_counter)
            
            # Kirim ke Discord jika lantai baru dan ada URL webhook
            if is_new_floor_detected and self.webhook_url:
                discord_message = self._format_for_discord(current_floor_storage, self.floor_count)
                # Jalankan pengiriman di thread terpisah agar tidak memblokir UI
                threading.Thread(target=self._send_to_discord, args=(discord_message,), daemon=True).start()
            
            self.status_label.configure(text=f"Status: Scan lantai {self.floor_count} selesai.")
        else:
            self.status_label.configure(text="Status: Scan selesai. Tidak ada file dungeon aktif.")
            
        self.update_display_content()
        self.button_scan.configure(state="normal", text="SCAN / UPDATE LANTAI")
        if current_scan_results or is_new_floor_detected : # Hanya tampilkan popup jika ada sesuatu yang baru/berubah
            tkinter.messagebox.showinfo(notification_title, notification_message)

    def _get_chest_color_name(self, item_id: str) -> str:
        """Mendapatkan nama warna peti berdasarkan ID untuk laporan Discord."""
        upper_id = item_id.upper() # Konversi ke huruf besar untuk pencocokan case-insensitive
        # Urutan penting: dari yang paling spesifik/langka ke umum
        if "LEGENDARY" in upper_id: return " (gold)"
        if "EPIC" in upper_id: return " (purple)"
        if "RARE" in upper_id: return " (blue)"
        # Standard dan Uncommon bisa dianggap hijau atau sesuai preferensi
        if "UNCOMMON" in upper_id : return " (green)"
        if "STANDARD" in upper_id: return " (green)" # Atau "" jika tidak ingin warna untuk standar
        return "" # Default jika tidak ada kata kunci rarity

    def _format_for_discord(self, floor_data: dict, floor_num: int) -> str:
        """Memformat data dari satu lantai untuk pesan Discord, mirip contoh."""
        lines = [f"**FLOOR {floor_num}**"]
        
        # Gabungkan semua jenis bos
        all_bosses = floor_data.get(TYPE_DUNGEON_BOSS, Counter()) + floor_data.get(TYPE_EVENT_BOSS, Counter())
        all_chests = floor_data.get(TYPE_CHEST, Counter())

        for item_id, count in all_bosses.items():
            # Ambil nama dari database terjemahan, atau gunakan ID yang diformat jika tidak ada
            display_name = self.current_translations.get(item_id, (item_id.replace("_", " ").title(), "❓"))[0]
            lines.append(f"boss: {display_name}" + (f" (x{count})" if count > 1 else ""))
        
        for item_id, count in all_chests.items():
            display_name = self.current_translations.get(item_id, (item_id.replace("_", " ").title(), "❓"))[0]
            color_str = self._get_chest_color_name(item_id)
            lines.append(f"chest: {display_name}{color_str}" + (f" (x{count})" if count > 1 else ""))

        # Hitung total mob dari semua tier yang dilaporkan
        total_mobs = 0
        if "mobs_by_tier" in floor_data:
            for tier_counter in floor_data["mobs_by_tier"].values():
                total_mobs += sum(tier_counter.values())
        
        if total_mobs > 0:
            lines.append(f"mobs: {total_mobs}")
            
        return "\n".join(lines)

    def _send_to_discord(self, message: str):
        """Mengirim pesan ke URL webhook Discord."""
        if not self.webhook_url:
            print("PERINGATAN: URL Webhook Discord tidak diatur. Pesan tidak dikirim.")
            return 
        
        # Hanya kirim jika pesan memiliki konten selain header lantai
        if len(message.splitlines()) <= 1 and "**FLOOR" in message : # Cek jika hanya header lantai
            print("Pesan Discord tidak dikirim (hanya berisi header lantai atau kosong).")
            return
        if not message.strip():
            print("Pesan Discord tidak dikirim (konten kosong).")
            return

        headers = {"Content-Type": "application/json"}
        payload = {"content": message}
        
        try:
            response = requests.post(self.webhook_url, data=json.dumps(payload), headers=headers, timeout=10) # Timeout 10 detik
            if response.status_code >= 400: # Error dari Discord
                print(f"Error mengirim ke Discord (Status {response.status_code}): {response.text}")
        except requests.RequestException as e: # Error jaringan, timeout, dll.
            print(f"Gagal mengirim pesan ke Discord: {e}")

    def _format_single_category_lines(self, category_title: str, items_counter: Counter) -> list:
        """Helper untuk memformat satu kategori menjadi list of tuples (text, item_id_or_tagtype)."""
        lines = []
        if not items_counter: return lines
        
        lines.append((f"\n {category_title}", "category_title", None))
        
        sorted_items = sorted(
            items_counter.items(),
            key=lambda item: self.current_translations.get(item[0], (item[0], "❓"))[0]
        )
        
        for item_id, count in sorted_items:
            entry = self.current_translations.get(item_id)
            icon, item_name_display = "❓", f"ID: {item_id}" 
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
        """Menghasilkan list data yang akan ditampilkan, termasuk pemisah lantai."""
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
            
            mobs_on_floor = floor_data_dict.get("mobs_by_tier", {})
            if any(mobs_on_floor.values()): 
                display_lines_with_tags.append(("\n [ Mob (T6+ atau Tidak Diketahui) di Lantai Ini ]", "category_title", None))
                total_mobs_on_floor = 0
                sorted_tiers = sorted(mobs_on_floor.keys(), key=lambda t: (t.startswith("T"), int(t[1:]) if t[1:].isdigit() else float('inf'), t))
                for tier in sorted_tiers:
                    if tier_counter := mobs_on_floor[tier]: 
                        tier_total_count = sum(tier_counter.values())
                        total_mobs_on_floor += tier_total_count
                        display_lines_with_tags.append((f"   - Spawn Point Mob {tier}: {tier_total_count}", "item", None))
                display_lines_with_tags.append((f"   👾 Total Mob (T6+/?) di Lantai Ini: {total_mobs_on_floor}", "item", None))

        display_lines_with_tags.append(("\n\n\n══════ Laporan Kumulatif Total Sesi ══════", "header", None))
        
        total_cumulative_findings = {
            TYPE_EVENT_BOSS: Counter(), TYPE_DUNGEON_BOSS: Counter(),
            TYPE_CHEST: Counter(), TYPE_SHRINE: Counter(), "exits": set()
        }
        total_mobs_by_tier_cumulative = {}

        for floor_data_dict_item in self.findings_by_floor:
            for category, data in floor_data_dict_item.items():
                if category in [TYPE_EVENT_BOSS, TYPE_DUNGEON_BOSS, TYPE_CHEST, TYPE_SHRINE]:
                    total_cumulative_findings[category].update(data)
                elif category == "exits":
                    total_cumulative_findings["exits"].update(data)
                elif category == "mobs_by_tier":
                    for tier, mobs_in_tier_counter_item in data.items():
                        total_mobs_by_tier_cumulative.setdefault(tier, Counter()).update(mobs_in_tier_counter_item)
        
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Event Boss ]", total_cumulative_findings[TYPE_EVENT_BOSS]))
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Boss Dungeon ]", total_cumulative_findings[TYPE_DUNGEON_BOSS]))
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Peti ]", total_cumulative_findings[TYPE_CHEST]))
        display_lines_with_tags.extend(self._format_single_category_lines("[ Total Altar Buff ]", total_cumulative_findings[TYPE_SHRINE]))

        if any(total_mobs_by_tier_cumulative.values()):
            display_lines_with_tags.append(("\n [ Total Mob Sesi Ini (T6+ atau Tidak Diketahui) ]", "category_title", None))
            grand_total_mobs = 0
            sorted_tiers_total = sorted(total_mobs_by_tier_cumulative.keys(), key=lambda t: (t.startswith("T"), int(t[1:]) if t[1:].isdigit() else float('inf'), t))
            for tier_item in sorted_tiers_total:
                 if tier_counter_item := total_mobs_by_tier_cumulative[tier_item]:
                    tier_total_count_item = sum(tier_counter_item.values())
                    grand_total_mobs += tier_total_count_item
                    display_lines_with_tags.append((f"   - Spawn Point Mob {tier_item}: {tier_total_count_item}", "item", None))
            display_lines_with_tags.append((f"   👾 Total Mob (T6+/?) Sesi Ini: {grand_total_mobs}", "item", None))

        display_lines_with_tags.append(("\n" + "="*57, "item", None)) 
        last_floor_exits = self.findings_by_floor[-1].get("exits", set()) if self.findings_by_floor else set()
        has_next_floor_exit = any("EXIT" in e and "ENTER" not in e for e in last_floor_exits)
        floor_status_text = "Ada Pintu Keluar ke Lantai Berikut" if has_next_floor_exit else "Lantai Terakhir atau Hanya Pintu Masuk"
        display_lines_with_tags.append((f" 🚪 Lantai Saat Ini: {self.floor_count} dari ? | Status: {floor_status_text}", "item", None))
        
        return display_lines_with_tags

    def update_display_content(self):
        if not hasattr(self, 'textbox') or self.textbox is None:
            return

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
                # Coba dapatkan warna dari ID rarity di akhir ID item (misal LOOTCHEST_RARE)
                color_tag_name = None
                if "_" in item_id_for_color:
                    rarity_part = item_id_for_color.upper().split("_")[-1]
                    # Cek jika rarity_part adalah salah satu kunci warna (STANDARD, UNCOMMON, RARE, EPIC, LEGENDARY)
                    if f"LOOTCHEST_{rarity_part}" in COLOR_ID_MAP: # Cek dengan prefix LOOTCHEST
                         color_tag_name = COLOR_ID_MAP[f"LOOTCHEST_{rarity_part}"]
                    elif f"BOOKCHEST_{rarity_part}" in COLOR_ID_MAP: # Cek dengan prefix BOOKCHEST
                         color_tag_name = COLOR_ID_MAP[f"BOOKCHEST_{rarity_part}"]

                if not color_tag_name: # Fallback jika tidak ada rarity part atau tidak ada di map
                    color_tag_name = COLOR_ID_MAP.get(item_id_for_color) # Cek ID lengkap
                
                if color_tag_name:
                    tags_to_apply.append(color_tag_name)
            
            self.textbox.insert("end", text_line + "\n", tuple(tags_to_apply) if tags_to_apply else None)
            
        self.textbox.configure(state="disabled")
        self.textbox.see("1.0") # Scroll ke atas setiap update

    def handle_scan_error(self, error_obj: Exception):
        """Menangani error yang terjadi selama proses scan."""
        error_message = f"TERJADI ERROR SAAT SCAN:\n\n{type(error_obj).__name__}: {error_obj}\n\nPastikan path Albion Online di config.ini sudah benar dan game sedang berjalan."
        # Tampilkan di textbox
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", error_message)
        self.textbox.configure(state="disabled")
        # Reset tombol dan status
        self.button_scan.configure(state="normal", text="SCAN / UPDATE LANTAI")
        self.status_label.configure(text="Status: Error saat scan. Periksa path & coba lagi.")
        # Tampilkan juga di messagebox
        tkinter.messagebox.showerror("Error Scan", f"Terjadi kesalahan:\n{error_obj}\n\nPastikan path Albion Online sudah benar dan Anda berada di dalam game.")

# Blok utama untuk menjalankan aplikasi
if __name__ == "__main__":
    # Pastikan TRANSLATIONS dimuat sebelum App dibuat jika App bergantung padanya saat init
    from scanner import load_translations # Impor fungsi load_translations
    load_translations() # Panggil untuk memastikan TRANSLATIONS terisi
    
    app = App()
    app.mainloop()
