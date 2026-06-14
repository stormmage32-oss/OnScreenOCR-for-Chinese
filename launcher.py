import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

def check_python():
    try:
        subprocess.run(["python", "--version"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False

def check_dependencies():
    try:
        subprocess.run(["python", "-c", "import PyQt5, paddle, paddleocr, mss, pypinyin, jieba, keyboard"], capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False

def main():
    # Hide the root tkinter window
    root = tk.Tk()
    root.withdraw()

    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    if not check_python():
        messagebox.showerror(
            "Python Not Found", 
            "Python 3.8+ must be installed on your computer to run this application.\n\n"
            "Please install Python from python.org, make sure to check the 'Add Python to PATH' option during installation, and try again."
        )
        return

    if not check_dependencies():
        ans = messagebox.askyesno(
            "First Time Setup", 
            "The required AI libraries (PaddleOCR, PaddlePaddle, etc.) are missing and need to be downloaded.\n\n"
            "This is a one-time process and may take a few minutes depending on your internet speed.\n\n"
            "Do you want to install them now?"
        )
        if ans:
            install_bat = os.path.join(base_dir, "install.bat")
            if os.path.exists(install_bat):
                # Run install.bat in a new console window and wait for it
                subprocess.run(
                    ["cmd", "/c", install_bat],
                    cwd=base_dir,
                    check=False
                )
                
                # Check again if installation was successful
                if not check_dependencies():
                    messagebox.showerror(
                        "Installation Failed", 
                        "The required libraries could not be installed properly.\n"
                        "Please check your internet connection and try again."
                    )
                    return
            else:
                messagebox.showerror("Error", "install.bat not found! Make sure you have extracted all files from the ZIP.")
                return
        else:
            return

    main_py = os.path.join(base_dir, "main.py")
    if not os.path.exists(main_py):
        messagebox.showerror("Error", "main.py not found! Make sure you have extracted all files from the ZIP.")
        return

    # Run the main app without a console window
    subprocess.Popen(["python", "main.py"], cwd=base_dir, creationflags=subprocess.CREATE_NO_WINDOW)

if __name__ == "__main__":
    main()
