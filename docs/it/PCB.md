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
finché l'FPGA non è configurata. Le reti `DIR_*` hanno pull-down da 10k (SCAS416P "Power-Up Considerations", p. 7: prima VCCA,
OE con pull-up a VCCA, DIR basso salvo serva A→B; la rampa del 5 V della console non è nota, da verificare al banco). PROG e CHA sono unite da due connettori Hirose DF12 a 80 contatti, passo 0,5 mm (presa
`DF12NB(3.0)-80DS-0.5V(51)` sulla CHA, spina `DF12NB(3.0)-80DP-0.5V(51)` sulla PROG; segnali alternati a
massa, 3,3 V dalla CHA, 5 V da entrambi i bordi). `CKE` della SDRAM è fissato alto.
Sull'MVS le copie PROG di `RESET`/`SLOTCS` restano scollegate (si usano quelle della CHA).
La seconda SDRAM condivide il bus e ha un suo `SDR_CS1_N` (con pull-up se il chip non è montato).
I/O FPGA usati: AES 215, MVS 235 su 245; l'MVS usa 7 ball del banco 8 che fanno anche da pin
di configurazione (ultima risorsa in `assign_balls`).

**Adattamento al guscio.** Contorno, fori di fissaggio e dita vengono dalle schede di riferimento
(jwestfall69, pubblico dominio), lo spessore è 1,6 mm come quelle schede, tutti i componenti stanno
sul lato anteriore. Lo spazio tra PROG e CHA e l'altezza libera nel guscio non sono in nessuna
fonte raggiungibile (la pagina del negozio richiede un captcha). Perciò la pila è fatta bassa
quanto i componenti permettono: la coppia Hirose DF12NB(3.0) è alta 3,0 +0,2 mm da accoppiata (disegno Hirose; i vecchi
DF12(3.0)-80DS/DP(86) sono fuori produzione dal 2021 e questo è il sostituto compatibile; 0,3 A per
contatto, 50 cicli), quindi le due schede stanno al massimo a 6,4 mm di spessore totale, invece
degli 8,5 mm dei connettori 2×40 a 1,27 mm. `checks.py` verifica che la PROG, capovolta attorno
a un asse verticale, abbia i suoi 160 pad di collegamento sui pad della CHA con lo stesso numero
e la stessa rete, che i fori di fissaggio coincidano e che i componenti che si fronteggiano
sommino meno di 2,9 mm (caso peggiore ora 2,5 mm: FPGA sotto l'RP2040). I footprint sono generati dai disegni di piazzole Hirose (`hardware/gen/hirose_fp.py`): pad 0,3 × 1,6 mm
con passo 0,5 mm, righe a 2,0 mm, due pad di fissaggio 0,8 × 1,8 mm, stencil da 120 µm. La
numerazione dei pad non è in quei disegni: segue la libreria standard di KiCad, quindi va confrontata
con il catalogo Hirose prima di ordinare. La disponibilità dei DF12NB non è stata verificata. 0,3 A per contatto bastano per l'alimentazione della PROG (3 contatti a 3,3 V, 2 a
5 V). Misura un guscio vero prima di ordinare.

**Verificato sui datasheet (nov 2026):** il pinout TSSOP-48 e i range di alimentazione
dell'SN74ALVC164245 (VCCA 2,3–3,6 V, VCCB 3–5,5 V, DIR alto = A→B), il pinout SOT-23-5 del
TLV62569 (VFB 0,6 V), il pinout a 54 pin x16 della SDRAM (concordano Alliance AS4C32M16SB e
ISSI IS42S16320D), la modalità ECP5 `CFG[2:0] = 010` Master SPI (checklist hardware TN1269 e
guida della scheda ECP5 PCIe) e le ball JTAG/flash/configurazione contro il CSV dei pin
Lattice. Dalla checklist TN1269 la scheda ora ha pull-up da 4,7k su INITN, PROGRAMN, TDI, TMS,
TDO, pull-down da 4,7k su TCK e CCLK, e pull-up sui pin IO2/IO3 della flash. L'header JTAG è il
connettore ARM Cortex Debug a 10 pin da 1,27 mm (stesso pinout dell'header Cortex del Tigard;
utilizzabile con J-Link e altre sonde supportate da openFPGALoader); nRESET (pin 10) non è
collegato.

