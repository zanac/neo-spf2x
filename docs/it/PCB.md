# Architettura delle schede (AES e MVS): proposta

KiCad non è disponibile in questo ambiente, quindi qui **non ci sono ancora
schema e layout**: solo la partizione, da cui si disegna. Quote del guscio AES/MVS
non disponibili (vanno misurate su un esemplare: wiki *Cartridge specifications*).

## Partizione

Ogni cartuccia è fatta di due schede, PROG e CHA, ciascuna con il suo pettine di
contatti. Proposta, uguale per i due formati:

| Scheda | Contenuto |
|--------|-----------|
| **CHA** | FPGA (ECP5 caBGA554), SDRAM 64 MiB, flash di configurazione, traslatori 5 V↔3,3 V per i segnali CHA |
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
