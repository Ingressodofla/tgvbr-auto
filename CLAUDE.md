# TGV BR Auto — regras do repositório

- Projeto da The Game Versus BR. Não tem relação com a UNBANK; não misturar estado, decisões ou arquivos.
- Falar com o dono em pt-BR. Conteúdo publicado da página: pt-BR.
- Nada é publicado em rede real sem autorização explícita do dono. Etapas de distribuição começam em modo teste/privado.
- Credenciais só em variáveis de ambiente ou cofre do agendador. Nunca em código, config, banco, log, painel ou chat.
- Nenhuma dependência de terceiros, API nova ou integração sem explicar custo e risco e receber autorização. Versões fixadas.
- Não inventar capacidades de plataforma: o que não estiver confirmado vai como "(conferir)" em `docs/PLATFORM_LIMITS.md`.
- Regras editoriais (`docs/COMPLIANCE.md`) são código testado: rumor nunca vira fato; reutilização de mídia exige licença registrada.
- Antes de commit: `python -m unittest discover -s tests -t .` e `git diff --check`. Código novo vai por branch.