**Verificato sui datasheet primari forniti dall'autore** (conservati in `datasheets/`): TLV62569, ECP5
DS-02012 / TN-02039 (sysCONFIG) / TN-02038 (hardware checklist) / TN-02200 (PLL), W25Q128JV,
SN74ALVC164245 e SN74LVC16T245, AS4C32M16SB, guida hardware del RP2040, disegno Hirose DM3AT, SD Physical
Layer Simplified Spec 9.10 e AMS1117 (non più usato). Errori trovati e corretti:

* il rail a 3,3 V era un regolatore lineare (1,2 W in un SOT-223): ora un buck TLV62569, 0,6 × (1 + 453k/100k) = 3,32 V;
* il rail a 2,5 V (VCCAUX) era alimentato dai 3,3 V con un LDO 1117 con 0,8 V di margine, poi dai 5 V, che poteva
  salire prima del VCCIO (TN-02038 §4 vuole il VCCIO per primo): ora è un terzo TLV62569 alimentato dal rail a
  3,3 V, 0,6 × (1 + 316k/100k) = 2,496 V, così VCCIO, VCCAUX e VCC partono sempre in quest'ordine;
* pin di configurazione (TN-02039 Tab. 4.5 / TN-02038 Tab. 6.2): CFG[2:0] = 010 con pull-up da 4,7 kΩ e strap a 0 Ω
  per gli zeri, MCLK con pull-up da 1 kΩ e 33 Ω in serie, CSSPIN 4,7 kΩ, MOSI/MISO con pull-up da 10 kΩ (erano sbagliati);
* disaccoppiamento FPGA secondo TN-02038 Tab. 3.1: 100 nF per ogni ball VCC/VCCAUX/VCCIO, 3 × 10 µF su VCC, 10 µF per
  banco VCCIO, ferrite da 120 Ω + 10 µF su VCCAUX (il posizionatore automatico non garantisce un condensatore accanto
  a ogni ball: da controllare a mano);
* il riferimento del PLL a 24 MHz è ora su una ball di ingresso PLL dedicata (A2, `ULC_GPLL1T_IN`, TN-02200 §7.1);
* SDRAM: CKE è pilotato dall'FPGA, basso all'accensione, e DQM resta alto finché non finisce l'attesa di 200 µs (nota 11);
* i canali non usati dei traslatori sono a GND su entrambi i lati (gli ingressi sono sempre attivi); si tiene
  l'SN74ALVC164245 perché il suo VIH di 2 V sul lato 5 V accetta livelli TTL e CMOS, mentre l'SN74LVC16T245 richiede
  3,5 V (0,7 × VCCB); l'ALVC è "non raccomandato per nuovi progetti" e vuole VCCA prima di VCCB: da rivedere;
* il cristallo del RP2040 è l'ABM8-272-T3 della guida Raspberry Pi (15 pF, 1 kΩ in serie).

Induttori (catalogo Taiyo Yuden, 2013): i tre buck usano l'NRS4018T2R2MDGJV (2,2 µH, schermato, 4,0 × 4,0 mm,
corrente di saturazione 3,0 A, corrente per salita di temperatura 2,2 A, DCR 42 mΩ); il land pattern del catalogo (pad
1,2 × 3,7 mm, interasse 2,8 mm) è quello del footprint KiCad `L_Taiyo-Yuden_NR-40xx`. Con la formula del TLV62569
(ΔIL = VOUT (1 − VOUT/VIN) / (L fSW), IL,max = IOUT,max + ΔIL/2, saturazione 20-30 % sopra) il pezzo da 3,0 A copre
anche i 2 A nominali del regolatore (2,1 A × 1,3 = 2,7 A); con i miei carichi stimati (circa 1 A, 0,2 A e 0,5 A, non
misurati) basterebbe anche un NRS4012 da 1,65 A.

