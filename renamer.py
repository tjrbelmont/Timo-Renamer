import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Timo Renamer"
ICON_FILENAME = "blood_moon.ico"

FORMAT_CNC4 = "CNC4"
FORMAT_CNC3 = "CNC3"


def get_icon_path():
    """Return absolute path to the icon file, working in both source and
    PyInstaller-bundled environments."""
    # When bundled with PyInstaller --onefile, resources live in sys._MEIPASS
    base_dir = getattr(sys, "_MEIPASS", None)
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, ICON_FILENAME)


def hide_console_window():
    if os.name != 'nt':
        return

    try:
        import ctypes

        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, 0)
            ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def get_parent_folder_name(folder_path):
    return os.path.basename(os.path.abspath(os.path.join(folder_path, os.pardir)))


def get_parent_folder_id(folder_path):
    return get_parent_folder_name(folder_path)[:5]


def get_maxilla_code(filename):
    name_lower = filename.lower()
    if "upper" in name_lower:
        return "U"
    if "lower" in name_lower:
        return "L"
    if "U" in filename:
        return "U"
    if "L" in filename:
        return "L"
    raise ValueError(f"Unable to determine upper/lower from filename: {filename}")


def get_movement_code(filename):
    base_name = os.path.splitext(filename)[0]
    if len(base_name) < 9:
        raise ValueError(f"Filename is too short to parse movement from: {filename}")

    # Check if already in CNC4 format
    if "-" in base_name:
        parts = base_name.split("-")
        if len(parts) >= 3 and len(parts[1]) == 3 and parts[1][0] in "UL" and parts[1][1:].isdigit():
            return parts[1][1:].zfill(2)

    # Check if already in CNC3 format (parent name + Inf/Sup + NN)
    for marker in ("Inf", "Sup"):
        idx = base_name.rfind(marker)
        if idx != -1:
            tail = base_name[idx + len(marker):].strip()
            if tail.isdigit():
                return tail.zfill(2)

    # Original logic
    tail = base_name[8:]
    if tail.startswith("1-0"):
        return "00"

    movement_digits = []
    for char in tail:
        if char.isdigit():
            movement_digits.append(char)
        else:
            break

    if not movement_digits:
        raise ValueError(f"Unable to parse movement number from: {filename}")

    return str(int("".join(movement_digits))).zfill(2)


def get_suffix_for_movement(movement_code):
    """Return the file suffix letter based on movement code.
    Movement 00 gets -B, all others get -A. CNC4 only."""
    return "B" if movement_code == "00" else "A"


def build_new_name(filename, folder_path, output_format):
    maxilla = get_maxilla_code(filename)
    movement = get_movement_code(filename)

    if output_format == FORMAT_CNC3:
        parent_name = get_parent_folder_name(folder_path)
        if not parent_name:
            raise ValueError("Could not determine parent folder name.")
        side = "Sup" if maxilla == "U" else "Inf"
        return f"{parent_name} {side} {movement}.stl"

    # Default: CNC4
    folder_id = get_parent_folder_id(folder_path)
    if not folder_id:
        raise ValueError("Could not determine ID from the parent folder name.")
    suffix = get_suffix_for_movement(movement)
    return f"{folder_id}-{maxilla}{movement}-{suffix}.stl"


def get_folder_entries(folder_path):
    try:
        return sorted([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith('.stl')], key=lambda name: name.lower())
    except Exception:
        return []


def get_predicted_names(folder_path, output_format):
    stl_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.stl') and os.path.isfile(os.path.join(folder_path, f))]
    stl_files.sort()
    predicted = []
    for filename in stl_files:
        try:
            predicted.append(build_new_name(filename, folder_path, output_format))
        except Exception:
            predicted.append("")
    return predicted


def rename_stl_files(folder_path, output_format):
    stl_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.stl') and os.path.isfile(os.path.join(folder_path, f))]
    total_stl = len(stl_files)
    if total_stl == 0:
        return [], 0

    stl_files.sort()
    renamed_pairs = []

    for filename in stl_files:
        old_path = os.path.join(folder_path, filename)
        new_name = build_new_name(filename, folder_path, output_format)
        new_path = os.path.join(folder_path, new_name)

        if old_path == new_path:
            continue

        if os.path.exists(new_path):
            raise FileExistsError(f"Target filename already exists: {new_name}")

        os.rename(old_path, new_path)
        renamed_pairs.append((old_path, new_path))

    return renamed_pairs, total_stl


