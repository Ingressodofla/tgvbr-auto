# Produção (etapa 2)

Transforma uma pauta selecionada em um pacote para revisão: **roteiro + narração + vídeo vertical + capa + carrossel**. Tudo termina com status `review` no painel. **Nada é publicado.**

## Fluxo

```
item selecionado
  → roteiro (Claude API, JSON validado por esquema)        tgv/production/script.py
  → validação editorial (rumor, fonte, duração, alegação)   validate_script()
      └─ reprovado: nada é renderizado; item vai para a fila de revisão
  → narração por segmento (Piper, local)                    tgv/production/tts.py
  → legendas sincronizadas (ASS, por segmento)              tgv/production/subtitles.py
  → vídeo 1080×1920 30 fps H.264 + AAC, -14 LUFS            tgv/production/render.py
  → capa 1080×1920 + carrossel 1080×1350                    tgv/production/graphics.py
  → productions.status = review
```

Arquivos de cada pauta ficam em `media/item_<id>/` (fora do Git): `script.json`, `voice_*.wav`, `narration.wav`, `captions.ass`, `video.mp4`, `cover.jpg`, `carousel/slide_*.jpg`.

## Instalação (uma vez)

Requisitos: Python 3.11+, FFmpeg 6+ (com libx264, libass e libfreetype) e as fontes do kit de marca.

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

Voz em português (Piper, gratuita e local, cerca de 60 MB):

```bash
.venv/bin/python -m piper.download_voices --download-dir voices pt_BR-faber-medium
```

O caminho fica em `config/brand.json` → `voice.piper_model` (padrão `voices/pt_BR-faber-medium.onnx`). Ouça a voz antes de aprovar; se não agradar, troque a voz do Piper ou adote um serviço pago no lugar de `PiperTTS` (mesma interface `synthesize(texto, arquivo) -> segundos`).

Chave da API do Claude (para os roteiros): crie em https://platform.claude.com e defina `ANTHROPIC_API_KEY` no ambiente (nunca no repositório).

## Uso

Produzir as 3 melhores pautas selecionadas:

```bash
.venv/bin/python -m tgv produce --limit 3
```

Produzir um item específico:

```bash
.venv/bin/python -m tgv produce 42
```

Prévia sem chave do Claude nem voz (roteiro em modelo fixo, sem tradução, e áudio mudo; serve para conferir layout e tempo, **nunca para publicar**):

```bash
.venv/bin/python -m tgv produce --writer template --voice placeholder
```

Depois, `python -m tgv dashboard` mostra as produções com links para vídeo, capa e carrossel.

## Roteiro com o Claude

- Modelo `claude-opus-5-5`, esforço `medium`, saída em JSON validado pelo esquema `SCRIPT_SCHEMA`.
- Fallback automático no servidor quando o modelo recusa uma solicitação (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`). Recusa ou resposta cortada viram erro e o item vai para revisão.
- O texto da fonte entra marcado como dado (`<item>...</item>`), não como instrução.
- O roteirista **não pode mudar o status da afirmação**: ele vem do item, e a validação reprova se mudar.
- Custo estimado por roteiro: ~2 mil tokens de entrada e até ~3 mil de saída, incluindo o raciocínio interno, a US$ 4 / US$ 20 por milhão. Fica em torno de **US$ 0,03–0,07 por roteiro**, ou cerca de US$ 5–10/mês com 5 roteiros por dia. Confira os preços atuais em https://platform.claude.com/docs/en/about-claude/pricing.

## Validação editorial (bloqueia antes de renderizar)
- URL original ausente das fontes → erro.
- Status da afirmação alterado → erro.
- Rumor (`unverified`) sem "rumor" / "não confirmado" na capa ou no primeiro segmento **e** na legenda → erro.
- Rumor com linguagem de confirmação ("confirmado", "oficial", exceto em "não confirmado") → erro.
- Narração acima de ~75 s → erro; abaixo de ~15 s → aviso.
- Legenda acima de 2.200 caracteres → erro.

## Identidade visual
`config/brand.json` controla cores, fontes, logo, @ e voz. **O kit atual é provisório** (cores e fontes escolhidas só por legibilidade, sem logo); cada produção registra essa observação até o kit oficial entrar. Para trocar: mande o logo (PNG com fundo transparente), as cores e as fontes da página.

## Fundo do vídeo
Sem imagens, o fundo é um gradiente animado da marca. `render.build_command(images=[...])` aceita imagens **próprias ou licenciadas** com zoom lento (efeito Ken Burns). Material de terceiros nunca é baixado automaticamente (ver `COMPLIANCE.md`).

## Licenças das dependências
| Pacote | Licença | Observação |
|---|---|---|
| anthropic 2.6.0 | MIT | SDK oficial |
| pillow 12.0.0 | MIT-CMU (HPND) | |
| piper-tts 1.8.0 | GPL-3.0-or-later | Executado como programa separado (`python -m piper`); cada voz tem licença própria, confira o MODEL_CARD da voz |
| FFmpeg | LGPL/GPL conforme a compilação | Ferramenta do sistema |
