# Diagnóstico das contas — 06/11/2026

Levantamento feito no navegador, com as contas logadas pelo dono. Os números são os que aparecem nas plataformas nesse dia.

## Identidade

| Item | Valor |
|---|---|
| @ (nas 3 redes) | `@thegameversebr` |
| Nome exibido | "Game Verse BR" (IG/FB); "thegameversebr" (TikTok) |
| Logo | Escudo com as cores do Brasil, o céu da bandeira com "ORDEM E PROGRESSO", um controle branco e o texto **GAME** (branco) / **VERSE** (degradê de verde para amarelo) / **BR** (branco). Arquivo original: `assets/brand/logo-original.webp`; versão recortada com fundo transparente: `assets/brand/logo.png` |
| Bio IG/FB | "🎮 Games, nostalgia e novidades · Clipes rápidos pra quem vive o mundo gamer · Veja mais no TikTok" |
| Bio TikTok | "Crio conteúdos sobre jogos para todos os apaixonados por games 🎮" |
| Categoria | Criador de conteúdo digital |

## Paleta (amostrada da logo)

| Uso no brand.json | Cor | Origem |
|---|---|---|
| background_top / bottom | `#001848` → `#000A24` | azul-marinho do escudo |
| accent | `#FFD800` | amarelo da logo e das tarjas das capas |
| official | `#18E048` | verde da logo |
| text / accent_2 | `#FFFFFF` | branco de "GAME" e "BR" |
| rumor | `#FF7A00` | laranja, propositalmente diferente do amarelo da marca para o rumor não se confundir com o destaque normal |

## Estilo visual dos posts

- **Instagram e Facebook:** vídeo com faixas pretas em cima e embaixo. Em cima, uma tarja amarela arredondada com o título em preto, todo em maiúsculas e bem pesado, e logo abaixo uma linha branca menor ("SIMPLESMENTE INSANO", "NOVO TRAILER"). A logo pequena vai como marca d'água embaixo, no centro.
- **TikTok:** capas com títulos enormes em fonte condensada e pesada, em branco, amarelo e vermelho, com contorno e sombra ("FINALMENTE A NOVA GERAÇÃO", "NVIDIA EM OUTRO PATAMAR").
- **Fonte:** ainda não foi identificada com certeza. Os títulos lembram fontes condensadas pesadas (tipo Anton ou Bebas) e as tarjas lembram Montserrat Black. Por enquanto o brand.json continua com a Inter, como provisória.

## Números

| Rede | Seguidores | Posts | Período ativo | Ritmo |
|---|---|---|---|---|
| TikTok | 1.650 (94,7 mil curtidas) | 80 vídeos | 27/05 a 29/08/2026 | jun 26, jul 36 (≈1 por dia), ago 13 |
| Instagram | 140 | 130 | até 12/09/2026 | o mesmo conteúdo do TikTok, repostado |
| Facebook | 67 | Reels | até 12/09/2026 | Reels com cerca de 6 a 62 visualizações cada |

As views por post do Instagram não apareceram no navegador. Para ter esse número, a etapa 5 vai usar a API oficial.

### O que mais deu resultado (TikTok, views)

1. GTA V com DLSS 4.5 vs DLSS 5 (comparação de gráficos): **325,6 mil**
2. A água de Kung Fu Panda (2008) (nostalgia e gráficos): **241,9 mil**
3. Queridos Passageiros, coop caótico (jogo novo e curioso): **235,5 mil**
4. Lumen Field: de The Last of Us para a Copa (crossover com a atualidade): **112,2 mil**
5. NVIDIA RTX Spark (hardware): **110,6 mil**
6. Gears of War: e-Day (nova geração): **109,9 mil**
7. Jak II envelheceu bem (nostalgia): **106 mil**
8. Roblox "melhor que COD?" (pergunta polêmica): **90,4 mil**

Mais ou menos metade dos vídeos ficou entre 1 mil e 10 mil views. Os virais seguem um padrão: **comparação visual de gráficos, nostalgia, ou uma pergunta que provoca comentário**.

### Atenção para o foco em GTA VI

Os posts específicos de GTA VI renderam pouco: a compilação do mapa teve 1.433 views, o "novo teaser" 5.247 e o "007 vs GTA 6" 1.374. O GTA que viralizou foi o **GTA V comparando gráficos**. Sugestão para a etapa de seleção: tratar GTA VI pelos ângulos que já funcionaram nesta página (comparação visual, "antes e depois", nostalgia da franquia, pergunta polêmica), e não com notícia seca.

## Pendências de marca

- [ ] Escolher a fonte dos títulos (a mesma das capas antigas, se o dono souber qual é) e depois marcar `provisional: false`.
- [ ] Decidir se o nome exibido continua "Game Verse BR" ou passa a ser "The Game Verse BR" nas três redes.
