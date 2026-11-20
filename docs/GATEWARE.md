# Gateware (stato)

Verilog generico, nessuna primitiva di un costruttore. Simulazione con
Icarus Verilog (`iverilog`, `vvp`); i test girano solo se `iverilog` è installato.

## Moduli

| File | Cosa fa | Stato |
|------|---------|-------|
| `gateware/rtl/ng_cfetch.v` | Cattura l'indirizzo dal bus `P` su `PCK1B`, legge dalla SDRAM le due metà da 32 bit della riga di tile C, le serializza a 2 pixel per tick di `12M` (con `H` per il flip) | simulato |

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
