import scapy.all as scapy

# ================== PENTING ==================
# Ganti string di bawah ini dengan nama antarmuka yang Anda gunakan untuk bermain.
# Pilih salah satu dari dua opsi di bawah ini. Hapus yang tidak dipakai.

# Opsi 1: Jika menggunakan USB Tethering
INTERFACE_NAME = "Remote NDIS Compatible Device"

# Opsi 2: Jika menggunakan Kabel Ethernet
# INTERFACE_NAME = "Intel(R) Ethernet Connection (14) I219-V"

# Pastikan hanya ada satu baris INTERFACE_NAME yang aktif (tidak ada tanda # di depannya)
# =============================================

print(f"[*] Memulai tes sniffing pada antarmuka: '{INTERFACE_NAME}'")
print("[*] Menunggu paket UDP di port 5056 selama 20 detik...")

try:
    # Kita hanya mencoba menangkap SATU paket saja
    packet = scapy.sniff(
        iface=INTERFACE_NAME,
        filter="udp and port 5056",
        count=1,
        timeout=20  # Akan berhenti setelah 20 detik jika tidak ada paket
    )

    if packet:
        print("\n[+] SUKSES! Paket berhasil ditangkap.")
        print("="*40)
        print(packet[0].summary())
        print("="*40)
    else:
        print("\n[-] GAGAL! Tidak ada paket yang tertangkap setelah 20 detik.")
        print("[!] Ini mengkonfirmasi ada masalah pada Scapy/Npcap di lingkungan ini.")

except Exception as e:
    print(f"\n[X] Terjadi error saat sniffing: {e}")