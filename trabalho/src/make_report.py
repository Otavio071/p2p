#!/usr/bin/env python3
"""Gera relatorio/Relatorio_Avaliacao_Desempenho.pdf a partir de resultados.csv."""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from analise import ORDEM, carregar, graficos

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "relatorio")
PDF = os.path.join(FIG, "Relatorio_Avaliacao_Desempenho.pdf")

agg = carregar()
graficos(agg)

ss = getSampleStyleSheet()
N = ParagraphStyle("N", parent=ss["Normal"], fontSize=10, leading=14, alignment=4, spaceAfter=6)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=14, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4)
CAP = ParagraphStyle("CAP", parent=N, fontSize=8.5, leading=11, alignment=1, textColor=colors.HexColor("#444444"))
TT = ParagraphStyle("TT", parent=ss["Title"], fontSize=18, leading=22)
B = ParagraphStyle("B", parent=N, leftIndent=14, bulletIndent=2, spaceAfter=2)


def p(t, st=N):
    return Paragraph(t, st)


def bullets(items):
    return [Paragraph(t, B, bulletText="\u2022") for t in items]


def tabela(size):
    ns = sorted({k[2] for k in agg if k[1] == size})
    reps = next(v["reps"] for k, v in agg.items() if k[1] == size)
    rows = [["Clientes", "Arquitetura", "Mínimo (s)", "Médio (s)", "Máximo (s)"]]
    style = [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5), ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    r = 1
    for i, n in enumerate(ns):
        for a in ORDEM:
            v = agg[(a, size, n)]
            rows.append([str(n) if a == ORDEM[0] else "", a, f"{v['min_s']:.2f}", f"{v['medio_s']:.2f}",
                         f"{v['max_s']:.2f}"])
            r += 1
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, r - 4), (-1, r - 1), colors.HexColor("#f2f4f6")))
        style.append(("LINEABOVE", (0, r - 4), (-1, r - 4), 0.8, colors.black))
    t = Table(rows, colWidths=[1.8 * cm, 6.0 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm], repeatRows=1)
    t.setStyle(TableStyle(style))
    return t, reps


s = []
s.append(p("Avaliação de Desempenho na Transferência de Arquivos:<br/>Cliente-Servidor × P2P", TT))
s.append(p("Relatório dos experimentos", ParagraphStyle("c", parent=N, alignment=1)))
s.append(Spacer(1, 6))

s.append(p("1. Objetivo", H1))
s.append(p("Comparar o tempo de conclusão da transferência de um arquivo de um nó de origem para vários nós "
           "clientes usando quatro arquiteturas: três variações de cliente-servidor (sequencial, uma thread por "
           "cliente e pool de threads) e uma arquitetura P2P. Os experimentos variam o tamanho do arquivo "
           "(5 MB, 50 MB e 500 MB) e o número de clientes. Para cada experimento são reportados os tempos "
           "<b>mínimo, médio e máximo</b> de conclusão entre os clientes. Nos clientes o arquivo baixado é descartado "
           "(não é gravado em disco)."))

s.append(p("2. Arquiteturas implementadas", H1))
s.append(p("Tudo foi implementado em Python 3 (somente biblioteca padrão), sobre sockets TCP."))
s += bullets([
    "<b>CS sequencial</b> (<i>server.py --mode seq</i>): o servidor atende um download por vez; os demais "
    "clientes aguardam na fila de conexões do TCP.",
    "<b>CS multithread</b> (<i>--mode thread</i>): uma thread por conexão; todos os clientes são atendidos "
    "simultaneamente e dividem a banda do servidor.",
    "<b>CS pool</b> (<i>--mode pool</i>): pool com N = 5 threads; no máximo 5 clientes são atendidos ao mesmo tempo "
    "e os demais esperam na fila do pool.",
    "<b>P2P</b> (<i>p2p_peer.py</i>, implementação própria no estilo BitTorrent): o arquivo é dividido em peças "
    "(256 KB para 5 MB; 1 MB para 50 e 500 MB). Há 1 seed (peer com o arquivo completo) e N leechers. Cada leecher "
    "consulta periodicamente (a cada 0,2 s) o mapa de peças dos demais peers, escolhe a peça mais rara "
    "(<i>rarest-first</i>, desempate aleatório), prefere buscá-la de outro leecher para poupar o seed e, assim que "
    "recebe uma peça, passa a servi-la aos outros. Cada peer atende no máximo 4 uploads simultâneos e usa 4 "
    "threads de download. Peers que terminam continuam semeando até o fim do experimento.",
])

