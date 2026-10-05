#!/usr/bin/env python3
"""Orquestrador: executa todos os experimentos e grava resultados/resultados.csv (retomavel).

uso: python3 run_experiments.py [--quick]
"""
import argparse
import csv
import glob
import json
import os
import shutil
import socket
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("DATA_DIR", "/tmp/dados_exp")
OUT = os.path.join(ROOT, "resultados", "resultados.csv")
MB = 1024 * 1024
RATE = 50 * MB          # upload de cada maquina (servidor ou peer): 50 MB/s (~400 Mbit/s)
POOL_N = 5              # N do servidor com pool de threads
_port = [21000]


def next_port(span=1):
    p = _port[0]
    _port[0] += span + 2
    return p


def ensure_file(size_mb):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"arquivo_{size_mb}MB.bin")
    if not os.path.exists(path) or os.path.getsize(path) != size_mb * MB:
        with open(path, "wb") as f:
            for _ in range(size_mb):
                f.write(os.urandom(MB))
    return path


def wait_port(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("servidor nao subiu")


def run_cs(mode, size_mb, n):
    path = ensure_file(size_mb)
    port = next_port()
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py"), "--mode", mode, "--port", str(port),
                            "--file", path, "--rate", str(RATE), "--workers", str(POOL_N)], cwd=HERE)
    try:
        wait_port(port)
        start = time.time() + 1.0 + 0.1 * n
        cl = [subprocess.Popen([sys.executable, os.path.join(HERE, "client.py"), str(port), str(start), str(i)],
                               cwd=HERE, stdout=subprocess.PIPE, text=True) for i in range(n)]
        res = []
        for c in cl:
            out, _ = c.communicate(timeout=3600)
            res.append(json.loads(out.strip().splitlines()[-1]))
        assert all(r["ok"] for r in res), "download incompleto"
        return [r["time"] for r in res]
    finally:
        srv.kill()
        srv.wait()


def run_p2p(size_mb, n):
    path = ensure_file(size_mb)
    size = size_mb * MB
    piece = 256 * 1024 if size_mb <= 5 else MB
    base = next_port(n + 1)
    work = "/tmp/p2p_work"
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    start = time.time() + 2.0 + 0.3 * n
    common = ["--total", str(n + 1), "--base-port", str(base), "--size", str(size), "--piece", str(piece),
              "--rate", str(RATE), "--start-at", str(start), "--workdir", work]
    procs = [subprocess.Popen([sys.executable, os.path.join(HERE, "p2p_peer.py"), "--id", "0", "--file", path] + common,
                              cwd=HERE)]
    time.sleep(0.5)
    outs = []
    for i in range(1, n + 1):
        o = os.path.join(work, f"res_{i}.json")
        outs.append(o)
        procs.append(subprocess.Popen([sys.executable, os.path.join(HERE, "p2p_peer.py"), "--id", str(i), "--out", o]
                                      + common, cwd=HERE))
    try:
        t0 = time.time()
        while not all(os.path.exists(o) for o in outs):
            time.sleep(0.5)
            if time.time() - t0 > 3600:
                raise RuntimeError("timeout P2P")
        res = [json.load(open(o)) for o in outs]
        assert all(r["ok"] for r in res), "download incompleto"
        return [r["time"] for r in res]
    finally:
        for p in procs:
            p.kill()
        for p in procs:
            p.wait()
        shutil.rmtree(work, ignore_errors=True)


ARCHS = {
    "CS sequencial (1 por vez)": lambda s, n: run_cs("seq", s, n),
    "CS multithread (todos)": lambda s, n: run_cs("thread", s, n),
    f"CS pool (max {POOL_N})": lambda s, n: run_cs("pool", s, n),
    "P2P (swarm)": run_p2p,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="teste rapido")
    a = ap.parse_args()
    if a.quick:
        plan = [(5, [1, 3], 1)]
    else:
        # (tamanho MB, lista de nos clientes, repeticoes)
        plan = [(5, [1, 5, 10, 20], 3), (50, [1, 5, 10, 20], 2), (500, [1, 5, 10], 1)]

    done = set()
    if os.path.exists(OUT) and not a.quick:
        for r in csv.DictReader(open(OUT)):
            done.add((r["arquitetura"], int(r["tamanho_mb"]), int(r["clientes"]), int(r["rep"])))
    new = not os.path.exists(OUT) or a.quick
    f = open(OUT if not a.quick else OUT + ".quick", "w" if new else "a", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["arquitetura", "tamanho_mb", "clientes", "rep", "min_s", "medio_s", "max_s", "tempos_s"])
    for size_mb, ns, reps in plan:
        for n in ns:
            for arch, fn in ARCHS.items():
                for rep in range(1, reps + 1):
                    if (arch, size_mb, n, rep) in done:
                        continue
                    t0 = time.time()
                    ts = fn(size_mb, n)
                    w.writerow([arch, size_mb, n, rep, f"{min(ts):.3f}", f"{statistics.mean(ts):.3f}",
                                f"{max(ts):.3f}", ";".join(f"{t:.3f}" for t in ts)])
                    f.flush()
                    print(f"{arch:28s} {size_mb:4d}MB n={n:2d} rep={rep} min={min(ts):7.2f} "
                          f"med={statistics.mean(ts):7.2f} max={max(ts):7.2f}  (exec {time.time()-t0:.0f}s)", flush=True)
    f.close()


if __name__ == "__main__":
    main()
