import logging
import sys

# Tentukan format log
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s"
# Tentukan level log default (misalnya, INFO atau DEBUG)
# DEBUG akan menampilkan semua pesan (DEBUG, INFO, WARNING, ERROR, CRITICAL)
# INFO hanya akan menampilkan INFO, WARNING, ERROR, CRITICAL
DEFAULT_LOG_LEVEL = logging.DEBUG # Ubah ke logging.INFO untuk produksi

# Buat logger utama untuk aplikasi Anda
# Anda bisa menggunakan nama modul (__name__) atau nama kustom.
# Menggunakan nama kustom seperti 'albion_scanner' bisa berguna jika Anda ingin
# mengkonfigurasi logger ini secara terpisah dari logger library lain.
logger = logging.getLogger("albion_scanner")
logger.setLevel(DEFAULT_LOG_LEVEL)

# Cegah duplikasi handler jika skrip ini diimpor berkali-kali atau logger sudah ada handler
# Ini penting agar pesan log tidak muncul berkali-kali di konsol.
if not logger.handlers:
    # Buat console handler dan set levelnya
    console_handler = logging.StreamHandler(sys.stdout) # Menggunakan sys.stdout untuk output yang lebih konsisten
    console_handler.setLevel(DEFAULT_LOG_LEVEL)

    # Buat formatter dan tambahkan ke handler
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)

    # Tambahkan handler ke logger
    logger.addHandler(console_handler)

    # (Opsional) Tambahkan file handler jika Anda ingin log ke file
    # try:
    #     # Pastikan direktori logs ada jika Anda ingin membuat file di dalamnya
    #     # import os
    #     # if not os.path.exists("logs"):
    #     #     os.makedirs("logs")
    #     # file_handler = logging.FileHandler("logs/scanner.log", mode='a', encoding='utf-8')
    #     file_handler = logging.FileHandler("scanner.log", mode='a', encoding='utf-8') # Menyimpan di direktori yang sama
    #     file_handler.setLevel(DEFAULT_LOG_LEVEL)
    #     file_handler.setFormatter(formatter)
    #     logger.addHandler(file_handler)
    #     # logger.info("File logger handler ditambahkan ke scanner.log") # Hindari log saat setup awal
    # except Exception as e:
    #     # Hindari menggunakan logger di sini jika logger itu sendiri gagal di-setup
    #     print(f"[ERROR_LOGGING_SETUP] Gagal membuat file logger handler: {e}", file=sys.stderr)

# Contoh penggunaan (bisa dihapus jika tidak perlu diuji di sini):
# if __name__ == '__main__':
#     logger.debug("Ini adalah pesan debug dari logging.py.")
#     logger.info("Ini adalah pesan info dari logging.py.")
#     logger.warning("Ini adalah pesan peringatan dari logging.py.")
#     logger.error("Ini adalah pesan error dari logging.py.")
#     logger.critical("Ini adalah pesan kritikal dari logging.py.")

