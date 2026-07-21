"""Helper de mesure mémoire portable (RSS du process courant).

Priorité : psutil > ctypes (Windows) > resource (Unix).
Si aucun outil n'est disponible, lève RuntimeError pour permettre un skip propre.
"""

import os


def get_rss_bytes():
    """Retourne l'empreinte mémoire RSS du process en octets.

    Ordre de résolution :
      1. psutil (multiplateforme)
      2. ctypes + GetProcessMemoryInfo (Windows natif)
      3. resource.getrusage (Unix)
    Lève RuntimeError si aucun moyen de mesurer n'est disponible.
    """
    # 1. psutil — solution privilégiée et multiplateforme
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss
    except ImportError:
        pass

    # 2. Windows natif via ctypes (sans dépendance)
    try:
        import ctypes
        from ctypes import wintypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):  # noqa: N801
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.windll.kernel32
        if kernel32.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        ):
            return counters.WorkingSetSize
    except (ImportError, AttributeError, OSError):
        pass

    # 3. Unix — resource.getrusage (ru_maxrss en Ko)
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except (ImportError, AttributeError):
        pass

    raise RuntimeError("Aucun outil de mesure mémoire disponible (psutil/ctypes/resource).")
