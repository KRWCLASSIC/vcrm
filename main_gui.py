import tkinter as tk
from tkinter import ttk
import asyncio
import subprocess
from pathlib import Path
import json
import shutil

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("VCRedist Manager")
        
        # Console View
        self.console_view = tk.Text(root, height=10, width=50)
        self.console_view.pack(pady=10)

        # Version Dropdown
        self.version_var = tk.StringVar()
        self.version_dropdown = ttk.Combobox(root, textvariable=self.version_var)
        self.version_dropdown.pack(pady=5)

        # Checkboxes
        self.iov_var = tk.BooleanVar()
        self.show_32bit_var = tk.BooleanVar()
        self.no_cleanup_var = tk.BooleanVar()

        self.iov_checkbox = tk.Checkbutton(root, text="Include Old Versions (Not recommended)", variable=self.iov_var, command=self.update_versions)
        self.iov_checkbox.pack(anchor='w')

        self.show_32bit_checkbox = tk.Checkbutton(root, text="Show 32-bit Versions (Doesn't work)", variable=self.show_32bit_var, command=self.update_versions)
        self.show_32bit_checkbox.pack(anchor='w')

        self.no_cleanup_checkbox = tk.Checkbutton(root, text="No Cleanup", variable=self.no_cleanup_var)
        self.no_cleanup_checkbox.pack(anchor='w')

        # Buttons
        self.run_button = tk.Button(root, text="Run (Will freeze the app)", command=self.run_async)
        self.run_button.pack(pady=5)

        self.cleanup_button = tk.Button(root, text="Perform Cleanup", command=self.cleanup_async)
        self.cleanup_button.pack(pady=5)

        self.remove_runtimes_button = tk.Button(root, text="Remove Runtimes", command=self.remove_runtimes_async)
        self.remove_runtimes_button.pack(pady=5)

        # Load versions into dropdown
        self.load_versions()

    def load_versions(self):
        # Load versions from vcredists.json
        with open('vcredists.json', 'r') as f:
            config = json.load(f)
            versions = [runtime['version'] for runtime in config['runtimes']['x64']]
            
            # Filter versions based on the checkbox state
            if not self.iov_var.get():  # If the checkbox is not checked
                # Exclude old versions (e.g., versions < 14)
                versions = [v for v in versions if int(v.split('.')[0]) >= 14]

            self.version_dropdown['values'] = versions

    def update_versions(self):
        # Update the dropdown values based on the checkbox state
        self.load_versions()

        # Check if both checkboxes are checked
        if self.iov_var.get() and self.show_32bit_var.get():
            self.version_dropdown.set("All")  # Set dropdown to "All"
            self.version_dropdown['values'] = ["All"]  # Only show "All"

    async def run(self):
        # Prepare command-line arguments
        args = [
            'python', 'main_cli.py',  # Adjust the command if necessary
        ]

        # Add optional arguments based on user input
        if self.iov_var.get():
            args.append('--include-old-versions')
        if self.no_cleanup_var.get():
            args.append('--no-cleanup')
        args.append('--silent')

        # Only add version argument if "All" is not selected
        if self.version_var.get() != "All":
            args.append('--version')
            args.append(self.version_var.get())

        # Run the CLI command in a separate thread
        result = await asyncio.to_thread(subprocess.run, args, capture_output=True, text=True)
        self.console_view.insert(tk.END, result.stdout + "\n")
        if result.stderr:
            self.console_view.insert(tk.END, "Error: " + result.stderr + "\n")

    async def cleanup(self):
        # Prepare command-line arguments for cleanup
        args = [
            'python', 'main_cli.py',  # Adjust the command if necessary
            '-c',  # Use -c for cleanup
            '--silent' if self.no_cleanup_var.get() else ''
        ]

        # Filter out empty arguments
        args = [arg for arg in args if arg]

        # Run the CLI command in a separate thread
        result = await asyncio.to_thread(subprocess.run, args, capture_output=True, text=True)
        self.console_view.insert(tk.END, result.stdout + "\n")
        if result.stderr:
            self.console_view.insert(tk.END, "Error: " + result.stderr + "\n")

    async def remove_runtimes(self):
        # Prepare command-line arguments for removing runtimes
        args = [
            'python', 'main_cli.py',  # Adjust the command if necessary
            '-rv'  # Use -rv for removing runtimes
        ]

        # Run the CLI command in a separate thread
        result = await asyncio.to_thread(subprocess.run, args, capture_output=True, text=True)
        self.console_view.insert(tk.END, result.stdout + "\n")
        if result.stderr:
            self.console_view.insert(tk.END, "Error: " + result.stderr + "\n")

    def run_async(self):
        asyncio.run(self.run())

    def cleanup_async(self):
        asyncio.run(self.cleanup())

    def remove_runtimes_async(self):
        asyncio.run(self.remove_runtimes())

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
