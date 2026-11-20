# Cartuccia Neo Geo AES con microSD: formato, packer e loader

Prima parte del progetto: il lato software modulare. Il PCB e il gateware FPGA
non sono ancora stati fatti, vedi `docs/ARCHITECTURE.md` per lo stato e i punti
aperti.

## Contenuto

| Percorso | Cosa |
|----------|------|
| `docs/FORMAT.md` | Specifica del formato `.ngpk` e delle ricette |
| `docs/AES_PINOUT.md` | Nomi dei segnali e numeri di pin dei connettori AES PROG e CHA |
| `docs/TIMING.md` | Comportamento di sprite, fix, bank switching e NEO-ZMC ricavato da Geolith, con ciò che manca |
| `docs/ARCHITECTURE.md` | Architettura, mappa SDRAM, contratto con l'FPGA, punti aperti |
| `tools/ngpk.py` | Packer/ispettore (Python 3, nessuna dipendenza) |
| `recipes/` | Ricette: Samurai Shodown III (esempio) e `spf2ng` (il gioco del progetto) |
| `docs/GATEWARE.md` | Stato del gateware Verilog e di cosa dimostrano i test |
| `gateware/` | RTL e testbench (Icarus Verilog), per ora il fetch/serializzatore degli sprite |
| `firmware/` | Parser `.ngpk` e loader in C99 portabile, più test su PC |
| `tests/` | Test del packer e script che esegue tutto |

I file ROM non sono inclusi: servono i tuoi dump.

**Licenza:** GPL-3.0-or-later, testo in `LICENSE`.

## Uso

```sh
# creare un pacchetto (la ricetta elenca i file, --base-dir dice dove sono)
python3 tools/ngpk.py pack recipes/samsho3.json --base-dir /percorso/romset -o samsho3.ngpk

python3 tools/ngpk.py info   samsho3.ngpk    # regioni, dimensioni, CRC
python3 tools/ngpk.py verify samsho3.ngpk    # ricontrolla i CRC
python3 tools/ngpk.py unpack samsho3.ngpk -o out/   # P.bin, C.bin, ...
# unpack --canonical riporta C e S in ordine MAME; pack usa il layout sdram1 (docs/FORMAT.md)

# test (senza ROM usa un gioco sintetico; con una cartella usa anche il romset)
tests/run_all.sh
tests/run_all.sh /percorso/romset
```

Copia i `.ngpk` sulla microSD: il loader li legge tramite il file system dell'MCU (FatFS).

## Aggiungere un gioco

Si scrive una ricetta (vedi `docs/FORMAT.md`): quali file vanno in quale
regione e con quale operazione (`concat`, `swap16`, `interleave8`). Il packer
controlla che a `0x100` della P ci sia `NEO-GEO`, quindi uno swap sbagliato non
passa inosservato. Giochi che richiedono protezioni o cifratura (SMA, PCM2,
CMC, PVC...) non sono ancora supportati e vengono rifiutati.

## Portare il loader su un MCU

`firmware/ngsd_loader.c` non dipende dall'hardware. Si implementano quattro
funzioni in `ngsd_hal_t`: lettura dal file sulla SD (FatFS), scrittura in SDRAM
tramite l'FPGA, scrittura dei registri FPGA e, se serve, una barra di
avanzamento. Il codice si compila con `-std=c99` senza librerie.
