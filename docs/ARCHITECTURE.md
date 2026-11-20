# Architettura della cartuccia Neo Geo AES con microSD

Stato del progetto: **formato, packer e loader sono scritti e testati; PCB e
gateware FPGA non esistono ancora.** Questo documento separa ciò che è stato
verificato da ciò che è ancora una proposta o un punto aperto.

## 1. Come funziona

```
PC                    microSD                 Cartuccia
ricetta + ROM  --ngpk.py-->  gioco.ngpk  --->  MCU (FatFS + loader)
                                                  |  scrive in SDRAM
                                                  v
                                   FPGA <--> SDRAM 64 MiB
                                     |
                                     +-- logica da cartuccia AES verso la console
```

1. Sul PC `tools/ngpk.py` converte il romset di un gioco in un file `.ngpk`.
2. All'accensione l'MCU legge il `.ngpk` dalla microSD, controlla i CRC e copia
   le regioni in SDRAM (`firmware/ngsd_loader.c`).
3. L'MCU scrive nei registri dell'FPGA le dimensioni e gli indirizzi delle
   regioni, poi imposta `CTRL.RUN`.
4. L'FPGA serve alla console i dati dalla SDRAM, replicando ciò che farebbero le
   ROM e i chip di una cartuccia vera.

La modularità sta in due punti: il formato `.ngpk` (i dettagli del gioco
restano nel packer) e il campo `mapper` (le differenze di logica restano nel
gateware, selezionate da un registro).

## 2. Fatti verificati sul wiki neogeodev

* Il connettore AES ha 200 contatti (2 × 2 × 50).
* Le cartucce AES contengono un chip **NEO-ZMC2** (o PRO-CT0); le MVS no.
  NEO-ZMC2 unisce NEO-ZMC (bank switching dello Z80, ingressi `SDA0, SDA1,
  SDA8-SDA15`, uscite `MA11-MA21` verso la M ROM) e PRO-CT0 (serializzatore
  degli sprite).
* PRO-CT0 prende i dati C in parallelo (`C0-C31`, "2×16 bit", tutto il
  necessario per una linea di 8 pixel), li latcha sul fronte di discesa di
  `12M` quando c'è `LOAD`, emette un pixel per ogni fronte di discesa di `12M`,
  inverte l'ordine con `H` (flip orizzontale) e produce `DOTA/DOTB` e
  `GAD0-3/GBD0-3`.
* Tile: 16×16 px a 4 bpp = 128 byte. Le C ROM dispari hanno i bitplane 0-1, le
  pari i bitplane 2-3.
* Velocità richieste: C ROM sotto 250 ns (7 mclk); P ROM almeno 150 ns (con wait
  state configurabili); V ROM ADPCM-A qualsiasi (> 2 µs), ADPCM-B 250 ns.
* Bank switching della P: una scrittura (word, o byte a indirizzo dispari) nella
  finestra `$200000-$2FFFFF` porta `/PORTWEL` basso e latcha D0/D1 su A20/A21
  della P2; i latch si azzerano al reset; la finestra è di 1 MiB.

**Conseguenza importante:** su AES la cartuccia non porta solo memoria. L'FPGA
deve **replicare NEO-ZMC2** (bank switching Z80 e serializzatore pixel) oltre al
latch della P. Il serializzatore ha vincoli di tempo veri: i dati C devono
arrivare dalla SDRAM entro i 250 ns, quindi servono prefetch e una gestione
attenta degli accessi a banco/riga.

