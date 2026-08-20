"""Motor analitico do Pharma Intelligence.

Funcoes puras de sqlite3.Connection — sem FastAPI, sem backend.app.db. Os
routers do backend chamam essas funcoes passando a conexao; qualquer camada
futura (o agente de IA da Etapa 6, por exemplo) pode reusar sem carregar a API.

Toda funcao que devolve um numero comercial (faturamento, crescimento...)
devolve tambem o "calculo": formula, periodo, valores usados. Isso alimenta o
"Ver como foi calculado" da interface — nenhum numero aparece sem proveniencia.
"""
