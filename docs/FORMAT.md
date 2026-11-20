# Formato NGPK v1 (Neo Geo Pack)

Un file `.ngpk` contiene **tutte le ROM di un gioco** in un ordine di byte
canonico, indipendente dal gioco e dall'hardware. Tutto il lavoro specifico del
gioco (swap, interleave, concatenazione) lo fa il packer sul PC; il firmware
della cartuccia si limita a copiare le regioni in SDRAM. Aggiungere un gioco
significa scrivere una *ricetta* JSON, non toccare firmware o gateware.

Tutti i campi interi sono **little-endian**. I dati delle regioni sono allineati
a 512 byte (un settore SD) e riempiti con zeri fino al settore successivo.

## Header (64 byte, offset 0)

| Off | Dim | Campo        | Note |
|----:|----:|--------------|------|
| 0   | 4   | magic        | `"NGPK"` |
| 4   | 2   | version      | 1 |
| 6   | 2   | hdr_size     | 64 |
| 8   | 4   | flags        | 0, riservato |
| 12  | 4   | nregions     | 1..8 |
| 16  | 2   | mapper       | 0 = `plain` (vedi sotto) |
| 18  | 2   | mapper_arg   | 0 per `plain`; 1 riservato per P singola da 2 MiB |
| 20  | 2   | ngh          | numero NGH, 0 per homebrew |
| 22  | 2   | riservato    | 0 |
| 24  | 32  | title        | UTF-8, riempito con zeri (max 31 byte) |
| 56  | 4   | hdr_crc      | CRC-32 di header (con questo campo a 0) + tabella regioni |
| 60  | 4   | riservato    | 0 |

## Tabella regioni (nregions × 32 byte, offset 64)

| Off | Dim | Campo    | Note |
|----:|----:|----------|------|
| 0   | 1   | type     | 1=P 2=C 3=S 4=M 5=V 6=VB |
| 1   | 1   | flags    | bit 0-3: layout dei dati (vedi "Layout delle regioni"); bit 4-7 riservati, 0 |
| 2   | 2   | riservato| 0 |
| 4   | 4   | size     | byte di dati reali (senza padding) |
| 8   | 4   | file_off | offset nel file, multiplo di 512 |
| 12  | 4   | crc32    | CRC-32 (zlib) dei `size` byte |
| 16  | 16  | riservato| 0 |

Regole di validità (il parser C le verifica tutte; il packer le rispetta per
costruzione): una sola
regione per tipo; `size > 0`; `file_off` multiplo di 512 e non prima della fine
della tabella (arrotondata a 512); regioni non sovrapposte; CRC dell'header
corretto. Il packer scrive le regioni nell'ordine P, S, M, V, VB, C.

## Contenuto canonico delle regioni

| Regione | Contenuto nel pacchetto |
|---------|-------------------------|
| **P**   | Programma 68k in **ordine di byte 68k** (big-endian). I dump in stile MAME sono word-swapped, quindi la ricetta usa `swap16`. Il packer controlla che a 0x100 ci sia `"NEO-GEO"`: se manca, quasi sempre lo swap è sbagliato. I primi 1 MiB sono P1 (68k `$000000`); il resto è P2, in banchi da 1 MiB visibili nella finestra `$200000-$2FFFFF`. |
| **C**   | Tile degli sprite. Per ogni coppia di chip `(c_dispari, c_pari)` i byte sono alternati: `out[0::2] = c1`, `out[1::2] = c2`; le coppie sono poi concatenate in ordine (c1/c2, c3/c4, ...). È lo stesso layout che usa MAME. Un tile 16×16 a 4 bpp occupa 128 byte, quindi `size` è multiplo di 128. |
| **S**   | Tile del fix layer, dump grezzo. |
| **M**   | Codice Z80 (M1), dump grezzo. |
| **V**   | Campioni ADPCM, file concatenati in ordine (v1, v2, ...). Usata sia da ADPCM-A sia da ADPCM-B. |
| **VB**  | Solo per giochi con ROM ADPCM-B separata (titoli più vecchi). Il formato la prevede; il profilo 64M non ha uno slot per lei e rifiuta questi giochi. |

