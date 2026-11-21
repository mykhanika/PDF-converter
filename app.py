"""PDF Toolkit (local server). Normally started through desktop.py; or run:  python app.py"""
import io, os, re, sys, json, time, uuid, base64, shutil, hmac, socket, secrets, zipfile, tempfile, threading, subprocess
from pathlib import Path
import fitz  # PyMuPDF
import pikepdf
from urllib.parse import quote
from flask import Flask, request, send_file, send_from_directory, jsonify, abort, Response
from werkzeug.exceptions import HTTPException
from pdf2docx import Converter
from PIL import Image
import pytesseract

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
app = Flask(__name__, static_folder=str(BASE / "static"))
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
WORK = Path(os.environ.get("PDFTK_WORK") or tempfile.mkdtemp(prefix="pdftk_")); WORK.mkdir(parents=True, exist_ok=True)
KEY = os.environ.get("PDFTK_KEY", "")  # optional access key when the server is shared
DL = {}
HIST = {}  # per-session undo/redo (document versions)
NAMES = {}
IMG = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
STARTUP = []  # PDF paths given on the command line (set by desktop.py only)
UI = (BASE / "ui.html").read_text(encoding="utf-8")

@app.errorhandler(Exception)
def fail(e):
    if isinstance(e, HTTPException): return Response(e.description, e.code)
    return Response(f"{type(e).__name__}: {e}", 500)

# ---------- access key, cleanup, PWA files ----------
@app.before_request
def gate():
    if not KEY or request.path.startswith("/static/") or request.path == "/sw.js": return
    got = request.args.get("key") or request.cookies.get("k") or ""
    if not hmac.compare_digest(got, KEY): return Response("Access key required. Open the link that ends with ?key=YOUR_KEY", 401)
@app.after_request
def remember_key(r):
    if KEY and request.args.get("key") == KEY: r.set_cookie("k", KEY, max_age=31536000, httponly=True, samesite="Lax")
    return r
def _sweep():
    while True:
        time.sleep(1800)
        for k in list(HIST):
            if not (WORK / f"{k}.pdf").exists(): HIST.pop(k, None)
        for p in WORK.glob("*"):
            try:
                if time.time() - p.stat().st_mtime > 6 * 3600: p.unlink() if p.is_file() else shutil.rmtree(p)
            except OSError: pass
threading.Thread(target=_sweep, daemon=True).start()
@app.get("/sw.js")
def sw(): return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
@app.get("/api/file/<tok>/<name>")
def get_file(tok, name):
    p = WORK / f"dl_{re.sub('[^0-9a-f]', '', tok)}"
    if not p.exists(): abort(404, "Download expired; please try again.")
    return send_file(p, mimetype=DL.get(tok, "application/octet-stream"), as_attachment=True, download_name=name)

# ---------- helpers ----------
def rgb(h): h = h or "#000000"; return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
def fmt(n): return f"{n/1048576:.2f} MB" if n > 1048576 else f"{n/1024:.0f} KB"
def out(data, name, mime="application/pdf", info=None):
    tok = uuid.uuid4().hex; (WORK / f"dl_{tok}").write_bytes(data); DL[tok] = mime
    return jsonify(url=f"/api/file/{tok}/{quote(name)}", info=info)
def path(pid):
    if not re.fullmatch(r"[0-9a-f]{32}", pid or ""): abort(400, "Bad session id")
    return WORK / f"{pid}.pdf"
def load(pid):
    p = path(pid)
    if not p.exists(): abort(404, "Session expired; please re-open the file.")
    p.touch()
    return fitz.open(stream=p.read_bytes(), filetype="pdf")
def store(pid, doc): path(pid).write_bytes(doc.tobytes(garbage=1, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE))
def session(doc, name):
    pid = uuid.uuid4().hex; NAMES[pid] = name; store(pid, doc); return pid
def push_hist(pid):
    h = HIST.setdefault(pid, {"u": [], "r": []}); h["u"].append(path(pid).read_bytes()); del h["u"][:-10]; h["r"].clear()
