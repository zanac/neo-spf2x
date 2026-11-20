# Pinout del connettore AES (schede PROG e CHA)

**Fonte:** simboli KiCad del progetto `neogeo-diag-aes-prog` di jwestfall69 e
della sua libreria `neogeo-diag-kicad-library` (entrambi di pubblico dominio),
estratti automaticamente dai file `.kicad_sym`: nessuna trascrizione a mano.
Lati e numeri di pin sono quelli dei simboli di quella libreria.

**Stato:** sono nomi di segnale e numeri di pin, **non** una specifica
elettrica. Mancano direzioni, temporizzazioni e livelli. Prima di mandare in
produzione un PCB vanno confrontati con una cartuccia AES reale (continuità con
il multimetro) e con la pagina *Signal names* del wiki neogeodev.

Una cartuccia AES è fatta di due schede affiancate, PROG e CHA, ognuna con 50
contatti per lato (100 per scheda, 200 in tutto, come riportato dal wiki).
La nostra cartuccia, se vuole stare in un guscio AES, deve presentare entrambi
i connettori.

## Geometria dei contatti

Dal footprint `neogeo-aes-a-side-edge`: 50 contatti con passo 2,54 mm, ciascuno
1,5 × 10 mm. Scheda da 1,6 mm di spessore; il repo suggerisce finitura ENIG e
contatti dorati con smusso a 45°. La scheda PROG del repo è a due strati di rame.

## Alimentazione e linee comuni

`VCC` sui pin 25, 26, 27 di entrambi i lati e `GND` sui pin 1, 2, 49, 50.
`L_OUT/L_IN` e `R_OUT/R_IN` sono i pin 23 e 24 di entrambe le schede (A: L, B: R):
nel PCB del repo sono sulla stessa rete (`L_AUDIO`, `R_AUDIO`), cioè
l'audio fa un giro attraverso la cartuccia e va richiuso.

## Scheda PROG

| Pin | Lato A | Lato B |
|----:|--------|--------|
| 1 | GND | GND |
| 2 | GND | GND |
| 3 | D0 | A1 |
| 4 | D1 | A2 |
| 5 | D2 | A3 |
| 6 | D3 | A4 |
| 7 | D4 | A5 |
| 8 | D5 | A6 |
| 9 | D6 | A7 |
| 10 | D7 | A8 |
| 11 | D8 | A9 |
| 12 | D9 | A10 |
| 13 | D10 | A11 |
| 14 | D11 | A12 |
| 15 | D12 | A13 |
| 16 | D13 | A14 |
| 17 | D14 | A15 |
| 18 | D15 | A16 |
| 19 | R/W | A17 |
| 20 | AS | A18 |
| 21 | ROMOEU | A19 |
| 22 | ROMOEL | ROMOE |
| 23 | L_OUT | R_OUT |
| 24 | L_IN | R_IN |
| 25 | VCC | VCC |
| 26 | VCC | VCC |
| 27 | VCC | VCC |
| 28 | PORTOEU | ROMWAIT |
| 29 | PORTOEL | PWAIT1 |
| 30 | PORTWEU | PWAIT0 |
| 31 | PORTWEL | PDTACK |
| 32 | 68KCLKB | SDRAD0 |
| 33 | RESET | SDRAD1 |
| 34 | SDPAD0 | SDRAD2 |
| 35 | SDPAD1 | SDRAD3 |
| 36 | SDPAD2 | SDRAD4 |
| 37 | SDPAD3 | SDRAD5 |
| 38 | SDPAD4 | SDRAD6 |
| 39 | SDPAD5 | SDRAD7 |
| 40 | SDPAD6 | SDRA8 |
| 41 | SDPAD7 | SDRA9 |
| 42 | SDPA8 | SDRA20 |
| 43 | SDPA9 | SDRA21 |
| 44 | SDPA10 | SDRA22 |
| 45 | SDPA11 | SDRA23 |
| 46 | SDPMPX | SDRMPX |
| 47 | SDPOE | SDROE |
| 48 | PORTADRS | 4MB |
| 49 | GND | GND |
| 50 | GND | GND |

