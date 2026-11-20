# Scelta dei componenti (proposta, da confermare)

**Correzione a una mia proposta precedente.** Avevo suggerito un Cyclone 10 LP
con SDRAM da 64 MiB. Contando i segnali veri del connettore (`hardware/gen_signals.py`
da `docs/it/AES_PINOUT.md`) quella scelta non regge: i **segnali lato console sono
162**, e il numero di I/O utili dell'FPGA sale a circa 220.

## 1. Budget di I/O

| Voce | Pin FPGA |
|------|---------:|
| Segnali console (PROG 82 + CHA 80, esclusi alimentazione e audio) | 162 |
| SDRAM 16 bit (16 DQ, 13 A, 2 BA, CKE, CS, RAS, CAS, WE, 2 DQM, clock) | 39 |
| Collegamento MCU (bus a 8 bit + strobe, o SPI/QSPI) | ~12 |
| Direzione dei traslatori, LED, pulsante, varie | ~8 |
| **Totale** | **~221** |

Dei 162 segnali, per nome: 99 ingressi (indirizzi, strobe, clock, bit di banco),
22 uscite (pixel, fix, linee di attesa), 40 bidirezionali (`D0-D15`, `SDD0-7`,
bus ADPCM multiplexati `SDPAD`/`SDRAD`), 1 incerto (`4MB`). **Le direzioni sono
dedotte dai nomi**, non verificate (colonna `basis` di `hardware/signals.csv`).

### Budget MVS

L'MVS ha **182 segnali** (`docs/it/MVS.md`): 182 + 39 + ~12 + ~8 ≈ **241** con il bus MCU
parallelo, ≈ 233 con un link SPI. Sul 45F caBGA554 (245 I/O) restano pochi pin:
(≈ 12), ma ci si sta: il numero finale lo fissa l'assegnazione in `hardware/gen`.
La **LFE5U-85F nello stesso caBGA554** (259 I/O) resta come ripiego compatibile.

## 2. FPGA

Dati dai siti dei costruttori (consultati oggi):

| Famiglia / dispositivo | Pacchetto | I/O utente | Basta (≥ ~230 con margine)? |
|------------------------|-----------|-----------:|-----------------------------|
| Cyclone 10 LP 10CL016/025 | UBGA-256 | 162 / 150 | no |
| Cyclone 10 LP 10CL010 | UBGA-256 | 176 | no |
| ECP5 LFE5U-25F / 45F | caBGA256 | 197 | no |
| ECP5 LFE5U-45F | caBGA381 | 203 | no |
| **ECP5 LFE5U-45F** | **caBGA554 (23×23 mm)** | **245** | **sì** |
| ECP5 LFE5U-85F | caBGA554 | 259 | sì (più grande del necessario) |
| Cyclone 10 LP 10CL025/040 | UBGA-484 | 325 | sì |

**Proposta: Lattice ECP5 LFE5U-45F in caBGA554.** Supporta I/O LVCMOS a 3,3 V,
è sufficiente come logica (44 k LUT contro le poche migliaia del gateware
attuale) e ha una toolchain aperta (Yosys + nextpnr-ecp5 + openFPGALoader), in
linea con il resto del progetto: **che nextpnr-ecp5 supporti proprio questo
pacchetto è da verificare** prima di ordinare. L'alternativa è un Cyclone 10 LP
10CL025 in UBGA-484 con Quartus Lite. In entrambi i casi serve un BGA, quindi
PCB a più strati e assemblaggio in fabbrica.

Il gateware esistente è Verilog generico: non cambia con la famiglia (cambiano
PLL, vincoli e SDRAM I/O).

## 3. Memoria e MCU

* **SDRAM:** uno o due chip da 512 Mbit (64 MiB) × 16 sullo stesso bus (il secondo chip dà
  128 MiB, un pin `CS` in più, serve a 77 set su 307 della lista di MAME), SDR, in classe 143-166 MHz (grade -6/-7).
  Famiglie compatibili da controllare per disponibilità: ISSI IS42S16320,
  Alliance AS4C32M16SB, Micron MT48LC32M16A2. Il controller attuale richiede
  ≥ ~133-144 MHz (`docs/it/GATEWARE.md`).
* **MCU:** RP2040. Il suo PIO può pilotare la microSD a 4 bit e un bus parallelo
  a 8 bit verso l'FPGA; il loader C (`firmware/`) non cambia. L'alternativa è
  uno STM32 con SDMMC. Stima di tempi di caricamento (non misurata): SD a 4 bit
  circa 10-20 MB/s, quindi 3-5 s per 45 MiB.
* **Configurazione FPGA:** flash SPI NOR dedicata (non quella dell'MCU).

## 4. Traslatori di livello 5 V ↔ 3,3 V

Servono per tutti i 162 segnali (l'FPGA non è tollerante a 5 V). Famiglia
proposta: traslatori a doppia alimentazione a 16 bit (classe `74LVC16T245`,
TSSOP-48): lato FPGA 3,3 V, lato console 5 V, pin DIR pilotato dall'FPGA per i
40 bidirezionali (circa 5 pin DIR), fisso per ingressi e uscite. Con 22 gruppi
da 8 bit sono circa **11 componenti** (AES; circa 12 per l'MVS). Ritardo di propagazione dell'ordine di
qualche ns per tratta: da mettere nel budget di temporizzazione dopo le misure
sulla console.

## 5. Alimentazione (stima, non verificata)

Dal connettore arrivano 5 V (`VCC` sui pin 25-27). Servono almeno 3,3 V
(I/O FPGA, SDRAM, MCU, traslatori lato FPGA), 2,5 V (ausiliaria ECP5) e 1,1 V
(core ECP5). Non conosco la corrente che lo slot AES può dare a una cartuccia
né quanto consumerà il progetto: **va misurato** prima di scegliere i
regolatori (e magari serve un limitatore di inrush).

## 6. Cosa non è deciso e ostacola lo schema

1. **Meccanica.** Una cartuccia AES è fatta da due schede (PROG e CHA) con 100
   contatti ciascuna; non ho le quote del guscio né la posizione relativa dei
   due connettori. Servono le misure da una cartuccia vera (o un guscio) per
   decidere se è una scheda sola con due pettini o due schede collegate (proposta in `docs/it/PCB.md`).
2. **Direzioni e livelli dei segnali** (`signals.csv`, `signals_mvs.csv`).
3. **Corrente 5 V** e tempi di avvio rispetto al BIOS (`docs/it/BOOT.md`).
4. **Disponibilità e prezzo** di FPGA e SDRAM scelte (non verificati).
5. **Schema KiCad:** non l'ho generato. Non c'è KiCad in questo ambiente per
   validarlo (ERC), e produrre uno schema non verificabile con un BGA da 554 sfere
   avrebbe poco valore; il passo successivo è farlo con KiCad installato, a
   partire da `hardware/signals.csv`, `hardware/signals_mvs.csv` e dai footprint AES della libreria
   `neogeo-diag-kicad-library`.