def info(pid, doc, msg=None):
    return jsonify(id=pid, pages=len(doc), name=NAMES.get(pid, "document"), msg=msg,
                   sizes=[[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc])
def page_img(page, dpi=200): return Image.open(io.BytesIO(page.get_pixmap(dpi=dpi).tobytes("png")))
def page_text(page, force=False):
    t = page.get_text().strip()
    return pytesseract.image_to_string(page_img(page)).strip() if force or len(t) < 15 else t
def searchable(doc):
    new = fitz.open()
    for p in doc: new.insert_pdf(fitz.open("pdf", pytesseract.image_to_pdf_or_hocr(page_img(p), extension="pdf")))
    return new
def office_to_pdf(p):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe: abort(500, "LibreOffice not found. Install it to convert Word/Excel/PowerPoint.")
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(WORK), str(p)], check=True, capture_output=True, timeout=180)
    return WORK / (p.stem + ".pdf")
def raster(doc, mode="none", dpi=150):
    new = fitz.open()
    for p in doc:
        pix = p.get_pixmap(dpi=dpi)
        if mode == "gray": pix = fitz.Pixmap(fitz.csGRAY, pix)
        elif mode == "invert": pix.invert_irect(pix.irect)
        elif mode == "bw":
            im = page_img(p, dpi).convert("L").point(lambda v: 255 if v > 140 else 0).convert("1"); b = io.BytesIO(); im.save(b, "PNG"); pix = fitz.Pixmap(b.getvalue())
        np_ = new.new_page(width=p.rect.width, height=p.rect.height); np_.insert_image(np_.rect, pixmap=pix)
    return new

# ---------- open / merge / convert-to-pdf ----------
@app.get("/")
def home(): return Response(UI, mimetype="text/html")

@app.post("/api/open")
def open_():
    f = request.files.get("file")
    if not f: abort(400, "No file uploaded.")
    doc = fitz.open(stream=f.read(), filetype="pdf")
    if doc.needs_pass and not doc.authenticate(request.form.get("password", "")): return jsonify(needs_password=True)
    return info(session(doc, Path(f.filename).stem), doc)

@app.post("/api/startup")
def startup():
    if not STARTUP: return jsonify(none=True)
    doc = fitz.open(STARTUP[0])
    if doc.needs_pass and not doc.authenticate(request.form.get("password", "")): return jsonify(needs_password=True)
    return info(session(doc, Path(STARTUP.pop(0)).stem), doc)

@app.post("/api/merge")
def merge():
    res = fitz.open()
    if request.form.get("id"): res.insert_pdf(load(request.form["id"]))
    files = request.files.getlist("files")
    for f in files: res.insert_pdf(fitz.open(stream=f.read(), filetype="pdf"))
    if not len(res): abort(400, "Add at least one PDF.")
    return info(pid := session(res, "merged"), res, f"Merged into {len(res)} pages.")

@app.post("/api/to-pdf")
def to_pdf():
    files = request.files.getlist("files"); merged = fitz.open()
    if not files: abort(400, "No files uploaded.")
    for f in files:
        p = WORK / f"{uuid.uuid4().hex}{Path(f.filename).suffix.lower()}"; f.save(p)
        if p.suffix == ".pdf": src = fitz.open(p)
        elif p.suffix in IMG: src = fitz.open("pdf", fitz.open(p).convert_to_pdf())
        else: src = fitz.open(office_to_pdf(p))
        merged.insert_pdf(src)
    return info(session(merged, Path(files[0].filename).stem), merged, "PDF created. Use Save to download it.")

# ---------- viewer ----------
@app.get("/api/preview/<pid>/<int:pg>")
def preview(pid, pg):
    doc = load(pid); z = max(0.3, min(float(request.args.get("z", 1.5)), 5))
    return Response(doc[max(0, min(pg, len(doc)) - 1)].get_pixmap(matrix=fitz.Matrix(z, z)).tobytes("png"), mimetype="image/png")