Gruppi: bus dati 68k `D0-D15`, bus indirizzi `A1-A19`, controllo
(`R/W`, `AS`, `ROMOE`, `ROMOEU/L`, `PORTOEU/L`, `PORTWEU/L`, `PORTADRS`,
`68KCLKB`, `RESET`), attese (`ROMWAIT`, `PWAIT0/1`, `PDTACK`), bus ADPCM
(`SDPAD0-7`, `SDPA8-11`, `SDPMPX`, `SDPOE` e `SDRAD0-7`, `SDRA8-9`,
`SDRA20-23`, `SDRMPX`, `SDROE`) e `4MB`.

## Scheda CHA

| Pin | Lato A | Lato B |
|----:|--------|--------|
| 1 | GND | GND |
| 2 | GND | GND |
| 3 | PCK1B | FIXD0 |
| 4 | PCK2B | FIXD1 |
| 5 | 12M | FIXD2 |
| 6 | 2H1 | FIXD3 |
| 7 | EVEN | FIXD4 |
| 8 | H | FIXD5 |
| 9 | LOAD | FIXD6 |
| 10 | CA4 | FIXD7 |
| 11 | P0 | P1 |
| 12 | P2 | P3 |
| 13 | P4 | P5 |
| 14 | P6 | P7 |
| 15 | P8 | P9 |
| 16 | P10 | P11 |
| 17 | P12 | P13 |
| 18 | P14 | P15 |
| 19 | P16 | P17 |
| 20 | P18 | P19 |
| 21 | P20 | P21 |
| 22 | P22 | P23 |
| 23 | L_OUT | R_OUT |
| 24 | L_IN | R_IN |
| 25 | VCC | VCC |
| 26 | VCC | VCC |
| 27 | VCC | VCC |
| 28 | SDRD0 | NC |
| 29 | SDRD1 | NC |
| 30 | SDA0 | DOTA |
| 31 | SDA1 | DOTB |
| 32 | SDA2 | GAD0 |
| 33 | SDA3 | GAD1 |
| 34 | SDA4 | GAD2 |
| 35 | SDA5 | GAD3 |
| 36 | SDA6 | GBD0 |
| 37 | SDA7 | GBD1 |
| 38 | SDA8 | GBD2 |
| 39 | SDA9 | GBD3 |
| 40 | SDA10 | SDD0 |
| 41 | SDA11 | SDD1 |
| 42 | SDA12 | SDD2 |
| 43 | SDA13 | SDD3 |
| 44 | SDA14 | SDD4 |
| 45 | SDA15 | SDD5 |
| 46 | SDMRD | SDD6 |
| 47 | SDROM | SDD7 |
| 48 | 24M | 8M |
| 49 | GND | GND |
| 50 | GND | GND |

Gruppi: **ingressi di indirizzo** `P0-P23` (divisi tra i due lati: pari lato A,
dispari lato B) con `CA4`, `PCK1B`, `PCK2B`, `2H1`, `12M`, `LOAD`, `EVEN`, `H`,
`8M`, `24M`; **uscite pixel** `DOTA`, `DOTB`, `GAD0-3`, `GBD0-3`; **dati fix**
`FIXD0-7`; **bus Z80** `SDA0-15`, `SDD0-7`, `SDRD0/1`, `SDMRD`, `SDROM`.
`NC` sono pin non collegati.

## Cosa implica per il progetto

* Sulla CHA il connettore AES **non porta i dati delle C ROM** (nei simboli non
  compare nessun pin `CR`, in linea con il wiki su NEO-ZMC2): porta
  l'indirizzo del tile (`P0-P23`) e si aspetta indietro i pixel già serializzati
  (`DOTA/DOTB`, `GAD`, `GBD`) e i dati del fix layer (`FIXD0-7`). Il lavoro del
  chip PRO-CT0 spetta quindi interamente al nostro FPGA.
* Il bus Z80 (`SDA`, `SDD`, `SDMRD`, `SDROM`) è sul connettore: la M ROM e il
  bank switching che fa NEO-ZMC li dobbiamo servire noi.
* La PROG ha `ROMWAIT`, `PWAIT0/1` e `PDTACK`: sono i candidati per tenere
  ferma la console durante il caricamento da SD. Funzione e polarità vanno
  ancora verificate.

