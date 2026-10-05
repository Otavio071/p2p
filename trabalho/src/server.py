#!/usr/bin/env python3
"""Servidor de arquivos cliente-servidor com 3 variacoes de atendimento.

  --mode seq     : atende 1 cliente por vez (sequencial)
  --mode thread  : 1 thread por cliente (todos de uma vez)
  --mode pool    : pool de N threads (no maximo N clientes simultaneos; demais ficam na fila)

Protocolo: o cliente conecta; o servidor envia 8 bytes (tamanho) + conteudo do arquivo.
"""
import argparse
import os
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor

from common import CHUNK, Limiter


def make_handler(path, limiter):
    size = os.path.getsize(path)

    def handle(conn):
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.sendall(struct.pack("!Q", size))
            with open(path, "rb", buffering=0) as f:
                while True:
                    data = f.read(CHUNK)
                    if not data:
                        break
                    limiter.acquire(len(data))   # banda de upload do servidor (compartilhada)
                    conn.sendall(data)
        except OSError:
            pass
        finally:
            conn.close()

    return handle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["seq", "thread", "pool"], required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--rate", type=float, default=50 * 1024 * 1024, help="upload do servidor (bytes/s)")
    ap.add_argument("--workers", type=int, default=5, help="N do pool (modo pool)")
    a = ap.parse_args()

    handle = make_handler(a.file, Limiter(a.rate))
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", a.port))
    srv.listen(256)
    pool = ThreadPoolExecutor(max_workers=a.workers) if a.mode == "pool" else None
    while True:
        conn, _ = srv.accept()
        if a.mode == "seq":
            handle(conn)                                   # bloqueia ate terminar este cliente
        elif a.mode == "thread":
            threading.Thread(target=handle, args=(conn,), daemon=True).start()
        else:
            pool.submit(handle, conn)                      # fila quando ja ha N em atendimento


if __name__ == "__main__":
    main()