Non verificato: i pull-up da 47 kΩ della microSD (le sezioni elettriche della Simplified Spec SD sono vuote), le
correnti di alimentazione (Lattice Power Calculator), la corrente di saturazione degli induttori, il posizionamento
dei condensatori pin per pin, TN-02024 (layout BGA), le quote della shell e le capacità del produttore di PCB.

**Registrazione meccanica, verificata sulle schede di riferimento (file KiCad di jwestfall69):**
PROG e CHA hanno entrambe due fori di montaggio da 10 mm a 90 mm di distanza, nella stessa
posizione rispetto alle dita di contatto (46,27 mm a sinistra del dito A in tutte e due). Nell'AES
l'origine del PROG è spostata di (13,29, 1,65) mm rispetto a quella del CHA, nell'MVS di
(15,08, 1,65) mm, gli stessi numeri delle dita. La PROG è impilata capovolta attorno a un asse verticale (le schede sono quasi simmetriche
allo specchio: riquadri allineati dopo il ribaltamento, contorni diversi per meno dell'1 %
dell'area, fori coincidenti entro 0,01 mm), quindi i suoi connettori di collegamento sono
messi specchiati, e `hardware/gen/checks.py` verifica che
ogni componente stia dentro il contorno reale (tagli compresi) e lontano dai fori. Resta ignota
la distanza tra le schede nel guscio (sotto).

**Slot microSD:** nel footprint Hirose DM3AT i contatti sono sul lato −y e la scheda entra da
+y; lo slot è ruotato di 180° così si apre verso il bordo superiore del PROG, quello opposto
alle dita. Lo slot è a filo del bordo superiore del contorno (l'apertura sul bordo, `prog_anchors` in `build_pcb.py`);
serve comunque un'apertura nel guscio (scelta di progetto, non verificata su un guscio vero).

**SDRAM (datasheet AS4C32M16SB):** vedi `docs/it/GATEWARE.md`.

**Footprint BGA, verificato sul Lattice FPGA-DS-02053 v8.8 (caBGA554):** corpo 23,0 × 23,0 mm,
26 × 26 sfere a passo 0,80 mm (20,0 mm di lato), sfera nominale 0,40 mm (0,35–0,45), lettere
delle righe A–AF senza I, O, Q, S, X, Z, altezza massima del package 1,76 mm. Il datasheet del package non
dà la dimensione del land, ma la TN-02024 v4.1 di Lattice sì: per il caBGA554 il land consigliato sul PCB è
0,400 mm NSMD (apertura della maschera 0,500 mm se SMD), contro un'apertura di 0,300 mm lato package, cioè il pad
da 0,4 mm usato qui. La TN-02024 mostra anche un breakout del 554 in 4 strati con piste da 4 mil (0,10 mm) e
fori via da 7 mil (0,18 mm); questo progetto usa 6 strati, regole 0,1/0,1 mm e fori da 0,2 mm. Il processo
deve comunque essere confermato dall'assemblatore.

**Ancora non verificato:** l'altezza e la distanza reali nel guscio, tutte le correnti di alimentazione dinamiche (il
data sheet dà solo quelle statiche: serve il power calculator di Lattice Diamond), l'assorbimento
dai 5 V della console, la corrente di saturazione dell'induttore del buck del core e le ipotesi
MVS di `docs/it/MVS.md`.

**Stato:** schemi e netlist fatti per le quattro schede, con assegnazione delle ball.
Il piazzamento è fatto e controllato
geometricamente (`checks.py`, `fanout.py` per il BGA); autorouting, DRC e Gerbers non ancora fatti. Tutto ciò che si genera richiede una
revisione umana prima della produzione.
