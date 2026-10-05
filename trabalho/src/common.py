"""Utilitarios comuns: limitador de banda de upload (emula a placa de rede de cada maquina)."""
import threading
import time

CHUNK = 256 * 1024  # tamanho do bloco de envio/recebimento (bytes)


class Limiter:
    """Limitador de taxa compartilhado entre threads (reserva de 'slots' de tempo).

    Todas as conexoes de um mesmo no (servidor ou peer) dividem a mesma banda de upload,
    como aconteceria com uma unica interface de rede fisica.
    """

    def __init__(self, rate_bytes_s):
        self.rate = rate_bytes_s
        self.lock = threading.Lock()
        self.next_free = time.perf_counter()

    def acquire(self, n):
        if not self.rate:
            return
        with self.lock:
            now = time.perf_counter()
            start = max(self.next_free, now)
            self.next_free = start + n / self.rate
            end = self.next_free
        delay = end - time.perf_counter()
        if delay > 0:
            time.sleep(delay)


def recv_exact(sock, n):
    buf = bytearray(n)
    mv = memoryview(buf)
    got = 0
    while got < n:
        r = sock.recv_into(mv[got:])
        if not r:
            raise ConnectionError("conexao fechada")
        got += r
    return buf


def wait_until(t_epoch):
    d = t_epoch - time.time()
    if d > 0:
        time.sleep(d)