@app.post("/api/textat")
def textat():
    f = request.form; pg = load(f["id"])[int(f["page"]) - 1]; pt = fitz.Point(float(f["x"]), float(f["y"]))
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if (fitz.Rect(s["bbox"]) + (-1, -1, 1, 1)).contains(pt):
                    return jsonify(found=True, text=s["text"], bbox=s["bbox"], origin=s["origin"], size=s["size"], bold=bool(s["flags"] & 16), color="#%06x" % s["color"])
    return jsonify(found=False)

# ---------- apply annotations / edits ----------
def apply_ops(doc, ops):
    for o in ops:
        pg = doc[o["page"] - 1]; t = o["t"]; c = rgb(o.get("color")); x, y = o.get("x", 0), o.get("y", 0)
        if t in ("hl", "ul", "st"):
            r = fitz.Rect(x, y, x + o["w"], y + o["h"])
            rs = [fitz.Rect(w[:4]) for w in pg.get_text("words") if fitz.Rect(w[:4]).intersects(r)] or [r]
            a = {"hl": pg.add_highlight_annot, "ul": pg.add_underline_annot, "st": pg.add_strikeout_annot}[t](quads=rs)
            a.set_colors(stroke=c); a.update()
        elif t == "ink":
            a = pg.add_ink_annot([[tuple(p) for p in o["pts"]]]); a.set_colors(stroke=c); a.set_border(width=o["w"]); a.set_opacity(o.get("alpha", 1)); a.update()
        elif t == "text": pg.insert_text((x, y), o["v"], fontsize=o["s"], fontname="helv", color=c)
        elif t == "callout":
            bx, by, bw, bh = o["bx"], o["by"], o["bw"], o["bh"]
            pg.draw_line((bx + bw / 2, by + bh / 2), (x, y), color=c, width=1.2); pg.draw_circle((x, y), 2.5, color=c, fill=c)
            pg.draw_rect(fitz.Rect(bx, by, bx + bw, by + bh), color=c, fill=(1, 1, .8), width=1.2)
            pg.insert_textbox(fitz.Rect(bx + 4, by + 3, bx + bw - 4, by + bh - 3), o["v"], fontsize=o["s"], fontname="helv")
        elif t == "image": pg.insert_image(fitz.Rect(x, y, x + o["w"], y + o["h"]), stream=base64.b64decode(o["v"].split(",")[1]))
        elif t == "sign":
            r = fitz.Rect(x, y, x + o["w"], y + o["h"]); data = base64.b64decode(o["v"].split(",")[1])
            try:
                a = pg.add_stamp_annot(r, stamp=fitz.Pixmap(data)); a.set_info(subject="PDFTK-SIGN"); a.update()
            except Exception: pg.insert_image(r, stream=data)
        elif t == "stamp": pg.add_stamp_annot(fitz.Rect(x, y, x + o["w"], y + o["h"]), stamp=int(o["i"]))
        elif t == "note": pg.add_text_annot((x, y), o["v"], icon="Note")
        elif t == "redact":
            pg.add_redact_annot(fitz.Rect(x, y, x + o["w"], y + o["h"]), fill=(0, 0, 0)); pg.apply_redactions()
        elif t == "replace":
            pg.add_redact_annot(fitz.Rect(o["bbox"]), fill=(1, 1, 1)); pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            pg.insert_text(o["origin"], o["v"], fontsize=o["s"], fontname="hebo" if o.get("bold") else "helv", color=c)

@app.post("/api/apply")
def apply():
    pid = request.form["id"]; doc = load(pid); apply_ops(doc, json.loads(request.form.get("ops", "[]"))); push_hist(pid); store(pid, doc); return info(pid, doc)

