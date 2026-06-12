# Verificador de Cartões

MVP em Python para:
- ler vários PDFs misturados
- identificar o cliente
- identificar o primeiro processo válido da esquerda para a direita
- agrupar por processo + cliente + cor
- gerar um PDF final para cada grupo
- montar a saída em **6 cartões por folha**
- levar o **desenho técnico no verso** quando o cartão estiver marcado com `SIM`

## Ajustado para os seus PDFs reais

Esta versão já considera o layout observado nos arquivos enviados:
- até 6 cartões por página
- leitura do cliente pelo texto entre `CLIENTE` e `PEDIDO ITEM`
- leitura do roteiro pela seção `ROTEIRO`
- primeiro processo = primeira coluna com `SIM` da esquerda para a direita
- detecção de `DESENHO TÉCNICO = SIM/NÃO`
- saída final em lotes de 6 cartões por folha
- criação de página de verso com os desenhos quando existirem

## Como usar

### Interface desktop

Abra o executavel gerado para Windows.

### Interface web com Docker

Rode:

```bash
docker compose up -d --build
```

Acesse `http://localhost:8080`, envie os PDFs e baixe os resultados.

Os arquivos processados ficam armazenados no volume Docker
`verificador_data`.

### Linha de comando

1. Coloque os PDFs de entrada na pasta `input/`.
2. Rode:

```bash
python main.py
```

## Saídas

- PDFs agrupados em `output/`
- cartões para revisão em `logs/cards_review.csv`
- resumo em `logs/summary.json`
- log detalhado em `logs/debug_cards.json`

## Regras já cadastradas

- WEG BLUMENAU = AZUL
- WEG GRAVATAI = LARANJA
- WEG BETIM = VERMELHO
- BLUTRAFOS = BRANCO

## Implantacao no Dockhand

1. Em **Settings > Git**, cadastre este repositorio e a credencial do GitHub.
2. Em **Compose Stacks**, escolha criar uma stack a partir do Git.
3. Selecione a branch `main` e o arquivo `docker-compose.yml`.
4. Implante a stack.

A porta padrao e `8080`. Para alterar, configure a variavel `APP_PORT`.
O limite padrao de upload e 200 MB e pode ser alterado com
`MAX_UPLOAD_MB`.

Como a interface nao possui login proprio e armazena os PDFs processados,
publique-a apenas em rede interna ou proteja-a com autenticacao no proxy
reverso.
