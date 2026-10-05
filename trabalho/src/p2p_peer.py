#!/usr/bin/env python3
"""Peer P2P simplificado (estilo BitTorrent).

- O arquivo e dividido em pecas (256 KB para arquivos <= 5 MB, 1 MB para os maiores).
- Peer 0 e o seed (tem o arquivo completo). Os demais (leechers) baixam pecas de QUALQUER peer
  que as possua e, assim que uma peca chega, passam a serve-la aos outros.
- Politica: rarest-first (peca mais rara primeiro, desempate aleatorio); prefere buscar de
  leechers para poupar o seed. Cada peer atende no maximo --slots uploads simultaneos.
- Cada peer tem seu proprio limite de upload (--rate), igual ao do servidor nos demais modos.
- Apos concluir, o peer continua semeando (como um cliente BitTorrent) ate o orquestrador encerrar.
- As pecas ficam em arquivo temporario (necessario para re-semear); apagado ao final do experimento.

Protocolo (conexao persistente): 'B' -> bitmap de pecas | 'G'+idx(4B) -> status(1B)+dados
"""
import argparse
import json
import os
import random
import socket
import struct
import threading
import time

from common import CHUNK, Limiter, recv_exact, wait_until


class Peer:
    def __init__(self, a):
        self.id = a.id
        self.total = a.total
        self.ports = [a.base_port + i for i in range(a.total)]
        self.size = a.size
        self.psize = a.piece
        self.np = (self.size + self.psize - 1) // self.psize
        self.is_seed = a.id == 0
        self.have = bytearray(b"\x01" * self.np) if self.is_seed else bytearray(self.np)
        self.nhave = self.np if self.is_seed else 0
        self.lock = threading.Lock()
        self.inflight = set()
        self.limiter = Limiter(a.rate)
        self.slots = threading.Semaphore(a.slots)
        self.maps = [None] * self.total
        self.counts = [0] * self.np
        self.finished = False
        self.workers_n = a.workers
        self.refresh_s = a.refresh
        if self.is_seed:
            self.fd = os.open(a.file, os.O_RDONLY)
        else:
            self.fd = os.open(os.path.join(a.workdir, f"peer_{self.id}.bin"), os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            os.ftruncate(self.fd, self.size)

    def plen(self, i):
        return min(self.psize, self.size - i * self.psize)

    # ---------------- lado servidor (upload) ----------------
    def serve(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.ports[self.id]))
        srv.listen(256)
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()

    def handle(self, conn):
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            while True:
                cmd = conn.recv(1)
                if not cmd:
                    break
                if cmd == b"B":
                    conn.sendall(bytes(self.have))
                elif cmd == b"G":
                    (idx,) = struct.unpack("!I", recv_exact(conn, 4))
                    if not self.have[idx]:
                        conn.sendall(b"\x00")
                        continue
                    with self.slots:                       # limita uploads simultaneos
                        data = os.pread(self.fd, self.plen(idx), idx * self.psize)
                        conn.sendall(b"\x01")
                        mv = memoryview(data)
                        for off in range(0, len(data), CHUNK):
                            part = mv[off:off + CHUNK]
                            self.limiter.acquire(len(part))  # banda de upload do peer
                            conn.sendall(part)
        except OSError:
            pass
        finally:
            conn.close()

    # ---------------- lado cliente (download) ----------------
    def connect(self, j, cache):
        c = cache.get(j)
        if c is None:
            c = socket.create_connection(("127.0.0.1", self.ports[j]), timeout=60)
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            cache[j] = c
        return c

    def refresh_loop(self):
        cache = {}
        while not self.finished:
            for j in range(self.total):
                if j == self.id:
                    continue
                try:
                    c = self.connect(j, cache)
                    c.sendall(b"B")
                    self.maps[j] = bytes(recv_exact(c, self.np))
                except OSError:
                    cache.pop(j, None)
            maps = [m for m in self.maps if m]
            if maps:
                self.counts = [sum(col) for col in zip(*maps)]
            time.sleep(self.refresh_s)

    def worker(self):
        cache = {}
        while True:
            with self.lock:
                if self.nhave == self.np:
                    return
                best, cands = 10 ** 9, []
                for i in range(self.np):                     # rarest-first
                    if self.have[i] or i in self.inflight:
                        continue
                    c = self.counts[i]
                    if c == 0:
                        continue
                    if c < best:
                        best, cands = c, [i]
                    elif c == best:
                        cands.append(i)
                idx = random.choice(cands) if cands else None
                if idx is not None:
                    self.inflight.add(idx)
            if idx is None:
                time.sleep(0.01)
                continue
            holders = [j for j in range(self.total) if j != self.id and self.maps[j] and self.maps[j][idx]]
            pool = [j for j in holders if j != 0] or holders   # poupa o seed
            if not pool:
                with self.lock:
                    self.inflight.discard(idx)
                continue
            j = random.choice(pool)
            try:
                c = self.connect(j, cache)
                c.sendall(b"G" + struct.pack("!I", idx))
                if recv_exact(c, 1)[0] == 0:
                    raise ConnectionError("peer sem a peca")
                data = recv_exact(c, self.plen(idx))
                os.pwrite(self.fd, data, idx * self.psize)
                with self.lock:
                    self.have[idx] = 1
                    self.nhave += 1
                    self.inflight.discard(idx)
            except OSError:
                try:
                    cache.pop(j).close()
                except Exception:
                    pass
                with self.lock:
                    self.inflight.discard(idx)
                time.sleep(0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--total", type=int, required=True, help="seed + leechers")
    ap.add_argument("--base-port", type=int, required=True)
    ap.add_argument("--file", help="arquivo (somente o seed)")
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--piece", type=int, required=True)
    ap.add_argument("--rate", type=float, default=50 * 1024 * 1024)
    ap.add_argument("--slots", type=int, default=4)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--refresh", type=float, default=0.2)
    ap.add_argument("--start-at", type=float, required=True)
    ap.add_argument("--workdir", default="/tmp/p2p_work")
    ap.add_argument("--out", help="arquivo JSON de resultado (leechers)")
    a = ap.parse_args()

    p = Peer(a)
    threading.Thread(target=p.serve, daemon=True).start()
    if p.is_seed:
        while True:
            time.sleep(3600)

    wait_until(a.start_at)
    t0 = time.perf_counter()
    threading.Thread(target=p.refresh_loop, daemon=True).start()
    ws = [threading.Thread(target=p.worker) for _ in range(p.workers_n)]
    for w in ws:
        w.start()
    for w in ws:
        w.join()
    t = time.perf_counter() - t0
    p.finished = True
    with open(a.out + ".tmp", "w") as f:           # escrita atomica (evita leitura parcial)
        json.dump({"id": a.id, "time": t, "ok": p.nhave == p.np}, f)
    os.replace(a.out + ".tmp", a.out)
    while True:                       # continua semeando para os demais
        time.sleep(3600)


if __name__ == "__main__":
    main()
