# Gateware (stato)

Verilog generico, nessuna primitiva di un costruttore. Simulazione con
Icarus Verilog (`iverilog`, `vvp`); i test girano solo se `iverilog` è installato.

## Moduli

| File | Cosa fa |
|------|---------|
| `gateware/rtl/ng_cfetch.v` | Sprite: cattura l'indirizzo dal bus `P` su `PCK1B`, legge dalla SDRAM la riga di tile (8 byte, una sola lettura) e la serializza a 2 pixel per tick di `12M`, con `H` per il flip |
| `gateware/rtl/ng_sfetch.v` | Fix layer: cattura tile/posizione su `PCK2B`, legge 8 byte, `S2H1` sceglie il byte per `FIXD0-7` |
| `gateware/rtl/ng_pbank.v` | 68k: lettura della P (P1 fissa + finestra da 1 MiB) e latch di bank, azzerato al reset |
| `gateware/rtl/ng_zmc.v` | Z80: bank switching della M ROM (4 finestre, reach 512 KiB, mappa identità al reset) |
| `gateware/rtl/ng_boot.v` | Boot RAM da 1 KiB servita al 68k in modalità stub (`docs/BOOT.md`), scritta dall'MCU, precaricabile da `BOOT_HEX` |
| `gateware/rtl/ng_rdport.v` | Lettura di un byte da una regione (porta M e porta V dei dati ADPCM, astratta) |
| `gateware/rtl/ng_sdram.v` | Controller SDR SDRAM 16 bit, 4 banchi, CL3, burst 4, pagina chiusa, una richiesta alla volta; init e refresh |
| `gateware/rtl/ng_arb.v`, `ng_fifo4.v` | Arbitro a priorità fissa MCU > C > S > P > M > V con FIFO di 4 richieste per porta |
| `gateware/rtl/ng_top.v` | Integrazione: registri dell'MCU (la mappa di `firmware/ngsd_loader.h`), maschere dei tile ricavate da `SIZE_x`, basi da `ADDR_x`, porta SDRAM dell'MCU, boot RAM e modalità stub |
| `gateware/tb/` | Testbench e modello comportamentale della SDRAM con controlli di temporizzazione e refresh |
| `gateware/model/` | `sdram_budget.py` (modello ideale in Python) e `rtl_budget.py` (stress sull'RTL) |

Non ancora scritti: interfaccia fisica verso l'MCU (SPI/QSPI), ADPCM vero
(bus `SDPAD/SDRAD`), gestione dell'avvio (`ROMWAIT`, `PDTACK`), vincoli di pin e
temporizzazione, controller SDRAM con bank interleaving.

## Come si prova

```sh
python3 gateware/tests/test_cfetch.py                # serializzatore sprite, dati casuali
python3 gateware/tests/test_cfetch.py C_canonico.bin # idem con dati reali (ordine MAME)
python3 gateware/tests/test_modules.py               # fix, banco P, Z80 banking
python3 gateware/tests/test_system.py                # tutto insieme con controller e chip SDRAM
python3 gateware/model/rtl_budget.py                 # traffico di picco sull'RTL, latenze
```

`tests/run_all.sh` li esegue se `iverilog` è installato.

Il test converte i dati canonici nel layout `sdram1` con `tools/ngpk.py`, li
carica nel modello di SDRAM del testbench e confronta, per 400 righe di tile
casuali (con e senza `H`, numeri di tile a 20 bit che si ripiegano sulla
dimensione della C ROM), ogni pixel in uscita con il modello di decodifica
canonica scritto seguendo Geolith. Prova anche tre combinazioni di latenza
SDRAM e anticipo di `LOAD`; l'ultima è un test negativo che deve segnalare
underrun. Risultato attuale: **0 pixel sbagliati** con dati casuali e con una
porzione reale degli sprite di `spf2ng`.

## Cosa dimostra e cosa no

Dimostra che la permutazione `sdram1` e il serializzatore insieme restituiscono
gli stessi pixel del decoder di riferimento, e che la logica regge il flusso di
dati con le ipotesi sotto. **Non** dimostra che combaci con una console vera.

Scelte di modello non verificate su hardware:

* `CA4 = 0` seleziona i primi 4 byte della riga (la metà a `+0x40` canonico).
* Ogni tick di `12M` esce una coppia `(gad, gbd)` = (pixel precedente, pixel
  seguente) nell'ordine temporale; `EVEN` non è usato. Su una cartuccia vera
  `EVEN` e `H` decidono quali bit formano la coppia: da controllare.
* `LOAD` è campionato su un tick di `12M` modellato come impulso del clock
  veloce; la polarità e il fronte reali del `12M` sono un punto aperto.
* La dimensione della C ROM è una potenza di due (`tile_mask`); per altre
  dimensioni serve un modulo vero, che Geolith applica con `%`.
* Nel test del solo serializzatore il modello di SDRAM ha latenza fissa; il
  comportamento con una SDRAM e un controller veri è nella sezione "Misura
  sull'RTL" (sotto), che però resta una simulazione.

## Budget della SDRAM (modello, `gateware/model/sdram_budget.py`)

Non è RTL: è uno scheduler a livello di ciclo di una SDRAM SDR da 16 bit
(4 banchi, pagina chiusa con auto-precharge, parametri tipo 133 MHz CL3 con
tRCD 20 ns, tRC 64 ns, refresh ogni 7,8 µs) che serve insieme il traffico
peggiore che la console può generare, con le frequenze ricavate da
`docs/TIMING.md`:

| Classe | Traffico | Modello |
|--------|----------|---------|
| C | riga di sprite da 8 byte ogni 667 ns (96 sprite per linea, 100 % di duty) | indirizzi casuali nei 32 MiB |
| S | due letture da 16 bit ogni 667 ns | casuali in 128 KiB |
| P | una lettura da 16 bit ogni 333 ns (68k a 12 MHz) | sequenziale |
| M | un byte ogni 750 ns (Z80 a 4 MHz) | casuale |
| V | ADPCM-A (6 canali) + ADPCM-B | casuale |

Risultato su 4 ms simulati (mappatura dei banchi "top" = 16 MiB per banco, o
"interleave" = pagine da 2 KiB intercalate; priorità C-first o P-first):

* uso del bus dati **10 % a 133 MHz, 14 % a 100 MHz**: la banda non è il problema;
* latenza peggiore (arrivo → ultimo dato) sulle letture C **173-241 ns a 133 MHz,
  240-270 ns a 100 MHz**; p99 135-150 ns; P e S simili, M e V fino a 390 ns;
* nessun accumulo di richieste in coda.

**Cosa significa e cosa no.** La SDRAM regge il traffico di picco con ampio
margine di banda. Quello che il modello non può dire è se 170-270 ns bastano:
dipende dalla distanza tra `PCK1B` e il `LOAD` che usa il dato, che non
conosco (punto aperto, da misurare). Un indizio: il core NeoGeo_MiSTer serve
le C ROM da una SDRAM a 120 MHz, quindi la scadenza reale è compatibile con
latenze di questo ordine, ma è una deduzione dal suo funzionamento, non una
misura. Il modello trascura inoltre sincronizzatori tra clock, ritardi dei
traslatori 5 V, tRAS/precharge fini sui cambi di comando e l'arbitraggio vero
del controller: va rifatto sul controller RTL quando esiste. Le scelte che
restano utili: SDRAM a 133 MHz (non 100) per avere più margine sul caso peggiore
di latenza, priorità a C e S rispetto al resto.

## Misura sull'RTL (`gateware/model/rtl_budget.py`)

Stesso traffico di picco della tabella sopra, ma sull'RTL vero (`ng_top` +
`ng_sdram` + chip comportamentale con controllo dei tempi), 2 ms simulati. Il
controller attuale esegue **una richiesta alla volta** e non fa bank
interleaving, quindi è peggiore del modello ideale.

