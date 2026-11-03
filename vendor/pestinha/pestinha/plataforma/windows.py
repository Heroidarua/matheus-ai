"""Windows: a API do sistema (user32, dwmapi) via ctypes e pywin32. Retângulos em pixels físicos."""

import ctypes
import threading
from ctypes import wintypes

import psutil
import pywintypes
import win32api
import win32con
import win32gui
import win32process

from ..log import log

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
WM_HOTKEY = 0x0312
HOTKEY_ID = 0xB0DD


class LASTINPUTINFO(ctypes.Structure):
    """Estrutura da API do Windows que guarda o instante da última entrada (teclado ou mouse)."""
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def ocioso_segundos():
    """Tempo ocioso lido da API do Windows (GetLastInputInfo)."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0


def processo_ativo():
    """Nome do programa da janela ativa, pelo pid da janela e o psutil."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "unknown.exe"
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ValueError,
            pywintypes.error):
        return "unknown.exe"


def tela_cheia():
    """Janela em primeiro plano cobrindo o monitor inteiro (jogo, vídeo, apresentação)."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False
    try:
        if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
            return False
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        m_left, m_top, m_right, m_bottom = win32api.GetMonitorInfo(monitor)["Monitor"]
    except Exception:
        return False
    return left <= m_left and top <= m_top and right >= m_right and bottom >= m_bottom


def _is_cloaked(hwnd):
    """Diz se o Windows está mostrando a janela como escondida (ex.: ela está em outro desktop virtual)."""
    cloaked = ctypes.c_int(0)
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
    except Exception:
        return False
    return cloaked.value != 0


def _frame_rect(hwnd):
    """Retângulo visível (sem as bordas invisíveis de redimensionar do Windows 10/11)."""
    rect = wintypes.RECT()
    try:
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), 9, ctypes.byref(rect), ctypes.sizeof(rect)
        ) == 0:
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        pass
    return win32gui.GetWindowRect(hwnd)


def janelas_visiveis(excluir, escala=1.0):
    """Janelas visíveis em ordem de z (de cima para baixo): [(hwnd, (l, t, r, b), maximizada)]."""
    found = []
    user32 = ctypes.windll.user32

    def callback(hwnd, _):
        """Chamado pelo Windows para cada janela: guarda só as que estão visíveis e são janelas de verdade."""
        try:
            if hwnd in excluir or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
                return True
            # só janelas "de verdade" (as do Alt+Tab): sem dono, sem overlay transparente
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & (win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE):
                return True
            if win32gui.GetWindow(hwnd, win32con.GW_OWNER) or _is_cloaked(hwnd):
                return True
            rect = _frame_rect(hwnd)
            if rect[2] - rect[0] < 120 or rect[3] - rect[1] < 60:
                return True
            found.append((hwnd, rect, bool(user32.IsZoomed(hwnd))))
        except Exception:
            pass        # janela sumiu no meio da leitura
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception as error:
        log(f"[senses] não deu para listar janelas: {error}")
    return found


def retangulo_ativo(escala=1.0):
    """Retângulo da janela ativa (pixels físicos), para ele olhar para ela."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    try:
        if win32gui.GetClassName(hwnd) in SHELL_CLASSES:
            return None
        return _frame_rect(hwnd)
    except Exception:
        return None


def sem_foco_nativo(janela_id):
    """A janela não ativa nem rouba o foco ao aparecer ou ser clicada."""
    try:
        style = win32gui.GetWindowLong(janela_id, win32con.GWL_EXSTYLE)
        style |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(janela_id, win32con.GWL_EXSTYLE, style)
    except Exception:
        pass    # sem janela nativa (ex.: teste offscreen)


def iniciar_atalho(callback):
    """RegisterHotKey numa thread com fila de mensagens própria. Devolve True se conseguiu."""
    pronto = threading.Event()
    resultado = {"ok": False}

    def laco():
        """Laço da thread que registra o atalho e recebe as teclas do sistema."""
        user32 = ctypes.windll.user32
        resultado["ok"] = bool(user32.RegisterHotKey(
            None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, ord("B")
        ))
        pronto.set()
        if not resultado["ok"]:
            log("[pânico] não deu para registrar o atalho (outro programa usa?)")
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                callback()

    threading.Thread(target=laco, daemon=True).start()
    pronto.wait(2.0)
    return resultado["ok"]
