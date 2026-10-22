# Jake no Carro — design do MVP

## Por quê
O Bruno comprou um HB20 1.6 Comfort 2013 (sem comando no volante) e instalou uma central Android 14 genérica (9", 2 GB RAM, sem 4G — internet pelo hotspot do celular). Quer um "JARVIS" de bordo: fala com o Jake por voz, o Jake responde falando e executa (rota, música). Uso dirigindo → nada que exija olhar ou tocar na tela no uso normal.

## Objetivos do MVP
1. App abre e cumprimenta por voz ("Boa noite, patrão…"), variando por horário e com clima.
2. Botão grande "Falar" + bolinha flutuante por cima do Maps/Spotify pra chamar o Jake sem sair da rota.
3. Comandos em linguagem natural: navegar (Maps, Waze opcional), tocar no Spotify, pausar/próxima, perguntas rápidas.
4. Respostas sempre faladas, curtas, pt-BR.
5. Sem internet: "tô sem internet, patrão" + tentativa local de "me leva pra X" / "toca X".

## Não-objetivos (MVP)
- Wake word "Jake" e abrir sozinho ao ligar (fase 2 — depende do modelo da central).
- WhatsApp, Meta Ads, ClickUp, agenda (fase 3). OBD2 (fase 4).
- Rodar dentro do CarPlay/Android Auto.

## Anti-objetivos
- Resposta longa ou que precise ler a tela.
- Enviar qualquer coisa pra terceiros sem confirmação por voz (vale pra fase 3).
- Derrubar Jake OS, Joias Camila ou Amiarte ao subir/reiniciar o serviço do carro.

## Decisões do Bruno
- IA = OpenAI (regra [[feedback-ia-openai]]). Comandos: `gpt-4.1-mini`; transcrição: `gpt-4o-mini-transcribe`.
- Tem Spotify Premium → play direto.
- Pasta `/root/jake_carro`; endereço `carro.amiartejoias.com.br`.

## Arquitetura (minhas escolhas)

### Servidor — `/root/jake_carro/servidor/app.py`
Flask próprio, `127.0.0.1:5055`, systemd `jake-carro.service` (EnvironmentFile `/root/.env`). Serviço separado do Jake OS de propósito: reiniciar um não derruba o outro, e não mexe no `app.py` gigante do Jake OS.

Auth: `Authorization: Bearer <JAKE_CARRO_TOKEN>` em todas as rotas, menos `/carro/saude`. Download do APK aceita `?t=<token>` (navegador da central).

| Rota | Faz |
|---|---|
| `GET /carro/saude` | ping |
| `GET /carro/config` | `spotify_client_id`, versão mais nova do app |
| `GET /carro/saudacao?lat=&lon=` | `{fala, audio_b64}` — GPT gera saudação curta com hora, dia, clima (Open-Meteo) |
| `POST /carro/comando` | multipart `audio` (m4a) ou campo `texto` + `sessao` → transcreve, GPT decide, devolve ação |
| `GET /carro/apk?t=` | baixa o APK mais recente |

Resposta de `/carro/comando`:
```json
{ "ouvido": "me leva pro escritório",
  "fala": "Bora, patrão. Rota pro escritório.",
  "audio_b64": "<mp3>",
  "acao": "navegar",
  "parametros": { "destino": "Rua X, 123 - Cidade", "app": "maps" } }
```
Ações: `navegar {destino, app: maps|waze}`, `tocar_musica {busca, tipo: musica|artista|playlist|album, uri?}`, `midia {comando: pausar|continuar|proxima|anterior}`, `responder {}`, `nada {}`.

- GPT com saída JSON estrita (json_schema). Memória curta: últimas 6 falas por sessão, em memória, 15 min.
- Lugares salvos: tabela `carro_lugares(apelido, endereco)` no Neon, cacheada; vão no prompt.
- Spotify: se houver `SPOTIFY_CLIENT_ID/SECRET` no .env, o servidor busca na Web API e devolve `uri`.
- Voz: Edge TTS `pt-BR-AntonioNeural` (já instalado em /opt/edge-tts), mp3 em base64 na mesma resposta (1 ida e volta só).
- Log: tabela `carro_log` (texto ouvido, ação, latência), gravado depois da resposta.

### App Android — `/root/jake_carro/app`
Kotlin, Views simples (sem Compose), OkHttp, pacote `br.zati.jakecarro`, minSdk 26, alvo 34. Tela escura, horizontal, botão enorme.

- Grava com `MediaRecorder` (fonte VOICE_RECOGNITION, AAC 16 kHz) e corta sozinho no silêncio (amplitude); máx. 10 s.
- Pede foco de áudio enquanto ouve/fala (Spotify abaixa/pausa).
- Toca o mp3 recebido; se falhar, usa o TTS do Android.
- Executa: Maps `google.navigation:q=`; Waze `https://waze.com/ul?q=&navigate=yes`; Spotify via App Remote SDK quando houver Client ID e `uri`, senão `MEDIA_PLAY_FROM_SEARCH` no pacote do Spotify; mídia via teclas de mídia do sistema.
- Bolinha flutuante (permissão de sobreposição): toque → traz o Jake pra frente já ouvindo; depois da ação ele volta pro app anterior.
- Sem internet: fala local + `SpeechRecognizer` do aparelho (se existir) + regras simples pra navegar/tocar.
- Atualização: compara versão com `/carro/config`; botão "Atualizar" baixa e abre o instalador.
- Compila na própria VPS (JDK 17 + Android SDK em /opt/android-sdk); chave de assinatura fica em `/root/jake_carro/app/keystore/` (fora do git).

## Fica pro builder
Layout exato, textos de status, limiares de silêncio (ajustar no carro).

## Riscos conhecidos
- Microfone da central fraco com barulho de estrada → limiar ajustável; mic externo se precisar.
- Central pode matar o app em segundo plano → fase 2.
- Spotify App Remote exige app registrado com pacote + SHA1 no dashboard do Spotify.
