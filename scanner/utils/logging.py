import logging
import sys

from scanner.utils.singleton import Singleton


class LoggingManager(object, metaclass=Singleton):
    """
    Sebuah manajer singleton untuk mengkonfigurasi dan menyediakan logger untuk aplikasi.
    """

    def __init__(self):
        """
        Menginisialisasi root logger dengan pengaturan default.
        """
        self.root_logger = logging.getLogger()
        # Set level default ke INFO
        self.root_logger.setLevel(logging.INFO)

        # Buat formatter hanya sekali
        formatter = logging.Formatter(
            "{asctime} - {levelname:>5.5} - {name:^20.20} - {message}", style="{"
        )

        # Hanya tambahkan handler jika belum ada, untuk mencegah duplikasi
        if not self.root_logger.handlers:
            # Handler untuk menampilkan log di konsol
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            self.root_logger.addHandler(stream_handler)

            # Handler untuk menyimpan log ke file
            file_handler = logging.FileHandler("dungeon_scanner.log", mode='w') # mode 'w' untuk overwrite log setiap kali jalan
            file_handler.setFormatter(formatter)
            self.root_logger.addHandler(file_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """
        Mengambil instance logger dengan nama yang spesifik.

        Args:
            name (str): Nama logger (biasanya __name__ dari modul pemanggil).

        Returns:
            logging.Logger: Instance logger yang dikonfigurasi.
        """
        return logging.getLogger(name)


# Buat satu instance dari manager untuk digunakan di seluruh aplikasi
logging_manager = LoggingManager()