import os
import sys
import json
import base64
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk  # Pillow bleibt (Variante A)
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H

# ----------------------------------------------------------------------
# App-Ordner & Settings
# ----------------------------------------------------------------------
APP_DIR = Path.home() / ".qr_code_generator"
APP_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DIR / "settings.json"

def resource_path(relative: str) -> str:
    """
    Liefert einen Pfad zu Ressourcen, der sowohl im normalen Python-Run
    als auch in einer PyInstaller-EXE funktioniert.
    """
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path:
        return os.path.join(base_path, relative)
    return os.path.join(os.path.abspath("."), relative)

# ----------------------------------------------------------------------
# Tooltip Helper
# ----------------------------------------------------------------------
class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)
        widget.bind("<Motion>", self._on_motion)

    def _on_enter(self, event=None):
        self.show(event)

    def _on_leave(self, event=None):
        self.hide()

    def _on_motion(self, event):
        # Tooltip folgt leicht der Maus
        if self.tip:
            x = self.widget.winfo_rootx() + event.x + 16
            y = self.widget.winfo_rooty() + event.y + 16
            self.tip.wm_geometry(f"+{x}+{y}")

    def show(self, event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + 24
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=6, pady=3,
        )
        lbl.pack()

    def hide(self):
        if self.tip:
            self.tip.destroy()
            self.tip = None

# ----------------------------------------------------------------------
# Optionen-Dialog
# ----------------------------------------------------------------------
class OptionsDialog(tk.Toplevel):
    def __init__(self, master, options, on_apply, info_icon_img):
        super().__init__(master)
        self.title("QR-Optionen")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.on_apply = on_apply

        # Lokale Kopie der Optionen
        self.var_version = tk.IntVar(value=options.get("version", 0))
        self.var_box = tk.IntVar(value=options.get("box_size", 10))
        self.var_border = tk.IntVar(value=options.get("border", 4))
        self.var_ec = tk.StringVar(value=options.get("error_correction", "M"))

        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)

        # Version
        ttk.Label(frm, text="Version (1–40, 0=auto):").grid(row=0, column=0, sticky="w", pady=(0,6))
        spn_version = ttk.Spinbox(frm, from_=0, to=40, textvariable=self.var_version, width=6)
        spn_version.grid(row=0, column=1, sticky="w", pady=(0,6))
        info_v = ttk.Label(frm, image=info_icon_img, cursor="question_arrow")
        info_v.image = info_icon_img
        info_v.grid(row=0, column=2, sticky="w")
        ToolTip(info_v, "QR-Version: 0 = automatische Wahl.\nHöhere Version = mehr Daten möglich,\naber größeres Raster. 1–40 = fix.")

        # Fehlerkorrektur
        ttk.Label(frm, text="Fehlerkorrektur:").grid(row=1, column=0, sticky="w", pady=(0,6))
        cb_ec = ttk.Combobox(frm, textvariable=self.var_ec, values=["L", "M", "Q", "H"], width=4, state="readonly")
        cb_ec.grid(row=1, column=1, sticky="w", pady=(0,6))
        info_ec = ttk.Label(frm, image=info_icon_img, cursor="question_arrow")
        info_ec.image = info_icon_img
        info_ec.grid(row=1, column=2, sticky="w")
        ToolTip(info_ec, "Fehlerkorrektur:\nL ≈ 7%, M ≈ 15%, Q ≈ 25%, H ≈ 30% Redundanz.\nHöher = robuster, aber größer.")

        # Box-Größe
        ttk.Label(frm, text="Box-Größe (Pixel/Modul):").grid(row=2, column=0, sticky="w", pady=(0,6))
        spn_box = ttk.Spinbox(frm, from_=1, to=100, textvariable=self.var_box, width=6)
        spn_box.grid(row=2, column=1, sticky="w", pady=(0,6))
        info_box = ttk.Label(frm, image=info_icon_img, cursor="question_arrow")
        info_box.image = info_icon_img
        info_box.grid(row=2, column=2, sticky="w")
        ToolTip(info_box, "Pixelgröße eines QR-Moduls.\nGrößer = höhere Bildauflösung.")

        # Rand
        ttk.Label(frm, text="Rand (Module):").grid(row=3, column=0, sticky="w", pady=(0,12))
        spn_border = ttk.Spinbox(frm, from_=0, to=20, textvariable=self.var_border, width=6)
        spn_border.grid(row=3, column=1, sticky="w", pady=(0,12))
        info_bd = ttk.Label(frm, image=info_icon_img, cursor="question_arrow")
        info_bd.image = info_icon_img
        info_bd.grid(row=3, column=2, sticky="w")
        ToolTip(info_bd, "Weißer Ruhebereich in Modulen um den QR-Code.\n4 ist üblich/empfohlen für die Lesbarkeit.")

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky="e")
        ttk.Button(btns, text="Abbrechen", command=self.destroy).grid(row=0, column=0, padx=(0,8))
        ttk.Button(btns, text="Übernehmen", command=self.apply).grid(row=0, column=1)

        self.bind("<Return>", lambda e: self.apply())
        self.bind("<Escape>", lambda e: self.destroy())

    def apply(self):
        opts = {
            "version": max(0, int(self.var_version.get())),
            "box_size": max(1, int(self.var_box.get())),
            "border": max(0, int(self.var_border.get())),
            "error_correction": self.var_ec.get(),
        }
        self.on_apply(opts)
        self.destroy()

