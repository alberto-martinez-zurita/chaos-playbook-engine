from __future__ import annotations

import argparse
import json
import subprocess
import sys
import os
import platform
import time
import threading
import queue
import shutil
import webbrowser
from pathlib import Path

# Try to import optional libraries
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    console = Console(force_terminal=True)
    HAS_RICH = True
except ImportError:
    HAS_RICH = False # type: ignore

# Library to simulate keystrokes (Optional, for the preview trick)
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

def print_step(title, style="bold blue"):
    if HAS_RICH:
        console.print(Panel(title, style=style, expand=False))
    else:
        print(f"\n{'='*10} {title} {'='*10}\n")

def get_latest_run_dir(base_path: Path):
    if not base_path.exists(): return None
    dirs = sorted([d for d in base_path.iterdir() if d.is_dir() and d.name.startswith('run_')])
    return dirs[-1] if dirs else None

def open_markdown_in_vscode(path: Path):
    """Opens Markdown in VS Code and optionally activates Preview."""
    if not path.exists(): return
    
    print(f"📄 Opening Report in VS Code: {path.name}...")
    
    if shutil.which("code"):
        try:
            # Open the file in VS Code
            subprocess.run(["code", "-r", str(path)], shell=True, check=True)
            
            # MAGIC TRICK (If you have pyautogui installed)
            # Wait a bit for VS Code to get focus and press the Preview shortcut
            if HAS_PYAUTOGUI:
                time.sleep(1.5) # Wait for the window to load
                # Detect system for the correct shortcut
                if platform.system() == 'Darwin': # Mac
                    pyautogui.hotkey('command', 'shift', 'v')
                else: # Windows / Linux
                    pyautogui.hotkey('ctrl', 'shift', 'v')
                print("   (Auto-triggered Preview Mode 🪄)")
            return
        except: pass
    
    open_file_default(path)

def open_dashboard_in_browser(path: Path):
    """Shows the link AND opens the system's browser."""
    uri = path.absolute().as_uri()
    
    print(f"🌐 Launching Dashboard in default browser...")
    try:
        webbrowser.open(uri)
    except Exception as e:
        print(f"❌ Could not launch browser: {e}")

def open_file_default(path: Path):
    try:
        if platform.system() == 'Darwin': subprocess.call(('open', str(path)))
        elif platform.system() == 'Windows': os.startfile(str(path))
        else: subprocess.call(('xdg-open', str(path)))
    except: pass

def enqueue_output(out_stream, q):
    for line in iter(out_stream.readline, ''):
        q.put(line)
    out_stream.close()

def run_command(script_path, args, description):
    cmd = [sys.executable, script_path] + args
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"⚙️  Launching: {script_path} {' '.join(args)}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=env,
        encoding='utf-8',
        errors='replace'
    )

    q = queue.Queue()
    t = threading.Thread(target=enqueue_output, args=(process.stdout, q))
    t.daemon = True
    t.start()

    if HAS_RICH:
        with Progress(
            SpinnerColumn("earth"),    
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None, pulse_style="yellow"),
            TimeElapsedColumn(),       
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"[yellow]Running {description}...", total=None)
            while True:
                alive = process.poll() is None
                while True:
                    try:
                        line = q.get_nowait()
                        clean_line = line.rstrip()
                        if clean_line:
                            progress.console.print(f"  │ {clean_line}", style="dim")
                    except queue.Empty:
                        break
                if not alive and q.empty(): break
                time.sleep(0.05)
    else:
        # Simple fallback
        while True:
            alive = process.poll() is None
            while True:
                try:
                    line = q.get_nowait()
                    print(f"  │ {line.rstrip()}")
                except queue.Empty:
                    break
            if not alive and q.empty(): break
            time.sleep(0.1)

    if process.returncode != 0:
        print(f"❌ Critical error in {description}. Code: {process.returncode}")
        sys.exit(1)
    
    print(f"✅ {description} completed.\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    with open(config_path, 'r', encoding='utf-8') as f:
        scenario = json.load(f)

    print_step(f"🎬 SCENARIO: {scenario.get('title', 'Untitled')}", "bold magenta")
    
    for step in scenario['steps']:
        print_step(f"Step: {step['name']}", "bold cyan")
        run_command(step['script'], step['args'], step['name'])
        time.sleep(1) 

    if 'auto_open' in scenario:
        print_step("🚀 Launching Results", "bold green")
        results_base = Path("reports/parametric_experiments")
        latest = get_latest_run_dir(results_base)
        
        if latest:
            print(f"📍 Reports found at: {latest.name}")
            
            for f_name in scenario['auto_open']:
                file_path = latest / f_name
                
                if f_name.endswith('.md'):
                    open_markdown_in_vscode(file_path)
                    # Short pause to ensure VS Code processes before opening the browser
                    time.sleep(3) 
                
                elif f_name.endswith('.html'):
                    open_dashboard_in_browser(file_path)
                    
                else:
                    open_file_default(file_path)
        else:
             print("⚠️ Reports directory not found.")

if __name__ == "__main__":
    main()