# Pharma Intelligence

Motor de inteligência comercial farmacêutica: BI local para análise de
distribuidores, produtos, PDVs, vendas, estoque e mercado — na ótica de um
Gerente de Contas, não de um dashboard genérico.

O objetivo não é descrever números. É responder: **onde estamos perdendo venda,
o que priorizar, quem mobilizar e o que executar amanhã com o distribuidor.**

Cópia isolada do motor original em `Agente Farmacêutico` (que continua rodando
sem alteração, na Desktop). Aqui ele vira aplicação web: banco, importação de
múltiplas fontes com detecção automática, perfil do dado e (nas próximas
etapas) as análises comerciais completas. Todo cálculo quantitativo é local —
sem custo obrigatório de API de IA.

Contexto: indústria **VITAMEDIC**. Primeiro cliente analisado: **EMEFARMA (RJ + ES)**.

---

## Como rodar a plataforma web

Windows, um usuário, tudo local — sem custo de nuvem.

```bash
instalar.bat   REM uma vez: cria o ambiente Python e instala o frontend
iniciar.bat    REM dia a dia: sobe a API (8000), a interface (3000) e abre o navegador
parar.bat      REM desliga os dois
```

`dev.bat` sobe a API com `--reload`, só para desenvolvimento — nunca use durante
uma importação longa, porque qualquer alteração de código derruba o processo no
meio.

Verificação de ponta a ponta (backend + banco + os 3 arquivos reais):

```bash
backend\.venv\Scripts\python.exe backend\testar_etapa1.py --completo
```

### Estrutura da aplicação

```
backend/       FastAPI — routers/, ingest/ (adaptadores + perfilador), core/
frontend/      React + TypeScript + Vite
database/      schema.sql, seed.sql, pharma.db (gerado, fora do git)
imports/       arquivos importados, organizados por sha256 (fora do git)
analytics/     reservado para as análises comerciais (Etapa 2+)
reports/       reservado para relatório executivo (Etapa 6+)
prompts/       reservado para o gerador de prompt / respostas do Claude (Etapa 5+)
```

---

## O motor original (`engine/`)

Os scripts abaixo continuam funcionando exatamente como antes — a plataforma
web reusa `vmd.py` e `iqvia.py` sem alterar uma linha, e `analise.py` serve de
oráculo de conferência para a importação (os totais têm que bater ao centavo).

### Estrutura

```
dados/       exports originais dos dashboards (entrada)
engine/      motor de leitura + scripts de análise
cache/       derivados descompactados (regenerável, fora do git)
relatorios/  dossiês entregues
```

### Como rodar pelo terminal

Requisitos: Python 3.12 e `numpy`.

```bash
"C:\Users\Home\AppData\Local\Programs\Python\Python312\python.exe" -m pip install numpy
```

Depois, a partir de `engine/`. A análise completa de qualquer distribuidor sai de um comando:

```bash
cd engine && "C:\Users\Home\AppData\Local\Programs\Python\Python312\python.exe" analise.py MILLENIUM
```

Na primeira execução o motor descompacta as bases para `cache/` (leva ~1 min e
gera ~122 MB). As execuções seguintes leem do cache — inclusive as da
plataforma web, que compartilha o mesmo `cache/pack.bin`.

### Motor

| Arquivo | O que faz |
|---|---|
| `config.py` | Caminhos do projeto. Tudo resolve a partir da raiz. |
| `vmd.py` | Lê o sell-out (formato binário VMD1). Descompacta sozinho na 1ª vez. |
| `iqvia.py` | Lê a base IQVIA Mercado Relevante (dados de concorrência). |

### Análises

Os três scripts parametrizados cobrem quase tudo — recebem o nome do distribuidor
como argumento:

| Script | Pergunta que responde | Base |
|---|---|---|
| `analise.py NOME` | **Análise completa** — volume, YoY, CNPJ × UF, crescimento vs estado, curva ABC, churn, mix, cobertura, cross-sell, white spot, preço, carteira, tendência | sell-out |
| `a09_ponte_molecula.py NOME` | Preço e share da Vitamedic na molécula de cada SKU que o distribuidor vende | IQVIA |
| `a10_perda_industria.py A B` | Separa perda do **distribuidor** de perda da **indústria**, cruzando duas carteiras | sell-out |
| `a11_robustez_preco.py` | Testa se a conclusão sobre preço muda ao comparar com o líder em vez da média | IQVIA |

