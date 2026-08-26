o que faço manualmente:
1 - baixo um vídeo do youtube com o "C:\Users\Wender\AppData\Local\Programs\YTSage"
2 - uso algum site pra gerar legendas em .srt com o vídeo que baixei.
3 - traduzo a legenda pra pt-br com alguma ia, criando um novo .srt.
3 - abro o "C:\Program Files (x86)\subs2srs_v29.7\subs2srs" e gero um deck anki com as 2 legendas, o video, o deck tem generated snapshots, video clips, audio clips.
4 - ceio um novo deck no anki. 
4.1 - importo no anki, utilizando a note type "Clips audio 🔉", ajustando os campos correspondes.
5 - no anki no field "Clip", eu replace "Sound:" por "", e ".{format}]" por ".webm"
6 - no anki no field "index", eu replace ".{format}]" por ".webm"
7 - rodo comando "anki-conv" que converte todos os videos do diretoria de midias do anki pra .webm
8 - copio a midia gerada no passo 3 para o diretorio de midia do anki.

o passo 5 é importante pq o anki reconhece webm de forma boa, e o 6 pra o anki reconher a mídia e não aparecer como mídia sem card.

meu pc:
- xeon 2680 v4
- 16gb ram
- rx 5500 xt 8gb

observações:
o processo de gerar a legenda deve ser bem preciso, pois qwuando falha gera muitos problermas para o etnendimento do conteudo. Considere usar uma ia local para esse processo, desde que isso seja possivel ser feito com um desempenho bom nessa maquina.


Add-on anki, caso o anki esteja fechado, vai dar falha na conxõa ai abra ele:
{
    "apiKey": null,
    "apiLogPath": null,
    "ignoreOriginList": [],
    "webBindAddress": "127.0.0.1",
    "webBindPort": 8765,
    "webCorsOriginList": [
        "http://localhost",
        "http://localhost:8096",
        "http://127.0.0.1:8096",
        "*"
    ]
}

para a ia local de tradução:
- use o comando "omniroute"
- api key "sk-91d3746c342d6cf3-cc6e99-1fa3d1c0"
- baseUrl "http://localhost:20128",
- model "combo"

depois disso deixei os processos relacionados a tradução.