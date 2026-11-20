# Comportamento e temporizzazioni ricavati da Geolith

**Fonti.** Sorgente di Geolith (porta libretro, licenza BSD a tre clausole),
letto ma non eseguito: `src/geo_lspc.c`, `geo_m68k.c`, `geo_z80.c`, `geo_neo.c`.
Più la pagina *PRO-CT0* del wiki neogeodev. Il sorgente originale è su GitLab,
non raggiungibile da qui; la porta libretro ne contiene una copia.

**Limite importante.** Geolith è un emulatore: riproduce *cosa* viene letto e
*quando*, a livello di cicli del 68k e di linee di scansione. **Non** riproduce i
fronti dei segnali sul connettore (`PCK1B`, `LOAD`, `CA4`...). Il wiki, sulla
pagina PRO-CT0, non ha forme d'onda né conteggi di cicli. Quindi qui sotto c'è
tutto ciò che serve per decidere *cosa* deve fare il gateware, non ancora
*con quali ritardi*. L'elenco di ciò che manca è in fondo.

Ogni punto è marcato: **[Geolith]** lo dice il codice dell'emulatore,
**[wiki]** la documentazione, **[calcolo]** l'ho derivato io.

## 1. Quadro video

* **[Geolith]** 384 pixel per linea × 264 linee; 768 cicli del 68k per linea.
* **[calcolo]** Con il 68k a 12 MHz una linea dura 64 µs (15,625 kHz), il pixel
  clock è 6 MHz (24M/4), un pixel dura 166,7 ns e un frame 16,9 ms (circa
  59,2 Hz). Quadra con i valori noti della Neo Geo.

## 2. Sprite (C ROM)

Tutta la logica degli sprite sta **nella console** (LSPC): catena, rimpicciolimento
tramite la ROM L0, limite di 96 sprite per linea, auto-animazione, flip
verticale. La cartuccia vede solo l'indirizzo finale e il segnale `H`.

* **[Geolith]** Il numero di tile è di 20 bit (16 bit bassi più 4 alti dalla
  VRAM), il tile occupa 128 byte: indirizzo byte = `tile × 128`.
* **[MiSTer, sezione 8]** `P0-P23` sono 20 bit di tile più 4 di riga (0-15):
  ogni indirizzo identifica una riga di 16 pixel. Geolith da solo non lo dice.
* **[Geolith]** Un tile 16×16 è letto in due metà da 8 pixel, una per valore
  di `CA4` (il wiki dice che `CA4` seleziona le colonne di blocchi). Senza flip
  orizzontale: pixel 0-7 dalla metà a `tile + 0x40`, pixel 8-15 dalla metà a
  `tile + 0x00`; con flip le metà si scambiano e l'ordine dei pixel si inverte.
  Dentro una metà, la riga `y` sta a `+ 4·y` (4 byte = 32 bit per 8 pixel,
  coerente con `C0-C31` del wiki).
* **[Geolith]** Nel layout interleaved che usa anche il nostro `.ngpk`, i 4
  byte di una riga `b0 b1 b2 b3` danno i bitplane così: piano 0 = `b0`,
  piano 1 = `b2`, piano 2 = `b1`, piano 3 = `b3`. Cioè i piani 0-1 vengono dal
  chip dispari (c1), i piani 2-3 dal chip pari (c2): combacia con il wiki.
* **[Geolith]** Il pixel `x` di una metà usa il bit `x` di ogni byte (il pixel
  più a sinistra è il bit 0). Con `H` attivo l'ordine si inverte (`x ^ 7`).
  Flip verticale: la riga diventa `15 - y`. Il valore 0 è trasparente.
* **[Geolith]** Il numero di tile viene mascherato sulla dimensione della C ROM
  (`% csz`): su una cartuccia vera gli indirizzi alti "si ripiegano" sulla
  memoria presente. Il nostro FPGA deve fare lo stesso (tile modulo dimensione C).
* **[calcolo]** Nel caso peggiore una linea richiede 96 tile × 2 letture da
  32 bit = 192 letture C; su 64 µs sono circa 333 ns di media per lettura
  (due pixel clock). È un'ipotesi di budget, non un dato documentato.

## 3. Fix layer (S ROM)

* **[Geolith]** Tile 8×8 da 32 byte; una riga di 8 pixel sono 4 byte, nelle
  posizioni `+0x10, +0x18, +0x00, +0x08` più il numero di riga. Ogni byte porta 2
  pixel: nibble basso a sinistra, alto a destra.
* Sul connettore la S ROM passa da `FIXD0-7` (8 bit): la cartuccia risponde a un
  indirizzo portato dal bus `P`, latchato su `PCK2B`: il cablaggio è descritto
  nella sezione 8 (parola da 16 bit più `S2H1` per scegliere il byte).
* **[Geolith]** Alcune cartucce commutano banco del fix per linea o per tile
  (tipi 1 e 2): non sono nel mapper `plain`.

## 4. P ROM: bank switching