# ---------- document actions that change the open document ----------
@app.post("/api/do/<action>")
def do(action):
    f = request.form; pid = f["id"]; doc = load(pid); pi = int(f.get("page", 1)) - 1; msg = None
    if action == "rotate":
        for p in (doc if f.get("scope") == "all" else [doc[pi]]): p.set_rotation((p.rotation + int(f["angle"])) % 360)
    elif action == "delete":
        if len(doc) < 2: abort(400, "A PDF needs at least one page.")
        doc.delete_page(pi)
    elif action == "blank": r = doc[pi].rect; doc.new_page(pno=pi + 1, width=r.width, height=r.height)
    elif action == "strip":
        kind, n = f["kind"], 0
        for p in doc:
            for a in list(p.annots() or []):
                sign = a.info.get("subject") == "PDFTK-SIGN"
                if kind == "annots" or (kind == "sig" and sign) or (kind == "stamp" and a.type[0] == fitz.PDF_ANNOT_STAMP and not sign):
                    p.delete_annot(a); n += 1
            if kind == "sig":
                for w in list(p.widgets() or []):
                    if w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE: p.delete_widget(w); n += 1
        msg = f"Removed {n} item(s)."
    elif action == "headerfooter":
        s, al, tot = float(f.get("size", 10)), f.get("align", "center"), len(doc)
        for i, p in enumerate(doc, 1):
            for txt, yy in ((f.get("header", ""), 30), (f.get("footer", ""), p.rect.height - 22)):
                txt = txt.replace("{page}", str(i)).replace("{total}", str(tot))
                if not txt: continue
                w = fitz.get_text_length(txt, fontname="helv", fontsize=s)
                x = 36 if al == "left" else p.rect.width - 36 - w if al == "right" else (p.rect.width - w) / 2
                p.insert_text((x, yy), txt, fontsize=s, fontname="helv", color=rgb(f.get("color", "#444444")))
        msg = "Header and footer added."
    elif action == "ocr": doc = searchable(doc); msg = "OCR complete: the text is now searchable."
    elif action == "color":
        mode = f["mode"]
        if mode == "gray":
            try: [p.recolor(1) for p in doc]
            except Exception: doc = raster(doc, "gray")
        else: doc = raster(doc, mode)
        msg = "Colours changed (invert/black-and-white turn pages into images)."
    elif action == "flatten":
        try: doc.bake(annots=True, widgets=True)
        except Exception: doc = raster(doc)
        msg = "Annotations and form fields flattened."
    else: abort(404, "Unknown action")
    push_hist(pid); store(pid, doc); return info(pid, doc, msg)

@app.post("/api/history/<kind>")
def history(kind):
    if kind not in ("undo", "redo"): abort(404)
    pid = request.form["id"]; h = HIST.setdefault(pid, {"u": [], "r": []}); a, b = ("u", "r") if kind == "undo" else ("r", "u")
    if not h[a]: abort(400, f"Nothing to {kind}.")
    h[b].append(path(pid).read_bytes()); path(pid).write_bytes(h[a].pop())
    return info(pid, load(pid), "Undone." if kind == "undo" else "Redone.")