### Conferência antes de publicar

Rode os dois antes de mandar um dossiê para reunião:

| Script | O que confere |
|---|---|
| `verifica_dossies.py` | Recomputa **38 números** afirmados nos dossiês direto da base e aponta divergências |
| `valida_dossies.py` | Estrutura HTML: tags balanceadas, tabelas com colunas consistentes, numeração das seções |

Os dois saem com código 0 quando está tudo certo, então dá para encadear.

Os demais são recortes de apoio, escritos durante a primeira análise:

| Script | Pergunta que responde | Base |
|---|---|---|
| `a01_emefarma_visao.py` | Volume, evolução mensal, ranking nacional | sell-out |
| `a02_emefarma_deep.py` | Crescimento YoY e curva ABC | sell-out |
| `a03_pdv_whitespot.py` | Churn de PDV, mix, lacunas vs concorrentes | sell-out |
| `a04_cobertura_mix.py` | Cobertura por SKU, cross-sell, perfil da carteira | sell-out |
| `a05_preco.py` | Preço vs outros distribuidores da praça | sell-out |
| `a06_vs_estado.py` | Crescimento e share contra o próprio estado | sell-out |
| `a07_crosstab.py` | CNPJ × UF do PDV — separa unidade de praça | sell-out |
| `a08_preco_concorrentes.py` | Preço vs indústrias, varrendo os 104 mercados relevantes | IQVIA |

Esses ainda têm o distribuidor fixo no código (`idx_of("provNome", "...")`).

---

## Formato das bases

Os dashboards exportados são HTML grandes com a base inteira embutida. São dois
formatos diferentes, ambos já decodificados pelo motor.

### Sell-out — formato binário próprio `VMD1`

Payload em `<script id="pack">`, como **base64 → gzip → binário VMD1**:

```
"VMD1" (4 bytes) + uint32 LE do tamanho do header + header JSON + colunas
```

Três coisas que custam caro se passarem despercebidas:

1. **O offset `o` de cada coluna é em BYTES**, não em elementos.
2. **`fUnd` e `fVal` vêm multiplicados por 100** — o JS do dashboard faz `und/100, val/100`.
   Esquecer isso infla tudo em 100×.
3. **`provNome` é o distribuidor** (o cliente). `grupo` é a rede de farmácias do PDV —
   coisa diferente.

Versão de 14/08/2026: 6.802.108 linhas, jan/2025 a jul/2026, 547 distribuidores,
112.933 PDVs, 240 apresentações.

### Mercado Relevante — JSON puro (IQVIA)

Payload em `<script type="application/json" id="__model_json__">`, sem compressão.
Abas `m24` (24 meses) e `m5` (5 anos MAT junho).

Layout de cada linha de `sku`, documentado no próprio JS do dashboard:

```
[mer, apre, uf, canal, tipo, labFull, uL, rL, uP, rP, uYtd, rYtd, uYtdP, rYtdP]
```

`L` = último mês · `P` = mês anterior · `Ytd` = acumulado do ano · `YtdP` = ano anterior.

### Estoque do distribuidor — Excel (`.xlsx`)

Export próprio do distribuidor, uma linha por SKU × filial. Colunas usadas na análise:
`Cobertura` (dias de estoque no ritmo de venda atual), `Estoque Disponível R$` (valor a
custo de reposição), `Média Venda R$` (últimos 4 meses). Linhas de subtotal (`Filial` =
`Total` ou `Nenhum filtro aplicado`) devem ser descartadas antes de somar.

Cuidado: nem toda filial vem com posição física. No export de 20/08/2026 o RJ tinha
estoque completo e o ES só tinha dados de venda — sinal de operação sem estoque próprio
(cross-dock a partir do CD do RJ), a confirmar com o distribuidor.

---

## Cuidado ao cruzar as duas bases

Elas medem **elos diferentes da cadeia** e não devem ser comparadas entre si:

- **Sell-out**: preço do distribuidor para o PDV. Share = entre distribuidores de Vitamedic.
- **IQVIA**: preço do PDV para o consumidor. Share = da indústria Vitamedic no varejo,
  incluindo o que outros distribuidores e a venda direta entregam.

Um share baixo no IQVIA não é falha do distribuidor — é espaço de mercado.

## Cuidado ao ler por CNPJ

CNPJ do faturador **não é** praça de venda. O CNPJ "EMEFARMA ES" atendia São Paulo,
e por isso aparecia em queda mesmo tendo crescido 90% no próprio estado.
Para avaliar praça, use sempre a **UF do PDV** (`a06`/`a07`), nunca o CNPJ.

