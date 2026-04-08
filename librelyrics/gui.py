"""GUI interface for librelyrics using tkinter."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from librelyrics.config import ConfigManager
from librelyrics.core import LibreLyrics, download_lyrics
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

        lbl = ttk.Label(frame, text="Download Folder:")
        lbl.pack(anchor=tk.W)

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill=tk.X, pady=5)

        self.path_var = tk.StringVar(value=self.config_manager.get('download_path', 'downloads'))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, state='readonly')
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        btn_browse = ttk.Button(path_frame, text="Browse", command=self._on_browse_clicked)
        btn_browse.pack(side=tk.RIGHT)

    def _on_browse_clicked(self):
        current_path = self.path_var.get()
        new_path = filedialog.askdirectory(initialdir=current_path, title="Select Download Folder")
        if new_path:
            self.path_var.set(new_path)
            self.config_manager.set('download_path', new_path)
            self.config_manager.save()
            messagebox.showinfo("Settings Saved", f"Download path set to:\n{new_path}")

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
            else:
                self.after(0, messagebox.showerror, "Error", f"Failed to remove plugin '{package}'.")

        threading.Thread(target=worker).start()

def main():
    app = LibreLyricsGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
