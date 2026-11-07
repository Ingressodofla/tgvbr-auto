# TGV BR Auto

Operação de conteúdo da **The Game Versus BR** (Instagram, Facebook e TikTok), foco inicial em **GTA VI**.

Estado: **etapa 1 pronta** — descoberta, análise, ranking e painel. Produção, publicação e métricas vêm nas próximas etapas ([plano](docs/ARCHITECTURE.md#6-plano-de-implementação-por-etapas)). **Nada é publicado.**

## Rodar

Requisitos: Python 3.11+. A etapa 1 não usa pacotes de terceiros.

```bash
python -m tgv run
```

Isso coleta das fontes ativas, deduplica, classifica, pontua e gera `out/dashboard.html`. O banco fica em `data/tgv.db` (fora do Git).

Outros comandos:

```bash
python -m tgv rank --limit 15
```

```bash
python -m tgv select --limit 5
```

```bash
python -m tgv import-csv achados_tiktok.csv
```

```bash
python -m tgv youtube-channel @RockstarGames
```

## Credenciais

Copie `.env.example` e preencha no seu ambiente (nunca no repositório). Sem chave, a fonte é pulada e o painel avisa.
- `TGV_YOUTUBE_API_KEY`: Google Cloud → APIs e serviços → ativar "YouTube Data API v3" → Credenciais → chave de API (restrinja à YouTube Data API). **Não precisa ter canal no YouTube**: basta uma conta Google. A chave só lê dados públicos.
- `TGV_REDDIT_CLIENT_ID` / `TGV_REDDIT_CLIENT_SECRET`: só depois da aprovação da Reddit.

## Agendar

A cada 2 horas, por exemplo (cron no Linux/macOS):

```bash
0 */2 * * * cd /caminho/tgvbr-auto && TGV_YOUTUBE_API_KEY=... python3 -m tgv run >> data/cron.out 2>&1
```

No Windows, use o Agendador de Tarefas com o mesmo comando. Com 3 termos × 2 regiões, cada ciclo gasta ~600 unidades de cota do YouTube; o orçamento diário padrão (6.000) para o YouTube antes de estourar e as fontes RSS seguem rodando.

## Testes

```bash
python -m unittest discover -s tests -t .
```

## Documentação
- [Arquitetura, ferramentas, custos, agentes e plano](docs/ARCHITECTURE.md)
- [Limites das plataformas](docs/PLATFORM_LIMITS.md)
- [Regras editoriais e de direitos](docs/COMPLIANCE.md)
