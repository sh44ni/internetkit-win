# Internet Kit - Network Speed Monitor

<p align="center">
  <img src="assets/banner.png" alt="Internet Kit Banner" width="100%">
  <br><br>
  <a href="https://github.com/sh44ni/internet-kit/releases/latest">
    <img src="https://img.shields.io/badge/⬇️%20Download%20for%20Windows-Click%20Here-blue?style=for-the-badge&logo=windows" alt="Download for Windows">
  </a>
</p>

---

## 🚀 First Stable Release v1.0

We’re excited to announce the first stable release of **Internet Kit for Windows**!  
After months of testing and feedback, this version is ready for daily use.

---

## 📖 About Internet Kit

**Internet Kit** is a free, open-source tool that monitors your internet speed and usage — completely offline and private.

### Highlights
- **Live Speed Monitor:** Real-time upload/download tracking  
- **Year-Long History:** Stores data for up to 12 months  
- **Privacy First:** 100% offline, no tracking  
- **Modern Dashboard:** Beautiful dark UI with charts and insights  
- **Lightweight:** Runs quietly with minimal resource use  

---

## ✨ Features

### 📊 Real-Time Monitoring
- Floating overlay showing current speeds  
- Real-time arc animation  
- Draggable window and system-tray behavior  

### 📈 Usage History
- Daily, weekly, and yearly summaries  
- Charts and visual trends  
- Peak usage tracking  

### 🔒 Privacy & Control
- All data saved locally in `C:\Users\<you>\InternetKitData`  
- No cloud sync, no analytics, no tracking  

### 🎨 Interface
- Dark theme with gradient highlights  
- Responsive local dashboard (opens in browser)  

---

## 🛠 Installation (Windows)

1. Go to the [Releases page](https://github.com/sh44ni/internet-kit/releases/latest)  
2. Download the **InternetKit-Setup.exe** file  
3. Run it — no setup required  
4. The overlay will start automatically  

**System Requirements**
- Windows 10 or later  
- ~100 MB RAM  
- 50 MB free storage  

---

## 🚀 Quick Start

1. **Launch** Internet Kit  
2. See your live upload/download speed in the overlay  
3. **Right-click** the overlay → open dashboard  
4. View detailed stats for the day, month, and year  

---

## 📊 Data Handling

- Stored locally in JSON under:
C:\Users<you>\InternetKitData\

yaml
Copy code
- Data auto-cleans older than 12 months  
- Updates every second  

---

## 🏗 Architecture
Internet Kit
├── Background Monitor (psutil)
├── Overlay Widget (Tkinter)
├── Dashboard Server (Chart.js + HTTP)
└── Local Storage (JSON, 1-year retention)

yaml
Copy code

---

## 🧩 Development Setup (Optional)

<<<<<<< HEAD
### Data Collection
- Network I/O monitoring via `psutil`
- 1-second sampling intervals
- Atomic JSON writes for data safety
- **Automatic cleanup of records older than 1 year**


API Endpoints
/api/live - Current speed data

/api/history - Historical data by timeframe (up to 1 year)

/api/summary - Usage statistics

/api/network - Network information

Development Setup
bash
=======
```bash
>>>>>>> 722960d (docs: update Windows-focused README with download button)
git clone https://github.com/sh44ni/internet-kit.git
cd internet-kit
pip install -r requirements.txt
python main.py
Build EXE from Source
bash
Copy code
pyinstaller --onefile --windowed --add-data "assets;assets" main.py
📄 License
Licensed under the MIT License — see the LICENSE file.

🐛 Report Issues
Found a bug?
Open a GitHub Issue with details.

🌟 Coming Soon
Theme customization (light/dark)

App-wise data usage

Notifications and alerts

CSV/PDF data export

Advanced analytics

🔒 Privacy Policy
Works offline only

No data leaves your computer

<<<<<<< HEAD
No internet connection required for monitoring
=======
Open-source and transparent

Made with ❤️ by Zeeshan K.
>>>>>>> 722960d (docs: update Windows-focused README with download button)
