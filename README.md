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
