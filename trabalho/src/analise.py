#!/usr/bin/env python3
"""Agrega resultados.csv (media das repeticoes) e gera graficos PNG em relatorio/."""
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "resultados", "resultados.csv")
FIG = os.path.join(ROOT, "relatorio")
ORDEM = ["CS sequencial (1 por vez)", "CS multithread (todos)", "CS pool (max 5)", "P2P (swarm)"]
CORES = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad"]
MARC = ["o", "s", "^", "D"]


def carregar():
    d = defaultdict(lambda: defaultdict(list))   # (arq,size,n) -> {min,medio,max: [..]}
    for r in csv.DictReader(open(CSV)):
        k = (r["arquitetura"], int(r["tamanho_mb"]), int(r["clientes"]))
        for m in ("min_s", "medio_s", "max_s"):
            d[k][m].append(float(r[m]))
        d[k]["reps"] = d[k].get("reps", 0) or 0
    agg = {}
    for k, v in d.items():
        agg[k] = {m: sum(v[m]) / len(v[m]) for m in ("min_s", "medio_s", "max_s")}
        agg[k]["reps"] = len(v["min_s"])
    return agg


def graficos(agg):
    sizes = sorted({k[1] for k in agg})
    fig, axs = plt.subplots(1, len(sizes), figsize=(4.6 * len(sizes), 3.8))
    for ax, s in zip(axs, sizes):
        for arq, c, m in zip(ORDEM, CORES, MARC):
            pts = sorted((k[2], v["medio_s"]) for k, v in agg.items() if k[0] == arq and k[1] == s)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=m, color=c, label=arq)
        ax.set_title(f"Arquivo de {s} MB")
        ax.set_xlabel("Nº de clientes")
        ax.set_ylabel("Tempo médio de conclusão (s)")
        ax.grid(alpha=.3)
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_tempo_medio.png"), dpi=160)
    plt.close(fig)

    # min / medio / max para o maior numero de clientes de cada tamanho
    fig, axs = plt.subplots(1, len(sizes), figsize=(4.6 * len(sizes), 3.8))
    for ax, s in zip(axs, sizes):
        n = max(k[2] for k in agg if k[1] == s)
        for i, (arq, c) in enumerate(zip(ORDEM, CORES)):
            v = agg.get((arq, s, n))
            if not v:
                continue
            for j, (m, lab) in enumerate((("min_s", "mín"), ("medio_s", "méd"), ("max_s", "máx"))):
                ax.bar(i + (j - 1) * 0.26, v[m], 0.26, color=c, alpha=[.45, .75, 1][j],
                       label=lab if i == 0 else None)
        ax.set_xticks(range(len(ORDEM)))
        ax.set_xticklabels(["Seq.", "Thread", "Pool", "P2P"], fontsize=8)
        ax.set_title(f"{s} MB, {n} clientes")
        ax.set_ylabel("Tempo (s)")
        ax.grid(axis="y", alpha=.3)
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_min_med_max.png"), dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    graficos(carregar())
    print("ok")
