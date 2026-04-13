"""CustomTkinter GUI for chatbot-export-converter."""

from __future__ import annotations

import queue
import sys
import threading
from tkinter import filedialog

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_W, _H = 620, 540


class _LogWriter:
    """Redirects print() output from the conversion thread into a queue."""

    def __init__(self, q: "queue.Queue[str]") -> None:
        self._q = q

    def write(self, text: str) -> None:
        if text:
            self._q.put(text)

    def flush(self) -> None:
        pass


class _App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("chatbot-export-converter")
        self.geometry(f"{_W}x{_H}")
        self.resizable(False, False)

        self._log_q: queue.Queue[str] = queue.Queue()
        self._running = False

        self._build_ui()
        self._poll_log()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 18, "pady": (6, 0)}

        # Input
        ctk.CTkLabel(self, text="Input  (zip file or unzipped folder)", anchor="w").pack(
            fill="x", **pad
        )
        r1 = ctk.CTkFrame(self, fg_color="transparent")
        r1.pack(fill="x", padx=18, pady=(4, 0))
        self._input_var = ctk.StringVar()
        ctk.CTkEntry(r1, textvariable=self._input_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r1, text="Browse", width=80, command=self._browse_input).pack(
            side="left", padx=(8, 0)
        )

        # Output
        ctk.CTkLabel(self, text="Output folder", anchor="w").pack(fill="x", **pad)
        r2 = ctk.CTkFrame(self, fg_color="transparent")
        r2.pack(fill="x", padx=18, pady=(4, 0))
        self._output_var = ctk.StringVar()
        ctk.CTkEntry(r2, textvariable=self._output_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(r2, text="Browse", width=80, command=self._browse_output).pack(
            side="left", padx=(8, 0)
        )

        # Options
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", padx=18, pady=(12, 0))
        self._incremental = ctk.BooleanVar(value=False)
        self._tool_blocks = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts,
            text="Incremental  (skip unchanged conversations — ChatGPT only)",
            variable=self._incremental,
        ).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(
            opts,
            text="Include tool blocks  (tool_use / tool_result — Claude only)",
            variable=self._tool_blocks,
        ).pack(anchor="w", pady=2)

        # Convert button
        self._btn = ctk.CTkButton(self, text="Convert", height=40, command=self._on_convert)
        self._btn.pack(fill="x", padx=18, pady=14)

        # Log area
        self._log = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self._log.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self._log_append("Ready.\n")

    # ── File pickers ─────────────────────────────────────────────────────────

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select export zip",
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
        )
        if not path:
            path = filedialog.askdirectory(title="Or select unzipped export folder")
        if path:
            self._input_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self._output_var.set(path)

    # ── Log helpers ──────────────────────────────────────────────────────────

    def _log_append(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _poll_log(self) -> None:
        try:
            while True:
                self._log_append(self._log_q.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    # ── Conversion ───────────────────────────────────────────────────────────

    def _on_convert(self) -> None:
        if self._running:
            return
        inp = self._input_var.get().strip()
        out = self._output_var.get().strip()
        if not inp:
            self._log_append("\n  Please select an input file or folder.\n")
            return
        if not out:
            self._log_append("\n  Please select an output folder.\n")
            return

        self._running = True
        self._btn.configure(state="disabled", text="Converting…")
        self._log_append("\n" + "─" * 48 + "\n")

        threading.Thread(target=self._convert_thread, args=(inp, out), daemon=True).start()

    def _convert_thread(self, inp: str, out: str) -> None:
        argv = ["chatbot-convert", "--input", inp, "--output", out]
        if self._incremental.get():
            argv.append("--incremental")
        if self._tool_blocks.get():
            argv.append("--include-tool-blocks")

        writer = _LogWriter(self._log_q)
        old_argv = sys.argv
        old_out, old_err = sys.stdout, sys.stderr
        sys.argv = argv
        sys.stdout = writer  # type: ignore[assignment]
        sys.stderr = writer  # type: ignore[assignment]

        try:
            from chatbot_export_converter.converter import main

            rc = main()
            if rc == 0:
                self._log_q.put("\nDone.\n")
            else:
                self._log_q.put(f"\nExited with code {rc}.\n")
        except SystemExit as exc:
            code = exc.code
            if code not in (0, None):
                self._log_q.put(f"\nExited with code {code}.\n")
            else:
                self._log_q.put("\nDone.\n")
        except Exception as exc:
            self._log_q.put(f"\nError: {exc}\n")
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
            sys.argv = old_argv
            self.after(0, self._on_done)

    def _on_done(self) -> None:
        self._running = False
        self._btn.configure(state="normal", text="Convert")


# ── Public entry points ──────────────────────────────────────────────────────


def run_gui() -> int:
    app = _App()
    app.mainloop()
    return 0


def main() -> None:
    raise SystemExit(run_gui())
