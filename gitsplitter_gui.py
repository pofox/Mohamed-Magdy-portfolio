import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import sys
import io
import gitsplitter  # Your script file (rename gitsplitter.py to be importable)

class RedirectLogger(io.StringIO):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def write(self, message):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, message)
        self.widget.see(tk.END)
        self.widget.configure(state='disabled')

    def flush(self):
        pass

class GitSplitterUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Git Large File Splitter")

        # Frame for options
        options_frame = ttk.Frame(root)
        options_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(options_frame, text="Mode:").pack(side="left", padx=5)
        self.mode_var = tk.StringVar(value="push")
        mode_menu = ttk.Combobox(options_frame, textvariable=self.mode_var, values=["push", "pull"], state="readonly")
        mode_menu.pack(side="left", padx=5)

        ttk.Label(options_frame, text="Size Limit (MB):").pack(side="left", padx=5)
        self.size_limit_var = tk.IntVar(value=100)
        ttk.Entry(options_frame, textvariable=self.size_limit_var, width=5).pack(side="left", padx=5)

        ttk.Button(options_frame, text="Run", command=self.run_script).pack(side="left", padx=10)

        # Frame for lists
        lists_frame = ttk.Frame(root)
        lists_frame.pack(padx=10, pady=5, fill="both", expand=True)

        # Tracked large files
        tracked_frame = ttk.LabelFrame(lists_frame, text="Tracked Large Files")
        tracked_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.tracked_list = tk.Listbox(tracked_frame)
        self.tracked_list.pack(fill="both", expand=True, padx=5, pady=5)

        # Changed files
        changed_frame = ttk.LabelFrame(lists_frame, text="Changed Files")
        changed_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.changed_list = tk.Listbox(changed_frame)
        self.changed_list.pack(fill="both", expand=True, padx=5, pady=5)

        # Log output
        log_frame = ttk.LabelFrame(root, text="Log Output")
        log_frame.pack(padx=10, pady=5, fill="both", expand=True)
        self.log_box = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, state='disabled')
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)

        self.load_file_lists()

    def load_file_lists(self):
        tracked_files = gitsplitter.load_tracked_large_files()
        self.tracked_list.delete(0, tk.END)
        for f in tracked_files:
            self.tracked_list.insert(tk.END, f)

        changed_files = gitsplitter.get_changed_and_new_files()
        self.changed_list.delete(0, tk.END)
        for f in changed_files:
            self.changed_list.insert(tk.END, f)

    def run_script(self):
        mode = self.mode_var.get()
        size_limit = self.size_limit_var.get()

        def task():
            logger = RedirectLogger(self.log_box)
            sys.stdout = logger
            sys.stderr = logger
            try:
                sys.argv = ["", f"--size-limit={size_limit}", mode]
                gitsplitter.main()
            except Exception as e:
                print(f"[ERROR] {e}")
            finally:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                self.load_file_lists()

        threading.Thread(target=task).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = GitSplitterUI(root)
    root.mainloop()
