# Avaliação de desempenho: transferência de arquivo Cliente-Servidor x P2P

Conteúdo:
- relatorio/Relatorio_Avaliacao_Desempenho.pdf  -> relatório (PDF)
- src/        -> código (Python 3, somente biblioteca padrão; matplotlib/reportlab só p/ gráficos e PDF)
    server.py (modos seq | thread | pool), client.py (descarta os dados), p2p_peer.py (P2P estilo BitTorrent),
    run_experiments.py (executa tudo), analise.py (gráficos), make_report.py (gera o PDF)
- resultados/ -> resultados.csv (tempo de cada cliente em cada execução) e log_execucao.txt

Reproduzir:
    cd src
    python3 run_experiments.py      # ~25 min, 1 vCPU; precisa de ~5 GB livres em /tmp (P2P 500 MB)
    python3 make_report.py          # requer matplotlib e reportlab

Banda de upload de cada nó emulada em 50 MB/s; tudo em localhost.
