import tkinter as tk
import serial
import threading

PORT = "/dev/ttyUSB0"
BAUD = 115200

BG      = "#0b1a0b"
CARD_BG = "#122212"
BAR_BG  = "#1c3a1c"
BORDER  = "#2d5a2d"
FG      = "#d4edda"
FG_DIM  = "#4a7a4a"
ACCENT  = "#4caf50"
RED_BTN = "#c0392b"

GAUGE_SIZE   = 270
GAUGE_MARGIN = 30
GAUGE_WIDTH  = 20
GAUGE_START  = 220
GAUGE_SWEEP  = -260


def temp_color(t):
    if t < 20:
        return "#66bb6a"
    if t <= 25:
        return "#ffa726"
    return "#ef5350"


def moisture_color(pct):
    pct = max(0, min(100, pct))
    if pct <= 50:
        r, g = 255, int(255 * pct / 50)
    else:
        r, g = int(255 * (1 - (pct - 50) / 50)), 255
    return f"#{r:02x}{g:02x}00"


class Gauge(tk.Frame):
    def __init__(self, parent, title, default_color, unit="%",
                 vmin=0, vmax=100, show_fahrenheit=False):
        super().__init__(parent, bg=CARD_BG,
                         highlightthickness=2, highlightbackground=BORDER)
        self.unit            = unit
        self.vmin            = vmin
        self.vmax            = vmax
        self.default_color   = default_color
        self.show_fahrenheit = show_fahrenheit

        tk.Label(self, text=title.upper(),
                 font=("Helvetica", 14, "bold"),
                 bg=CARD_BG, fg=FG_DIM).pack(pady=(20, 0))

        s = GAUGE_SIZE
        self.canvas = tk.Canvas(self, width=s, height=s,
                                bg=CARD_BG, highlightthickness=0)
        self.canvas.pack(padx=20, pady=(10, 5))

        m = GAUGE_MARGIN
        self.canvas.create_arc(m, m, s-m, s-m,
                               start=GAUGE_START, extent=GAUGE_SWEEP,
                               style="arc", outline="#1e3a1e", width=GAUGE_WIDTH)

        self._arc = self.canvas.create_arc(m, m, s-m, s-m,
                                           start=GAUGE_START, extent=0,
                                           style="arc", outline=default_color,
                                           width=GAUGE_WIDTH)

        self._val_text = self.canvas.create_text(
            s // 2, s // 2 - 14,
            text="--", font=("Helvetica", 36, "bold"), fill=FG)

        self._sub_text = self.canvas.create_text(
            s // 2, s // 2 + 28,
            text="", font=("Helvetica", 13), fill=FG_DIM)

        self._big_label = tk.Label(self, text="--",
                                   font=("Helvetica", 42, "bold"),
                                   bg=CARD_BG, fg=default_color)
        self._big_label.pack(pady=(4, 2))

        if show_fahrenheit:
            self._fahr_label = tk.Label(self, text="-- °F",
                                        font=("Helvetica", 16),
                                        bg=CARD_BG, fg=FG_DIM)
            self._fahr_label.pack(pady=(0, 20))
        else:
            self._fahr_label = None
            tk.Frame(self, height=20, bg=CARD_BG).pack()

    def update(self, value, color=None, sub=""):
        pct    = (value - self.vmin) / (self.vmax - self.vmin)
        pct    = max(0.0, min(1.0, pct))
        extent = GAUGE_SWEEP * pct
        c      = color or self.default_color

        self.canvas.itemconfig(self._arc, extent=extent, outline=c)

        label = f"{int(round(value))}%" if self.unit == "%" else f"{value:.1f}{self.unit}"

        self.canvas.itemconfig(self._val_text, text=label, fill=c)
        self.canvas.itemconfig(self._sub_text, text=sub.upper(), fill=FG_DIM)
        self._big_label.config(text=label, fg=c)

        if self._fahr_label is not None:
            self._fahr_label.config(text=f"{value * 9/5 + 32:.1f} °F")


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Garden Monitor")
        self.configure(bg=BG)
        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))
        self.bind("<F11>",    lambda e: self.attributes(
            "-fullscreen", not self.attributes("-fullscreen")))

        self._ser     = None
        self._running = False

        self._build_header()
        self._build_conn_bar()
        self._build_gauges()
        self._build_status_bar()

    # ------------------------------------------------------------------ build

    def _build_header(self):
        f = tk.Frame(self, bg=CARD_BG)
        f.pack(fill="x")

        tk.Label(f, text="Garden Monitor",
                 font=("Helvetica", 28, "bold"),
                 bg=CARD_BG, fg=ACCENT).pack(side="left", padx=28, pady=16)

        tk.Label(f, text="Connected Plant Station",
                 font=("Helvetica", 13),
                 bg=CARD_BG, fg=FG_DIM).pack(side="left", padx=4, pady=16)

    def _build_conn_bar(self):
        f = tk.Frame(self, bg=BAR_BG)
        f.pack(fill="x")

        lbl = lambda t: tk.Label(f, text=t, bg=BAR_BG, fg=FG_DIM,
                                 font=("Helvetica", 11))

        lbl("Port:").pack(side="left", padx=(16, 3), pady=8)
        self._port_var = tk.StringVar(value=PORT)
        tk.Entry(f, textvariable=self._port_var, width=14,
                 bg=BG, fg=FG, insertbackground=FG,
                 relief="flat", font=("Helvetica", 11)).pack(side="left", padx=3)

        lbl("Baud:").pack(side="left", padx=(12, 3))
        self._baud_var = tk.StringVar(value=str(BAUD))
        tk.Entry(f, textvariable=self._baud_var, width=8,
                 bg=BG, fg=FG, insertbackground=FG,
                 relief="flat", font=("Helvetica", 11)).pack(side="left", padx=3)

        self._conn_btn = tk.Button(f, text="Connect",
                                   command=self._toggle,
                                   bg=ACCENT, fg="white",
                                   relief="flat", padx=16, pady=4,
                                   font=("Helvetica", 11, "bold"),
                                   cursor="hand2")
        self._conn_btn.pack(side="left", padx=16, pady=8)

        tk.Label(f, text="ESC — exit fullscreen   F11 — toggle",
                 bg=BAR_BG, fg=FG_DIM,
                 font=("Helvetica", 10)).pack(side="right", padx=16)

    def _build_gauges(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(expand=True, fill="both")

        f = tk.Frame(outer, bg=BG)
        f.place(relx=0.5, rely=0.5, anchor="center")

        self._light = Gauge(f, "Luminosity",  "#f9a825")
        self._temp  = Gauge(f, "Temperature", "#4fc3f7",
                            unit="°C", vmin=0, vmax=50,
                            show_fahrenheit=True)
        self._moist = Gauge(f, "Moisture",    "#29b6f6")

        for i, g in enumerate((self._light, self._temp, self._moist)):
            g.grid(row=0, column=i, padx=22, pady=10)

    def _build_status_bar(self):
        f = tk.Frame(self, bg=CARD_BG)
        f.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(value="Disconnected")
        tk.Label(f, textvariable=self._status_var,
                 bg=CARD_BG, fg=FG_DIM,
                 font=("Helvetica", 11)).pack(side="left", padx=16, pady=6)

    # ----------------------------------------------------------------- serial

    def _toggle(self):
        if self._running:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        try:
            self._ser = serial.Serial(
                self._port_var.get(), int(self._baud_var.get()), timeout=2)
            self._running = True
            self._conn_btn.config(text="Disconnect", bg=RED_BTN)
            self._status("Connected — waiting for data...")
            threading.Thread(target=self._read_loop, daemon=True).start()
        except Exception as e:
            self._status(f"Connection failed: {e}")

    def _disconnect(self):
        self._running = False
        if self._ser:
            self._ser.close()
            self._ser = None
        self._conn_btn.config(text="Connect", bg=ACCENT)
        self._status("Disconnected")

    def _read_loop(self):
        while self._running:
            try:
                raw   = self._ser.readline().decode("utf-8", errors="ignore")
                parts = raw.strip().split(",")
                if len(parts) == 3:
                    light    = int(parts[0])
                    temp     = float(parts[1])
                    moisture = int(parts[2])
                    self.after(0, self._refresh, light, temp, moisture)
            except Exception:
                if self._running:
                    self.after(0, self._status, "Read error — check connection")
                break

    def _refresh(self, light, temp, moisture):
        tc = temp_color(temp)
        mc = moisture_color(moisture)

        self._light.update(light,
                           sub="bright" if light >= 80 else "dim")
        self._temp.update(temp, color=tc,
                          sub="cool" if temp < 20 else ("warm" if temp <= 25 else "hot"))
        self._moist.update(moisture, color=mc,
                           sub="wet" if moisture >= 60 else ("ok" if moisture >= 30 else "dry"))

        self._status(
            f"Light: {light}%     Temperature: {temp:.1f} °C  /  {temp*9/5+32:.1f} °F"
            f"     Moisture: {moisture}%"
        )

    def _status(self, msg):
        self._status_var.set(msg)


if __name__ == "__main__":
    Dashboard().mainloop()
