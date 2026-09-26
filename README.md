# ScreenSharingWindowsInput (TabSign)

[![Python 3.12](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets%20Binary-yellow.svg)](https://websockets.readthedocs.io/)
[![Win32 API](https://img.shields.io/badge/Input-Win32%20SendInput-informational.svg)](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
[![DevSecOps](https://img.shields.io/badge/Security-DevSecOps%20Compliant-success.svg)](#devsecops--keamanan)

Aplikasi *screen sharing* dan *input mirroring* berlatensi sangat rendah dari PC Windows ke perangkat tablet (seperti Samsung Galaxy Tab S7 dengan S-Pen) secara *real-time*.

Dirancang khusus untuk memudahkan pengguna menandatangani dokumen berbasis website (seperti DocuSign, Privy, Adobe Sign, form web, atau PDF viewer) yang dibuka di Windows langsung menggunakan stylus S-Pen pada tablet.

---

## 📌 Ringkasan Masalah & Solusi (*Overview*)

### Masalah
Saat membuka dokumen resmi yang membutuhkan tanda tangan digital di peramban PC (Google Chrome, Microsoft Edge, dll.), menandatangani menggunakan mouse seringkali kaku, tidak rapi, dan tidak menyerupai tanda tangan asli.

### Solusi
**ScreenSharingWindowsInput** mentransmisikan tampilan layar Windows (seluruh desktop atau jendela web tertentu) ke tablet Android melalui browser secara instan. Input stylus (S-Pen) dan sentuhan jari dari tablet diterjemahkan dan diinjeksikan secara presisi ke Windows menggunakan API resmi `SendInput`, menghadirkan pengalaman menggambar tanda tangan alami layaknya *drawing tablet* profesional.

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

Untuk memverifikasi keandalan sistem penangkapan layar, injeksi input, dan endpoint API:
```bash
pytest test_app.py -v
```

Hasil pengujian:
```text
test_app.py::test_screen_capturer_frame PASSED
test_app.py::test_injector_coords PASSED
test_app.py::test_injector_click_and_scroll PASSED
test_app.py::test_api_endpoints PASSED
==================== 4 passed in 2.53s ====================
```

---

## ✍️ Tanda Tangan Pembuat

Proyek ini dikembangkan dan dirancang oleh:

**Dibuat oleh Adriansyah Gidding**  
*Full Stack Developer & DevSecOps Enthusiast*
