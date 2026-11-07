# Limites e requisitos das plataformas

> Levantamento para o projeto. Plataformas mudam regras com frequência: **confirme na documentação oficial antes de cada etapa** e atualize este arquivo. Itens marcados *(conferir)* não foram confirmados nesta sessão (o ambiente não tinha acesso à web).

## YouTube (descoberta: ✅ etapa 1)
- **API**: YouTube Data API v3 — https://developers.google.com/youtube/v3
- **Credencial**: chave de API de um projeto Google Cloud, restrita à YouTube Data API. Variável `TGV_YOUTUBE_API_KEY`.
- **Cota**: padrão de 10.000 unidades/dia por projeto. `search.list` = 100 unidades; `videos.list` = 1 unidade por chamada (até 50 vídeos). O sistema registra o gasto em `api_usage` e respeita `daily_unit_budget` (6.000 por padrão, deixando folga).
- **Dados**: título, canal, data, idioma declarado (quando o canal informa), duração, licença (`youtube` ou `creativeCommon`), views, likes, comentários. Não há views por hora: o sistema calcula pela diferença entre coletas.
- **Shorts**: a API não marca "Short". O sistema trata vídeo de até 180 s como provável Short.
- **Sem custo de cota**: o feed RSS de um canal (`/feeds/videos.xml?channel_id=...`) traz os últimos vídeos com views. Usado para o canal oficial da Rockstar.

## Reddit (descoberta: implementado, desligado)
- **API**: https://www.reddit.com/dev/api — exige app registrado, OAuth e user agent identificado.
- **Acesso**: novos acessos à API passam por aprovação da Reddit; uso comercial requer acordo próprio *(conferir os termos atuais antes de ativar)*.
- **Dados**: score (votos líquidos), comentários, data. **Não há contagem de visualizações.**
- Variáveis: `TGV_REDDIT_CLIENT_ID`, `TGV_REDDIT_CLIENT_SECRET`. Ativar em `config/sources.json` só depois da aprovação.

## TikTok
- **Descoberta**: a Research API é restrita a pesquisadores acadêmicos e não serve para uso comercial. **Não há API oficial para um negócio buscar vídeos em alta de outros criadores.** Alternativas: (1) CSV manual (`python -m tgv import-csv`); (2) ferramenta de monitoramento que tenha acordo com o TikTok, se valer o custo; (3) Creative Center do TikTok, consultado manualmente *(conferir disponibilidade no Brasil)*; (4) **garimpo assistido**: o Claude usa a busca do próprio TikTok ou Instagram no navegador, com a conta do dono logada e só quando o dono pede numa sessão. Ele junta link, views, data e legenda num CSV em `data/garimpo_*.csv` e importa com `import-csv`. Testado em 06/11/2026: a busca "gta 6" trouxe 24 vídeos com views. Não é robô agendado: raspagem automática sem supervisão viola os termos do TikTok e do Instagram e arrisca a conta.
- **Publicação**: Content Posting API — https://developers.tiktok.com/doc/content-posting-api-get-started
  - Exige app no TikTok for Developers, login do dono via OAuth (escopo `video.publish` ou `video.upload`) e **auditoria do app**. Antes da auditoria, os posts via API ficam restritos a visualização privada.
  - Existe limite diário de posts por criador via API *(conferir o número atual)*.
  - Alternativa sem auditoria: enviar como rascunho (`video.upload`) e o dono finaliza no app.
- **Métricas próprias**: Display API (views, likes, comentários e compartilhamentos dos próprios vídeos).

## Instagram
- **Descoberta**: Graph API, busca por hashtag (`ig_hashtag_search`, `top_media`, `recent_media`). Limite de hashtags únicas consultadas por semana *(30 em 7 dias na última documentação conhecida; conferir)*; retorna likes e comentários, **não views de terceiros**. Business Discovery traz dados básicos de outras contas profissionais. Útil como complemento, não como fonte principal de "virais".
- **Publicação**: Content Publishing API — https://developers.facebook.com/docs/instagram-platform/content-publishing
  - Conta **profissional** (Business ou Creator); dependendo do fluxo de login, ligada a uma Página do Facebook.
  - App na Meta for Developers com permissões de publicação; para contas que não têm papel no app, **App Review** da Meta.
  - Reels, imagens e carrosséis (até 10 itens). A mídia precisa estar em URL pública acessível pela Meta no momento do envio.
  - Limite de posts publicados via API por 24 h, consultável pelo endpoint `content_publishing_limit`.
- **Métricas**: Insights API (alcance, visualizações, curtidas, comentários, compartilhamentos, salvamentos) dos próprios posts.

## Facebook (Página)
- Graph API: publicação de vídeos e Reels na Página (`pages_manage_posts` e afins), insights da Página.
- Um mesmo app Meta cobre Instagram e Facebook.

## Rockstar Games / Newswire
- Nenhuma API pública. Nenhum feed RSS oficial do Newswire foi confirmado *(conferir)*.
- Cobertura adotada: canal oficial da Rockstar no YouTube via RSS (resolver o ID com `python -m tgv youtube-channel @RockstarGames`) e imprensa internacional via RSS, com o oficial confirmado pelo cruzamento de fontes.
- Raspagem do site não é usada sem verificar os termos de uso.

## Sites de games
- RSS de IGN, GameSpot, PC Gamer, Eurogamer, VGC, Polygon e Google News (busca "GTA 6"). URLs em `config/sources.json`; uma URL que parar de funcionar vira alerta no painel, sem derrubar as demais.
- RSS dá título, link, data e resumo. **Sem métricas**: a força de uma notícia vem de recência, autoridade e quantos veículos cobrem a mesma história.

## Monetização
- Não há API confiável e unificada de elegibilidade. Requisitos mudam e variam por país.
- O módulo (etapa 6) registra só o que a plataforma confirmar (tela do app, e-mail, relatório) em `monetization_programs` e `revenue`, com a evidência.
