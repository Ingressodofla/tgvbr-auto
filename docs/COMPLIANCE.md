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

## Bloqueios automáticos (vão para a fila de revisão)
- `unverified_claim`: rumor, especulação ou "insider".
- `leak_content`: vazamento ou datamining. Material vazado nunca é reutilizado.
- `license_review`: candidato à modalidade A.

## Credenciais e publicação
- Credenciais só em variáveis de ambiente ou no cofre do agendador. Nunca em código, config, banco, log ou painel.
- Nenhuma publicação real antes da autorização inicial do dono e da validação dos testes (etapa 4).