# ---------- exports (download a file) ----------
@app.post("/api/export/<action>")
def export(action):
    f = request.form; pid = f["id"]; doc = load(pid); name = NAMES.get(pid, "document")
    if action == "save": return out(doc.tobytes(garbage=3, deflate=True), name + ".pdf")
    if action == "protect":
        F = fitz; perm = (F.PDF_PERM_ACCESSIBILITY | F.PDF_PERM_PRINT | F.PDF_PERM_COPY | F.PDF_PERM_MODIFY | F.PDF_PERM_ANNOTATE | F.PDF_PERM_FORM | F.PDF_PERM_ASSEMBLE | F.PDF_PERM_PRINT_HQ)
        if f.get("no_print"): perm &= ~(F.PDF_PERM_PRINT | F.PDF_PERM_PRINT_HQ)
        if f.get("no_copy"): perm &= ~F.PDF_PERM_COPY
        if f.get("no_edit"): perm &= ~(F.PDF_PERM_MODIFY | F.PDF_PERM_ANNOTATE | F.PDF_PERM_ASSEMBLE | F.PDF_PERM_FORM)
        user = f.get("user_pw", ""); owner = f.get("owner_pw") or user + "-owner"
        return out(doc.tobytes(encryption=F.PDF_ENCRYPT_AES_256, user_pw=user, owner_pw=owner, permissions=int(perm)), name + "-protected.pdf", info="Protected with AES-256.")
    if action == "optimize":
        src = doc.tobytes(garbage=3, deflate=True); b = io.BytesIO()
        with pikepdf.open(io.BytesIO(src)) as pdf: pdf.save(b, linearize=True)
        return out(b.getvalue(), name + "-web.pdf", info=f"Optimized for fast web view ({fmt(len(b.getvalue()))}).")
    if action == "compress":
        before = len(doc.tobytes()); dpi_hi, dpi_to, q = {"low": (150, 130, 85), "medium": (110, 96, 70), "high": (96, 72, 50)}[f.get("level", "medium")]
        try: doc.rewrite_images(dpi_threshold=dpi_hi, dpi_target=dpi_to, quality=q)
        except Exception: pass
        data = doc.tobytes(garbage=4, deflate=True, clean=True)
        return out(data, name + "-small.pdf", info=f"Reduced {fmt(before)} to {fmt(len(data))} ({max(0, 100 - 100 * len(data) // before)}% smaller).")
    if action == "extract":
        idx = []
        for part in filter(None, (s.strip() for s in f.get("arg", "").split(","))):
            a, _, b = part.partition("-"); idx += list(range(max(1, int(a)) - 1, min(len(doc), int(b or a))))
        if not idx: abort(400, "Enter pages like 1-3,5.")
        doc.select(idx); return out(doc.tobytes(), name + "-extract.pdf")
    if action == "split":
        n, mode, arg = len(doc), f.get("mode"), f.get("arg", "").strip(); groups = []
        if mode == "each": groups = [[i] for i in range(n)]
        elif mode == "ranges":
            for part in filter(None, (s.strip() for s in arg.split(","))):
                a, _, b = part.partition("-"); groups.append(list(range(max(1, int(a)) - 1, min(n, int(b or a)))))
        else:
            cur = []
            for i, p in enumerate(doc):
                t = page_text(p, bool(f.get("ocr")))
                if mode == "blank" and len(re.sub(r"\s", "", t)) < 5:
                    if cur: groups.append(cur)
                    cur = []; continue
                if mode == "kw" and arg.lower() in t.lower() and cur: groups.append(cur); cur = []
                cur.append(i)
            if cur: groups.append(cur)
        groups = [g for g in groups if g]
        if not groups: abort(400, "Nothing to split with those settings.")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for k, g in enumerate(groups, 1):
                part = fitz.open(); [part.insert_pdf(doc, from_page=i, to_page=i) for i in g]
                z.writestr(f"{name}_part{k:02d}_p{g[0]+1}-{g[-1]+1}.pdf", part.tobytes())
        return out(buf.getvalue(), name + "-split.zip", "application/zip", f"Created {len(groups)} files.")
    if action == "word":
        if sum(len(p.get_text().strip()) for p in doc) < 50: doc = searchable(doc)
        src = WORK / f"{uuid.uuid4().hex}.pdf"; doc.save(src); dst = src.with_suffix(".docx")
        cv = Converter(str(src)); cv.convert(str(dst)); cv.close()
        return out(dst.read_bytes(), name + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if action == "images":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i, p in enumerate(doc, 1): z.writestr(f"{name}_page{i:03d}.png", p.get_pixmap(dpi=150).tobytes("png"))
        return out(buf.getvalue(), name + "-images.zip", "application/zip")
    if action == "text":
        txt = "\n\n".join(f"--- Page {i} ---\n{page_text(p, bool(f.get('ocr')))}" for i, p in enumerate(doc, 1))
        return out(txt.encode(), name + ".txt", "text/plain")
    abort(404, "Unknown export")

if __name__ == "__main__":
    lan = "--lan" in sys.argv
    host = os.environ.get("PDFTK_HOST", "0.0.0.0" if lan else "127.0.0.1"); port = int(os.environ.get("PORT", 5000))
    if lan and not KEY: KEY = secrets.token_urlsafe(6)
    if host != "127.0.0.1":
        try: s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_.connect(("8.8.8.8", 80)); ip = s_.getsockname()[0]
        except OSError: ip = "your-pc-ip"
        print(f"\nOpen on your phone (same Wi-Fi):  http://{ip}:{port}/" + (f"?key={KEY}" if KEY else "") + "\n")
    app.run(host, port, threaded=True)