s.append(p("3. Metodologia", H1))
s += bullets([
    "<b>Ambiente:</b> máquina virtual Linux (Ubuntu 24) com 1 vCPU e 4 GB de RAM; todos os nós são processos "
    "distintos comunicando-se por TCP em <i>localhost</i>.",
    "<b>Emulação de rede:</b> como o loopback não possui gargalo, a banda de <b>upload de cada nó</b> (servidor ou peer) "
    "foi limitada a 50 MB/s (400 Mbit/s) por um limitador compartilhado entre todas as conexões do nó, "
    "equivalente a uma única placa de rede. O download não é limitado.",
    "<b>Sincronização:</b> todos os clientes aguardam um instante de início comum; o tempo de cada cliente é medido "
    "da sua abertura de conexão (ou início do swarm) até receber o último byte. No servidor com fila (sequencial e pool) "
    "o tempo de espera na fila faz parte do tempo medido.",
    "<b>Variáveis:</b> tamanho do arquivo (5, 50 e 500 MB) e nº de clientes (1, 5, 10 e 20; para 500 MB, 1, 5 e 10). "
    "No P2P, \"clientes\" = nº de leechers, além de 1 seed.",
    "<b>Repetições:</b> 3 execuções (5 MB), 2 (50 MB) e 1 (500 MB). Em cada execução calcula-se o mínimo, a média e o "
    "máximo entre os clientes; as tabelas mostram a média desses valores entre as repetições. Os dados brutos "
    "(tempo de cada cliente) estão em <i>resultados/resultados.csv</i>.",
    "<b>Integridade:</b> cada cliente verifica que recebeu todos os bytes (o experimento é invalidado caso contrário).",
])

s.append(p("Modelo esperado.", H2))
s.append(p("Seja S o tamanho do arquivo e C = 50 MB/s a banda de upload. Para S = 500 MB, S/C = 10 s. "
           "No servidor sequencial o k-ésimo cliente termina em k·S/C: mínimo S/C, médio (N+1)/2·S/C e máximo N·S/C. "
           "No multithread todos terminam juntos em N·S/C. No pool de 5 threads os clientes terminam em lotes de 5: "
           "com N = 10 em 5·S/C e 10·S/C (mínimo 50 s, médio 75 s, máximo 100 s). No P2P o seed precisa enviar apenas "
           "uma cópia do arquivo (S/C) e os peers se ajudam, de modo que o tempo cresce muito mais devagar com N."))

s.append(PageBreak())
s.append(p("4. Resultados", H1))
s.append(p("Tempos de conclusão da transferência por cliente, em segundos (mínimo, médio e máximo entre os clientes).", N))
for size in (5, 50, 500):
    t, reps = tabela(size)
    s.append(p(f"4.{ {5: 1, 50: 2, 500: 3}[size] } Arquivo de {size} MB ({reps} repetição(ões) por configuração)", H2))
    s.append(t)
    s.append(Spacer(1, 6))
    if size == 5:
        s.append(PageBreak())

s.append(PageBreak())
s.append(p("4.4 Gráficos", H2))
s.append(Image(os.path.join(FIG, "fig_tempo_medio.png"), width=17 * cm, height=17 * cm * 3.8 / 13.8))
s.append(p("Figura 1 – Tempo médio de conclusão em função do número de clientes.", CAP))
s.append(Spacer(1, 8))
s.append(Image(os.path.join(FIG, "fig_min_med_max.png"), width=17 * cm, height=17 * cm * 3.8 / 13.8))
s.append(p("Figura 2 – Tempos mínimo, médio e máximo para o maior número de clientes de cada tamanho.", CAP))

