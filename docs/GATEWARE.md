# Gateware (stato)

Verilog generico, nessuna primitiva di un costruttore. Simulazione con
Icarus Verilog (`iverilog`, `vvp`); i test girano solo se `iverilog` è installato.

## Moduli

| File | Cosa fa | Stato |
|------|---------|-------|
| `gateware/rtl/ng_cfetch.v` | Cattura l'indirizzo dal bus `P` su `PCK1B`, legge dalla SDRAM le due metà da 32 bit della riga di tile C, le serializza a 2 pixel per tick di `12M` (con `H` per il flip) | simulato |

Modello di budget SDRAM (Python, non RTL): `gateware/model/sdram_budget.py`, vedi sotto.

Non ancora scritti: fix layer (S), latch di bank della P, bank switching Z80
(NEO-ZMC), bus ADPCM, controller SDRAM, registri verso l'MCU.

## Come si prova

```sh
python3 gateware/tests/test_cfetch.py                # dati casuali
python3 gateware/tests/test_cfetch.py C_canonico.bin # dati reali (ordine MAME)
```

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
* Il modello di SDRAM ha latenza fissa e nessun refresh né conflitto di riga:
  il test dice solo che la logica funziona con una latenza data, non che una
  SDRAM reale basti. Questo è il prossimo controllo (modello con ritardi di
  riga/banco e refresh) e il punto in cui il budget di 333 ns per lettura
  verrà messo alla prova.

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