| Clock SDRAM | Sprite, latenza max / media | Fix | 68k (P) | Z80 (M) | V | Note |
|-------------|----------------------------|-----|---------|---------|---|------|
| 144 MHz | 285 / 138 ns | 285 ns | 326 ns | 590 ns | 667 ns | tutte le richieste servite, 0 errori di protocollo |
| 96 MHz | 375 / 232 ns | 375 ns | 323 ns (25 % delle letture perse) | 740 ns | 11 µs (V affamata) | controller saturo |

(Latenza = dal fronte di `PCK1B`/`PCK2B` o dalla richiesta fino al dato pronto.)

Letture: con questo controller **servono almeno circa 133-144 MHz** (parti
speed grade -6/-7); a 96 MHz il traffico di picco lo satura. Il modello ideale
dava il 10-14 % di uso del bus, ma presupponeva richieste sovrapposte su banchi
diversi: se serve più margine o un clock più basso, il passo successivo è un
controller con bank interleaving. Resta aperta, come prima, la scadenza reale
tra `PCK1B` e `LOAD`, che non si ricava da simulazione.

Il controller legge 8 byte per richiesta (burst da 4 beat su 16 bit) perché
sprite e fix leggono esattamente 8 byte allineati; per P, M e V si usa solo la
metà o il byte che serve. La scrittura è di una parola da 32 bit per volta
(`dqm` maschera le altre): ~12 cicli per parola, ampiamente sopra i requisiti
del caricamento da SD.

## Come vengono verificati i collegamenti con il firmware

`tests/test_system.py` programma i registri come fa `firmware/ngsd_loader.c`
(`SIZE_x`, `ADDR_x`, poi `CTRL.RUN`) e controlla: scrittura e rilettura SDRAM
dall'MCU, 240 mezze righe sprite, 150 letture fix, 174 letture 68k con latch di
bank, 113 letture Z80 con bank switching e 60 letture V. Il modello della SDRAM
segnala violazioni di tRCD/tRC/tRP/tRFC, refresh mancato e indirizzi fuori
memoria; con una violazione introdotta apposta (tRCD di un ciclo più corto) il
test fallisce, quindi i controlli sono attivi.
