"""GUI interface for librelyrics using tkinter."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from librelyrics.config import ConfigManager
from librelyrics.core import LibreLyrics, download_lyrics
from librelyrics.registry import load_all_plugins
from librelyrics.plugin_manager import install_plugin, remove_plugin, list_plugins
from librelyrics.logging_config import setup_logging

class LibreLyricsGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("LibreLyrics")
        self.geometry("600x400")

        self.config_manager = ConfigManager()

        # Setup logging so we don't crash if something logs
        setup_logging(verbose=False)

        # Create Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Download
        self.tab_download = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_download, text="Download Lyrics")
        self._setup_download_tab()

        # Tab 2: Settings
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_settings, text="Settings")
        self._setup_settings_tab()

        # Tab 3: Plugins
        self.tab_plugins = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_plugins, text="Plugins")
        self._setup_plugins_tab()

    def _setup_download_tab(self):
        frame = ttk.Frame(self.tab_download)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        lbl = ttk.Label(frame, text="Enter URL or Path:")
        lbl.pack(anchor=tk.W)

        self.url_entry = ttk.Entry(frame, width=60)
        self.url_entry.pack(fill=tk.X, pady=5)

        btn_fetch = ttk.Button(frame, text="Fetch Lyrics", command=self._on_fetch_clicked)
        btn_fetch.pack(pady=5)

        self.status_text = tk.Text(frame, height=10, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def _log_status(self, message: str):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def _on_fetch_clicked(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a URL or path.")
            return

        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)

        self._log_status(f"Fetching lyrics for: {url}")

        # Run fetch in a thread so UI doesn't freeze
        thread = threading.Thread(target=self._fetch_lyrics_thread, args=(url,))
        thread.start()

    def _fetch_lyrics_thread(self, url: str):
        try:
            ll = LibreLyrics()
            successful, failed = download_lyrics(ll, url)

            # Update UI from main thread
            self.after(0, self._log_status, f"Finished fetching.")
            if successful:
                self.after(0, self._log_status, f"Success: {len(successful)} tracks.")
            if failed:
                self.after(0, self._log_status, f"Failed: {len(failed)} tracks.")

            if not successful and not failed:
                 self.after(0, self._log_status, "No tracks downloaded (maybe skipped or none found).")
        except Exception as e:
            self.after(0, self._log_status, f"Error: {str(e)}")

    def _setup_settings_tab(self):
        frame = ttk.Frame(self.tab_settings)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Use a canvas and scrollbar to allow scrolling if there are many settings
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)

        self.settings_container = ttk.Frame(canvas)
        self.settings_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.settings_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # General Settings Section
        gen_lf = ttk.LabelFrame(self.settings_container, text="General Settings")
        gen_lf.pack(fill=tk.X, expand=True, padx=5, pady=5)

        lbl = ttk.Label(gen_lf, text="Download Folder:")
        lbl.pack(anchor=tk.W, padx=5, pady=2)

        path_frame = ttk.Frame(gen_lf)
        path_frame.pack(fill=tk.X, pady=2, padx=5)

        self.path_var = tk.StringVar(value=self.config_manager.get('download_path', 'downloads'))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, state='readonly')
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        btn_browse = ttk.Button(path_frame, text="Browse", command=self._on_browse_clicked)
        btn_browse.pack(side=tk.RIGHT)

        # Frame for dynamic plugin settings
        self.plugin_settings_frame = ttk.Frame(self.settings_container)
        self.plugin_settings_frame.pack(fill=tk.BOTH, expand=True)

        self.plugin_config_vars = {} # dict mapping plugin_name -> {key -> StringVar/BooleanVar}
        self._refresh_plugin_settings()

        # Save Button at the bottom
        btn_save = ttk.Button(self.settings_container, text="Save Settings", command=self._on_save_settings_clicked)
        btn_save.pack(pady=10)

    def _refresh_plugin_settings(self):
        # Clear existing plugin settings UI
        for widget in self.plugin_settings_frame.winfo_children():
            widget.destroy()

        self.plugin_config_vars.clear()

        config = self.config_manager.raw
        plugins = load_all_plugins(config)

        if 'plugins' not in config:
            config['plugins'] = {}

        for plugin_cls in plugins:
            meta = plugin_cls.META
            if not meta.config_schema:
                continue

            plugin_name = meta.name.lower()
            if plugin_name not in config['plugins']:
                config['plugins'][plugin_name] = plugin_cls.default_config()

            plugin_lf = ttk.LabelFrame(self.plugin_settings_frame, text=f"{meta.name} Plugin Settings")
            plugin_lf.pack(fill=tk.X, expand=True, padx=5, pady=5)

            self.plugin_config_vars[plugin_name] = {}

            for key, description in meta.config_schema.items():
                row_frame = ttk.Frame(plugin_lf)
                row_frame.pack(fill=tk.X, pady=2, padx=5)

                lbl = ttk.Label(row_frame, text=f"{description}:", width=30)
                lbl.pack(side=tk.LEFT, anchor=tk.W)

                current_value = config['plugins'][plugin_name].get(key, '')

                if isinstance(current_value, bool):
                    var = tk.BooleanVar(value=current_value)
                    chk = ttk.Checkbutton(row_frame, variable=var)
                    chk.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self.plugin_config_vars[plugin_name][key] = var
                else:
                    var = tk.StringVar(value=str(current_value))
                    entry = ttk.Entry(row_frame, textvariable=var)
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self.plugin_config_vars[plugin_name][key] = var

    def _on_browse_clicked(self):
        current_path = self.path_var.get()
        new_path = filedialog.askdirectory(initialdir=current_path, title="Select Download Folder")
        if new_path:
            self.path_var.set(new_path)

    def _on_save_settings_clicked(self):
        # Save general settings
        self.config_manager.set('download_path', self.path_var.get())

        # Save plugin settings
        config = self.config_manager.raw
        for plugin_name, keys_dict in self.plugin_config_vars.items():
            if plugin_name not in config['plugins']:
                config['plugins'][plugin_name] = {}
            for key, var in keys_dict.items():
                config['plugins'][plugin_name][key] = var.get()

        self.config_manager.save()
        messagebox.showinfo("Settings Saved", "Configuration saved successfully!")

    def _setup_plugins_tab(self):
        frame = ttk.Frame(self.tab_plugins)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # List of plugins
        lbl_list = ttk.Label(frame, text="Installed Plugins:")
        lbl_list.pack(anchor=tk.W)

        self.plugin_listbox = tk.Listbox(frame, height=8)
        self.plugin_listbox.pack(fill=tk.BOTH, expand=True, pady=5)

        self._refresh_plugin_list()

        # Install/Remove
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=5)

        lbl_install = ttk.Label(action_frame, text="Plugin Package Name:")
        lbl_install.pack(side=tk.LEFT)

        self.plugin_entry = ttk.Entry(action_frame, width=20)
        self.plugin_entry.pack(side=tk.LEFT, padx=5)

        btn_install = ttk.Button(action_frame, text="Install", command=self._on_install_plugin)
        btn_install.pack(side=tk.LEFT, padx=2)

        btn_remove = ttk.Button(action_frame, text="Remove Selected", command=self._on_remove_plugin)
        btn_remove.pack(side=tk.RIGHT, padx=2)

    def _refresh_plugin_list(self):
        self.plugin_listbox.delete(0, tk.END)
        config_raw = self.config_manager.raw
        try:
            plugins = list_plugins(config_raw)
            for p in plugins:
                # Store package name if available, otherwise module
                display_text = f"{p['name']} (Package: {p.get('package', p['module'])})"
                self.plugin_listbox.insert(tk.END, display_text)
                # Save the underlying package name for removal
                # It's hacky but works for the listbox
        except Exception as e:
            self.plugin_listbox.insert(tk.END, f"Error loading plugins: {e}")

    def _on_install_plugin(self):
        package = self.plugin_entry.get().strip()
        if not package:
            messagebox.showwarning("Warning", "Please enter a plugin package name.")
            return

        def worker():
            success = install_plugin(package)
            if success:
                self.after(0, messagebox.showinfo, "Success", f"Plugin '{package}' installed successfully.")
                self.after(0, self._refresh_plugin_list)
                self.after(0, self._refresh_plugin_settings)
                self.after(0, lambda: self.plugin_entry.delete(0, tk.END))
            else:
                self.after(0, messagebox.showerror, "Error", f"Failed to install plugin '{package}'.")

        # Run in thread so GUI doesn't freeze
        threading.Thread(target=worker).start()

    def _on_remove_plugin(self):
        selection = self.plugin_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a plugin from the list to remove.")
            return

        item_text = self.plugin_listbox.get(selection[0])
        # Parse package name from string like "Spotify (Package: librelyrics-spotify)"
        package = None
        if "(Package: " in item_text:
            package = item_text.split("(Package: ")[1].strip(")")

        if not package:
            messagebox.showerror("Error", "Could not determine package name.")
            return

        def worker():
            success = remove_plugin(package)
            if success:
                self.after(0, messagebox.showinfo, "Success", f"Plugin '{package}' removed successfully.")
                self.after(0, self._refresh_plugin_list)
                self.after(0, self._refresh_plugin_settings)
            else:
                self.after(0, messagebox.showerror, "Error", f"Failed to remove plugin '{package}'.")

        threading.Thread(target=worker).start()

def main():
    app = LibreLyricsGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
