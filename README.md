# Auto Movies Anki

O Auto Movies Anki transforma cenas de vídeos em cards do Anki com:

- Frase original em inglês
- Tradução em português brasileiro
- Clipe de vídeo em WebM
- Áudio da cena em MP3
- Imagem da cena em JPG

## Requisitos

- Windows 10 ou 11
- Anki aberto
- Add-on AnkiConnect ativo na porta `8765`
- FFmpeg e FFprobe disponíveis no `PATH`
- OmniRoute instalado para tradução local
- Conexão com a internet para vídeos do YouTube e download inicial do Whisper

## Como usar

1. Abra o Anki.
2. Execute `AutoAnki.exe`.
3. Cole uma URL do YouTube ou selecione um vídeo local.
4. Opcionalmente, selecione uma legenda original em `.srt`.
5. Escolha o deck e o tipo de nota.
6. Clique no botão de iniciar.
7. Confira como cada campo do Anki será preenchido.
8. Confirme para iniciar o processamento.

É possível fornecer:

- Somente uma URL do YouTube
- Somente um vídeo local
- URL e legenda local
- Vídeo e legenda locais

A legenda local deve representar o texto original em inglês. A tradução em PT-BR será criada pela IA local.

## Etapas do processamento

1. Download ou cópia do vídeo
2. Transcrição em inglês com Faster-Whisper
3. Auditoria de regiões de voz sem texto
4. Tradução para PT-BR com OmniRoute
5. Geração dos slices com FFmpeg
6. Envio das mídias e notas para o Anki

## Configuração recomendada do Whisper

Para priorizar precisão:

```json
{
  "model_size": "medium.en",
  "device": "cpu",
  "compute_type": "int8",
  "cpu_threads": 14
}
```

O modelo é baixado automaticamente na primeira utilização. Esse download pode demorar, mas fica armazenado no cache para as próximas execuções.

Para maior velocidade, use `small.en`. Ele é mais rápido, mas pode perder precisão em diálogos com ruído, música ou efeitos.

## Progresso da transcrição

Durante a transcrição, a interface exibe:

- Percentual processado
- Tempo de áudio processado e duração total
- Quantidade de trechos encontrados
- Estimativa de tempo restante

Ao final, o arquivo `transcription_audit.txt` registra:

- Regiões de voz detectadas
- Regiões inicialmente sem texto
- Segmentos recuperados
- Hallucinações fora da duração da mídia
- Total final de segmentos

## Configurações

O botão de engrenagem permite configurar:

### Anki

- Endereço do AnkiConnect
- Deck padrão
- Tipo de nota padrão

### IA local

- Endpoint do OmniRoute
- Modelo de tradução
- Chave da API
- Modelo Whisper
- Dispositivo
- Precisão numérica
- Threads da CPU

As configurações ficam armazenadas em `config.json`, ao lado do executável.

## Mapeamento dos campos

Antes de iniciar, o aplicativo mostra os campos do tipo de nota escolhido. Cada campo pode receber:

- Áudio da cena
- Clipe de vídeo
- Imagem da cena
- Legenda original
- Legenda traduzida
- Identificador do card
- Nenhum conteúdo

O mapeamento fica salvo separadamente para cada tipo de nota.

## Arquivos temporários

Cada execução cria uma pasta `workspace_<id>`. Ela pode conter:

```text
workspace_<id>/
├── video.mp4
├── original.srt
├── translated.srt
├── transcription_audit.txt
└── slices/
    ├── *.webm
    ├── *.mp3
    └── *.jpg
```

Ao terminar, o aplicativo permite excluir ou preservar o workspace.

## Solução de problemas

### Anki não encontrado

Abra o Anki e confirme que o AnkiConnect está ativo em:

```text
http://127.0.0.1:8765
```

### OmniRoute indisponível

O aplicativo tenta iniciar o OmniRoute automaticamente. Caso isso falhe, execute:

```powershell
omniroute serve --daemon --no-open --port 20128
```

### Download do modelo demorado

O `medium.en` é baixado apenas no primeiro uso. Aguarde a mensagem informando que o modelo está disponível.

### Slice fora da duração do vídeo

Timestamps que ultrapassam levemente o final são ajustados automaticamente. Segmentos totalmente fora da mídia são registrados como hallucinações e não são enviados ao Anki.

### Deck incompleto

Se algum slice ou card falhar, o lote é interrompido. Notas e mídias enviadas naquela execução são revertidas para evitar um deck parcialmente criado.

## Build

Para gerar o executável:

```powershell
venv\Scripts\pyinstaller.exe --noconfirm AutoAnki.spec
```

O resultado será criado em:

```text
dist\AutoAnki\AutoAnki.exe
```

Distribua a pasta `dist\AutoAnki` completa. O executável depende dos arquivos presentes em `_internal`.
