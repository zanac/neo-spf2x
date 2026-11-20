# Architettura delle schede (AES e MVS): proposta

KiCad non è disponibile in questo ambiente, quindi qui **non ci sono ancora
schema e layout**: solo la partizione, da cui si disegna. Quote del guscio AES/MVS
non disponibili (vanno misurate su un esemplare: wiki *Cartridge specifications*).

## Partizione

Ogni cartuccia è fatta di due schede, PROG e CHA, ciascuna con il suo pettine di
contatti. Proposta, uguale per i due formati:

| Scheda | Contenuto |
|--------|-----------|
| **CHA** | FPGA (ECP5 caBGA554), SDRAM 64 MiB (+ seconda impronta per 128 MiB), flash di configurazione, traslatori 5 V↔3,3 V per i segnali CHA |
| **PROG** | traslatori per i segnali PROG, RP2040, slot microSD, LED/pulsante |
| Collegamento | board-to-board a 3,3 V tra PROG e CHA (circa 83 segnali PROG + SPI/alimentazione) |

I segnali PROG (A1-A19, D0-D15, strobe, ADPCM) devono arrivare all'FPGA: da qui il
collegamento. Con l'FPGA su una sola scheda non servono traslatori sul ponte.

## Set di schede

* **AES:** pettine 50 contatti per lato (162 segnali): `AES_PINOUT.md`, `signals.csv`.
* **MVS:** pettine 60 contatti per lato (182 segnali): `MVS.md`, `signals_mvs.csv`.
* Stessa logica; cambiano solo i due pettini, il blocco traslatori (numero di
  linee) e `MVS` nel gateware (parametro di `ng_top`).

## Da fare in KiCad (nell'ordine)

1. Schema: FPGA con banchi I/O a 3,3 V, SDRAM, traslatori (~12 da 16 bit per l'MVS,
   ~11 per l'AES), RP2040, microSD, alimentazione da `VCC` del connettore (5 V).
2. Footprint dei pettini dalla libreria `neogeo-diag-kicad-library`
   (AES: `neogeo-aes-*-side-edge`; MVS: simboli già usati in `mvs_pins.csv`).
3. Layout a 6-8 strati con SDRAM a impedenza controllata, finitura ENIG, smusso 45°.
4. Verifica contro una cartuccia reale prima della produzione (continuità e
   direzioni), assorbimento da 5 V, tenuta delle uscite in Hi-Z con `SLOTCS`
   (MVS) e durante la configurazione FPGA.

## Generatore hardware (`hardware/gen/`)

I file KiCad 7 si generano da script, così le schede seguono le tabelle dei pin.

* `fpga_db.py`: database delle ball e impronta BGA554 dal CSV ufficiale Lattice
  (`hardware/fpga/`).
* `design.py`, `kisch.py`: modello di netlist e scrittore di schemi; `selftest_sch.py` verifica
  che lo schema generato esporti la stessa netlist (la CLI di KiCad 7 non ha l'ERC).
* Contorni scheda e dita di contatto vengono da `hardware/outline.json` e `hardware/footprints/`.

* `boards.py`: netlist delle quattro schede (AES/MVS × CHA/PROG) da `signals*.csv` e
  `*_pins.csv`; `build_sch.py` scrive `hardware/out/*.kicad_sch`, `*_fpga_pins.csv` (rete → ball)
  e `*_cha.lpf` (vincoli dei pin), e verifica ogni schema con un giro di netlist.
* `tests/test_hw_netlist.py`: ogni segnale della console deve andare dito → traslatore → ball
  dell'FPGA (via link per la PROG), nessuna ball usata due volte.

**Scelte nella netlist.** Un SN74ALVC164245 a 16 bit ogni due gruppi da 8 segnali con la stessa
direzione; i bus bidirezionali (`D0-15`, `SDRAD`, `SDPAD`, `SDD`) hanno una rete `DIR_*` pilotata
dall'FPGA; un `OE_*_N` per scheda, con pull-up, così i traslatori restano in alta impedenza
finché l'FPGA non è configurata. PROG e CHA sono unite da due connettori 2×40 a 1,27 mm (segnali
alternati a massa, 3,3 V dalla CHA, 5 V da entrambi i bordi). `CKE` della SDRAM è fissato alto.
Sull'MVS le copie PROG di `RESET`/`SLOTCS` restano scollegate (si usano quelle della CHA).
La seconda SDRAM condivide il bus e ha un suo `SDR_CS1_N` (con pull-up se il chip non è montato).
I/O FPGA usati: AES 215, MVS 235 su 245; l'MVS usa 7 ball del banco 8 che fanno anche da pin
di configurazione (ultima risorsa in `assign_balls`).

**Non verificato (scritto a memoria, da controllare sui datasheet prima di produrre):** il
pinout TSSOP-48 dell'SN74ALVC164245, quello SOT-23-5 del TLV62569, quello a 54 pin della SDRAM,
il land pattern del BGA, la modalità ECP5 `CFG[2:0] = 010` (SPI master), il pinout dell'header
JTAG (non è uno standard) e tutte le correnti di alimentazione.

**Stato:** schemi e netlist fatti per le quattro schede, con assegnazione delle ball.
Piazzamento, routing, DRC e Gerbers non ancora fatti. Tutto ciò che si genera richiede una
revisione umana prima della produzione.
