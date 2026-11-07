# Regras editoriais e de direitos

Valem para todo conteúdo, automático ou não. Estão codificadas em `tgv/classify.py` e cobertas por testes.

## Afirmações
| Status | Quando | Como pode ser publicado |
|---|---|---|
| `confirmed` | Fonte oficial (Rockstar Games / Take-Two) | Como fato, citando a fonte |
| `reported` | Imprensa sem linguagem de rumor | "Segundo [veículo]...", com atribuição |
| `unverified` | Palavras de rumor, vazamento ou especulação (en/pt) | **Nunca como fato.** Só rotulado como RUMOR, e sempre após revisão humana |
| `not_a_claim` | Vídeo de criador, post de comunidade | Referência de tendência; o conteúdo novo é nosso |

## Modalidades
- **A — Reutilização autorizada**: o sistema só marca `A_candidate` quando a fonte declara licença reutilizável (ex.: Creative Commons no YouTube) e manda para revisão (`license_review`). Mesmo com CC, o vídeo pode conter material da Rockstar que o criador não podia licenciar. Só vira produção com a base de direitos registrada (`productions.rights_basis`), incluindo monetização.
- **B — Produção original**: análise, lista, explicação ou comparação em pt-BR, com narração e edição próprias. Vídeos de terceiros servem de referência de pauta, não de material (`third_party_media`).
- **C — Notícias**: publicação informativa rápida, com fonte citada e status da afirmação respeitado.

## Mídia (trailers, imagens) — biblioteca licenciada
Todo visual dos vídeos e das capas sai de `media/library/library.json`, um manifesto validado por `tgv/production/library.py` (modelo: `config/media_library.example.json`). O robô **nunca baixa vídeo sozinho**. Baixar do YouTube fora dos recursos dele viola os Termos do YouTube. Cada arquivo entra com origem, crédito e base de direitos:

| `rights_basis` | Uso | Monetizar |
|---|---|---|
| `own` | captura própria da página | sim |
| `licensed` | licença ou permissão escrita (`reference` obrigatório) | conforme a licença |
| `press_kit` | kit de imprensa da publisher (`reference` = termos) | conforme os termos |
| `rockstar_fan_policy` | trailer ou imagem oficial da Rockstar | **não** |

Sobre a Rockstar, a [política oficial](https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz), atualizada em 10/01/2025, tolera o uso por fãs **não comercial**, sem spoiler e sem material vazado, e a Take-Two pode derrubar o conteúdo quando quiser. Por isso:
- Produção que usa esse material recebe a nota "do not monetise" e grava `productions.rights_basis`.
- A legenda leva automaticamente "Imagens: <crédito>".
- Itens com tag de vazamento ou spoiler são recusados no manifesto.
- Áudio de trailer nunca é usado: o único som é a nossa narração (evita Content ID da trilha).
- Para monetizar com material da Rockstar, é preciso uma licença pedida a copyright@take2games.com.

## Bloqueios automáticos (vão para a fila de revisão)
- `unverified_claim`: rumor, especulação ou "insider".
- `leak_content`: vazamento ou datamining. Material vazado nunca é reutilizado.
- `license_review`: candidato à modalidade A.

## Credenciais e publicação
- Credenciais só em variáveis de ambiente ou no cofre do agendador. Nunca em código, config, banco, log ou painel.
- Nenhuma publicação real antes da autorização inicial do dono e da validação dos testes (etapa 4).