s.append(p("5. Análise", H1))
v = lambda a, sz, n, m: agg[(a, sz, n)][m]
s += bullets([
    f"<b>Um único cliente:</b> as quatro arquiteturas são equivalentes (500 MB: {v(ORDEM[0],500,1,'medio_s'):.1f} s no CS e "
    f"{v(ORDEM[3],500,1,'medio_s'):.1f} s no P2P), pois o limite é a banda de upload de um nó.",
    f"<b>CS sequencial:</b> melhor tempo mínimo (o primeiro cliente recebe a banda inteira: "
    f"{v(ORDEM[0],500,10,'min_s'):.1f} s com 10 clientes), mas o máximo cresce linearmente com N "
    f"({v(ORDEM[0],500,10,'max_s'):.1f} s). É justo apenas na ordem de chegada; o último cliente espera por todos.",
    f"<b>CS multithread:</b> divide a banda igualmente; mínimo, médio e máximo coincidem "
    f"(≈ {v(ORDEM[1],500,10,'medio_s'):.0f} s para 10 clientes e 500 MB). É o pior caso para o tempo médio, pois "
    "ninguém termina antes de todos; em compensação, a variação entre clientes é mínima.",
    f"<b>CS pool:</b> com N ≤ 5 comporta-se como o multithread; acima disso, atende em lotes e reduz o tempo médio "
    f"({v(ORDEM[2],500,10,'medio_s'):.0f} s contra {v(ORDEM[1],500,10,'medio_s'):.0f} s) sem alterar o tempo máximo. "
    "Também limita o consumo de recursos do servidor (threads e conexões ativas).",
    f"<b>P2P:</b> escala muito melhor. Para 500 MB e 10 clientes o máximo foi {v(ORDEM[3],500,10,'max_s'):.1f} s, "
    f"contra ≈ {v(ORDEM[1],500,10,'max_s'):.0f} s do CS (cerca de {v(ORDEM[1],500,10,'max_s')/v(ORDEM[3],500,10,'max_s'):.1f}x mais rápido); "
    f"para 50 MB e 20 clientes, {v(ORDEM[3],50,20,'max_s'):.1f} s contra {v(ORDEM[1],50,20,'max_s'):.1f} s. Como cada peer "
    "contribui com sua banda de upload, a capacidade total do sistema cresce com o número de nós, ao passo que no CS "
    "a banda do servidor é dividida entre todos.",
    f"<b>Custo do P2P:</b> o tempo mínimo do P2P é maior que o do sequencial (ex.: {v(ORDEM[3],500,10,'min_s'):.1f} s "
    f"contra {v(ORDEM[0],500,10,'min_s'):.1f} s), pois a banda do seed é compartilhada desde o início. Para arquivos pequenos "
    f"(5 MB) o ganho é menor, pois a coordenação (consulta de mapas de peças, conexões) pesa mais em relação ao "
    f"tempo total ({v(ORDEM[3],5,20,'max_s'):.2f} s no P2P contra {v(ORDEM[1],5,20,'max_s'):.2f} s no CS multithread).",
    "<b>Tendência com N:</b> nos CS o tempo máximo cresce proporcionalmente a N·S/C (ex.: 50 MB: 5, 10 e 20 s para 5, "
    "10 e 20 clientes). No P2P o crescimento é sublinear (50 MB: 2,7, 3,7 e 5,5 s), em linha com o que a literatura "
    "prevê para swarms (tempo de distribuição ≈ S/C + crescimento logarítmico em N).",
])

s.append(p("6. Limitações", H1))
s += bullets([
    "Os experimentos foram executados em uma única máquina com 1 vCPU (todos os nós disputam a mesma CPU), com banda "
    "emulada por software. Os valores absolutos não representam uma rede real (latência, perdas, banda de download "
    "e caminhos heterogêneos não são modelados), mas as tendências relativas entre as arquiteturas são válidas.",
    "Para 500 MB foram usados no máximo 10 clientes: no P2P cada peer guarda as peças em disco temporário para poder "
    "re-semear, e 20 cópias de 500 MB excederiam o espaço disponível. Também só houve 1 repetição nesse tamanho "
    "(os tempos do CS são muito estáveis, mas o P2P tem variação aleatória maior).",
    "O P2P é uma implementação simplificada (sem tracker, sem tit-for-tat, peers fixos e todos conectados entre si), "
    "e não um cliente BitTorrent completo.",
])

s.append(p("7. Conclusão", H1))
s.append(p("Com poucos clientes ou arquivos pequenos, o modelo cliente-servidor é simples e suficiente. À medida que o "
           "número de clientes e o tamanho do arquivo crescem, o servidor torna-se o gargalo e o tempo de conclusão cresce "
           "linearmente com N, qualquer que seja a política de atendimento (sequencial, multithread ou pool); a política "
           "apenas redistribui o tempo entre os clientes (sequencial e pool favorecem o tempo médio e mínimo, multithread "
           "favorece a equidade). O P2P reduz de forma significativa o tempo máximo e o médio ao aproveitar a banda de "
           "upload dos próprios clientes, sendo a melhor opção para distribuir arquivos grandes a muitos nós."))

s.append(p("8. Como reproduzir", H1))
s.append(p("<font face='Courier' size=8.5>cd src &amp;&amp; python3 run_experiments.py &nbsp; # executa os experimentos "
           "(gera resultados/resultados.csv)<br/>python3 make_report.py &nbsp; # gera gráficos e este PDF</font>"))


def rodape(c, d):
    c.setFont("Helvetica", 8)
    c.drawCentredString(A4[0] / 2, 1.2 * cm, f"Página {d.page}")


SimpleDocTemplate(PDF, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                  title="Avaliação de Desempenho – Cliente-Servidor × P2P").build(s, onFirstPage=rodape, onLaterPages=rodape)
print(PDF)
