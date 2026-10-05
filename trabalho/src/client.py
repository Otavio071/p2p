#!/usr/bin/env python3
"""Cliente: baixa o arquivo e DESCARTA os dados (nao grava em disco). Imprime o tempo em JSON.

uso: client.py PORTA INICIO_EPOCH ID
"""
import json
import socket
import struct
import sys
import time

from common import recv_exact, wait_until

port, start_at, cid = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
buf = bytearray(256 * 1024)
mv = memoryview(buf)
wait_until(start_at)                       # todos os clientes comecam ao mesmo tempo
t0 = time.perf_counter()
s = socket.create_connection(("127.0.0.1", port), timeout=1800)
(size,) = struct.unpack("!Q", recv_exact(s, 8))
got = 0
while got < size:
    r = s.recv_into(mv)
    if not r:
        break
    got += r                               # dado descartado
t = time.perf_counter() - t0
print(json.dumps({"id": cid, "bytes": got, "time": t, "ok": got == size}))
