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