## Cuidado ao somar valor de PDV

Um PDV compra Vitamedic de vários distribuidores. Ao medir **quanto um distribuidor
perdeu**, some só o que aquele PDV comprava *dele* — filtrando por `fProv`. Somar o
valor total do PDV infla a perda em 2 a 4 vezes. Ao medir **perda da indústria**, aí sim
use o total. Os dois cortes aparecem lado a lado em `a10_perda_industria.py`.

## Preço: comparar com o líder, não com a média

Ao medir preço da Vitamedic contra a concorrência, use o **líder de volume** da molécula.
A média ponderada dos concorrentes engana: concorrentes caros de baixo volume a puxam
para cima e fazem um produto caro parecer barato.

**Em 25 dos 104 mercados relevantes (24%) o sinal inverte.** O caso extremo é o Biovarixon
450+50mg × 30: 11% *abaixo* da média e 49% *acima* do líder Teuto. Rode
`a11_robustez_preco.py` para reproduzir.

A conclusão de fundo — preço não explica share — sobrevive aos dois critérios
(correlação de +0,12 pela média, +0,08 pelo líder), mas as decisões por SKU mudam.

## Perda do distribuidor não é perda da indústria

Cruzando as carteiras de MILLENIUM e EMEFARMA, 268 PDVs foram perdidos pelos dois ao
mesmo tempo — e 178 deles (R$ 448 mil) simplesmente pararam de comprar Vitamedic de
qualquer distribuidor. Cobrar isso do distribuidor é cobrança indevida: nem o concorrente
segurou. No agregado, a Vitamedic passou de 100.778 para 97.198 PDVs compradores
entre 2025 e 2026 — 13.914 sumiram, valendo R$ 17,0 milhões.

---

## Método das análises

Toda conclusão segue: **DADO → DIAGNÓSTICO → OPORTUNIDADE → AÇÃO → KPI**, e é
rotulada como uma de três coisas:

- **FATO** — o que os dados comprovam.
- **HIPÓTESE** — explicação possível, ainda não validada.
- **RECOMENDAÇÃO** — a ação sugerida.

Projeções de potencial não são somadas quando as alavancas se sobrepõem, e as
premissas são declaradas junto do número.

---

## Dossiês entregues

| Conta | Arquivo | Achado principal |
|---|---|---|
| EMEFARMA (RJ+ES) | `relatorios/emefarma-agosto-2026.html` | Toda a queda foi recuo de SP; ex-SP a conta cresceu 6,2%. Ganhou share nos dois estados de casa. Seção 12 cruza estoque (20/08/2026): R$ 318,9 mil parados em 53 SKUs no RJ, 89% do excesso da linha VMS já é zumbi. |
| MILLENIUM (RJ+ES) | `relatorios/millenium-agosto-2026.html` | Duas operações opostas: ES +69,7% e assumiu a liderança; RJ −25,8%, único recorte abaixo da praça. |

As duas contas disputam o Rio: a vantagem do MILLENIUM caiu de 10,36 pp para 3,61 pp
em doze meses.

Os dossiês têm botão de tema claro/escuro no canto superior direito, com a preferência
salva no navegador. O botão some na impressão e no PDF.

## Estado atual

- [x] Motor de leitura das duas bases (`engine/`, terminal)
- [x] Análise parametrizada por distribuidor (`analise.py NOME`)
- [x] Dossiês EMEFARMA e MILLENIUM
- [x] **Etapa 1 — Pharma Intelligence:** arquitetura, banco, importação das 3
      fontes com detecção automática, perfil do dado, cadastro de clientes
- [x] **Etapa 2 — Motor de performance comercial:** dashboard por cliente e
      período (resumo, YoY/MoM, evolução mensal, ranking e variação de
      produto, UF, PDV, concentração, alertas), tudo calculado localmente
- [ ] Etapa 3 — curva ABC, cobertura, mix, estoque, DDE, capital parado
- [ ] Etapa 4 — mercado, IQVIA, share, preço, regiões
- [ ] Etapa 5 — anomalias, oportunidades, simulador, matriz
- [ ] Etapa 6 — agente, FATO/HIPÓTESE/RECOMENDAÇÃO, limitações, gerador de prompt
- [ ] Etapa 7 — relatório executivo, histórico, refinamento visual
