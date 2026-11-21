# PDF Toolkit
Created by Washim Reja. Contact: 7003714487

## Start fresh on GitHub
1. Create a new empty repository.
2. Unzip `PDFToolkit-project.zip`. Open the `pdf-toolkit-local` folder.
3. Select everything inside it (including the folders `android`, `static` and `.github`) and drag it onto **Add file, Upload files**. Dragging folders keeps their structure. Commit.
4. Open **Actions, Build installers, Run workflow**.
5. When finished, download **PDFToolkit-Windows-Setup** (and **PDFToolkit-Android-APK** if that job succeeds) from Artifacts.

## Windows
Run `PDFToolkit-Setup.exe`. OCR is bundled. Word/Excel/PowerPoint to PDF needs LibreOffice (libreoffice.org).
Developer mode: `pip install -r requirements.txt`, then `python desktop.py`.

## What's in the app
Undo and Redo (header buttons, Ctrl+Z / Ctrl+Y) cover pending edits first, then earlier saved steps such as rotate or delete page.
Images, signatures and stamps are placed once. They then stay selected so you can drag to move, drag the blue corner to resize, and press Delete (or Edit, Delete Selected) to remove. Use Edit, Select / Move to select any pending item later. The Eraser also removes items.

## Android
The APK is a window onto a PDF Toolkit server (the PDF engine, OCR and Word conversion cannot run inside Android).
- **Server on your PC (same Wi-Fi):** `python app.py --lan` prints a link for your phone.
- **Server anywhere:** `PDFTK_KEY=long-random-text docker compose up -d --build`, behind HTTPS.
- **Install:** copy `app-debug.apk` to the phone, allow unknown apps, open it, paste the link, tap Connect. Android 10 or newer.

### If the GitHub Android job keeps failing: build the APK on your PC
1. Install Android Studio (developer.android.com/studio) and open the `android` folder.
2. Wait for Gradle sync to finish. Then **Build, Build Bundle(s) / APK(s), Build APK(s)**.
3. The file is at `android/app/build/outputs/apk/debug/app-debug.apk`.

## Notes
Keep your access key private and use HTTPS on the internet. Uploaded files are deleted from the server after 6 hours.
