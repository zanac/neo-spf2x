# Cartuccia MVS: differenze rispetto all'AES e stato del progetto

**Richiesta:** PCB sia per AES sia per MVS. Questo documento riassume cosa cambia
e cosa è già nel repo. I due formati **non** si possono coprire con un solo
connettore (geometria e pinout diversi): si fanno due set di schede con la stessa
logica (FPGA, SDRAM, MCU, microSD, firmware).

**Fonte dei pinout:** simboli KiCad di `jwestfall69/neogeo-diag-mvs-prog` e
`neogeo-diag-mvs-cha` (pubblico dominio), estratti con
`hardware/extract_kicad_pins.py` in `hardware/mvs_pins.csv` (240 pin).
Il wiki neogeodev ha i pinout MVS solo come immagini; il wiki dà 60 contatti per
lato, 120 per scheda, passo 2,54 mm, spessore 1,6 mm, e avverte che altrove
`/ROMOE` e `4MB` sono scambiati: `/ROMOE` è il pin 33 lato B, `4MB` il pin 34 lato B
(coerente con i simboli estratti). **Come per l'AES: nomi e numeri, non una
specifica elettrica**; direzioni dedotte dai nomi (`hardware/signals_mvs.csv`).

## 1. Differenze che contano

| Aspetto | AES | MVS |
|---------|-----|-----|
| Contatti | 50 per lato, 100 per scheda | 60 per lato, 120 per scheda |
| Segnali console-lato | 162 | **184 pin, 182 segnali** |
| Dati sprite verso la console | serializzati dalla NEO-ZMC2 in cartuccia: `GAD0-3`, `GBD0-3`, `DOTA`, `DOTB` (+ `LOAD`, `H`, `EVEN`, `12M`) | **paralleli: `CR0-CR31`** (32 bit); il serializzatore è nella console |
| Clock | `12M` | `24M`, `12M`, `8M` |
| Selezione slot | – | `SLOTCS` (più cartucce sul fondo comune: le uscite vanno tenute in alta impedenza se `SLOTCS` non è attivo) |
| Strobe 68k | indirizzi/strobe del bus | `ROMOEU/L`, `PORTOEU/L`, `PORTWEU/L` (byte alto/basso), `PORTADRS`, `AS`, `R/W`; solo `A1-A19` sul connettore |
| ADPCM | bus multiplexati `SDPAD`/`SDRAD` | stessi bus, con `SDPA8-11`, `SDPMPX`, `SDPOE` e `SDRA8-9`, `SDRA20-23`, `SDRMPX`, `SDROE` |
| Z80/M ROM | `SDA`, `SDRD0/1`, `SDMRD`, `SDROM` | uguale |

Sull'MVS il gateware è **più semplice** lato sprite: ci si limita a rispondere con
32 bit su `CR` all'indirizzo latchato da `PCK1B`, scegliendo la metà con `CA4`.
Il bus `P0-P23` e `FIXD0-7` sono invariati (il fix usa `PCK2B` e `2H1`).

## 2. Cosa c'è nel repo

* `gateware/rtl/ng_cfetch_mvs.v`: fetch C senza serializzatore, `cr = CA4 ? meta2 : meta1`
  (stesso layout `sdram1`, nessun cambiamento al formato `.ngpk` né al loader).
* `gateware/rtl/ng_mvs_pdec.v`: da `ROMOE*/PORTOE*/PORTWE*` + `A1-A19` all'interfaccia
  indirizzo/strobe di `ng_pbank` (invariato).
* `ng_top` ha il parametro `MVS` (0 = AES, 1 = MVS) e l'uscita `cr[31:0]`.
* `gateware/tests/test_mvs.py`: testbench autoverificante (40 righe di tile, due metà,
  tre accessi 68k) più elaborazione di `ng_top` con `MVS=0/1`. `tests/run_all.sh` → ALL OK.
* `hardware/signals_mvs.csv`: 184 pin con direzione dedotta.

## 3. Ipotesi **non verificate** specifiche dell'MVS

1. La mappa `ROMOE`/`PORTOE`/`PORTWE` → regioni `$000000` / `$200000` (`ng_mvs_pdec.v`).
   Il significato esatto di `PORTADRS` non è usato.
2. Quale metà da 4 byte corrisponde a `CA4 = 0` e l'ordine dei bit su `CR` (stessa
   ipotesi dell'AES, ancora non provata su hardware).
3. La scadenza tra `PCK1B` e il campionamento di `CR` da parte della console.
4. Lo stub di avvio (`docs/BOOT.md`) è stato pensato per l'AES: la logica di boot MVS
   (BIOS diverso, nessun menu AES) va verificata; `ROMWAIT`/`PWAIT`/`PDTACK` hanno
   gli stessi nomi.
5. **Il bus ADPCM MVS non è implementato** (come per l'AES: `v_rd`/`v_offs` generici,
   manca il collegamento con i multiplexati). Serve per i giochi con parlato.
6. `RESET` (pin 35 lato B PROG e pin 18 lato B CHA), `4MB` e `SLOTCS`: direzione e uso.

## 4. Effetti su I/O e componenti

182 segnali console + 39 SDRAM + ≥ 6 collegamento MCU (SPI) + ~6 varie
≈ **233-241**: sull'ECP5 LFE5U-45F caBGA554 (245 I/O) restano al massimo ~12 pin.
Per l'MVS conviene quindi prevedere la **LFE5U-85F nello stesso caBGA554** (259 I/O,
stessa impronta): nello stesso PCB si monta l'una o l'altra. Dettagli in
`docs/COMPONENTS.md` e architettura delle schede in `docs/PCB.md`.
