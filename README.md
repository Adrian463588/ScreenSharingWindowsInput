# ScreenSharingWindowsInput (TabSign)

[![Version](https://img.shields.io/badge/Version-v1.2.0-brightgreen.svg)](https://github.com/Adrian463588/ScreenSharingWindowsInput/releases/tag/v1.2.0)
[![Python 3.12](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets%20Binary-yellow.svg)](https://websockets.readthedocs.io/)
[![scrcpy](https://img.shields.io/badge/Mirroring-scrcpy%20v5.0-orange.svg)](https://github.com/Genymobile/scrcpy)
[![Win32 API](https://img.shields.io/badge/Input-Win32%20SendInput-informational.svg)](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
[![DevSecOps](https://img.shields.io/badge/Security-DevSecOps%20Compliant-success.svg)](#devsecops--keamanan)

Aplikasi *bidirectional screen sharing* dan *input mirroring* berlatensi sangat rendah antara PC Windows dan perangkat Android (HP & Tablet seperti Samsung Galaxy Tab S7 dengan S-Pen) secara *real-time*.

Dirancang khusus untuk dua mode utama:
1. **Windows ➔ Tablet:** Menandatangani dokumen web (DocuSign, Privy, Adobe Sign, form web, PDF) langsung menggunakan stylus S-Pen pada tablet.
2. **Android ➔ Windows:** Menampilkan layar HP/Tablet Android secara langsung di Windows dengan kontrol mouse & keyboard latensi rendah via engine `scrcpy` otomatis.

---

## 📌 Ringkasan Masalah & Solusi (*Overview*)

### Masalah
Saat membuka dokumen resmi yang membutuhkan tanda tangan digital di peramban PC (Google Chrome, Microsoft Edge, dll.), menandatangani menggunakan mouse seringkali kaku dan tidak rapi. Sebaliknya, saat presentasi atau pengujian aplikasi mobile, pengguna sering membutuhkan tampilan layar HP Android langsung di layar besar Windows dengan performa 60 FPS tanpa konfigurasi rumit.

### Solusi
**ScreenSharingWindowsInput** menyediakan solusi dua arah (*bidirectional*):
* **Mode Tanda Tangan:** Mentransmisikan layar Windows ke tablet Android via browser secara instan. Input S-Pen dan jari diterjemahkan dengan API resmi `SendInput`.
* **Mode Mirroring Android:** Mengintegrasikan engine `scrcpy` dengan deteksi otomatis. Jika sistem atau lingkungan ADB belum memiliki `scrcpy`, sistem akan **mengunduh dan memasangnya secara otomatis**.

---

## 🚀 Fitur Unggulan

1. **Zero-Install di Tablet (Web-Based Client):**
   * Tidak perlu mengompilasi APK atau sideloading ke tablet.
   * Cukup scan QR code dari kamera tablet dan buka di peramban bawaan (*Samsung Internet* atau *Google Chrome*).
2. **0ms Instant Local Ink Overlay:**
   * Goresan tanda tangan langsung muncul seketika di layar tablet saat stylus menyentuh kanvas tanpa menunggu jeda jaringan (*round-trip*), lalu disinkronkan mulus dengan tampilan PC.
3. **Smart Touch & S-Pen Distinction (Palm Rejection Cerdas):**
   * **S-Pen (`pointerType === 'pen'`):** Didedikasikan untuk menggambar tanda tangan presisi tinggi dengan sensitivitas tekanan.
   * **Sentuhan Tangan (`pointerType === 'touch'`):** Dikenali otomatis untuk klik menu, taskbar, navigasi, dan tombol web tanpa memicu goresan liar.
4. **Click Deadzone Jitter Filter (7 Pixel):**
   * Mengeliminasi getaran mikro jari saat mengetuk layar. Ketukan berdurasi $< 400\text{ms}$ dengan pergeseran $< 7\text{ px}$ dieksekusi sebagai **klik murni** atomik.
   * Memastikan klik pada ikon Taskbar Windows, menu Start, dan tombol web interaktif (seperti tombol *Expand* atau *Hapus*) merespons 100% sempurna.
5. **Two-Finger Scroll (Gulir Alami 2 Jari):**
   * Gulir dokumen web ke atas dan ke bawah secara langsung dengan mengusap 2 jari di layar tablet tanpa harus beralih mode.
6. **Fokus Kotak Tanda Tangan (ROI Zoom):**
   * Fitur pembesar selektif untuk memperbesar kotak tanda tangan kecil di website hingga memenuhi seluruh layar 11 inci tablet Samsung Tab S7.
7. **Host Management Dashboard:**
   * Dashboard kontrol lokal di PC (`http://localhost:8000/host`) untuk memilih target jendela (misal: Google Chrome), mengatur FPS (15–60 FPS), dan mengatur kualitas kompresi JPEG.
8. **Injeksi Input Tingkat Kernel Windows:**
   * Menggunakan Win32 API `SendInput` resmi dengan koordinat absolut ternormalisasi ($0 - 65535$) dan pengikatan stasiun desktop interaktif (`WinSta0\Default`).
9. **📱 ➔ 🖥️ Mirror Layar Android ke Windows (scrcpy Auto-Installer):**
   * Menampilkan layar HP/Tablet Android secara langsung di Windows dengan latensi sangat rendah (<35ms).
   * **Auto-Download:** Jika `scrcpy` belum terdeteksi di Windows atau ADB, sistem akan mengunduh dan mengekstrak rilis resmi secara otomatis tanpa intervensi manual.
   * Mendukung pemilihan perangkat ADB secara dinamis (USB maupun Wi-Fi ADB).

---

## 🛠️ Tech Stack & Tools yang Digunakan

| Komponen | Teknologi / Library | Deskripsi Peran |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.12, FastAPI, Uvicorn | Server HTTP asinkron, REST API, dan orchestrator koneksi |
| **Streaming Engine** | WebSockets Binary ArrayBuffer | Penyaluran frame JPEG layar PC ke tablet dengan latensi 15–30ms |
| **Screen Capture** | `mss`, Pillow, Win32 GDI | Penangkapan frame layar & jendela dengan binding `WinSta0\Default` |
| **Input Injection** | Win32 API (`ctypes.windll.user32`) | Eksekusi `SendInput`, `SetCursorPos`, mouse drag, click, & scroll |
| **Frontend / Client** | HTML5 Canvas, W3C Pointer Events, CSS3 | Antarmuka ganda (*dual-buffer*), gesture tracking, & glassmorphism |
| **Discovery & Pairing** | `psutil`, `socket`, `qrcode` | Deteksi otomatis IP LAN/Wi-Fi dan pembuat QR Code di terminal & web |
| **Hardware Link** | Android ADB Reverse Port Forwarding | Koneksi kabel USB tanpa jitter jaringan (alternatif Wi-Fi LAN) |
| **Testing & Quality** | `pytest`, `starlette.testclient` | Pengujian unit capture, mapping koordinat, dan endpoint API |

---

## 🏗️ Arsitektur Sistem

```
┌────────────────────────────────────────────────────────┐
│                   WINDOWS PC (Host)                    │
│                                                        │
│  [Dokumen Web di Google Chrome / Edge]                 │
│          ▲                                             │
│          │ user32.SendInput (Atomic Click, Drag, Pen)  │
│  [InputInjector Engine (WinSta0\Default)]              │
│          ▲                                             │
│          │ Koordinat Normalisasi (X, Y, Event, Button) │
│  [FastAPI & Async WebSocket Server (Port 8000)]        │
│          │                                             │
│          │ Binary Stream Frame (30-60 FPS JPEG)        │
│  [ScreenCapturer (mss Desktop Duplication)]            │
└──────────┼─────────────────────────────────────────────┘
           │ Koneksi: USB (ADB Reverse) atau Wi-Fi Lokal
           │ URL: http://localhost:8000 atau http://192.168.x.x:8000
           ▼
┌────────────────────────────────────────────────────────┐
│             SAMSUNG GALAXY TAB S7 (Client)             │
│                                                        │
│  Browser: Samsung Internet / Google Chrome             │
│  - Layer 1: Screen Canvas (Display Stream PC)          │
│  - Layer 2: Ink Canvas (0ms Real-time Stroke Preview)  │
│  - Input Filter: Deadzone 7px (Click vs Drag)          │
│  - Gesture Engine: S-Pen Draw, 1-Tap Click, 2-Finger   │
│  - ROI Zoom Engine: Bounding Box Magnifier             │
│  - Quick Toolbar: Hapus, Undo (Ctrl+Z), Fullscreen     │
└────────────────────────────────────────────────────────┘
```

---

## 📋 Prasyarat (*Prerequisites*)

1. **PC Host:**
   * Sistem Operasi: Windows 10 atau Windows 11 (64-bit).
   * Python 3.10 atau versi lebih baru.
   * Terhubung ke Wi-Fi yang sama dengan tablet ATAU terhubung via kabel USB dengan opsi *USB Debugging* aktif.
2. **Perangkat Tablet:**
   * Samsung Galaxy Tab S7 / S7+ / S8 / S9 atau tablet Android lainnya dengan stylus / layar sentuh.
   * Peramban: *Samsung Internet Browser* atau *Google Chrome*.

---

## 📖 Panduan Penggunaan Langkah demi Langkah (*Step-by-Step Guide*)

### 1. Kloning Repositori & Instalasi Dependensi
Buka terminal (PowerShell atau Command Prompt) di PC:
```bash
git clone https://github.com/Adrian463588/ScreenSharingWindowsInput.git
cd ScreenSharingWindowsInput
python -m pip install -r requirements.txt
```

### 2. Menjalankan Server
Anda dapat menjalankan server dengan klik ganda berkas `run.bat` atau via perintah:
```bash
python server.py
```
Terminal akan menampilkan informasi alamat IP lokal dan gambar **QR Code**.

### 3. Menghubungkan Tablet

#### Opsi A: Menggunakan Kabel USB (Sangat Direkomendasikan - Latensi Terendah & Tanpa Lag)
1. Hubungkan Samsung Galaxy Tab S7 ke PC menggunakan kabel USB.
2. Pastikan *USB Debugging* aktif di tablet.
3. Jalankan perintah port forwarding:
   ```bash
   adb reverse tcp:8000 tcp:8000
   ```
4. Buka peramban di tablet dan akses:
   ```
   http://localhost:8000
   ```

#### Opsi B: Menggunakan Wi-Fi Lokal
1. Pastikan PC dan tablet terhubung ke jaringan Wi-Fi yang sama.
2. Arahkan kamera Samsung Tab S7 ke **QR Code** di terminal PC Anda.
3. Ketuk tautan yang muncul (contoh: `http://192.168.0.5:8000`).

---

### 4. Menandatangani Dokumen Web dari Tablet
1. **Layar Penuh:** Ketuk ikon **Layar Penuh (⛶)** di toolbar tablet.
2. **Perbesar Kotak Tanda Tangan:**
   * Ketuk ikon **Fokus Kotak (🔍)**.
   * Buat kotak seleksi di atas area tanda tangan pada dokumen web di layar tablet.
   * Area tersebut akan langsung di-zoom memenuhi seluruh layar tablet.
3. **Mulai Menandatangani:**
   * Gunakan S-Pen untuk membuat tanda tangan. Telapak tangan Anda dapat bersandar bebas di atas layar tablet.
4. **Navigasi & Interaksi:**
   * Ketuk taskbar atau menu Windows dengan jari untuk berpindah aplikasi.
   * Usap dengan 2 jari untuk *scroll* dokumen web ke atas atau ke bawah.
   * Jika ada coretan yang keliru, ketuk **Undo (↩️)** atau **Hapus (🧹)**.

---

## 🔒 DevSecOps & Praktik Keamanan (*Security Best Practices*)

Proyek ini dibangun dengan mematuhi prinsip DevSecOps:
1. **Zero Secret Leakage:** Repositori bebas dari kredensial keras (*hardcoded secrets*), token API, kunci privat, ataupun data sensitif personal.
2. **Aturan `.gitignore` Ketat:** Mencegah kebocoran berkas lingkungan (`.env`), sertifikat digital, cache sesi, riwayat pengujian (`.pytest_cache`), dan log sistem.
3. **Local Network Binding:** Server berkomunikasi pada jaringan lokal (*LAN*) privat tanpa eksposur terbuka ke internet publik tanpa otentikasi.
4. **Input Sanitization & Boundary Clamping:** Semua koordinat normalisasi dari klien dibatasi secara ketat pada rentang $[0.0, 1.0]$ untuk mencegah manipulasi memori atau *overflow* di tingkat driver Win32.

---

## 🧪 Menjalankan Pengujian (*Unit Tests*)

Untuk memverifikasi keandalan sistem penangkapan layar, injeksi input, engine scrcpy, dan endpoint API:
```bash
pytest test_app.py -v
```

Hasil pengujian:
```text
test_app.py::test_screen_capturer_frame PASSED
test_app.py::test_injector_coords PASSED
test_app.py::test_injector_click_and_scroll PASSED
test_app.py::test_api_endpoints PASSED
test_app.py::test_terminal_qr_dimensions_and_fit PASSED
test_app.py::test_terminal_qr_camera_decodable PASSED
test_app.py::test_format_banner_fits_viewport PASSED
test_app.py::test_scrcpy_manager_status_and_discovery PASSED
test_app.py::test_api_android_endpoints PASSED
==================== 9 passed in 2.47s ====================
```

---

## 📦 Riwayat Versi & Tautan Unduhan (*Version History & Downloads*)

| Versi | Status | Catatan Rilis | Tautan Unduhan |
| :---: | :---: | :--- | :---: |
| **v1.2.0** | **Terbaru (Latest)** | Menambahkan fitur *bidirectional mirroring* (Android ➔ PC via `scrcpy` auto-installer & device selector), endpoint `/api/android/*`, dan panel kontrol host. | [⬇️ Download v1.2.0](https://github.com/Adrian463588/ScreenSharingWindowsInput/releases/tag/v1.2.0) |
| **v1.1.0** | Stabil | Perbaikan QR Code CLI kompak (15 baris) anti-terpotong, kompatibilitas pemindaian kamera HP, serta 3 test BDD. | [⬇️ Download v1.1.0](https://github.com/Adrian463588/ScreenSharingWindowsInput/releases/tag/v1.1.0) |
| **v1.0.0** | Awal | Rilis perdana: Screen mirroring Windows ke Samsung Tablet S7, input S-Pen dengan palm rejection, dan click deadzone filter. | [⬇️ Download v1.0.0](https://github.com/Adrian463588/ScreenSharingWindowsInput/releases/tag/v1.0.0) |

---

## ✍️ Tanda Tangan Pembuat

Proyek ini dikembangkan dan dirancang oleh:

**Dibuat oleh Adrian Syah Abidin**  
*Full Stack Developer & DevSecOps Enthusiast*