* **[Geolith]** Il 68k vede i primi 1 MiB fissi; la finestra `$200000-$2FFFFF`
  mostra il banco `n` all'offset `1 MiB × (n + 1)` della P. Il numero scritto è
  mascherato con (potenza di due successiva al numero di banchi) − 1.
  È lo stesso schema del nostro `.ngpk` (P1 = primi 1 MiB, poi i banchi).
* **Discrepanza da sciogliere.** Geolith agisce solo su scritture a indirizzo
  `>= $2FFFF0`; il wiki descrive il latch che scatta con **qualsiasi** scrittura
  (word, o byte dispari) nella finestra. Per il gateware conviene seguire
  l'hardware descritto dal wiki, che è un sovrainsieme.
* **[Geolith]** Varianti con protezione (SMA, PVC, "ct0", linkable) hanno regole
  proprie: confermano che vanno in mapper separati.

## 5. M ROM e NEO-ZMC (Z80)

* **[Geolith]** Mappa Z80: `0x0000-0x7FFF` fissa (inizio M1); `0x8000-0xBFFF`
  banco 0 da 16 KiB; `0xC000-0xDFFF` banco 1 da 8 KiB; `0xE000-0xEFFF` banco 2
  da 4 KiB; `0xF000-0xF7FF` banco 3 da 2 KiB; `0xF800-0xFFFF` RAM di lavoro.
* **[Geolith]** Il banco si cambia con una **lettura di porta** Z80: porta
  `0x0B` imposta il banco 0, `0x0A` il banco 1, `0x09` il banco 2, `0x08` il
  banco 3. Il numero di banco è l'**alto byte dell'indirizzo di porta**
  (`A15-A8`), mascherato con `0x0F`, `0x1F`, `0x3F`, `0x7F`; l'offset è
  numero × dimensione del banco. Con queste maschere ogni finestra copre
  256 KiB: è il limite che Geolith impone alla M1. Il core NeoGeo_MiSTer
  (sezione 8) usa un bit in più per finestra e arriva a 512 KiB: per il
  gateware si segue il secondo, che modella il chip vero.
* **[wiki]** NEO-ZMC ha come ingressi `SDA0, SDA1, SDA8-SDA15` e come uscite gli
  indirizzi alti della M ROM: coerente con quanto sopra (`SDA0/1` scelgono il
  banco, `SDA8-15` portano il valore).
* **[calcolo]** La M1 del gioco `spf2ng` è di 256 KiB: rientra in entrambi i modelli.
* Quali strobe (`SDRD0`, `SDRD1`...) qualificano la lettura di porta sul
  connettore va ancora confermato.

## 6. Formato `.neo` (spunto, non ancora usato)

Geolith carica solo `.NEO` (TerraOnion): header di 4096 byte (`'N' 'E' 'O' 1`,
dimensioni P, S, M1, V1, V2, C come interi a 32 bit little-endian, poi anno,
genere, NGH, nome, produttore), dati dopo l'header. Un importatore
`.neo → .ngpk` è fattibile; non l'ho scritto perché non ho un file `.neo` con
cui verificarlo.

## 7. Cosa NON si ricava da qui

Aggiornato dopo la lettura del core NeoGeo_MiSTer (sezione 8): i punti sul
significato di `P0-P23`, sul cablaggio verso S e C ROM e sulla produzione di
`DOTA/DOTB/GAD/GBD` sono stati risolti lì. Restano aperti:

1. Tempi sul connettore **in nanosecondi**: setup e hold di `PCK1B`, `PCK2B`,
   `LOAD`, `CA4`, `EVEN`, `H`, `2H1` rispetto a `12M`, `24M`, `8M`. Il core
   MiSTer lavora a 48 MHz con clock enable, quindi dà l'ordine degli eventi,
   non i margini analogici.
2. Il fronte esatto del `12M` che campiona `CR` (il core usa un enable
   chiamato "12M_N", le note parlano di fronte di salita): polarità da verificare.
3. Bus ADPCM: multiplexing `SDPMPX`/`SDRMPX` e tempi.
4. Semantica di `PDTACK`, `ROMWAIT`, `PWAIT0/1` (per tenere ferma la console).
5. Il wiki scrive "sotto 250 ns (7 mclk)" per la C ROM: 7 periodi di un clock a
   24 MHz sono 292 ns, 250 ns sono 6. Non so quale dei due sia il dato giusto.

## 8. Dal core NeoGeo_MiSTer (furrtek e altri)

**Fonte.** `github.com/MiSTer-devel/NeoGeo_MiSTer`: implementazione FPGA completa
della Neo Geo, con i chip separati in moduli (`rtl/video/zmc2_dot.v`,
`rtl/io/zmc.v`, `rtl/video/neo_273.v`, `rtl/video/lspc2_clk.v`) e un file di
appunti dell'autore (`DEV_NOTES.md`). **Licenza GPL** (file `LICENSE` v2, alcune
intestazioni v3 o successiva). L'ho letto per capire il comportamento e questa
sezione è scritta con parole mie; **non ho copiato codice**. Se in futuro il
nostro gateware dovesse riusare codice di quel core, erediterebbe la GPL: va
deciso prima.

