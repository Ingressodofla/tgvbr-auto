# Arquitetura — TGV BR Auto

> Sistema de operação de conteúdo da **The Game Versus BR**, foco inicial em **GTA VI**.
> Fluxo: DESCOBERTA → ANÁLISE → SELEÇÃO → PRODUÇÃO → VALIDAÇÃO → AGENDAMENTO → PUBLICAÇÃO → MÉTRICAS.
> Estado: **etapa 1 implementada** (descoberta, análise, seleção, banco, painel). Nada é publicado.

## 1. Arquitetura proposta

```
              ┌──────────────── agendador (cron / GitHub Actions / PC) ────────────────┐
              │                                                                         │
 FONTES ──► [1 Descoberta] ──► [2 Análise] ──► [3 Seleção] ──► [4 Produção] ──► [5 Validação]
 RSS, YouTube   conectores      dedup,          1 por história   roteiro, voz,    regras + fila
 API, Reddit,   isolados        classificação,  sem itens em     legendas,        de revisão
 CSV manual     por fonte       score 0-100     revisão          FFmpeg 1080x1920 humana
                                                                                    │
                    ┌──────────────────────────────────────────────────────────────┘
                    ▼
            [6 Agendamento/Publicação] ──► [7 Métricas] ──► pesos do score (retroalimentação)
             Meta Graph API (IG, FB),        insights de cada
             TikTok Content Posting API      rede + seguidores
                    │
                    └──► SQLite (um arquivo) ◄── painel HTML estático (owner)
```

Princípios:
- **Módulos independentes** em Python, cada um com entrada e saída no banco. Uma fonte quebrada não para as outras (cada execução fica em `runs`, cada falha em `alerts`).
- **Determinístico onde dá, IA só onde agrega** (roteiro, tradução, título). A classificação de risco (rumor, vazamento, licença) é por regra explícita e testada, não por modelo.
- **Sem servidor na etapa 1**: SQLite + HTML estático. Dá para rodar no PC do dono, num VPS pequeno ou no GitHub Actions.
- **Credenciais só em variáveis de ambiente** ou no cofre do agendador (GitHub Secrets). Nunca em código, config, banco ou log.
- **Portão humano**: rumor, vazamento e reutilização de mídia de terceiros sempre vão para a fila de revisão. Publicação real só depois da sua autorização inicial e dos testes.

Código (etapa 1):

| Módulo | Função |
|---|---|
| `tgv/sources/rss.py` | RSS/Atom: sites de games, Google News, feeds de canais do YouTube (trazem views sem gastar cota) |
| `tgv/sources/youtube.py` | YouTube Data API v3: busca recente por termo e região, estatísticas, licença, controle de cota |
| `tgv/sources/reddit.py` | Reddit OAuth (desligado até a Reddit liberar o acesso) |
| `tgv/sources/manual.py` | Importação CSV: alternativa documentada para TikTok e Instagram |
| `tgv/dedup.py` | Mesma URL (YouTube, Reddit, parâmetros de rastreio) e mesma história (títulos parecidos em 72 h) |
| `tgv/classify.py` | Relevância GTA VI, oficial / imprensa / rumor, modalidade A/B/C, alertas de risco |
| `tgv/scoring.py` | Score 0-100: velocidade de views, crescimento entre coletas, engajamento, recência, cobertura, autoridade, origem internacional |
| `tgv/pipeline.py` | Orquestra descoberta, análise e seleção |
| `tgv/db.py` | Esquema SQLite de todas as etapas |
| `tgv/dashboard.py` | Painel HTML |
| `tgv/cli.py` | `python -m tgv run`, `rank`, `select`, `import-csv`, `dashboard`, `youtube-channel` |

## 2. Ferramentas escolhidas

| Necessidade | Escolha | Por quê | Etapa |
|---|---|---|---|
| Linguagem | Python 3.11+ (só biblioteca padrão na etapa 1) | zero dependências para auditar agora | 1 |
| Banco | SQLite | um arquivo, sem servidor, suficiente para o volume | 1 |
| Notícias | RSS dos sites + Google News RSS | gratuito, sem chave, sem cota | 1 |
| Vídeos | YouTube Data API v3 + RSS de canais | API oficial gratuita com cota diária | 1 |
| Comunidade | Reddit API oficial (OAuth) | só após aprovação da Reddit | 1 (desligado) |
| TikTok / Instagram (descoberta) | CSV manual ou ferramenta de monitoramento autorizada | não há API comercial de descoberta (ver `PLATFORM_LIMITS.md`) | 1 |
| Roteiro e tradução | Claude API (Anthropic) | qualidade em pt-BR, saída estruturada | 2 |
| Narração | Piper TTS (local, gratuito, vozes pt-BR) como padrão; ElevenLabs ou Google Cloud TTS como opção paga | começar sem custo, trocar se a voz não convencer | 2 |
| Legendas sincronizadas | faster-whisper (local) para alinhar palavra a palavra | gratuito, roda em CPU | 2 |
| Edição | FFmpeg com templates (1080×1920, 30 fps, H.264 + AAC) | gratuito e scriptável | 2 |
| Capas e carrosséis | Pillow (imagem) com templates da marca | gratuito | 2 |
| Publicação | Meta Graph API (Instagram + Facebook), TikTok Content Posting API | oficiais | 4 |
| Agendamento | GitHub Actions (cron) ou cron no VPS/PC | gratuito ou quase | 1-4 |

Toda dependência externa nova (Piper, faster-whisper, Pillow, SDK da Anthropic) entra só depois de auditoria e da sua autorização, fixada em versão.

## 3. Custos recorrentes estimados

Valores aproximados; confira os preços atuais em cada serviço antes de contratar.