## Layout delle regioni (flags, bit 0-3)

Solo C e S hanno un layout alternativo; per le altre regioni il valore è 0.

* `0 = canonical`: ordine MAME, come descritto sopra.
* `1 = sdram1`: riordino fatto dal packer perché l'FPGA legga una riga di tile
  con un solo burst sequenziale. È il layout richiesto dal profilo `ngsd-64M`:
  il loader rifiuta con `NGPK_E_LAYOUT` un pacchetto con layout diverso, senza
  toccare l'hardware. Il comando `pack` usa `sdram1` per default
  (`--layout canonical` per l'altro); `unpack --canonical` ripristina l'ordine MAME.

**C, `sdram1`.** Per il tile `t` e la riga `y` (0..15) ci sono 8 byte a
`t*128 + y*8`: prima i 4 byte della metà a offset canonico `+0x40` (pixel 0-7
sullo schermo, senza flip, selezionata con `CA4 = 0`), poi i 4 byte della metà
a `+0x00` (pixel 8-15). Ogni gruppo di 4 byte `[b0 b1 b2 b3]` canonici è
riordinato in `[b0 b2 b1 b3]`, così che il byte `k` porti il bitplane `k`.

**S, `sdram1`.** Per il tile `t` e la riga `r` (0..7) ci sono 4 byte a
`t*32 + r*4`, presi dall'ordine canonico agli offset `+0x10+r, +0x18+r,
+0x00+r, +0x08+r`: ogni byte contiene due pixel adiacenti (nibble basso a
sinistra).

`tests/test_ngpk.py` (`TestLayout`) confronta ogni pixel decodificato dal layout
`sdram1` con un modello della decodifica canonica scritto seguendo
`geo_lspc_tpix` e la routine del fix layer di Geolith.

**Ipotesi non verificata su hardware.** La corrispondenza `CA4 = 0` ↔ metà
`+0x40` e l'assegnazione byte-lane ↔ bitplane sono dedotte dai sorgenti di
Geolith e NeoGeo_MiSTer, non misurate su una cartuccia. Se il gateware mostrasse
le metà scambiate basta cambiare una costante nel packer.

Il formato descrive i **dati**; come i byte di C vengano distribuiti sulle linee
`CR0-CR31` e come vengano usati dal serializzatore è compito del gateware.

## Mapper

Il campo `mapper` indica quale logica da cartuccia serve al gioco.

* `0 = plain`: solo il latch di bank-switching della P (scrittura nella finestra
  `$200000-$2FFFFF`, bit D0/D1 verso A20/A21 della P2, azzerato al reset) e la
  logica base della cartuccia AES. È l'unico mapper supportato oggi.
* Valori riservati per il futuro: protezioni e cifrature (SMA, PCM2, CMC, PVC...).
  Packer e loader rifiutano mapper sconosciuti invece di caricare un gioco che
  non funzionerebbe.

## Ricetta JSON (input del packer)

```json
{
  "title": "Nome del gioco",
  "ngh": 87,
  "mapper": "plain",
  "base_dir": ".",
  "regions": {
    "P": [{"op": "swap16", "files": ["a.p1", "b.p2"]}],
    "C": [{"op": "interleave8", "files": ["c1.bin", "c2.bin"]},
          {"op": "interleave8", "files": ["c3.bin", "c4.bin"]}],
    "S": [{"files": ["s1.bin"]}],
    "M": [{"files": ["m1.bin"]}],
    "V": [{"files": ["v1.bin", "v2.bin"]}]
  }
}
```

Operazioni per segmento (i segmenti di una regione vengono concatenati):

* `concat` (default): file concatenati così come sono.
* `swap16`: ogni file viene invertito a coppie di byte, poi concatenato.
* `interleave8`: esattamente due file `[pari, dispari]` della stessa lunghezza,
  byte alternati.

Ricette incluse: `recipes/samsho3.json` e `recipes/samsho3_fswords.json`
(stesso gioco, due versioni del programma: dimostrano che cambiare gioco o
revisione vuol dire cambiare solo la ricetta) e `recipes/spf2ng.json`, il gioco
del progetto.
