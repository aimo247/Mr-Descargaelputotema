import os
import sys
import json
import subprocess
import threading
import webbrowser
import ctypes
import webview


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
RESOURCE_DIR = get_resource_dir()

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.join(BASE_DIR, "APP")
    DEFAULT_DOWNLOAD = os.path.join(BASE_DIR, "Download")
else:
    APP_DIR = os.path.join(os.path.dirname(BASE_DIR), "APP")
    DEFAULT_DOWNLOAD = os.path.join(APP_DIR, "Download")

YTDLP = os.path.join(APP_DIR, "ytdlp", "yt-dlp.exe")
FFMPEG_DIR = os.path.join(APP_DIR, "ytdlp")
SPOTDL = os.path.join(APP_DIR, "spotdl", "spotdl.exe")

os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
os.makedirs(DEFAULT_DOWNLOAD, exist_ok=True)


def creation_flags():
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


# --- Comprobación e instalación de .NET Framework 4.8 ---
def check_dotnet48():
    """Devuelve True si .NET Framework 4.8 (o superior) está instalado."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
        )
        release, _ = winreg.QueryValueEx(key, "Release")
        winreg.CloseKey(key)
        return release >= 528040
    except Exception:
        return False


def run_dotnet_installer():
    """Lanza el instalador de .NET 4.8 con permisos de administrador."""
    candidates = [
        os.path.join(RESOURCE_DIR, "dotnet48.exe"),
        os.path.join(BASE_DIR, "dotnet48.exe"),
    ]
    installer = None
    for c in candidates:
        if os.path.exists(c):
            installer = c
            break

    if installer is None:
        # Aviso por si no está el instalador
        ctypes.windll.user32.MessageBoxW(
            0,
            "Esta aplicación necesita .NET Framework 4.8 para funcionar.\n\n"
            "No se encontró el instalador dotnet48.exe.\n"
            "Descárgalo desde:\n"
            "https://dotnet.microsoft.com/download/dotnet-framework/net48",
            "Falta .NET Framework 4.8",
            0x10  # MB_ICONERROR
        )
        return False

    # Aviso previo
    ctypes.windll.user32.MessageBoxW(
        0,
        "Se va a instalar .NET Framework 4.8.\n\n"
        "Es un componente oficial de Microsoft necesario para que la app funcione.\n"
        "El proceso puede tardar 1-2 minutos.\n\n"
        "Cuando termine, vuelve a abrir la aplicación.",
        "Instalando componente necesario",
        0x40  # MB_ICONINFORMATION
    )

    try:
        # ShellExecuteW con "runas" para forzar el aviso de administrador
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            installer,
            "/passive /norestart",
            None,
            1
        )
        return result > 32
    except Exception:
        return False


class Api:
    def __init__(self):
        self._window = None

    def set_window(self, w):
        self._window = w

    def check_tools(self):
        return {
            "ytdlp": os.path.exists(YTDLP),
            "spotdl": os.path.exists(SPOTDL),
            "ffmpeg": os.path.exists(os.path.join(FFMPEG_DIR, "ffmpeg.exe")),
            "default_folder": DEFAULT_DOWNLOAD,
        }

    def choose_folder(self):
        if self._window is None:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return result[0]
        return None

    def open_downloads(self):
        try:
            subprocess.Popen(["explorer", DEFAULT_DOWNLOAD], creationflags=creation_flags())
            return True
        except Exception:
            return False

    def open_url(self, url):
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"Error al abrir URL: {e}")
            return False

    def get_clipboard(self):
        try:
            import tkinter
            r = tkinter.Tk()
            r.withdraw()
            text = r.clipboard_get()
            r.destroy()
            return text
        except Exception:
            return ""

    def download_youtube(self, url, is_audio, quality, is_playlist, folder):
        threading.Thread(target=self._do_youtube,
                         args=(url, is_audio, quality, is_playlist, folder),
                         daemon=True).start()
        return True

    def download_spotify(self, url, fmt, folder):
        threading.Thread(target=self._do_spotify,
                         args=(url, fmt, folder),
                         daemon=True).start()
        return True

    def _js(self, code):
        if self._window is None:
            return
        try:
            self._window.evaluate_js(code)
        except Exception:
            pass

    def _log(self, msg, kind=None):
        self._js(f"addLog({json.dumps(msg)}, {json.dumps(kind) if kind else 'null'})")

    def _status(self, msg, kind=None):
        self._js(f"setStatus({json.dumps(msg)}, {json.dumps(kind) if kind else 'null'})")

    def _progress(self, active):
        self._js(f"setProgress({'true' if active else 'false'})")

    def _finish(self, success=True):
        self._js(f"downloadFinished({'true' if success else 'false'})")

    def _do_youtube(self, url, is_audio, quality, is_playlist, folder):
        if not os.path.exists(YTDLP):
            self._status("No se encuentra yt-dlp.exe", "error")
            self._log("Falta yt-dlp.exe en APP\\ytdlp\\", "err")
            self._finish(False)
            return
        self._progress(True)
        self._status("Descargando desde YouTube...", "working")
        self._log("Iniciando descarga de YouTube")
        args = []
        if is_playlist:
            args += ["--yes-playlist", "--ignore-errors"]
        else:
            args += ["--no-playlist"]
        if is_audio:
            bitrate = "320K"
            if quality == "192 kbps":
                bitrate = "192K"
            elif quality == "128 kbps":
                bitrate = "128K"
            args += ["-x", "--audio-format", "mp3", "--audio-quality", bitrate,
                     "--embed-thumbnail", "--embed-metadata"]
        else:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            if quality == "1080p":
                fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"
            elif quality == "720p":
                fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
            elif quality == "480p":
                fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best"
            elif quality == "360p":
                fmt = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best"
            args += ["-f", fmt, "--merge-output-format", "mp4",
                     "--embed-thumbnail", "--embed-metadata"]
        if is_playlist:
            args += ["-o", os.path.join("%(playlist_title)s", "%(playlist_index)02d - %(title)s.%(ext)s")]
        args += ["--ffmpeg-location", FFMPEG_DIR]
        args += ["-P", folder]
        args += ["--newline"]
        args += [url]
        rc = self._run_process([YTDLP] + args, cwd=os.path.dirname(YTDLP))
        self._progress(False)
        if rc == 0:
            self._status("¡Descarga completada!", "success")
            self._log("Descarga completada.", "ok")
            try:
                subprocess.Popen(["explorer", folder], creationflags=creation_flags())
            except Exception:
                pass
            self._finish(True)
        else:
            self._status(f"Terminó con avisos (código {rc})", "warning")
            self._log(f"yt-dlp terminó con código {rc}", "err")
            self._finish(False)

    def _do_spotify(self, url, fmt, folder):
        if not os.path.exists(SPOTDL):
            self._status("No se encuentra spotdl.exe", "error")
            self._log("Falta spotdl.exe en APP\\spotdl\\", "err")
            self._finish(False)
            return
        self._progress(True)
        self._status("Descargando desde Spotify...", "working")
        self._log("Iniciando descarga de Spotify")
        args = ["download", url, "--format", fmt, "--bitrate", "320k",
                "--output", os.path.join(folder, "{artist} - {title}.{output-ext}")]
        rc = self._run_process([SPOTDL] + args, cwd=folder)
        self._progress(False)
        if rc == 0:
            self._status("¡Descarga completada!", "success")
            self._log("Descarga completada.", "ok")
            try:
                subprocess.Popen(["explorer", folder], creationflags=creation_flags())
            except Exception:
                pass
            self._finish(True)
        else:
            self._status(f"Terminó con avisos (código {rc})", "warning")
            self._log(f"spotdl terminó con código {rc}", "err")
            self._finish(False)

    def _run_process(self, cmd, cwd=None):
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1, creationflags=creation_flags(), cwd=cwd,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                self._log(line)
            proc.wait()
            return proc.returncode
        except Exception as e:
            self._log(f"Error al ejecutar: {e}", "err")
            return -1


if __name__ == "__main__":
    # 1) Comprobar .NET Framework 4.8 antes de nada
    if not check_dotnet48():
        run_dotnet_installer()
        # Salir para que el usuario reinicie/relance tras la instalación
        sys.exit(0)

    # 2) Arrancar la app normal con pywebview (ventana nativa)
    api = Api()
    html_path = os.path.join(RESOURCE_DIR, "index.html")
    window = webview.create_window(
        "Mr Descargaelputotema", html_path, js_api=api,
        width=760, height=780, min_size=(640, 620),
        background_color="#0a0a0f",
    )
    api.set_window(window)
    webview.start()