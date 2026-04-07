#!/usr/bin/env python3

import os
import queue
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

CHORUS_PATH = os.path.expanduser("~/ai_chorus")

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
BRAILLE_SPINNER_RE = re.compile(r"^[\u2800-\u28FF\s]+")


def clean_chunk(text: str) -> str:
    text = text.replace("\r", "\n")
    text = ANSI_RE.sub("", text)
    text = CTRL_RE.sub("", text)
    return text


def clean_line(line: str) -> str:
    line = BRAILLE_SPINNER_RE.sub("", line)
    line = re.sub(r"\s+", " ", line).rstrip()
    return line


def is_heading(s: str) -> bool:
    s = s.strip()
    return (
        not s
        or s.startswith("===")
        or s.startswith("[") and "| score=" in s
        or s.startswith("⚖️")
        or s.startswith("💀")
        or s.startswith("🧠")
        or s.startswith("🌐")
        or (s.startswith("**") and s.endswith("**"))
    )


def is_list_item(s: str) -> bool:
    s = s.lstrip()
    return s.startswith("* ") or s.startswith("- ") or re.match(r"^\d+\.\s", s) is not None


def fix_split_duplicates(text: str) -> str:
    # chall challenge -> challenge
    text = re.sub(r"\b([A-Za-z]{1,12})\s+\1([A-Za-z]{1,20})\b", r"\1\2", text)
    # might might -> might
    text = re.sub(r"\b([A-Za-z]+)\s+\1\b", r"\1", text)
    return text


def reflow_text(text: str) -> str:
    raw_lines = [clean_line(line) for line in text.splitlines()]
    out = []
    i = 0

    while i < len(raw_lines):
        s = raw_lines[i].strip()

        if not s:
            if not out or out[-1] != "":
                out.append("")
            i += 1
            continue

        if is_heading(s):
            out.append(s)
            i += 1
            continue

        if is_list_item(s):
            bullet = s
            i += 1
            while i < len(raw_lines):
                nxt = raw_lines[i].strip()
                if not nxt or is_heading(nxt) or is_list_item(nxt):
                    break
                bullet += " " + nxt
                i += 1
            out.append(fix_split_duplicates(bullet))
            continue

        para = s
        i += 1
        while i < len(raw_lines):
            nxt = raw_lines[i].strip()
            if not nxt or is_heading(nxt) or is_list_item(nxt):
                break
            para += " " + nxt
            i += 1
        out.append(fix_split_duplicates(para))

    cleaned = []
    prev_blank = False
    for line in out:
        if line == "":
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    return "\n".join(cleaned).strip() + "\n"


class ChorusApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI Chorus")
        self.root.geometry("1200x820")
        self.root.minsize(850, 500)

        self.proc = None
        self.queue = queue.Queue()
        self.raw_output_buffer = []

        self._build_ui()
        self._poll_queue()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        title = ttk.Label(outer, text="AI Chorus", font=("TkDefaultFont", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            outer,
            text="Runs your local ~/ai_chorus script and shows the full debate output.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 10))

        paned = ttk.Panedwindow(outer, orient="vertical")
        paned.grid(row=2, column=0, sticky="nsew")

        prompt_pane = ttk.Frame(paned)
        prompt_pane.columnconfigure(0, weight=1)
        prompt_pane.rowconfigure(1, weight=1)

        ttk.Label(prompt_pane, text="Prompt").grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.prompt_text = tk.Text(
            prompt_pane,
            height=6,
            wrap="word",
            undo=True,
            font=("TkDefaultFont", 11),
        )
        self.prompt_text.grid(row=1, column=0, sticky="nsew")
        self.prompt_text.insert("1.0", "why is earth called earth?")

        prompt_scroll = ttk.Scrollbar(prompt_pane, orient="vertical", command=self.prompt_text.yview)
        prompt_scroll.grid(row=1, column=1, sticky="ns")
        self.prompt_text.configure(yscrollcommand=prompt_scroll.set)

        output_pane = ttk.Frame(paned)
        output_pane.columnconfigure(0, weight=1)
        output_pane.rowconfigure(1, weight=1)

        ttk.Label(output_pane, text="Output").grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.output = tk.Text(
            output_pane,
            wrap="word",
            state="disabled",
            font=("TkDefaultFont", 11),
        )
        self.output.grid(row=1, column=0, sticky="nsew")

        output_scroll = ttk.Scrollbar(output_pane, orient="vertical", command=self.output.yview)
        output_scroll.grid(row=1, column=1, sticky="ns")
        self.output.configure(yscrollcommand=output_scroll.set)

        paned.add(prompt_pane, weight=1)
        paned.add(output_pane, weight=4)

        controls = ttk.Frame(outer, padding=(0, 10, 0, 0))
        controls.grid(row=3, column=0, sticky="ew")
        controls.columnconfigure(5, weight=1)

        self.run_btn = ttk.Button(controls, text="Run Chorus", command=self.run_chorus)
        self.run_btn.grid(row=0, column=0, padx=(0, 8))

        self.clear_btn = ttk.Button(controls, text="Clear Output", command=self.clear_output)
        self.clear_btn.grid(row=0, column=1, padx=(0, 8))

        self.stop_btn = ttk.Button(controls, text="Stop", command=self.stop_chorus, state="disabled")
        self.stop_btn.grid(row=0, column=2, padx=(0, 8))

        self.save_btn = ttk.Button(controls, text="Save Output", command=self.save_output)
        self.save_btn.grid(row=0, column=3, padx=(0, 8))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=5, sticky="e")

    def render_output(self):
        combined = "".join(self.raw_output_buffer)
        cleaned = reflow_text(combined)

        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", cleaned)
        self.output.see("end")
        self.output.configure(state="disabled")

    def append_output(self, text: str):
        cleaned = clean_chunk(text)
        if cleaned:
            self.raw_output_buffer.append(cleaned)
            self.render_output()

    def clear_output(self):
        self.raw_output_buffer.clear()
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.status_var.set("Ready")

    def save_output(self):
        content = self.output.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Nothing to save", "There is no output to save yet.")
            return

        path = filedialog.asksaveasfilename(
            title="Save Chorus Output",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            self.status_var.set(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def run_chorus(self):
        if not os.path.exists(CHORUS_PATH):
            messagebox.showerror("Missing script", f"Could not find:\n{CHORUS_PATH}")
            return

        if self.proc is not None:
            messagebox.showinfo("Already running", "Chorus is already running.")
            return

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("No prompt", "Enter a prompt first.")
            return

        self.clear_output()
        self.status_var.set("Running...")
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        thread = threading.Thread(target=self._run_process, args=(prompt,), daemon=True)
        thread.start()

    def _run_process(self, prompt: str):
        try:
            env = os.environ.copy()
            env["TERM"] = "dumb"

            self.proc = subprocess.Popen(
                [CHORUS_PATH, prompt],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            assert self.proc.stdout is not None

            for line in self.proc.stdout:
                self.queue.put(("output", line))

            returncode = self.proc.wait()
            self.queue.put(("done", returncode))

        except Exception as e:
            self.queue.put(("error", str(e)))

    def stop_chorus(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.status_var.set("Stopping...")
            except Exception as e:
                messagebox.showerror("Stop failed", str(e))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()

                if kind == "output":
                    self.append_output(payload)
                elif kind == "done":
                    self.proc = None
                    self.run_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.status_var.set(f"Finished (exit {payload})")
                    self.render_output()
                elif kind == "error":
                    self.proc = None
                    self.run_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.status_var.set("Error")
                    messagebox.showerror("Error", payload)

        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    ChorusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
EOF
