# Luna, Leo e Stellina: automazione YouTube Shorts


Servizio che produce gli short del canale [Luna, Leo e Stellina](https://www.youtube.com/@LunaLeoStellina): genera la bozza, la controlla, ti chiede l'approvazione, crea il finale e lo programma su Buffer.
Pipeline automatica: Seedance su Kie, controllo qualità con misure e giudice OpenAI, finale 1080p, programmazione con Buffer.

## Flusso

```
n8n ──► POST /episodes/EP0xx/draft
          ├─ Seedance 2.5 (Kie) bozza 480p          ≈ $0,14/s
          ├─ post-produzione: colori pop, loop, audio −14 LUFS, numeri/bagliori
          ├─ misure (qc.py): camera, scatti nelle giravolte, proporzioni vs canone
          └─ giudice OpenAI: identità, azione, loop, tolleranze
      ◄── webhook "draft_ready" (anteprima + verdetto)  → Simone: approva / rifai
n8n ──► POST /episodes/EP0xx/approve?take=N
          ├─ 1080p della stessa bozza (stesso video)  ≈ $0,79/s
          └─ finale + copertina → Supabase (link pubblico)
      ◄── webhook "final_ready" → n8n copia su Google Drive (sincronizzato col PC)
n8n ──► POST /episodes/EP0xx/schedule?take=N&due_at=2026-10-20T17:30:00+02:00
          └─ Buffer → YouTube (titolo IT, descrizione, per bambini, contenuto AI)
n8n ──► POST /episodes/EP0xx/cleanup   (dopo la pubblicazione: libera Supabase)
```

## Regole fisse del canale

Sono nel codice: `app/channels/lunaleo/channel.json` ed `eps.py`.

- Personaggi sempre su Marte, all'esterno.
- Emoji stella sempre ⭐.
- Nessuna scritta nel video, tranne i numeri per contare e le lettere per l'alfabeto.
- Nessun invito a iscriversi.
- Nessun saluto finale fisso: il video è in loop.
- Prima sempre la bozza 480p. Il 1080p si fa solo dopo l'ok di Simone.
- Durata di default 12 s.

## Upscale con fal.ai (in prova)

Strada alternativa al 1080p di Seedance: la bozza 480p approvata passa da **SeedVR2 su fal.ai** e diventa 1080×1920.
Costo ≈ $0,55 a short invece di $9,48 (test su EP028: nitidezza vicina al nativo, struttura identica alla bozza).

Passaggi:
1. il servizio carica la bozza **grezza** su Supabase (fal vuole un link pubblico);
2. fal la porta a 1080p (modalità `target`, noise 0,05, seed fisso);
3. correzione `UPSCALE_FIX_VF` prima del grade: saturazione 0,86 (il 480p di Seedance nasce più saturo del 1080p) e un leggero filtro temporale contro il "brulichio" del dettaglio ricostruito;
4. audio originale della bozza, poi `postprod.finalize` come sempre (grade del canale, loop, overlay, −14 LUFS);
5. confronto strutturale con la bozza: segnala i secondi in cui l'upscale ha cambiato forme o volti;
6. costo registrato in `/costs` (servizio `fal`).

**Interruttore** `UPSCALE_PROVIDER` (variabile di Railway):
- `seedance` (default): "Approva" fa come prima, 1080p rigenerato da Seedance.
- `fal`: "Approva" usa l'upscale. Per tornare indietro basta rimettere `seedance`.

Il comando `/upscale EP028` (oppure `/upscale EP028 2` per una take precisa) usa **sempre** fal, anche con l'interruttore su `seedance`: è la prova. Il risultato arriva su Telegram con il pulsante **Usa come finale**, che lo mette al posto del finale Seedance (quello vecchio resta annotato nello stato).

## Telegram

Il bot manda ogni bozza con il giudizio e due pulsanti: **✅ Approva (1080p)** e **🔁 Rifai bozza**. Quando il finale è pronto manda il link e il pulsante **📅 Metti in coda su Buffer**.

Comandi del bot:
- `/bozza EP027`: genera la bozza dell'episodio.
- `/upscale EP027`: prova l'upscale fal della bozza.
- `/stato EP027`: mostra lo stato dell'episodio.
- `/episodi`: elenca gli episodi definiti.
- `/costi`: mostra il totale delle spese registrate.
- `/id`: mostra il tuo chat id.

Il webhook di Telegram si registra da solo all'avvio (usa `RAILWAY_PUBLIC_DOMAIN`). Il bot risponde solo alla chat `TELEGRAM_CHAT_ID`.

## n8n

`n8n/copia_finali_su_drive.json` va importato in n8n. Riceve l'evento `final_ready` e salva finale e copertina nella cartella Google Drive sincronizzata con il PC. L'URL di produzione del suo webhook va inserito nella variabile `N8N_WEBHOOK_URL` del servizio.

## Endpoint

Ogni chiamata richiede l'header `X-Token: <SERVICE_TOKEN>`.

| Metodo | Percorso | Cosa fa |
|---|---|---|
| GET | `/health` | Stato del servizio e chiavi presenti, senza mostrarne il valore. |
| GET | `/episodes` | Elenco degli episodi definiti. |
| POST | `/episodes/{ep}/define` | Aggiunge un episodio (stessi campi di `eps.py`) senza ridistribuire il codice. |
| GET | `/episodes/{ep}/request` | Mostra il JSON Seedance e i testi YouTube. |
| POST | `/episodes/{ep}/draft` | Genera la bozza, la controlla e invia il report. |
| POST | `/episodes/{ep}/approve?take=N` | Genera il finale 1080p e la copertina. |
| POST | `/episodes/{ep}/schedule?take=N&due_at=…` | Programma il video su Buffer. Senza `due_at` lo mette in coda. |
| POST | `/episodes/{ep}/cleanup` | Cancella i file temporanei su Supabase. |
| GET | `/jobs/{id}` | Stato di un lavoro in corso. |
| GET / POST | `/costs` | GET legge il registro costi (CSV); POST aggiunge una spesa manuale. |

## Messa in servizio su Railway

1. Crea un nuovo progetto e scegli **Deploy from GitHub repo**, poi questo repository.
2. Aggiungi un **Volume** montato su `/data`. Lì vengono salvati video, stato degli episodi e registro costi.
3. Nelle **Variables** inserisci i nomi elencati in `.env.example`, con i valori. Le chiavi non vanno mai nel repository.
4. Supabase: i video vanno nella cartella `video/` del bucket pubblico `youtube_short`.
5. Apri `https://<servizio>.up.railway.app/health` e controlla che tutte le chiavi risultino `true`.

## Note

- **Limiti di Supabase:** sul piano gratuito i limiti sono circa 50 MB per file e 1 GB in totale. Uno short a 1080p pesa 9–20 MB e il file viene cancellato dopo la pubblicazione.
- **Titolo inglese:** la traduzione va aggiunta a mano in YouTube Studio, perché Buffer gestisce una lingua sola.
- **Giudice OpenAI:** il modello si sceglie con `OPENAI_VISION_MODEL`. Il costo viene registrato in `/costs` se imposti i prezzi per milione di token.
- **Misure:** il riconoscimento dei personaggi (`isnet-anime`) è indicativo. Più avanti verrà sostituito da un riconoscitore addestrato su Luna, Leo e Stellina.