**Pinout AES (da `docs/AES_PINOUT.md`) e ruolo reale dell'FPGA.** Il connettore
CHA non porta i dati delle C ROM: porta in ingresso l'indirizzo del tile
(`P0-P23`) con i segnali di temporizzazione (`CA4`, `PCK1B`, `PCK2B`, `2H1`,
`12M`, `LOAD`, `EVEN`, `H`, `8M`, `24M`) e si aspetta in uscita i pixel già
serializzati (`DOTA`, `DOTB`, `GAD0-3`, `GBD0-3`) e i dati del fix layer
(`FIXD0-7`). L'FPGA quindi: legge `P0-P23`, va a prendere i dati nella SDRAM,
li serializza con le regole di NEO-ZMC2 (inclusi `H` per il flip e `LOAD`) e
pilota le uscite; in più serve il bus Z80 (`SDA0-15`, `SDD0-7`, `SDMRD`,
`SDROM`) con il bank switching della M ROM, i bus ADPCM (`SDPAD/SDRAD`...) per
la V ROM e, lato PROG, il bus 68k (`D0-D15`, `A1-A19`) con il latch di bank.
Tutti questi segnali sono a livello della console (5 V), quindi servono
traslatori o componenti tolleranti a 5 V.

## 3. Mappa SDRAM (profilo `ngsd-64M`)

Scelta di progetto, modificabile insieme al gateware.

| Regione | Base        | Massimo |
|---------|-------------|---------|
| P       | `0x0000000` | 8 MiB   |
| V       | `0x0800000` | 16 MiB  |
| S       | `0x1800000` | 1 MiB   |
| M       | `0x1900000` | 1 MiB   |
| C       | `0x1A00000` | 38 MiB  |

Totale 64 MiB. Samurai Shodown III (esempio fornito) occupa 35,25 MiB: P 3, C 26,
V 6, S 0,125, M 0,125. Il gioco `spf2ng` occupa 45,4 MiB (P 5, C 32, V 8, S 0,125,
M 0,25) e ci sta, con 6 MiB liberi sulla C.
Giochi con C oltre 38 MiB o con ADPCM-B separata vengono rifiutati dal loader
con un errore esplicito (`NGPK_E_PROFILE`). Con 128 MiB di SDRAM il profilo
potrebbe crescere, ma è un'altra scheda.

## 4. Contratto firmware ↔ FPGA

Registri a 32 bit (`firmware/ngsd_loader.h`):

| Registro | Indirizzo | Significato |
|----------|-----------|-------------|
| `CTRL` | `0x00` | bit0 `RUN`: 0 = cartuccia ferma, 1 = gioco in esecuzione |
| `MAPPER` | `0x01` | id mapper del pacchetto |
| `MAPPER_ARG` | `0x02` | argomento del mapper |
| `SIZE_x` | `0x10 + (tipo-1)` | byte presenti nella regione (0 se assente) |
| `ADDR_x` | `0x20 + (tipo-1)` | base SDRAM della regione |

Il loader mette `CTRL = 0` prima di scrivere in SDRAM e imposta `RUN` solo dopo
che tutti i CRC sono corretti. Il trasporto fisico (SPI a 1 bit o QSPI tra MCU e
FPGA) non è ancora scelto: il loader lo vede solo come `sdram_write` e
`fpga_reg`.

Tempi di caricamento stimati (non misurati): per 35 MiB circa 6 s con SPI a
50 MHz, 2-3 s con SDIO a 4 bit.

## 5. Cosa è stato testato

* Packer: round trip byte per byte sul romset di esempio (due versioni del
  programma), rifiuto di swap sbagliato, interleave di lunghezze diverse, mapper
  sconosciuto, header corrotto.
* Loader in C (compilato con AddressSanitizer e UBSan): carica per intero il
  pacchetto da 35 MiB in una SDRAM simulata e confronta ogni regione con i file
  estratti; prova buffer di 512, 1000, 4096 e 65536 byte; verifica che un bit
  alterato nei dati blocchi `RUN`, che un header alterato o un gioco troppo
  grande non tocchino l'hardware.
* Layout `sdram1` di C e S: round trip, permutazione, confronto pixel per pixel
  con un modello di riferimento della decodifica canonica, flag nelle regioni,
  e rifiuto di un pacchetto canonico da parte del loader (`NGPK_E_LAYOUT`).
* Come eseguirli: `tests/run_all.sh [cartella_romset]`.

