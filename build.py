"""Build a standalone app:  python build.py   (result in dist/PDFToolkit)"""
import os
import PyInstaller.__main__ as pi
pi.run(["desktop.py", "--name", "PDFToolkit", "--windowed", "--noconfirm", "--clean",
        "--add-data", f"ui.html{os.pathsep}.", "--add-data", f"static{os.pathsep}static",
        "--collect-all", "pdf2docx", "--collect-all", "docx", "--collect-all", "pymupdf", "--collect-all", "pikepdf"])
