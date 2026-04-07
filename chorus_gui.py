#!/usr/bin/env python3

import os
import queue
import re
import subprocess
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

CHORUS_PATH = os.path.expanduser("~/ai_chorus")

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
BRAILLE_SPINNER_RE = re.compile(r"^[\u2800-\u28FF\s]+")
SCORE_RE = re.compile(r"^\[(creative|practical|systems|critic)\s+\|\s+score=(\d+)\]$", re.IGNORECASE)


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
        or (s.startswith("[") and "| score=" in s)
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
    text = re.sub(r"\b([A-Za-z]{1,12})\s+\1([A-Za-z]{1,20})\b", r"\1\2", text)
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
        self.root.geometry("1420x1040")
        self.root.minsize(1040, 780)

        self.proc = None
        self.queue = queue.Queue()
        self.raw_output_buffer = []
        self.last_main_prompt = ""
        self.marker_counter = 0
        self.scroll_to_marker = None

        self.pending_task_save_enabled = False
        self.pending_task_save_path = ""
        self.pending_task_marker = None
        self.current_temp_prompt_file = None

        self._build_ui()
        self._setup_tags()
        self._poll_queue()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        title = ttk.Label(outer, text="AI Chorus", font=("TkDefaultFont", 20, "bold"))
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            outer,
            text="Run a debate, reply to it, or ask the chorus to complete a concrete task such as writing Python.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 12))

        paned = ttk.Panedwindow(outer, orient="vertical")
        paned.grid(row=2, column=0, sticky="nsew")

        prompt_pane = ttk.Frame(paned, padding=8)
        prompt_pane.columnconfigure(0, weight=1)
        prompt_pane.rowconfigure(1, weight=1)

        prompt_label = ttk.Label(prompt_pane, text="Debate question", font=("TkDefaultFont", 11, "bold"))
        prompt_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.prompt_text = tk.Text(
            prompt_pane,
            height=4,
            wrap="word",
            undo=True,
            font=("TkDefaultFont", 12),
            padx=8,
            pady=8,
        )
        self.prompt_text.grid(row=1, column=0, sticky="nsew")

        prompt_scroll = ttk.Scrollbar(prompt_pane, orient="vertical", command=self.prompt_text.yview)
        prompt_scroll.grid(row=1, column=1, sticky="ns")
        self.prompt_text.configure(yscrollcommand=prompt_scroll.set)

        output_pane = ttk.Frame(paned, padding=8)
        output_pane.columnconfigure(0, weight=1)
        output_pane.rowconfigure(1, weight=1)

        output_label = ttk.Label(output_pane, text="Debate output", font=("TkDefaultFont", 11, "bold"))
        output_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.output = tk.Text(
            output_pane,
            wrap="word",
            state="disabled",
            font=("TkDefaultFont", 12),
            padx=10,
            pady=10,
            bg="#fcfcfc",
        )
        self.output.grid(row=1, column=0, sticky="nsew")

        output_scroll = ttk.Scrollbar(output_pane, orient="vertical", command=self.output.yview)
        output_scroll.grid(row=1, column=1, sticky="ns")
        self.output.configure(yscrollcommand=output_scroll.set)

        reply_pane = ttk.Frame(paned, padding=8)
        reply_pane.columnconfigure(0, weight=1)
        reply_pane.rowconfigure(1, weight=1)

        reply_label = ttk.Label(reply_pane, text="Reply to the chorus", font=("TkDefaultFont", 11, "bold"))
        reply_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.reply_text = tk.Text(
            reply_pane,
            height=4,
            wrap="word",
            undo=True,
            font=("TkDefaultFont", 12),
            padx=8,
            pady=8,
        )
        self.reply_text.grid(row=1, column=0, sticky="nsew")

        reply_scroll = ttk.Scrollbar(reply_pane, orient="vertical", command=self.reply_text.yview)
        reply_scroll.grid(row=1, column=1, sticky="ns")
        self.reply_text.configure(yscrollcommand=reply_scroll.set)

        task_pane = ttk.Frame(paned, padding=8)
        task_pane.columnconfigure(0, weight=1)
        task_pane.columnconfigure(1, weight=0)
        task_pane.rowconfigure(1, weight=1)

        task_label = ttk.Label(task_pane, text="Task for the chorus to complete", font=("TkDefaultFont", 11, "bold"))
        task_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.task_text = tk.Text(
            task_pane,
            height=4,
            wrap="word",
            undo=True,
            font=("TkDefaultFont", 12),
            padx=8,
            pady=8,
        )
        self.task_text.grid(row=1, column=0, columnspan=2, sticky="nsew")

        task_scroll = ttk.Scrollbar(task_pane, orient="vertical", command=self.task_text.yview)
        task_scroll.grid(row=1, column=2, sticky="ns")
        self.task_text.configure(yscrollcommand=task_scroll.set)

        file_frame = ttk.Frame(task_pane)
        file_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        file_frame.columnconfigure(1, weight=1)

        self.save_task_result_var = tk.BooleanVar(value=False)
        self.save_task_check = ttk.Checkbutton(
            file_frame,
            text="Save task result directly to file",
            variable=self.save_task_result_var,
        )
        self.save_task_check.grid(row=0, column=0, sticky="w", padx=(0, 10))

        ttk.Label(file_frame, text="Task output file:").grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.task_file_var = tk.StringVar(value="")
        self.task_file_entry = ttk.Entry(file_frame, textvariable=self.task_file_var)
        self.task_file_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=(8, 8))

        self.browse_task_file_btn = ttk.Button(file_frame, text="Browse", command=self.browse_task_output_file)
        self.browse_task_file_btn.grid(row=1, column=2, sticky="e", pady=(8, 0))

        paned.add(prompt_pane, weight=1)
        paned.add(output_pane, weight=5)
        paned.add(reply_pane, weight=1)
        paned.add(task_pane, weight=2)

        controls = ttk.Frame(outer, padding=(0, 12, 0, 0))
        controls.grid(row=3, column=0, sticky="ew")
        controls.columnconfigure(10, weight=1)

        self.run_btn = ttk.Button(controls, text="Run Debate", command=self.run_chorus)
        self.run_btn.grid(row=0, column=0, padx=(0, 8))

        self.reply_btn = ttk.Button(controls, text="Reply", command=self.reply_to_chorus)
        self.reply_btn.grid(row=0, column=1, padx=(0, 8))

        self.task_btn = ttk.Button(controls, text="Complete Task", command=self.complete_task)
        self.task_btn.grid(row=0, column=2, padx=(0, 8))

        self.open_btn = ttk.Button(controls, text="Open Saved Output", command=self.open_saved_output)
        self.open_btn.grid(row=0, column=3, padx=(0, 8))

        self.clear_btn = ttk.Button(controls, text="Clear Output", command=self.clear_output)
        self.clear_btn.grid(row=0, column=4, padx=(0, 8))

        self.stop_btn = ttk.Button(controls, text="Stop", command=self.stop_chorus, state="disabled")
        self.stop_btn.grid(row=0, column=5, padx=(0, 8))

        self.save_btn = ttk.Button(controls, text="Save Output", command=self.save_output)
        self.save_btn.grid(row=0, column=6, padx=(0, 8))

        self.copy_btn = ttk.Button(controls, text="Copy Output", command=self.copy_output)
        self.copy_btn.grid(row=0, column=7, padx=(0, 8))

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(controls, textvariable=self.status_var, font=("TkDefaultFont", 10, "italic"))
        status.grid(row=0, column=10, sticky="e")

    def _setup_tags(self):
        self.output.tag_configure("meta", foreground="#666666", font=("TkDefaultFont", 11, "italic"))
        self.output.tag_configure("round", foreground="#5a2ca0", font=("TkDefaultFont", 12, "bold"), spacing1=12, spacing3=8)
        self.output.tag_configure("final", foreground="#0b6e4f", font=("TkDefaultFont", 13, "bold"), spacing1=16, spacing3=10)
        self.output.tag_configure("section", foreground="#4a4a4a", font=("TkDefaultFont", 12, "bold"), spacing1=8, spacing3=4)
        self.output.tag_configure("speaker_creative", foreground="#ffffff", background="#9c27b0", font=("TkDefaultFont", 12, "bold"), lmargin1=10, lmargin2=10, spacing1=12, spacing3=4)
        self.output.tag_configure("speaker_practical", foreground="#ffffff", background="#1565c0", font=("TkDefaultFont", 12, "bold"), lmargin1=10, lmargin2=10, spacing1=12, spacing3=4)
        self.output.tag_configure("speaker_systems", foreground="#ffffff", background="#00897b", font=("TkDefaultFont", 12, "bold"), lmargin1=10, lmargin2=10, spacing1=12, spacing3=4)
        self.output.tag_configure("speaker_critic", foreground="#ffffff", background="#c62828", font=("TkDefaultFont", 12, "bold"), lmargin1=10, lmargin2=10, spacing1=12, spacing3=4)
        self.output.tag_configure("speaker_default", foreground="#ffffff", background="#555555", font=("TkDefaultFont", 12, "bold"), lmargin1=10, lmargin2=10, spacing1=12, spacing3=4)

        self.output.tag_configure("body_creative", foreground="#111111", background="#f7e9fb", font=("TkDefaultFont", 12), lmargin1=16, lmargin2=16, rmargin=16, spacing1=0, spacing3=8)
        self.output.tag_configure("body_practical", foreground="#111111", background="#eaf3ff", font=("TkDefaultFont", 12), lmargin1=16, lmargin2=16, rmargin=16, spacing1=0, spacing3=8)
        self.output.tag_configure("body_systems", foreground="#111111", background="#e8faf7", font=("TkDefaultFont", 12), lmargin1=16, lmargin2=16, rmargin=16, spacing1=0, spacing3=8)
        self.output.tag_configure("body_critic", foreground="#111111", background="#fdecec", font=("TkDefaultFont", 12), lmargin1=16, lmargin2=16, rmargin=16, spacing1=0, spacing3=8)
        self.output.tag_configure("body_default", foreground="#111111", background="#f4f4f4", font=("TkDefaultFont", 12), lmargin1=16, lmargin2=16, rmargin=16, spacing1=0, spacing3=8)

        self.output.tag_configure("dead", foreground="#a00000", font=("TkDefaultFont", 11, "bold"), spacing1=8, spacing3=8)
        self.output.tag_configure("problem", foreground="#444444", font=("TkDefaultFont", 12, "bold"), spacing1=8, spacing3=6)
        self.output.tag_configure("reply_marker", foreground="#8a4f00", font=("TkDefaultFont", 12, "bold"), spacing1=10, spacing3=8)
        self.output.tag_configure("task_marker", foreground="#004a99", font=("TkDefaultFont", 12, "bold"), spacing1=10, spacing3=8)

    def browse_task_output_file(self):
        path = filedialog.asksaveasfilename(
            title="Choose task output file",
            defaultextension=".py",
            filetypes=[
                ("Python files", "*.py"),
                ("Shell scripts", "*.sh"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.task_file_var.set(path)

    def _next_marker(self, prefix: str) -> str:
        self.marker_counter += 1
        return f"=== {prefix} {self.marker_counter} ==="

    def _scroll_to_marker_top(self, marker: str):
        idx = self.output.search(marker, "end", backwards=True)
        if not idx:
            return
        end_idx = self.output.index("end-1c")
        total_lines = max(1, int(end_idx.split(".")[0]))
        marker_line = max(1, int(idx.split(".")[0]))
        fraction = max(0.0, min(1.0, (marker_line - 1) / total_lines))
        self.output.yview_moveto(fraction)

    def clear_output(self):
        self.raw_output_buffer.clear()
        self.scroll_to_marker = None
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.status_var.set("Ready")

    def copy_output(self):
        content = self.output.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Nothing to copy", "There is no output to copy yet.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("Output copied")

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

    def open_saved_output(self):
        path = filedialog.askopenfilename(
            title="Open saved chorus output",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            self.raw_output_buffer = [text]
            self.scroll_to_marker = None
            self.render_output()
            self.status_var.set(f"Loaded: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def _set_running_state(self, running: bool, status_text: str):
        self.status_var.set(status_text)
        self.run_btn.configure(state="disabled" if running else "normal")
        self.reply_btn.configure(state="disabled" if running else "normal")
        self.task_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")

    def run_chorus(self):
        if not os.path.exists(CHORUS_PATH):
            messagebox.showerror("Missing script", f"Could not find:\n{CHORUS_PATH}")
            return

        if self.proc is not None:
            messagebox.showinfo("Already running", "Chorus is already running.")
            return

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("No question", "Please enter a question first.")
            return

        self.last_main_prompt = prompt
        self.clear_output()
        self._set_running_state(True, "Running debate...")

        thread = threading.Thread(target=self._run_process, args=(["/home/lee/ai_chorus", prompt],), daemon=True)
        thread.start()

    def reply_to_chorus(self):
        if self.proc is not None:
            messagebox.showinfo("Already running", "Wait for the current run to finish first.")
            return

        current_output = self.output.get("1.0", "end").strip()
        if not current_output:
            messagebox.showwarning("No debate output", "There is no chorus output to reply to yet.")
            return

        reply = self.reply_text.get("1.0", "end").strip()
        if not reply:
            messagebox.showwarning("No reply", "Write a reply first.")
            return

        if self.last_main_prompt:
            combined_prompt = (
                f"Original user question:\n{self.last_main_prompt}\n\n"
                f"Current chorus output:\n{current_output}\n\n"
                f"User reply / how to proceed:\n{reply}\n\n"
                f"Please continue the debate from there and respond directly to the user's follow-up."
            )
        else:
            combined_prompt = (
                f"Current chorus output:\n{current_output}\n\n"
                f"User reply / how to proceed:\n{reply}\n\n"
                f"Please continue the debate from there and respond directly to the user's follow-up."
            )

        marker = self._next_marker("USER FOLLOW-UP")
        self.raw_output_buffer.append(f"\n{marker}\n")
        self.raw_output_buffer.append(reply + "\n\n")
        self.scroll_to_marker = marker
        self.render_output()

        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
        tmp.write(combined_prompt)
        tmp.close()
        self.current_temp_prompt_file = tmp.name

        self._set_running_state(True, "Sending reply to chorus...")

        thread = threading.Thread(
            target=self._run_process,
            args=(["/home/lee/ai_chorus", "--prompt-file", self.current_temp_prompt_file],),
            daemon=True,
        )
        thread.start()

    def complete_task(self):
        if self.proc is not None:
            messagebox.showinfo("Already running", "Wait for the current run to finish first.")
            return

        current_output = self.output.get("1.0", "end").strip()
        if not current_output:
            messagebox.showwarning("No debate output", "Run or load a debate first.")
            return

        task = self.task_text.get("1.0", "end").strip()
        if not task:
            messagebox.showwarning("No task", "Write a task for the chorus first.")
            return

        save_enabled = self.save_task_result_var.get()
        save_path = self.task_file_var.get().strip()

        if save_enabled and not save_path:
            messagebox.showwarning("No output file", "Choose an output file for the task result.")
            return

        if self.last_main_prompt:
            big_prompt = (
                f"Original user question:\n{self.last_main_prompt}\n\n"
                f"Debate output so far:\n{current_output}\n\n"
                f"Task for you to complete:\n{task}\n\n"
                f"Do not continue debating.\n"
                f"Complete the task now.\n"
                f"If the task is code, output one clean runnable code solution only.\n"
                f"If the task is writing, output the finished text only.\n"
                f"Minimize filler.\n"
            )
        else:
            big_prompt = (
                f"Debate output so far:\n{current_output}\n\n"
                f"Task for you to complete:\n{task}\n\n"
                f"Do not continue debating.\n"
                f"Complete the task now.\n"
                f"If the task is code, output one clean runnable code solution only.\n"
                f"If the task is writing, output the finished text only.\n"
                f"Minimize filler.\n"
            )

        marker = self._next_marker("TASK REQUEST")
        self.raw_output_buffer.append(f"\n{marker}\n")
        self.raw_output_buffer.append(task + "\n\n")
        self.scroll_to_marker = marker
        self.render_output()

        self.pending_task_save_enabled = save_enabled
        self.pending_task_save_path = save_path
        self.pending_task_marker = marker

        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
        tmp.write(big_prompt)
        tmp.close()
        self.current_temp_prompt_file = tmp.name

        self._set_running_state(True, "Sending task to chorus...")

        thread = threading.Thread(
            target=self._run_process,
            args=(["/home/lee/ai_chorus", "--prompt-file", self.current_temp_prompt_file],),
            daemon=True,
        )
        thread.start()

    def _run_process(self, cmd):
        try:
            env = os.environ.copy()
            env["TERM"] = "dumb"

            self.proc = subprocess.Popen(
                cmd,
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

    def append_output(self, text: str):
        cleaned = clean_chunk(text)
        if cleaned:
            self.raw_output_buffer.append(cleaned)
            self.render_output()

    def _extract_task_result_for_save(self) -> str:
        if not self.pending_task_marker:
            return self.output.get("1.0", "end").strip()

        full_text = self.output.get("1.0", "end")
        marker_pos = full_text.rfind(self.pending_task_marker)
        if marker_pos == -1:
            return full_text.strip()

        after_marker = full_text[marker_pos:]

        if "⚖️ FINAL DECISION:" in after_marker:
            result = after_marker.split("⚖️ FINAL DECISION:", 1)[1].strip()
            return result

        lines = after_marker.splitlines()
        if len(lines) > 1:
            return "\n".join(lines[1:]).strip()
        return after_marker.strip()

    def _save_pending_task_result_if_needed(self):
        if not self.pending_task_save_enabled or not self.pending_task_save_path:
            return

        try:
            content = self._extract_task_result_for_save().strip()
            if not content:
                raise ValueError("Task result was empty.")

            with open(self.pending_task_save_path, "w", encoding="utf-8") as f:
                f.write(content + "\n")

            self.status_var.set(f"Saved task result to {os.path.basename(self.pending_task_save_path)}")
        except Exception as e:
            messagebox.showerror("Task export failed", str(e))
        finally:
            self.pending_task_save_enabled = False
            self.pending_task_save_path = ""
            self.pending_task_marker = None

    def _cleanup_temp_prompt_file(self):
        if self.current_temp_prompt_file and os.path.exists(self.current_temp_prompt_file):
            try:
                os.unlink(self.current_temp_prompt_file)
            except OSError:
                pass
        self.current_temp_prompt_file = None

    def render_output(self):
        combined = "".join(self.raw_output_buffer)
        cleaned = reflow_text(combined)

        current_yview = self.output.yview()

        self.output.configure(state="normal")
        self.output.delete("1.0", "end")

        lines = cleaned.splitlines()
        current_body_tag = "body_default"

        for line in lines:
            stripped = line.strip()

            if not stripped:
                self.output.insert("end", "\n")
                continue

            if stripped.startswith("=== USER FOLLOW-UP"):
                self.output.insert("end", "\n" + stripped + "\n\n", "reply_marker")
                current_body_tag = "body_default"
                continue

            if stripped.startswith("=== TASK REQUEST"):
                self.output.insert("end", "\n" + stripped + "\n\n", "task_marker")
                current_body_tag = "body_default"
                continue

            if stripped.startswith("🌐") or stripped.startswith("🧠"):
                self.output.insert("end", stripped + "\n", "problem")
                continue

            if stripped.startswith("==="):
                self.output.insert("end", "\n" + stripped + "\n\n", "round")
                current_body_tag = "body_default"
                continue

            if stripped.startswith("⚖️ FINAL DECISION"):
                self.output.insert("end", "\n" + stripped + "\n\n", "final")
                current_body_tag = "body_default"
                continue

            if stripped.startswith("💀"):
                self.output.insert("end", stripped + "\n", "dead")
                continue

            if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
                heading_text = stripped[2:-2].strip()
                self.output.insert("end", heading_text + "\n", "section")
                continue

            score_match = SCORE_RE.match(stripped)
            if score_match:
                speaker = score_match.group(1).lower()
                score = score_match.group(2)

                if speaker == "creative":
                    header_tag = "speaker_creative"
                    current_body_tag = "body_creative"
                    label = f"🎨 Creative agent  |  score {score}"
                elif speaker == "practical":
                    header_tag = "speaker_practical"
                    current_body_tag = "body_practical"
                    label = f"🛠 Practical agent  |  score {score}"
                elif speaker == "systems":
                    header_tag = "speaker_systems"
                    current_body_tag = "body_systems"
                    label = f"🧩 Systems agent  |  score {score}"
                elif speaker == "critic":
                    header_tag = "speaker_critic"
                    current_body_tag = "body_critic"
                    label = f"⚔ Critic agent  |  score {score}"
                else:
                    header_tag = "speaker_default"
                    current_body_tag = "body_default"
                    label = stripped

                self.output.insert("end", "\n" + label + "\n", header_tag)
                continue

            if stripped.startswith("[") and "| score=" in stripped:
                self.output.insert("end", "\n" + stripped + "\n", "speaker_default")
                current_body_tag = "body_default"
                continue

            self.output.insert("end", stripped + "\n", current_body_tag)

        if self.scroll_to_marker:
            self._scroll_to_marker_top(self.scroll_to_marker)
            self.scroll_to_marker = None
        else:
            self.output.yview_moveto(current_yview[0])

        self.output.configure(state="disabled")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()

                if kind == "output":
                    self.append_output(payload)

                elif kind == "done":
                    self.proc = None
                    self._set_running_state(False, f"Finished (exit {payload})")
                    self.render_output()
                    self._save_pending_task_result_if_needed()
                    self._cleanup_temp_prompt_file()

                elif kind == "error":
                    self.proc = None
                    self._set_running_state(False, "Error")
                    self._cleanup_temp_prompt_file()
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
