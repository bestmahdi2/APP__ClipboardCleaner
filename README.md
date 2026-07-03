# 📋 Smart Clipboard Cleaner

**Smart Clipboard Cleaner** is a lightweight, developer-focused background utility that automatically sanitizes and formats text copied to your clipboard.

Ever copied code from a GitHub Pull Request and had to manually delete all the `+` and `-` signs? Ever copied text that carried invisible zero-width formatting characters? This tool solves that silently in the background, while providing a beautiful, searchable local GUI to view your clipboard history.

## ✨ Key Features

### 🛠️ Automated Text Cleaning

* **Smart Diff Cleaning:** Automatically strips git diff markers (`+`, `-`, `@@`, `--- a/`) so you can copy code directly from PRs, commits, and diff views without manual cleanup.
* **Intelligent Dedenting:** Removes leading whitespace/indentation from copied code blocks while preserving the internal structure using Python's `textwrap.dedent`.
* **JSON Auto-Formatting:** Detects minified or raw JSON strings and automatically formats them with a clean, readable 4-space indent.
* **Zero-Width Stripper:** Removes hidden formatting characters (`\u200b`, `\u200c`, `\u200d`, `\ufeff`) that often cause invisible syntax errors in code.
* **Markdown Code Block Removal:** Strips leading and trailing backticks (`````) when copying fenced code blocks.

### 🖥️ Modern Web GUI & System Integration

* **Beautiful Local Dashboard:** Built with Eel and vanilla JS/CSS. Features a dark-mode interface to view your clipboard history side-by-side (Original vs. Cleaned).
* **Search & Filter:** Easily search past clips or filter your history by date.
* **Interactive History:** Single-click any column to copy it back to your clipboard. Double-click to live-edit the text.
* **System Tray:** Runs quietly in the background. Access settings, pause cleaning, or open the GUI directly from the Windows tray icon.
* **Always on Top:** Pin the history GUI to stay on top of other windows during heavy coding sessions.
* **Privacy First:** All clipboard history is saved entirely locally on your machine (`Documents/smart-clipboard/`).

### ⌨️ Global Hotkeys

* `Ctrl + V`: Pastes your newly cleaned text (Standard OS behavior).
* `Ctrl + Shift + V`: Pastes the **original**, uncleaned text (if you actually needed those diff markers!).

---

## 🚀 Installation & Usage

### Option 1: Download the Standalone Executable (Recommended for Windows)

You do not need Python installed to run the app.

1. Navigate to the **[Releases](../../releases)** tab on this repository.
2. Download the latest `Clipboard Cleaner-x64.exe`.
3. Run the executable. It will minimize to your system tray automatically.

### Option 2: Run from Source

If you want to run the script natively or develop it further:

1. **Clone the repository:**
```bash
git clone https://github.com/bestmahdi2/APP__ClipboardCleaner.git
cd clipboard-cleaner

```


2. **Install dependencies:**
```bash
pip install -r requirements.txt

```


*(Note: Windows users should ensure `pywin32` is installed. Linux users will need `xdotool` installed via their package manager).*
3. **Run the application:**
```bash
python clipboard_cleaner.pyw

```


*To run without any console output, use the `--silent` flag.*

---

## ⚙️ Building the Application

This project includes a fully configured **GitHub Actions Workflow** (`build-release.yml`) that automatically compiles 32-bit and 64-bit `.exe` files using PyInstaller every time code is pushed to the `main` branch.

If you wish to build the executable manually on your local Windows machine, run:

```bash
pyinstaller --noconsole --onefile --name "Clipboard Cleaner" --icon "web/icon.ico" --add-data "web;web" clipboard_cleaner.pyw

```

Your standalone executable will be generated inside the `dist/` folder.

---

## 📂 File Structure

* `clipboard_cleaner.pyw`: The main Python backend (Clipboard monitoring, formatting rules, Eel initialization).
* `web/`: The frontend GUI folder.
* `index.html`: Layout and structure.
* `style.css`: Modern dark-theme styling.
* `app.js`: Frontend logic, search filtering, and Eel bridging.


* `.github/workflows/`: Contains the CI/CD pipeline for automated `.exe` builds.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
If you have a new regex pattern for cleaning specific types of code, or want to improve the Linux/Mac compatibility, feel free to open a Pull Request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
