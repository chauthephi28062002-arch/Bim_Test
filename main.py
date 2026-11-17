from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from file_renamer import (
    PreviewItem,
    RenameHistory,
    RenameOptions,
    filtered_files,
    perform_rename,
    preview_renames,
)


class FileRenamerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Windows File Renamer")
        self.geometry("1180x800")
        self.minsize(1000, 680)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        try:
            self.history = RenameHistory()
        except (OSError, ValueError) as error:
            messagebox.showerror("History could not be loaded", str(error))
            self.history = RenameHistory(path=Path.home() / "WindowsFileRenamer-history.json")

        self.folder_var = tk.StringVar()
        self.filter_var = tk.StringVar()
        self.prefix_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        self.find_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        self.remove_var = tk.StringVar()
        self.numbering_var = tk.BooleanVar(value=False)
        self.number_start_var = tk.StringVar(value="1")
        self.number_width_var = tk.StringVar(value="2")
        self.case_var = tk.StringVar(value="Keep")
        self.status_var = tk.StringVar(value="Choose a folder to get started.")
        self.files: list[Path] = []
        self.checked: set[str] = set()
        self.preview: list[PreviewItem] = []

        self._build_ui()
        self._refresh_undo_state()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Windows File Renamer", font=ctk.CTkFont(size=25, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Preview every change. Existing files are never overwritten.",
            text_color=("gray35", "gray70"), font=ctk.CTkFont(size=13)
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        folder_panel = ctk.CTkFrame(self, corner_radius=10)
        folder_panel.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        folder_panel.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(folder_panel, text="Folder", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(16, 10), pady=14
        )
        ctk.CTkEntry(folder_panel, textvariable=self.folder_var, placeholder_text="Select a folder").grid(
            row=0, column=1, sticky="ew", pady=12
        )
        ctk.CTkButton(folder_panel, text="Browse...", width=110, command=self._browse).grid(
            row=0, column=2, padx=10, pady=12
        )
        ctk.CTkLabel(folder_panel, text="Extensions", text_color=("gray35", "gray70")).grid(
            row=0, column=3, padx=(6, 8)
        )
        extension_entry = ctk.CTkEntry(
            folder_panel, width=170, textvariable=self.filter_var,
            placeholder_text="All files or .jpg,.png"
        )
        extension_entry.grid(row=0, column=4, padx=(0, 10), pady=12)
        extension_entry.bind("<Return>", lambda _event: self._load_folder())
        ctk.CTkButton(folder_panel, text="Load", width=76, command=self._load_folder).grid(
            row=0, column=5, padx=(0, 14), pady=12
        )

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 12))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        self._build_file_list(body)
        self._build_settings(body)

        footer = ctk.CTkFrame(self, corner_radius=10)
        footer.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=self.status_var, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=12
        )
        self.undo_button = ctk.CTkButton(
            footer, text="Undo last batch", width=145, fg_color="gray35",
            hover_color="gray25", command=self._undo
        )
        self.undo_button.grid(row=0, column=1, padx=(8, 8), pady=10)
        ctk.CTkButton(
            footer, text="Preview checked", width=145, command=self._preview_checked
        ).grid(row=0, column=2, padx=8, pady=10)
        ctk.CTkButton(
            footer, text="Rename checked", width=145, command=self._rename_checked
        ).grid(row=0, column=3, padx=8, pady=10)
        ctk.CTkButton(
            footer, text="Rename all visible", width=170,
            fg_color="#16845b", hover_color="#116b49", command=self._rename_all
        ).grid(row=0, column=4, padx=(8, 14), pady=10)

    def _build_file_list(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(parent, corner_radius=10)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(panel, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        toolbar.grid_columnconfigure(0, weight=1)
        self.file_count_label = ctk.CTkLabel(toolbar, text="Files")
        self.file_count_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(toolbar, text="Select all", width=84, height=28, command=self._select_all).grid(
            row=0, column=1, padx=4
        )
        ctk.CTkButton(toolbar, text="Clear", width=64, height=28, fg_color="gray35",
                      hover_color="gray25", command=self._clear_selection).grid(row=0, column=2)

        table_frame = ctk.CTkFrame(panel, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Renamer.Treeview", background="#20242c", foreground="#e7eaf0",
            fieldbackground="#20242c", rowheight=29, borderwidth=0
        )
        style.configure(
            "Renamer.Treeview.Heading", background="#2b303a", foreground="#e7eaf0",
            font=("Segoe UI", 9, "bold"), relief="flat"
        )
        style.map("Renamer.Treeview", background=[("selected", "#24456a")])
        self.tree = ttk.Treeview(
            table_frame, columns=("check", "original", "proposed"),
            show="headings", style="Renamer.Treeview", selectmode="browse"
        )
        self.tree.heading("check", text="✓")
        self.tree.heading("original", text="Original name")
        self.tree.heading("proposed", text="Proposed name")
        self.tree.column("check", width=42, minwidth=42, stretch=False, anchor="center")
        self.tree.column("original", width=250, minwidth=120)
        self.tree.column("proposed", width=250, minwidth=120)
        self.tree.tag_configure("changed", foreground="#76d7a5")
        self.tree.tag_configure("invalid", foreground="#ff7777")
        self.tree.tag_configure("conflict", foreground="#ffbd66")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.tree.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )
        self.tree.bind("<Button-1>", self._tree_click)

    def _build_settings(self, parent: ctk.CTkFrame) -> None:
        panel = ctk.CTkScrollableFrame(parent, label_text="Rename settings", corner_radius=10)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        panel.grid_columnconfigure(1, weight=1)
        row = 0

        def add_entry(label: str, variable: tk.StringVar, placeholder: str = "") -> None:
            nonlocal row
            ctk.CTkLabel(panel, text=label).grid(row=row, column=0, sticky="w", padx=(12, 8), pady=7)
            ctk.CTkEntry(panel, textvariable=variable, placeholder_text=placeholder).grid(
                row=row, column=1, sticky="ew", padx=(0, 12), pady=7
            )
            row += 1

        add_entry("Prefix", self.prefix_var, "Add to filename start")
        add_entry("Suffix", self.suffix_var, "Add before extension")
        add_entry("Find text", self.find_var)
        add_entry("Replace with", self.replace_var)
        add_entry("Text to remove", self.remove_var)

        ctk.CTkLabel(panel, text="Capitalization").grid(
            row=row, column=0, sticky="w", padx=(12, 8), pady=7
        )
        ctk.CTkOptionMenu(
            panel, variable=self.case_var,
            values=["Keep", "UPPERCASE", "lowercase", "Title Case"]
        ).grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=7)
        row += 1

        ctk.CTkCheckBox(panel, text="Add sequential numbering", variable=self.numbering_var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6)
        )
        row += 1
        ctk.CTkLabel(panel, text="Start / digits").grid(
            row=row, column=0, sticky="w", padx=(12, 8), pady=7
        )
        number_frame = ctk.CTkFrame(panel, fg_color="transparent")
        number_frame.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=7)
        number_frame.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkEntry(number_frame, textvariable=self.number_start_var, placeholder_text="1").grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ctk.CTkEntry(number_frame, textvariable=self.number_width_var, placeholder_text="2").grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )
        row += 1
        ctk.CTkLabel(
            panel, text="The original extension is preserved automatically.",
            text_color=("gray40", "gray65"), wraplength=300, justify="left"
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 16))

    def _browse(self) -> None:
        initial = self.folder_var.get() or str(Path.home())
        selected = filedialog.askdirectory(parent=self, initialdir=initial, mustexist=True)
        if selected:
            self.folder_var.set(selected)
            self._load_folder()

    def _load_folder(self) -> None:
        folder = Path(self.folder_var.get()).expanduser()
        if not folder.is_dir():
            self.status_var.set("Select a valid folder.")
            return
        try:
            self.files = filtered_files(folder, self.filter_var.get())
        except OSError as error:
            messagebox.showerror("Could not read folder", str(error), parent=self)
            return
        self.checked.clear()
        self.preview = []
        self._render_files()
        self.status_var.set(f"Loaded {len(self.files)} file(s) from {folder}")

    def _render_files(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, path in enumerate(self.files):
            self.tree.insert(
                "", "end", iid=str(index),
                values=("☑" if str(path) in self.checked else "☐", path.name, "")
            )
        self.file_count_label.configure(
            text=f"{len(self.files)} file(s)  ·  {len(self.checked)} checked"
        )

    def _tree_click(self, event: tk.Event) -> str | None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item:
            return None
        if column == "#1":
            path = self.files[int(item)]
            if str(path) in self.checked:
                self.checked.remove(str(path))
            else:
                self.checked.add(str(path))
            self._render_files()
            return "break"
        return None

    def _select_all(self) -> None:
        self.checked = {str(path) for path in self.files}
        self._render_files()

    def _clear_selection(self) -> None:
        self.checked.clear()
        self._render_files()

    def _selected_files(self) -> list[Path]:
        return [path for path in self.files if str(path) in self.checked]

    def _build_rename_options(self) -> RenameOptions:
        try:
            start = int(self.number_start_var.get() or "1")
            width = int(self.number_width_var.get() or "2")
            if start < 0 or width < 1 or width > 12:
                raise ValueError
        except ValueError as error:
            raise ValueError("Number start must be non-negative and digits must be from 1 to 12.") from error
        return RenameOptions(
            prefix=self.prefix_var.get(),
            suffix=self.suffix_var.get(),
            find_text=self.find_var.get(),
            replace_text=self.replace_var.get(),
            remove_characters=self.remove_var.get(),
            case_mode=self.case_var.get(),
            add_number=self.numbering_var.get(),
            number_start=start,
            number_width=width,
        )

    def _make_preview(self, sources: list[Path]) -> list[PreviewItem] | None:
        if not sources:
            self.status_var.set("Check at least one file first.")
            return None
        try:
            items = preview_renames(sources, self._build_rename_options())
        except ValueError as error:
            messagebox.showerror("Invalid setting", str(error), parent=self)
            return None
        self.preview = items
        item_ids = {path: str(index) for index, path in enumerate(self.files)}
        for item in items:
            iid = item_ids[item.source]
            values = (
                "☑" if str(item.source) in self.checked else "☐",
                item.source.name, item.proposed_name
            )
            tags: tuple[str, ...] = ()
            if item.errors:
                tags = ("conflict" if any("exists" in error or "Multiple" in error for error in item.errors)
                        else "invalid",)
            elif item.changed:
                tags = ("changed",)
            self.tree.item(iid, values=values, tags=tags)
        failures = [item for item in items if item.errors]
        changed = sum(item.changed for item in items)
        if failures:
            self.status_var.set(
                f"Preview: {changed} change(s), {len(failures)} issue(s). "
                f"{failures[0].source.name}: {failures[0].errors[0]}"
            )
        else:
            self.status_var.set(f"Preview ready: {changed} file(s) will be renamed.")
        return items

    def _preview_checked(self) -> None:
        self._make_preview(self._selected_files())

    def _rename_checked(self) -> None:
        self._rename(self._selected_files())

    def _rename_all(self) -> None:
        if not self.files:
            self.status_var.set("Load a folder first.")
            return
        self._rename(list(self.files))

    def _rename(self, sources: list[Path]) -> None:
        items = self._make_preview(sources)
        if items is None:
            return
        failures = [item for item in items if item.errors]
        if failures:
            messagebox.showwarning(
                "Fix preview issues",
                "Resolve all invalid names and conflicts before renaming.\n\n"
                + "\n".join(
                    f"{item.source.name}: {', '.join(item.errors)}"
                    for item in failures[:8]
                ),
                parent=self,
            )
            return
        pairs = [(item.source, item.destination) for item in items if item.changed]
        if not pairs:
            self.status_var.set("No filenames would change.")
            return
        summary = "\n".join(f"{source.name}  →  {destination.name}" for source, destination in pairs[:8])
        if len(pairs) > 8:
            summary += f"\n…and {len(pairs) - 8} more"
        if not messagebox.askyesno(
            "Confirm rename",
            f"Rename {len(pairs)} file(s)?\n\n{summary}\n\nYou can undo this batch.",
            parent=self,
        ):
            return
        try:
            perform_rename(pairs)
            try:
                self.history.record(pairs)
            except OSError as error:
                perform_rename([(destination, source) for source, destination in pairs])
                raise OSError(f"Rename was rolled back because history could not be saved: {error}") from error
        except OSError as error:
            messagebox.showerror("Rename failed", str(error), parent=self)
            self._load_folder()
            return
        self._load_folder()
        self._refresh_undo_state()
        self.status_var.set(f"Successfully renamed {len(pairs)} file(s).")

    def _undo(self) -> None:
        if not self.history.entries:
            return
        if not messagebox.askyesno(
            "Undo last batch", "Restore the filenames from the most recent rename batch?",
            parent=self,
        ):
            return
        try:
            pairs = self.history.undo_latest()
        except (OSError, ValueError) as error:
            messagebox.showerror("Undo failed", str(error), parent=self)
            return
        self._load_folder()
        self._refresh_undo_state()
        self.status_var.set(f"Undid {len(pairs)} rename(s).")

    def _refresh_undo_state(self) -> None:
        self.undo_button.configure(state="normal" if self.history.entries else "disabled")


if __name__ == "__main__":
    FileRenamerApp().mainloop()
