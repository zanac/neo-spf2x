# Giochi protetti e cartucce speciali: cosa serve a ciascuno

Fonte: MAME (`src/devices/bus/neogeo/`, `src/mame/snk/neogeo.cpp`, `hash/neogeo.xml`) letto il
2026-11-20, più il core NeoGeo_MiSTer (`neo_cmc.v`, `neo_pvc.v`, `neo_sma.sv`) per il banking
del fix layer. Niente di quanto segue è misurato su hardware. `tools/mame_census.py` riproduce i
numeri dalla lista software di MAME.

## 1. Cosa dice la lista software

307 set (originali e bootleg).

| Voce | Risultato |
|------|-----------|
| Cartuccia semplice (slot `rom`) | 225 set |
| Set con chip o logica speciale | 82 set (28 sono bootleg) |
| Set più grande | 90 MiB (P 9, C 64, V 16, S 0,5, M 0,5) |
| Set oltre 64 MiB | 77 |
| Set che stanno nel profilo `ngsd-64M` | 188 |
| Set con C oltre 38 MiB | 90 |
| Set con P oltre 8 MiB | 24 |
| Set con ROM ADPCM-B separata (VB, fino a 2 MiB) | 21 |

Conclusione: **128 MiB di SDRAM coprono ogni set** (profilo `ngsd-128M`: due chip da 64 MiB,
CS scelto dal bit 26 dell'indirizzo). La scheda ha la seconda impronta e la sua linea `CS`.

## 2. Tre tipi di lavoro

* **In fase di pacchetto (PC, nessun hardware):** i chip che si limitano a rimescolare i dati.
  CMC42/CMC50 (decifratura di C, S e M1, S estratta da C), PCM2 (V), gli scramble statici della P
  (famiglie SMA, KOF2002, PVC, KOF98) sono permutazioni fatte una volta da `tools/ngpk.py`. Il
  `.ngpk` contiene poi dati in chiaro e usa il mapper 0.
* **Logica a runtime nell'FPGA (nessuna modifica alla PCB):** tutto ciò che sta sui bus che
  l'FPGA già vede (bus P, `D`, `ROMOE`, `PORTOE`, `PORTWE`, linee di attesa).
* **Non ancora capito abbastanza:** elencato nella sezione 4.

## 3. Logica a runtime per famiglia

| Slot MAME | Giochi | Cosa fa la cartuccia a runtime |
|-----------|--------|--------------------------------|
| `rom` | 225 set | latch di bank della P a `$2FFFF0` (fatto) |
| `rom_fatfur2` | Fatal Fury 2 | letture/scritture in `$2xxxxx` passano da un PRO-CT0 (stessa famiglia del serializzatore degli sprite): serve un modello di quel chip |
| `rom_kof98` | KOF 98 | una scrittura di `$0090` a `$20AAAA` fa restituire `$00C200FD` alle letture di `$100-$103`, una di `$00F0` fa restituire `$4E454F2D`: una sovrapposizione a due stati |
| `rom_mslugx` | Metal Slug X | comandi a `$2FFFE0-$2FFFEF`, bit seriali presi dalla P ROM a `$DEDD2`; per un comando MAME legge la RAM di lavoro del 68k `$10F00A`, che una cartuccia non vede: non verificato |
| `sma_*` | KOF 99, Garou, Metal Slug 3, KOF 2000 | registro di bank (`$2FFFF0`, `$2FFFC0`, `$2FFFE4`, `$2FFFEC`) tramite una tabella di 64 voci su un valore rimescolato di 6 bit, un generatore di numeri casuali letto a `$2FE446` e altri accessori |
| `pvc_*` | Metal Slug 5, SvC Chaos, KOF 2003 | 8 KiB di RAM a `$2FE000-$2FFFFF`; le scritture alle parole `$FF0`, `$FF4-$FF5` (byte `$2FFFE0-$2FFFEB`) fanno scattare unpack/pack dei colori, `$FF8-$FF9` contengono un indirizzo di bank della P. Piccolo |
| `cmc42_*`, `cmc50_*`, `pcm2_*`, `k2k2_*` | circa 28 giochi | decifratura dei dati in fase di pacchetto (vedi sopra), più banking del fix layer, sotto |
| `cmc50_jockeygp`, `rom_vliner` | Jockey GP, V-Liner | 8 KiB di RAM a `$200000-$201FFF` (con batteria nell'originale; il V-Liner usa anche ingressi della console che una cartuccia non ha) |
| `boot_*` | 28 bootleg | ognuno con la sua logica; priorità più bassa |

**Banking del fix layer.** 23 cartucce usano il tipo 1 (Garou, Metal Slug 3/4/5, KOF 99,
KOF 2001, Samurai Shodown V, Rage of the Dragons e altre) e 5 il tipo 2 (KOF 2000 e 2000N,
Matrimelee, SvC, KOF 2003). La S ROM arriva a 512 KiB e il chip sceglie un banco da 128 KiB per
gruppo di linee o colonne di tile, da informazioni che il gioco scrive nella video RAM
(`$7500-$75FF`). MAME e MiSTer le leggono dall'indirizzo della video RAM; la cartuccia vede solo
le parole che l'LSPC mette sul bus P.

## 4. Rischi aperti

* Banking del fix: la cartuccia non vede l'indirizzo VRAM, mentre `neo_cmc.v` lo usa. Che lo stesso
  stato si possa ricostruire dal solo flusso `PCK2B` non risulta dalle fonti che ho letto. Circa 28
  giochi originali dipendono da questo. Serve una cattura con analizzatore logico o lo schema del
  PRO-CT0/CMC.
* Metal Slug X (un gioco) e SBP (un bootleg) hanno protezioni non documentate.
* Tempi: ogni lettura di `$2xxxxx` va servita entro il ciclo del 68k (le linee `PWAIT`/`PDTACK` esistono).
* Ancora niente gira: il campo mapper del formato è l'aggancio, i moduli di gateware non esistono.

## 5. Ordine di lavoro proposto

1. Decifrature in fase di pacchetto in `tools/ngpk.py` (CMC, PCM2, SMA, KOF2002, PVC, KOF98), ciascuna
   provata contro l'output decifrato di MAME quando i set ROM sono disponibili.
2. Gateware: bank/RNG dell'SMA, RAM del PVC, sovrapposizione del KOF98 (moduli piccoli, provabili in simulazione).
3. Banking del fix layer, dopo una cattura del vero traffico PCK1B/PCK2B.
4. PRO-CT0 e Metal Slug X.
5. Bootleg su richiesta.