## 6. Punti aperti (da risolvere prima del PCB)

0. **Cosa deve fare il gateware è ora in gran parte chiaro** (sprite, fix,
   bank switching P, NEO-ZMC): vedi `docs/TIMING.md`, ricavato dal sorgente di
   Geolith e dal core NeoGeo_MiSTer. Non lo sono i ritardi in nanosecondi sul
   connettore, elencati nella sezione 7 di quel documento.
1. **Pinout AES: nomi e numeri di pin noti, il resto no.** I nomi dei segnali e
   i numeri di pin di PROG e CHA vengono dal repo `neogeo-diag-aes-prog` (vedi
   `docs/AES_PINOUT.md`). Mancano direzioni, livelli e i **margini in
   nanosecondi** di `PCK1B/PCK2B`, `LOAD`, `CA4`, `EVEN`, `H`, `2H1`, `12M` e del
   bus ADPCM. L'ordine degli eventi è noto dal core MiSTer; i margini vanno
   misurati con un analizzatore logico su una console.
2. **Avvio.** Il BIOS legge la cartuccia subito all'accensione, ma la lettura
   della SD richiede qualche secondo. Sul connettore PROG esistono `ROMWAIT`,
   `PWAIT0/1` e `PDTACK`, candidati per tenere ferma la console: funzione e
   polarità non verificate. L'alternativa è una piccola ROM di avvio servita
   dall'FPGA nel frattempo.
3. **Layout dei dati C e S in SDRAM: definito, non verificato su hardware.** Il
   packer produce il layout `sdram1` (vedi `docs/FORMAT.md`), una permutazione
   per riga di tile, e il loader rifiuta pacchetti con altro layout
   (`NGPK_E_LAYOUT`). La permutazione è coerente con un modello della
   decodifica di Geolith (test automatici), ma la corrispondenza `CA4` ↔ metà
   del tile e byte-lane ↔ bitplane resta un'ipotesi finché il gateware non
   gira su una console.
4. **Divisione P1/P2.** Per Samurai Shodown III ho dedotto da un confronto dei
   file che `ep1+ep2` sia P1 (1 MiB) e `ep3+ep4+p5` sia P2 (2 MiB, uguale a
   `sp2` della versione fswords). Va confermato con i dati della scheda.
5. **Mapper.** Tutto ciò che richiede protezioni (SMA, PCM2, CMC, PVC...) non è
   supportato. Che Samurai Shodown III sia `plain` lo ritengo probabile ma non
   l'ho verificato.
6. **Scelta componenti.** FPGA (capacità, pin 5 V o traslatori), MCU (RP2040 o
   STM32, che dà SDIO a 4 bit), SDRAM, regolatori. Dipende dai punti 1-3.
7. **Selezione del gioco.** Per ora un file di configurazione sulla SD più un
   pulsante per passare al successivo. Un menu eseguito dalla Neo Geo stessa è
   possibile ma è un'altra fase.
8. **Licenza.** GPL-3.0-or-later (file `LICENSE`). Il core di riferimento (NeoGeo_MiSTer)
   ha un `LICENSE` v2 e file con intestazioni "v2 o successiva" e "v3 o
   successiva": GPL-3.0-or-later è compatibile con entrambe, ma non con eventuali
   file "solo v2" che non ho controllato uno per uno.

## 7. Prossimi passi

1. Ricavare le temporizzazioni dei segnali (punto 1) e decidere la strategia di
   avvio (punto 2). I footprint dei contatti AES (pubblico dominio) sono già
   disponibili nella libreria del repo `neogeo-diag-kicad-library`.
2. Scegliere FPGA/MCU/SDRAM e scrivere lo schema in KiCad.
3. Scrivere il gateware: controller SDRAM con prefetch, latch P, NEO-ZMC2.
4. Scrivere il livello hardware dell'MCU (SD, SPI/QSPI verso l'FPGA) sotto il
   loader esistente.
5. Simulare il gateware contro i dati del romset di esempio, poi prototipo.
