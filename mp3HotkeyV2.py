import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import pygame
import keyboard
import threading
import os
import json
import time

pygame.mixer.init()

# ---------------- DESIGN ----------------
BG_COLOR = "#0f0f0f"
TILE_COLOR = "#1c1c1c"
TEXT_COLOR = "#ffffff"
HOTKEY_TEXT_COLOR = "#000000"
ACCENT = "#ff8039"
ACCENT_HOVER = "#ffa066"
PROGRESS_COLOR = "#ff8039"
STATUS_COLOR = "#00ff00"

PRESETS_FILE = "presets.json"

def load_json(p):
    if not os.path.exists(p):
        return {}
    with open(p, "r") as f:
        return json.load(f)

def save_json(p, d):
    with open(p, "w") as f:
        json.dump(d, f, indent=4)

# ---------------- SOUND TILE ----------------
class SoundTile:
    def __init__(self, master, index, parent_app=None):
        self.index = index
        self.parent_app = parent_app
        self.sound = None
        self.filepath = None
        self.is_playing = False
        self.channel = pygame.mixer.Channel(index)
        self.start_time = 0
        self.hotkey = None
        self.muted = False
        self.prev_volume = 100
        self.volume_val = 100

        # ----- Tile -----
        self.frame = tk.Frame(master, bg=TILE_COLOR, width=330, height=310,
                              highlightbackground=ACCENT, highlightthickness=2)
        self.frame.grid_propagate(False)
        self.frame.grid(row=index//3, column=index%3, padx=15, pady=15)

        # ----- Name -----
        self.name_var = tk.StringVar(value=f"Sound {index+1}")
        self.name_entry = tk.Entry(self.frame, textvariable=self.name_var, justify="center",
                                   fg=TEXT_COLOR, bg=TILE_COLOR, insertbackground=TEXT_COLOR,
                                   bd=0, font=("Segoe UI", 12, "bold"))
        self.name_entry.pack(pady=(10,5))
        self.name_entry.bind("<FocusOut>", self.save_name)

        # ----- Drag & Drop + Click File -----
        self.drop = tk.Label(self.frame, text="🎵\nDrag MP3 here or click", fg=TEXT_COLOR, bg="#2a2a2a",
                             relief="ridge", width=26, height=3, font=("Segoe UI", 10),
                             justify="center", wraplength=240)
        self.drop.pack(pady=5, padx=5)
        self.drop.drop_target_register(DND_FILES)
        self.drop.dnd_bind("<<Drop>>", self.load_file)
        self.drop.bind("<Button-1>", lambda e: self.select_file())

        # ----- Hotkey -----
        self.hotkey_var = tk.StringVar(value="No HotKey")
        self.hotkey_entry = tk.Entry(self.frame, textvariable=self.hotkey_var,
                                     justify="center", bd=0, fg=HOTKEY_TEXT_COLOR,
                                     bg=TILE_COLOR, insertbackground=TEXT_COLOR,
                                     state="readonly", font=("Segoe UI", 10))
        self.hotkey_entry.pack(pady=5)

        self.hotkey_btn = tk.Button(self.frame, text="⌨️ Set Hotkey",
                                    bg=ACCENT, fg=HOTKEY_TEXT_COLOR, bd=0,
                                    activebackground=ACCENT_HOVER,
                                    font=("Segoe UI", 10),
                                    relief="flat",
                                    command=self.start_hotkey_record)
        self.hotkey_btn.pack(pady=5, ipadx=8, ipady=3)

        # ----- Volume (Canvas Slider mit Glanz) -----
        vol_frame = tk.Frame(self.frame, bg=TILE_COLOR)
        vol_frame.pack(pady=10, fill="x", padx=15)

        self.vol_icon = tk.Label(vol_frame, text="🔊", bg=TILE_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 20))
        self.vol_icon.pack(side="left", padx=(0,8))
        self.vol_icon.bind("<Button-1>", self.toggle_mute)

        self.vol_canvas = tk.Canvas(vol_frame, width=200, height=10, bg="#555555", bd=0, highlightthickness=0)
        self.vol_canvas.pack(side="left", fill="x", expand=True)
        # Handle: Hauptteil + Glanz
        self.vol_handle_bg = self.vol_canvas.create_rectangle(0, 0, 20, 10, fill=ACCENT, width=0)
        self.vol_handle_gloss = self.vol_canvas.create_rectangle(0, 0, 20, 4, fill="#ffb366", width=0)
        self.vol_canvas.bind("<Button-1>", self.set_volume_from_click)
        self.vol_canvas.bind("<B1-Motion>", self.set_volume_from_drag)

        # ----- Duration -----
        self.time_var = tk.StringVar(value="00:00 / 00:00")
        self.time_label = tk.Label(self.frame, textvariable=self.time_var,
                                   fg=TEXT_COLOR, bg=TILE_COLOR, font=("Segoe UI", 10))
        self.time_label.pack(pady=(5,0))

        # ----- Progress Bar -----
        self.progress_canvas = tk.Canvas(self.frame, width=260, height=8,
                                         bg="#333333", bd=0, highlightthickness=0)
        self.progress_canvas.pack(pady=(5,0))
        self.progress_rect = self.progress_canvas.create_rectangle(0, 0, 0, 8, fill=PROGRESS_COLOR, width=0)

        threading.Thread(target=self.update_time_progress, daemon=True).start()

    # ---------------- VOLUME FUNCTIONS ----------------
    def set_volume_from_click(self, event):
        self.update_volume_canvas(event.x)

    def set_volume_from_drag(self, event):
        self.update_volume_canvas(event.x)

    def update_volume_canvas(self, x):
        x = max(0, min(200, x))
        self.vol_canvas.coords(self.vol_handle_bg, 0, 0, x, 10)
        self.vol_canvas.coords(self.vol_handle_gloss, 0, 0, x, 4)
        vol = int((x/200)*100)
        self.volume_val = vol
        if vol == 0:
            self.muted = True
            self.vol_icon.config(text="🔇")
        else:
            self.muted = False
            self.vol_icon.config(text="🔊")
            self.prev_volume = vol
        if self.sound and self.channel.get_busy():
            self.channel.set_volume(vol/100)

    # ---------------- FILE/HOTKEY FUNCTIONS ----------------
    def load_file(self, event):
        path = event.data.strip("{}")
        if path.lower().endswith(".mp3"):
            self.set_file(path)

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("MP3 Files", "*.mp3")])
        if path:
            self.set_file(path)

    def set_file(self, path):
        self.filepath = path
        self.sound = pygame.mixer.Sound(path)
        self.drop.config(text=os.path.basename(path))

    def play_stop(self):
        if self.sound:
            if self.channel.get_busy():
                self.channel.stop()
                self.is_playing = False
            else:
                self.channel.set_volume(self.volume_val/100)
                self.channel.play(self.sound)
                self.is_playing = True
                self.start_time = time.time()

    def start_hotkey_record(self):
        self.hotkey_var.set("Press a key …")
        self.frame.bind_all("<Key>", self.record_hotkey)

    def record_hotkey(self, event):
        key_pressed = event.keysym
        if self.parent_app and self.parent_app.is_hotkey_taken(key_pressed, self.index):
            messagebox.showwarning("Hotkey Conflict", f"Hotkey '{key_pressed}' is already taken!")
            self.hotkey_var.set("No HotKey")
            return
        if hasattr(self, 'hotkey') and self.hotkey:
            keyboard.remove_hotkey(self.hotkey)
        self.hotkey = key_pressed
        keyboard.add_hotkey(self.hotkey, lambda: threading.Thread(target=self.play_stop).start())
        self.hotkey_var.set(self.hotkey)
        self.frame.unbind_all("<Key>")

    def toggle_mute(self, event=None):
        if not self.sound:
            return
        if not self.muted:
            self.prev_volume = self.volume_val
            self.volume_val = 0
            self.channel.set_volume(0)
            self.vol_icon.config(text="🔇")
            self.muted = True
            self.vol_canvas.coords(self.vol_handle_bg, 0,0,0,10)
            self.vol_canvas.coords(self.vol_handle_gloss, 0,0,0,4)
        else:
            self.volume_val = self.prev_volume
            self.channel.set_volume(self.prev_volume/100)
            self.muted = False
            self.vol_icon.config(text="🔊")
            self.vol_canvas.coords(self.vol_handle_bg, 0,0,int(self.prev_volume/100*200),10)
            self.vol_canvas.coords(self.vol_handle_gloss, 0,0,int(self.prev_volume/100*200),4)

    # ---------------- SAVE / LOAD ----------------
    def save_name(self, event=None):
        pass

    def to_dict(self):
        return {
            "file": self.filepath,
            "name": self.name_var.get(),
            "volume": self.volume_val,
            "hotkey": getattr(self, "hotkey", None)
        }

    def from_dict(self, data):
        self.clear()
        if data.get("file") and os.path.exists(data["file"]):
            self.set_file(data["file"])
        self.name_var.set(data.get("name", self.name_var.get()))
        vol = data.get("volume", 100)
        self.volume_val = vol
        self.vol_canvas.coords(self.vol_handle_bg, 0,0,int(vol/100*200),10)
        self.vol_canvas.coords(self.vol_handle_gloss, 0,0,int(vol/100*200),4)
        if data.get("hotkey"):
            self.hotkey = data["hotkey"]
            keyboard.add_hotkey(self.hotkey, lambda: threading.Thread(target=self.play_stop).start())
            self.hotkey_var.set(self.hotkey)

    def clear(self):
        if hasattr(self, 'hotkey') and self.hotkey:
            keyboard.remove_hotkey(self.hotkey)
        self.channel.stop()
        self.sound = None
        self.filepath = None
        self.hotkey = None
        self.name_var.set(f"Sound {self.index+1}")
        self.hotkey_var.set("No HotKey")
        self.volume_val = 100
        self.muted = False
        self.vol_canvas.coords(self.vol_handle_bg, 0,0,200,10)
        self.vol_canvas.coords(self.vol_handle_gloss, 0,0,200,4)
        self.vol_icon.config(text="🔊")
        self.progress_canvas.coords(self.progress_rect, 0,0,0,8)
        self.drop.config(text="🎵\nDrag MP3 here or click")

    # ---------------- TIME / PROGRESS ----------------
    def update_time_progress(self):
        while True:
            if self.sound:
                total = self.sound.get_length()
                pos = 0
                if self.channel.get_busy():
                    pos = min(time.time()-self.start_time, total)
                self.time_var.set(f"{int(pos//60):02d}:{int(pos%60):02d} / {int(total//60):02d}:{int(total%60):02d}")
                w = int((pos/total)*260) if total>0 else 0
                self.progress_canvas.coords(self.progress_rect, 0,0,w,8)
            time.sleep(0.2)