**[MiSTer] Clock.** Master 24 MHz; `12M`, `6M`, `3M`, `1.5M` sono divisioni per
2, 4, 8, 16; `8M` è 24M/3 e `4M` è 24M/6.

**[MiSTer] Serializzatore (zmc2_dot).** Registro a scorrimento da 32 bit
caricato da `CR` quando `LOAD` è attivo, su un tick del `12M`; poi ad ogni tick
fa scorrere di **due pixel** (le quattro corsie da un byte avanzano di 2 bit),
nella direzione scelta da `H`. In uscita ci sono due pixel alla volta, `GAD`
(pixel A) e `GBD` (pixel B), da 4 bit ciascuno; `EVEN` e `H` scelgono quali bit
formano la coppia (parità di X e direzione). `DOTA` e `DOTB` valgono 1 se il
pixel è diverso da 0, cioè non trasparente.
**[calcolo]** 8 pixel = 4 tick da 83,3 ns = 333 ns per ogni lettura `CR` da
32 bit. Coincide con la stima di budget della sezione 2.

**[MiSTer] Indirizzi sul bus P.** Il bus `P` è multiplexato: la cartuccia
cattura valori diversi su due fronti.
* Su `PCK1B` (sprite): `PBUS[15:0]` sono i 16 bit bassi del numero di tile,
  `PBUS[19:16]` la riga del tile (0-15), `PBUS[23:20]` i 4 bit alti del tile.
  In pratica `P0-P23` = tile (20 bit) + riga (4 bit), e ogni indirizzo
  identifica 8 byte, cioè una riga di 16 pixel (64 bit); `CA4` sceglie la
  metà da 32 bit mandata al serializzatore.
* Su `PCK2B` (fix): `PBUS[11:0]` sono il numero di tile e `PBUS[15:12]` quattro
  bit di posizione nel tile; insieme formano un indirizzo di parola a 16 bit
  (128 KiB di S ROM), e `S2H1` sceglie il byte alto o basso per `FIXD0-7`.

**[MiSTer] Innesco delle letture** (da `DEV_NOTES.md`): la lettura C parte
quando `PCK1B` sale, quella S quando `PCK2B` sale, il bus 68k quando `nROMOE`
o `nPORTOE` scendono. Il core del file usa SDRAM a 120 MHz (5 × 24M, fino a
144 MHz) e deve inserire **un wait state** sul 68k. Per noi vuol dire che la
latenza della SDRAM conta e che i segnali di attesa della PROG (`ROMWAIT`,
`PWAIT0/1`, `PDTACK`) vanno capiti davvero.

**[MiSTer] Riorganizzazione al caricamento.** Il core non tiene i dati nell'ordine
dei file: li riordina mentre li carica. Per il fix mette adiacenti le coppie di
pixel in modo che una sola lettura da 16 bit serva 4 pixel; per gli sprite
dispone i byte in modo che una riga di 16 pixel (64 bit) siano quattro parole
da 16 bit consecutive, leggibili in burst, con `CA4` che sceglie la metà.
Questo conferma la scelta di un loader che prepara i dati, ma significa che **il
layout canonico del `.ngpk` non è quello che l'FPGA leggerà**: serve una
permutazione definita (nel packer, nel loader o nella scrittura verso la SDRAM).
Il dettaglio esatto sta nel loader del software di MiSTer
(`support/neogeo/loader.cpp` secondo le note), che non ho ancora letto.

**[MiSTer] NEO-ZMC (Z80).** Quattro registri di finestra, uno per ogni
dimensione (2, 4, 8, 16 KiB), che all'azzeramento puntano alla stessa zona di
indirizzi (finestre "identità"). Sul fronte di salita di `SDRD0` si latcha il
valore presente su `SDA15-SDA8`, e `SDA1-SDA0` scelgono la finestra. L'uscita
`MA[18:11]` è l'indirizzo alto della M ROM: sotto `0x8000` passa l'indirizzo
così com'è. Gli indirizzi sono quindi fino a 19 bit (512 KiB).

**Limiti di questa fonte.** Il core è un modello a livello di registro
funzionante, non una misura del connettore. La licenza GPL e i dettagli di
`loader.cpp` sono i due punti da chiudere prima di scrivere il gateware.

## 9. Piste per colmare i vuoti

* `loader.cpp` di Main_MiSTer (`support/neogeo/`, secondo le note): contiene la
  permutazione esatta di C e S al caricamento. È il prossimo file da leggere.
* La pagina PRO-CT0 del wiki rimanda a un sorgente Verilog di PRO-CT0
  (`Ct0.zip`, di furrtek) e a un suo schema: utili per confrontare il
  serializzatore con `zmc2_dot`. Non sono riuscito a leggerli da qui.
* Misure con analizzatore logico su una console con una cartuccia vera, per i
  margini in nanosecondi.