# ----------------------------------------------------------------------
# Haupt-App
# ----------------------------------------------------------------------
class QRApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Einstellungen laden
        self.settings = self.load_settings()

        self.title("QR-Code Generator")
        # Geometry nur anwenden, wenn zuletzt NICHT maximiert war
        if not self.settings.get("maximized", False):
            self.geometry(self.settings.get("geometry", "680x620+80+60"))
        self.minsize(520, 520)

        # Fenster-Icon (PNG) setzen – getrennt vom EXE-Icon (PyInstaller --icon)
        try:
            icon_path = resource_path("qr-qrcode.png")
            # Für Fenstericon reicht Tk PhotoImage (PNG wird von Tk8.6 verstanden)
            icon_img = tk.PhotoImage(file=icon_path)
            self.iconphoto(False, icon_img)
            self._icon_img_ref = icon_img  # Referenz halten
        except Exception:
            pass

        # Info-Icon laden (für Tooltips im Optionen-Dialog)
        self.info_icon_img = None
        try:
            info_path = resource_path("info-icon.png")
            self.info_icon_img = tk.PhotoImage(file=info_path)
        except Exception:
            # Fallback: erzeugen wir ein kleines eingebettetes „i“-Icon per Base64 (1x notfalls)
            self.info_icon_img = self._fallback_info_icon()

        # QR-Optionen laden
        self.options = self.settings.get("qr_options", {
            "version": 0,
            "error_correction": "M",
            "box_size": 10,
            "border": 4,
        })

        self._build_ui()

        self.current_qr_image = None       # PIL.Image
        self.current_qr_tkimage = None     # ImageTk.PhotoImage

        # Events
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<F11>", self.toggle_maximize)
        self.bind("<Escape>", self.unmaximize_if_needed)

        # Beim Start maximieren, falls gemerkt
        if self.settings.get("maximized", False):
            self.after(0, self.set_maximized)

    # ---------- Settings ----------
    def load_settings(self) -> dict:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    def save_settings(self):
        data = dict(self.settings)
        is_max = (self.state() == "zoomed")
        data["maximized"] = is_max
        if not is_max:
            data["geometry"] = self.geometry()
        data["qr_options"] = self.options
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- Maximize Handling ----------
    def set_maximized(self, event=None):
        self.state("zoomed")

    def set_normal(self, event=None):
        self.state("normal")

    def toggle_maximize(self, event=None):
        if self.state() == "zoomed":
            self.set_normal()
        else:
            self.set_maximized()

    def unmaximize_if_needed(self, event=None):
        if self.state() == "zoomed":
            self.set_normal()

    # ---------- UI ----------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        hdr = ttk.Label(self, text="Text → QR-Code", font=("TkDefaultFont", 14, "bold"))
        hdr.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        txt_frame = ttk.Frame(self, padding=(12, 0, 12, 0))
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.columnconfigure(0, weight=1)
        txt_frame.rowconfigure(0, weight=1)

        self.txt = tk.Text(txt_frame, wrap="word", height=8)
        self.txt.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(txt_frame, orient="vertical", command=self.txt.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.txt.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(self, padding=12)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure(0, weight=1)

        self.btn_generate = ttk.Button(btns, text="Erstellen", command=self.generate_qr)
        self.btn_generate.grid(row=0, column=0, sticky="w")

        self.btn_save = ttk.Button(btns, text="QR-Code speichern…", command=self.save_qr, state="disabled")
        self.btn_save.grid(row=0, column=1, padx=(12, 0), sticky="w")

        self.btn_options = ttk.Button(btns, text="⚙ Optionen", command=self.open_options)
        self.btn_options.grid(row=0, column=2, padx=(12, 0), sticky="w")

        disp_frame = ttk.LabelFrame(self, text="Vorschau", padding=12)
        disp_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0,12))
        disp_frame.columnconfigure(0, weight=1)
        disp_frame.rowconfigure(0, weight=1)

        self.lbl_image = ttk.Label(disp_frame, anchor="center")
        self.lbl_image.grid(row=0, column=0, sticky="nsew")

    def _ec_const(self, key: str):
        return {
            "L": ERROR_CORRECT_L,
            "M": ERROR_CORRECT_M,
            "Q": ERROR_CORRECT_Q,
            "H": ERROR_CORRECT_H,
        }.get(key.upper(), ERROR_CORRECT_M)

    def generate_qr(self):
        data = self.txt.get("1.0", "end-1c")
        if not data.strip():
            messagebox.showinfo("Hinweis", "Bitte gib einen Text ein, der in den QR-Code soll.")
            return

        version = self.options.get("version", 0)
        version = None if version in (0, None) else int(version)

        qr = qrcode.QRCode(
            version=version,
            error_correction=self._ec_const(self.options.get("error_correction", "M")),
            box_size=int(self.options.get("box_size", 10)),
            border=int(self.options.get("border", 4)),
        )
        try:
            qr.add_data(data)
            qr.make(fit=True if version is None else False)
        except Exception as e:
            messagebox.showerror("Fehler beim Erstellen", f"{e}")
            return

        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        # Anzeige (ggf. skaliert)
        self.current_qr_image = img
        self._update_preview(img)
        self.btn_save.config(state="normal")

    def _update_preview(self, pil_image):
        self.update_idletasks()
        frame_width = max(self.lbl_image.winfo_width(), 300)
        frame_height = max(self.lbl_image.winfo_height(), 300)
        img_w, img_h = pil_image.size

        scale = min(frame_width / img_w, frame_height / img_h, 1.0)
        if scale < 1.0:
            new_size = (max(1, int(img_w * scale)), max(1, int(img_h * scale)))
            preview = pil_image.resize(new_size, Image.NEAREST)
        else:
            preview = pil_image

        self.current_qr_tkimage = ImageTk.PhotoImage(preview)
        self.lbl_image.configure(image=self.current_qr_tkimage)

    def save_qr(self):
        if self.current_qr_image is None:
            messagebox.showinfo("Hinweis", "Erstelle zuerst einen QR-Code.")
            return

        filetypes = [("PNG-Bild", "*.png"), ("Alle Dateien", "*.*")]
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=filetypes,
            title="QR-Code speichern"
        )
        if not path:
            return

        try:
            self.current_qr_image.save(path, format="PNG")
        except Exception as e:
            messagebox.showerror("Speichern fehlgeschlagen", f"{e}")
            return
        messagebox.showinfo("Gespeichert", f"QR-Code gespeichert:\n{path}")

    def open_options(self):
        OptionsDialog(self, self.options, self.apply_options, self.info_icon_img)

    def apply_options(self, new_options: dict):
        v = int(new_options.get("version", 0))
        if v not in range(0, 41):
            v = 0
        b = max(1, int(new_options.get("box_size", 10)))
        r = max(0, int(new_options.get("border", 4)))
        ec = str(new_options.get("error_correction", "M")).upper()
        if ec not in ("L", "M", "Q", "H"):
            ec = "M"
        self.options.update({"version": v, "box_size": b, "border": r, "error_correction": ec})

        if self.current_qr_image is not None:
            self.generate_qr()

    def on_close(self):
        self.save_settings()
        self.destroy()

    # Kleines Base64-Fallback-Icon, falls info-icon.png fehlt
    def _fallback_info_icon(self):
        # 16x16 „i“ Symbol (einfach), PNG base64 (transparent + dunkles i)
        # Das ist bewusst sehr klein gehalten; in echten Apps PNG-Datei verwenden.
        png_b64 = (
            b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAeFBMVEUAAAD/////////////////////////////////'
            b'//////////////////////////////////////////////////////////////////////////////8T4CqkAAAAK3RSTlMA'
            b'QFDgYBqkW0yqjQv2m1lOCP7yXc2m0w3jO8wqf1b9aP3x+0Hc7o3f1Hj1U5o0dy0b+3AAABFElEQVQY02XP2w6CMBQF4ZxA'
            b'QmQ5g1b//0k0d0Vb9m0oS2i0y1t8c0o0Vw0w0H2b0m4SDkG1h7b1G0H0oG0qHq3wWwJHcZb1tXw6oD0Dk9Jr4wzq8w2H2o'
            b'Qy0A3QW0lZC8q3lq2m0x4Gq1m9g2rjJmR3A1n2w3qJmYw3T1E0Q9g8mVd9Jk1j1r2aH6x0b7KzvR6LrQb4Jm3w3r2o9FJp'
            b'cHc9H4wKk5g9E7yNwJ1mA6f2m9Jp7n3oB3Q2s2HcE2lF2X3S1wQ0fX3c6h7AAAAAElFTkSuQmCC'
        )
        return tk.PhotoImage(data=base64.b64encode(base64.b64decode(png_b64)))

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = QRApp()
    app.mainloop()
