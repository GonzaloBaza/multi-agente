"""
Writer "tee" para structlog: escribe a stdout (Docker logs) **y** a un archivo
por worker en /app/logs, con rotación por tamaño.

Motivo: `docker logs` se borra al recrear el container (cada `--force-recreate`
= cada deploy). El archivo vive en un named volume que sobrevive a los
recreates, así que los logs de diagnóstico NO se pierden en el próximo deploy.

Decisiones:
  - **Un archivo por PID** (`api-<pid>.log`): uvicorn corre con `--workers 2`
    → 2 procesos. Un único archivo compartido haría que los dos workers
    rotaran el mismo archivo y se pisaran. Por-PID elimina la contención entre
    procesos; el lock interno cubre threads/tasks del mismo worker.
  - **Fork-safe**: el PID se resuelve en cada `write` (no al importar). Si
    uvicorn forkea los workers después de importar, cada proceso reabre su
    propio archivo en el primer write.
  - **Nunca rompe el logging**: si abrir/escribir el archivo falla, el stdout
    sigue funcionando igual (es lo crítico: Docker logs + Sentry).
"""

from __future__ import annotations

import os
import sys
import threading


class TeeRotatingWriter:
    """File-like para `structlog.PrintLoggerFactory(file=...)`."""

    def __init__(self, path_template: str, max_bytes: int = 50 * 1024 * 1024, backups: int = 5):
        # path_template usa `{pid}` — se resuelve por proceso en _ensure_open.
        self._tmpl = path_template
        self._max_bytes = max_bytes
        self._backups = backups
        self._lock = threading.Lock()
        self._pid: int | None = None
        self._path: str | None = None
        self._f = None

    def _ensure_open(self) -> None:
        pid = os.getpid()
        if self._f is not None and self._pid == pid:
            return
        # Primera vez en este proceso, o PID cambió (fork) → (re)abrir.
        self._pid = pid
        self._path = self._tmpl.format(pid=pid)
        try:
            d = os.path.dirname(self._path)
            if d:
                os.makedirs(d, exist_ok=True)
            self._f = open(self._path, "a", encoding="utf-8")
        except Exception:
            self._f = None  # sin archivo → seguimos solo con stdout

    def write(self, data: str) -> int:
        # stdout primero — es lo crítico (Docker logs).
        n = sys.stdout.write(data)
        with self._lock:
            self._ensure_open()
            if self._f is not None:
                try:
                    self._f.write(data)
                    self._f.flush()  # durabilidad: si matan al worker, ya está en disco
                    if self._f.tell() >= self._max_bytes:
                        self._rotate()
                except Exception:
                    pass
        return n

    def _rotate(self) -> None:
        if not self._path:
            return
        try:
            self._f.close()
            for i in range(self._backups - 1, 0, -1):
                src = f"{self._path}.{i}"
                dst = f"{self._path}.{i + 1}"
                if os.path.exists(src):
                    os.replace(src, dst)
            if os.path.exists(self._path):
                os.replace(self._path, f"{self._path}.1")
        except Exception:
            pass
        try:
            self._f = open(self._path, "a", encoding="utf-8")
        except Exception:
            self._f = None

    def flush(self) -> None:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        if self._f is not None:
            try:
                self._f.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return False