class RenamerApp(tk.Tk):
    DARK_BG = "#181818"
    DARK_PANEL = "#232323"
    DARK_TEXT = "#e8e8e8"
    DARK_ENTRY = "#2d2d2d"
    DARK_BUTTON = "#333333"
    DARK_BUTTON_ACTIVE = "#4a4a4a"
    DARK_SCROLL = "#3d3d3d"
    ROW_ALT_BG = "#252525"
    AFTER_TEXT = "#a31515"
    RED_BUTTON = "#5a0d0d"
    RED_BUTTON_ACTIVE = "#7a1818"
    RED_SCROLL = "#a31515"
    RED_SCROLL_ACTIVE = "#c92020"

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(True, True)
        self.geometry("760x460")
        self.configure(bg=self.DARK_BG)
        self._apply_icon()

        self.folder_path = tk.StringVar()
        self.output_format = tk.StringVar(value=FORMAT_CNC4)
        self.last_renames = []
        self.before_listbox = None
        self.after_listbox = None
        self.scrollbar = None

        self._setup_styles()
        self._build_ui()

    def _apply_icon(self):
        """Set the window/taskbar icon. Silently no-ops if the icon file is missing."""
        icon_path = get_icon_path()
        if not os.path.isfile(icon_path):
            return
        try:
            # iconbitmap handles title bar + taskbar on Windows
            self.iconbitmap(default=icon_path)
        except Exception:
            # Fallback for non-Windows or if iconbitmap fails: PhotoImage via iconphoto
            try:
                img = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, img)
                self._icon_image = img  # keep a reference so it isn't GC'd
            except Exception:
                pass

    def _setup_styles(self):
        """Configure a red ttk.Scrollbar style that overrides native Windows drawing."""
        style = ttk.Style(self)
        # 'clam' is one of the few built-in themes that actually honors custom colors on Windows
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        style.configure(
            "Red.Vertical.TScrollbar",
            background=self.RED_SCROLL,
            troughcolor=self.DARK_PANEL,
            bordercolor=self.DARK_BG,
            arrowcolor=self.DARK_TEXT,
            lightcolor=self.RED_SCROLL,
            darkcolor=self.RED_SCROLL,
            gripcount=0,
        )
        style.map(
            "Red.Vertical.TScrollbar",
            background=[
                ('pressed', self.RED_SCROLL_ACTIVE),
                ('active', self.RED_SCROLL_ACTIVE),
            ],
            arrowcolor=[('disabled', self.DARK_PANEL)],
        )

    def _build_ui(self):
        frame = tk.Frame(self, padx=16, pady=16, bg=self.DARK_BG)
        frame.pack(fill=tk.BOTH, expand=True)

        label = tk.Label(frame, text="Ingrese la carpeta STL del caso en Casos Terminados:", bg=self.DARK_BG, fg=self.DARK_TEXT)
        label.grid(row=0, column=0, sticky="w")

        entry = tk.Entry(frame, textvariable=self.folder_path, width=50, bg=self.DARK_ENTRY, fg=self.DARK_TEXT, insertbackground=self.DARK_TEXT, highlightthickness=1, highlightbackground="#444444")
        entry.grid(row=1, column=0, sticky="we", padx=(0, 8), pady=(4, 12))
        entry.bind('<Return>', lambda event: self.on_folder_load())

        search_button = tk.Button(frame, text="Buscar", width=12, command=self.on_folder_load, bg=self.RED_BUTTON, fg=self.DARK_TEXT, activebackground=self.RED_BUTTON_ACTIVE, relief=tk.FLAT)
        search_button.grid(row=1, column=1, pady=(4, 12))

        browse_button = tk.Button(frame, text="Explorar...", width=12, command=self.on_browse, bg=self.RED_BUTTON, fg=self.DARK_TEXT, activebackground=self.RED_BUTTON_ACTIVE, relief=tk.FLAT)
        browse_button.grid(row=2, column=1, pady=(0, 8))

        # Format selector
        format_frame = tk.Frame(frame, bg=self.DARK_BG)
        format_frame.grid(row=2, column=0, sticky="w", pady=(0, 8))

        format_label = tk.Label(format_frame, text="Formato:", bg=self.DARK_BG, fg=self.DARK_TEXT)
        format_label.pack(side=tk.LEFT, padx=(0, 8))

        cnc4_radio = tk.Radiobutton(
            format_frame, text="CNC4", variable=self.output_format, value=FORMAT_CNC4,
            command=self.on_format_change, bg=self.DARK_BG, fg=self.DARK_TEXT,
            selectcolor=self.RED_BUTTON, activebackground=self.DARK_BG,
            activeforeground=self.DARK_TEXT, highlightthickness=0,
        )
        cnc4_radio.pack(side=tk.LEFT, padx=(0, 8))

        cnc3_radio = tk.Radiobutton(
            format_frame, text="CNC3", variable=self.output_format, value=FORMAT_CNC3,
            command=self.on_format_change, bg=self.DARK_BG, fg=self.DARK_TEXT,
            selectcolor=self.RED_BUTTON, activebackground=self.DARK_BG,
            activeforeground=self.DARK_TEXT, highlightthickness=0,
        )
        cnc3_radio.pack(side=tk.LEFT)

        before_label = tk.Label(frame, text="Antes de renombrar:", bg=self.DARK_BG, fg=self.DARK_TEXT, font=("TkDefaultFont", 11, "bold"))
        before_label.grid(row=3, column=0, sticky="w", pady=(4, 0))

        after_label = tk.Label(frame, text="Despues de renombrar:", bg=self.DARK_BG, fg=self.DARK_TEXT, font=("TkDefaultFont", 11, "bold"))
        after_label.grid(row=3, column=1, sticky="w", pady=(4, 0))

        list_frame = tk.Frame(frame, bg=self.DARK_BG)
        list_frame.grid(row=4, column=0, columnspan=2, sticky="nsew")

        self.undo_button = tk.Button(frame, text="Deshacer", width=12, command=self.on_undo, state=tk.DISABLED, bg=self.RED_BUTTON, fg=self.DARK_TEXT, activebackground=self.RED_BUTTON_ACTIVE, disabledforeground="#8a6060", relief=tk.FLAT)
        self.undo_button.grid(row=5, column=0, pady=(8, 0), sticky="w")

        self.rename_button = tk.Button(frame, text="Renombrar", width=12, command=self.on_rename, bg=self.RED_BUTTON, fg=self.DARK_TEXT, activebackground=self.RED_BUTTON_ACTIVE, disabledforeground="#8a6060", relief=tk.FLAT)
        self.rename_button.grid(row=5, column=1, pady=(8, 0), sticky="e")

        before_frame = tk.Frame(list_frame, bg=self.DARK_PANEL)
        before_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.before_listbox = tk.Listbox(before_frame, height=14, bg=self.DARK_BG, fg=self.DARK_TEXT, selectbackground="#4f76b4", selectforeground="#ffffff", bd=0, highlightthickness=0, exportselection=False, activestyle="none", font=("TkDefaultFont", 9, "normal"))
        self.before_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        divider = tk.Frame(list_frame, width=8, bg="#4b4b4b")
        divider.pack(side=tk.LEFT, fill=tk.Y, pady=8)

        after_frame = tk.Frame(list_frame, bg=self.DARK_PANEL)
        after_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.after_listbox = tk.Listbox(after_frame, height=14, bg=self.DARK_BG, fg=self.AFTER_TEXT, selectbackground="#4f76b4", selectforeground="#ffffff", bd=0, highlightthickness=0, font=("TkDefaultFont", 9, "bold"), exportselection=False, activestyle="none")
        self.after_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.on_sync_scroll, style="Red.Vertical.TScrollbar")
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.before_listbox.config(yscrollcommand=self.on_scrollbar_set)
        self.after_listbox.config(yscrollcommand=self.on_scrollbar_set)

        self.before_listbox.bind('<MouseWheel>', self.on_mousewheel)
        self.after_listbox.bind('<MouseWheel>', self.on_mousewheel)
        self.before_listbox.bind('<<ListboxSelect>>', self.on_before_select)
        self.after_listbox.bind('<<ListboxSelect>>', self.on_after_select)
        self._syncing_selection = False

        self.status_label = tk.Label(frame, text="Pegue la ubicacion de la carpeta o use Explorar, y luego haga clic en Renombrar.", bg=self.DARK_BG, fg="#b0b0b0")
        self.status_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(4, weight=1)

    def on_browse(self):
        selected_folder = filedialog.askdirectory(title="Seleccione la carpeta STL del caso en Casos Terminados")
        if selected_folder:
            self.folder_path.set(selected_folder)
            self.on_folder_load()

    def on_folder_load(self):
        folder = self.folder_path.get().strip()
        if not folder:
            self.status_label.config(text="Por favor pegue o seleccione una carpeta primero.", fg="#ff6b6b")
            return

        if not os.path.isdir(folder):
            self.status_label.config(text="La ubicacion no es una carpeta valida.", fg="#ff6b6b")
            return

        self.status_label.config(text="Carpeta cargada. Lista para renombrar.", fg="#b0f5a8")
        self.update_before_list(folder)
        self.update_after_list(get_predicted_names(folder, self.output_format.get()))
        self.last_renames = []
        self.undo_button.config(state=tk.DISABLED)
        self.rename_button.config(state=tk.NORMAL)

    def on_format_change(self):
        folder = self.folder_path.get().strip()
        if folder and os.path.isdir(folder):
            self.update_after_list(get_predicted_names(folder, self.output_format.get()))

    def update_before_list(self, folder_path):
        if not self.before_listbox:
            return

        self.before_listbox.delete(0, tk.END)
        entries = get_folder_entries(folder_path)
        for entry in entries:
            self.before_listbox.insert(tk.END, entry)
        self._apply_row_banding(self.before_listbox, len(entries))

    def update_after_list(self, entries):
        if not self.after_listbox:
            return

        self.after_listbox.delete(0, tk.END)
        for entry in entries:
            self.after_listbox.insert(tk.END, entry)
        self._apply_row_banding(self.after_listbox, len(entries))

    def _apply_row_banding(self, listbox, count):
        """Alternate row backgrounds so rows are visually separated."""
        for i in range(count):
            bg = self.DARK_BG if i % 2 == 0 else self.ROW_ALT_BG
            listbox.itemconfig(i, background=bg)

    def on_rename(self):
        folder = self.folder_path.get().strip()
        if not folder:
            messagebox.showwarning("No Folder", "Por favor pegue o seleccione una carpeta primero.")
            return

        if not os.path.isdir(folder):
            messagebox.showerror("Invalid Folder", f"La ubicacion no es una carpeta valida:\n{folder}")
            return

        try:
            renamed_pairs, total_stl = rename_stl_files(folder, self.output_format.get())
            if total_stl == 0:
                self.last_renames = []
                self.undo_button.config(state=tk.DISABLED)
                self.status_label.config(text="No se encontraron archivos STL en la carpeta seleccionada.", fg="#ff6b6b")
                self.update_after_list([])
            else:
                self.last_renames = renamed_pairs
                self.undo_button.config(state=tk.NORMAL if renamed_pairs else tk.DISABLED)
                if renamed_pairs:
                    self.status_label.config(text=f"Renombrados {len(renamed_pairs)} archivo(s) STL.", fg="#b0f5a8")
                    self.rename_button.config(state=tk.DISABLED)
                else:
                    self.status_label.config(text="No files needed renaming.", fg="#b0f5a8")
                    self.rename_button.config(state=tk.DISABLED)
                self.update_before_list(folder)
                self.update_after_list(get_predicted_names(folder, self.output_format.get()))
        except Exception as exc:
            self.last_renames = []
            self.undo_button.config(state=tk.DISABLED)
            messagebox.showerror("Rename Failed", f"An error occurred while renaming files:\n{exc}")
            self.status_label.config(text="Renombrado fallido. Vea el mensaje de error.", fg="#ff6b6b")

    def on_undo(self):
        if not self.last_renames:
            return

        try:
            for old_path, new_path in reversed(self.last_renames):
                if os.path.exists(new_path) and not os.path.exists(old_path):
                    os.rename(new_path, old_path)
            self.status_label.config(text="Deshacer completo.", fg="#b0f5a8")
            folder = self.folder_path.get().strip()
            if os.path.isdir(folder):
                self.update_before_list(folder)
                self.update_after_list(get_predicted_names(folder, self.output_format.get()))
                self.rename_button.config(state=tk.NORMAL)
        except Exception as exc:
            messagebox.showerror("Undo Failed", f"An error occurred while undoing:\n{exc}")
            self.status_label.config(text="Undo failed. See error message.", fg="#ff6b6b")
        finally:
            self.last_renames = []
            self.undo_button.config(state=tk.DISABLED)

    def on_before_select(self, event):
        self._sync_selection_from(self.before_listbox, self.after_listbox)

    def on_after_select(self, event):
        self._sync_selection_from(self.after_listbox, self.before_listbox)

    def _sync_selection_from(self, source, target):
        if self._syncing_selection:
            return
        selected = source.curselection()
        if not selected:
            return
        index = selected[0]
        if index >= target.size():
            return
        self._syncing_selection = True
        try:
            target.selection_clear(0, tk.END)
            target.selection_set(index)
            target.see(index)
        finally:
            self._syncing_selection = False

    def on_scrollbar_set(self, first, last):
        if self.before_listbox and self.after_listbox:
            self.before_listbox.yview_moveto(first)
            self.after_listbox.yview_moveto(first)
        if self.scrollbar:
            self.scrollbar.set(first, last)

    def on_sync_scroll(self, *args):
        if self.before_listbox and self.after_listbox:
            self.before_listbox.yview(*args)
            self.after_listbox.yview(*args)
        if self.scrollbar:
            self.scrollbar.set(*args)

    def on_mousewheel(self, event):
        delta = -1 if event.delta > 0 else 1
        if self.before_listbox and self.after_listbox:
            self.before_listbox.yview_scroll(delta, 'units')
            self.after_listbox.yview_scroll(delta, 'units')
            if self.scrollbar:
                self.scrollbar.set(*self.before_listbox.yview())
            return "break"


if __name__ == "__main__":
    hide_console_window()
    app = RenamerApp()
    app.mainloop()