| Item | Cenário mínimo | Cenário confortável |
|---|---|---|
| Execução (agendador) | US$ 0 (PC do dono ou GitHub Actions no limite gratuito) | ~US$ 5–10/mês (VPS pequeno; renderização de vídeo fica mais rápida) |
| YouTube Data API, RSS, Meta Graph API, TikTok API | US$ 0 | US$ 0 |
| Reddit API | US$ 0 no uso não comercial aprovado | uso comercial depende de acordo com a Reddit (preço não público) |
| Claude API (roteiros, tradução, títulos) | alguns dólares/mês para ~3–5 peças/dia | ~US$ 10–30/mês com mais volume e revisões |
| Voz | US$ 0 (Piper local) | plano pago de TTS, a partir de ~US$ 5–22/mês |
| Armazenamento de mídia | US$ 0 (disco local) | ~US$ 1–5/mês (bucket de objetos) |
| **Total** | **≈ US$ 0–10/mês** | **≈ US$ 25–70/mês** |

## 4. Limitações técnicas

Resumo (detalhes e fontes em `PLATFORM_LIMITS.md`):
- **TikTok**: não há API para um negócio descobrir vídeos em alta de outros criadores (a Research API é para pesquisa acadêmica). Descoberta = CSV manual ou ferramenta autorizada. A publicação automática exige app auditado pelo TikTok; antes disso os posts via API ficam privados.
- **Instagram**: a busca por hashtag da Graph API tem limite de hashtags por semana e não traz visualizações de terceiros; publicar exige conta profissional (Business/Creator) ligada a uma Página do Facebook e permissões aprovadas.
- **YouTube**: cota diária (padrão 10.000 unidades; uma busca custa 100). O sistema controla o orçamento e para antes de estourar. Visualizações por hora vêm de coletas repetidas, não de um gráfico da plataforma.
- **Reddit**: acesso à API exige aprovação; uso comercial exige acordo.
- **Rockstar Newswire**: nenhum feed ou API pública confirmados. Notícias oficiais entram pelo canal oficial do YouTube (RSS) e pela cobertura da imprensa.
- **Direitos autorais**: trailers e imagens de GTA VI pertencem à Rockstar/Take-Two. Reutilização (modalidade A) só com licença ou permissão documentada; o sistema nunca decide isso sozinho.
- **Monetização**: não existe API confiável para checar elegibilidade em todos os programas; o módulo registra só o que a plataforma confirmar.

## 5. Estrutura de agentes e skills

Cada "agente" é um módulo com responsabilidade única. Só Roteirista e Revisor de texto usam LLM; os outros são código determinístico e testado.

| Agente | Responsabilidade | Implementação | Etapa |
|---|---|---|---|
| Scout | Coletar das fontes, isolar falhas, respeitar cotas | `tgv/sources/*` + `pipeline.discover` | 1 ✅ |
| Analyst | Deduplicar, classificar risco, pontuar | `dedup`, `classify`, `scoring`, `pipeline.analyze` | 1 ✅ |
| Editor-chefe | Escolher pautas (1 por história, sem itens em revisão) | `pipeline.select` | 1 ✅ |
| Roteirista | Roteiro em pt-BR, tradução contextual, título, legenda, hashtags | Claude API com saída estruturada | 2 |
| Produtor | Voz, legendas, montagem vertical, capa, carrossel | Piper, faster-whisper, FFmpeg, Pillow | 2 |
| Compliance | Barrar rumor como fato, vazamento, mídia sem licença, checar fontes citadas | regras + checklist + fila humana | 3 |
| Publisher | Agendar e publicar via APIs oficiais, modo teste primeiro | Meta Graph API, TikTok API | 4 |
| Analytics | Coletar insights, seguidores, desempenho por formato; ajustar pesos | APIs de insights | 5 |
| Monetização | Elegibilidade confirmada, receitas confirmadas, oportunidades | registros + painel | 6 |

Skills do Claude Code (para manutenção, criadas quando a etapa existir): `/tgv-run` (rodar e resumir o ciclo), `/tgv-review` (passar pela fila de revisão), `/tgv-script` (gerar roteiro de uma pauta selecionada).

## 6. Plano de implementação por etapas

| Etapa | Entrega | Critério de pronto | Depende de você |
|---|---|---|---|
| **1. Inteligência de conteúdo** ✅ | Conectores, dedup, classificação, score, seleção, banco, painel, testes | 39 testes passando; `python -m tgv run` gera painel | Chave da YouTube Data API; liberar a rede do agendador para os feeds |
| 2. Produção original (B) e notícias (C) | Roteiro → narração → legendas → vídeo 1080×1920 com identidade visual; capas e carrosséis | 3 vídeos-teste aprovados por você | Logo, cores, fontes, voz preferida; autorizar Piper/faster-whisper/Pillow/Claude API |
| 3. Validação | Regras de compliance, fila de revisão no painel, aprovar/rejeitar | Nenhum rumor sai como fato nos testes | Aprovar as regras de publicação autônoma |
| 4. Distribuição | Meta Graph API (IG + FB) e TikTok, primeiro em modo teste/privado | Post de teste aparece certo em cada rede | Criar app Meta, conectar contas, pedir auditoria TikTok; **autorizar a primeira publicação real** |
| 5. Performance | Insights por post e formato, crescimento de seguidores, pesos do score ajustados por dados | Relatório semanal no painel | — |
| 6. Monetização e autonomia | Programas, receitas confirmadas, afiliados/patrocínios; publicação autônoma só para conteúdo dentro das regras aprovadas | Uma semana estável sem intervenção, com alertas funcionando | Aprovar o modo autônomo |