# ---------------- APP ----------------
class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("mp3Hotkey")
        self.geometry("1180x680")
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)

        self.presets = load_json(PRESETS_FILE)
        self.current = None

        # ----- Left Panel -----
        left = tk.Frame(self, bg="#151515", width=240)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="Presets", bg="#151515", fg=TEXT_COLOR,
                 font=("Segoe UI", 13, "bold")).pack(pady=(10,5))

        self.list = tk.Listbox(left, bg="#202020", fg=TEXT_COLOR,
                               highlightthickness=1, selectbackground=ACCENT,
                               selectforeground=HOTKEY_TEXT_COLOR, font=("Segoe UI", 12),
                               height=20)
        self.list.pack(fill="both", expand=True, padx=10, pady=(0,5))
        self.list.bind("<<ListboxSelect>>", self.load_preset)

        for p in self.presets:
            self.list.insert(tk.END, p)

        btn_frame = tk.Frame(left, bg="#151515")
        btn_frame.pack(fill="x", padx=10, pady=10)
        for t, c in [
            ("➕ Add Preset", self.add_preset),
            ("Duplicate Preset", self.duplicate_preset),
            ("💾 Save Preset", self.save_preset),
            ("✏️ Rename Preset", self.rename_preset),
            ("Delete Preset", self.delete_preset)
        ]:
            tk.Button(btn_frame, text=t, bg=ACCENT, fg=HOTKEY_TEXT_COLOR, bd=0,
                      activebackground=ACCENT_HOVER, command=c).pack(fill="x", pady=4)

        # ----- Tiles -----
        grid = tk.Frame(self, bg=BG_COLOR)
        grid.pack(side="left", expand=True)
        self.tiles = [SoundTile(grid, i, parent_app=self) for i in range(6)]

        # ----- Status Label -----
        self.status_label = tk.Label(self, text="", bg=BG_COLOR, fg=STATUS_COLOR, font=("Segoe UI", 9))
        self.status_label.place(relx=1.0, rely=1.0, x=-15, y=-10, anchor="se")

    # ---------------- HOTKEY CONFLICT ----------------
    def is_hotkey_taken(self, key, index):
        if not self.current:
            return False
        for i, tile in enumerate(self.tiles):
            if i != index and tile.hotkey == key:
                return True
        return False

    # ---------------- PRESET ACTIONS ----------------
    def current_state(self):
        return {str(i): t.to_dict() for i, t in enumerate(self.tiles)}

    def save_preset(self, automatic=False):
        if not self.current:
            return
        self.presets[self.current] = self.current_state()
        save_json(PRESETS_FILE, self.presets)
        msg = (f'Preset "{self.current}" automatically saved'
               if automatic else f'Preset "{self.current}" successfully saved')
        self.status_label.config(text=msg)
        self.after(6000, lambda: self.status_label.config(text=""))

    def load_preset(self, _):
        sel = self.list.curselection()
        if not sel:
            return
        name = self.list.get(sel[0])
        if name == self.current:
            return

        if self.current:
            current_state = self.current_state()
            saved_state = self.presets.get(self.current, {})
            if current_state != saved_state:
                self.save_preset(automatic=True)

        self.current = name
        for i, t in enumerate(self.tiles):
            t.clear()
            if str(i) in self.presets[name]:
                t.from_dict(self.presets[name][str(i)])

        self.list.selection_clear(0, tk.END)
        idx = self.list.get(0, tk.END).index(name)
        self.list.selection_set(idx)
        self.list.activate(idx)
        self.list.see(idx)

    def add_preset(self):
        name = simpledialog.askstring("New Preset", "Preset name:", parent=self)
        if not name or name in self.presets:
            return
        self.presets[name] = {}
        self.list.insert(tk.END, name)
        self.current = name
        for t in self.tiles:
            t.clear()
        self.list.selection_clear(0, tk.END)
        self.list.selection_set(tk.END)
        self.list.activate(tk.END)

    def duplicate_preset(self):
        if not self.current:
            return
        new_name = simpledialog.askstring("Duplicate Preset", "New preset name:", parent=self)
        if not new_name or new_name in self.presets:
            return
        self.presets[new_name] = json.loads(json.dumps(self.presets[self.current]))
        self.list.insert(tk.END, new_name)

    def rename_preset(self):
        if not self.current:
            return
        n = simpledialog.askstring("Rename Preset", "New name:",
                                   initialvalue=self.current, parent=self)
        if n:
            self.presets[n] = self.presets.pop(self.current)
            self.current = n
            save_json(PRESETS_FILE, self.presets)
            self.refresh_listbox()
            idx = self.list.get(0, tk.END).index(n)
            self.list.selection_clear(0, tk.END)
            self.list.selection_set(idx)
            self.list.activate(idx)
            self.list.see(idx)

    def delete_preset(self):
        if not self.current:
            return
        if messagebox.askyesno("Delete Preset", f"Delete '{self.current}'?", parent=self):
            del self.presets[self.current]
            save_json(PRESETS_FILE, self.presets)
            self.current = None
            self.refresh_listbox()
            for t in self.tiles:
                t.clear()

    def refresh_listbox(self):
        existing = list(self.list.get(0, tk.END))
        for p in self.presets:
            if p not in existing:
                self.list.insert(tk.END, p)

App().mainloop()
