# Avvio: come la console vede la cartuccia mentre la SD si carica

Il problema: il BIOS legge la cartuccia subito all'accensione, ma copiare
decine di MiB dalla microSD alla SDRAM richiede secondi. Questo documento
separa ciò che è documentato da ciò che è dedotto, e descrive la soluzione
scelta (implementata e simulata, **non provata su una console**).

## 1. Cosa si sa

**Segnali di attesa (PROG).** `ROMWAIT`, `PWAIT0/1` e `PDTACK` sono pin che la
cartuccia può pilotare verso la console. Dal modello del core NeoGeo_MiSTer
(`rtl/io/c1_wait.v`, letto per capire il comportamento, non copiato):

* `ROMWAIT` attivo (basso) aggiunge **un numero fisso** di stati di attesa
  agli accessi alla zona ROM del 68k; `PWAIT0/1` fanno lo stesso (1 o 2 stati,
  a seconda della combinazione) per la zona porta. L'attesa è contata dal chip
  della console: non esiste un'attesa a durata arbitraria.
* `PDTACK` nel modello è commentato, con l'avvertenza che se tenuto a massa
  "potrebbe bloccare la CPU": il core lo tiene inattivo. La sua funzione reale
  non è documentata né verificata.
* In altre parole: **questi pin non servono per tenere ferma la console per
  secondi**. Servono per aggiungere uno stato di attesa fisso quando la ROM è
  lenta, ed è quello che ci serve per la P servita dalla SDRAM (il core MiSTer
  inserisce un wait state anche lui).

**Intestazione e BIOS** (wiki neogeodev, pagina *68k program header*): il BIOS
riconosce la cartuccia dalla stringa `NEO-GEO` a `$100` e da un secondo codice
(puntatore a `$182`, il "codice di sicurezza"). `$114` dice se il logo lo
disegna il BIOS (0), il gioco (1) o nessuno (2). `$122` è un `JMP` alla
subroutine USER, che il BIOS **raggiunge con un salto** e legge la richiesta in
`BIOS_USER_REQUEST` (`$10FDAE`: 0 init, 1 logo, 2 demo, 3 titolo). La USER deve
finire con un salto a `SYSTEM_RETURN` (`$C00444`); durante la richiesta 0 gli
interrupt sono disattivati. Punto di ingresso del BIOS: `$C00402`.

**Antecedente.** Esiste in commercio una cartuccia AES con microSD (NeoSD, di
Stone Age Gamer). Dal suo manuale: al primo avvio la console parte da un menu
mostrato dalla cartuccia; la scelta di un gioco lo carica nella memoria interna
e la console **si riavvia** nel gioco; se l'intestazione non viene riconosciuta
dal BIOS la console mostra una schermata a reticolo (crosshatch). Non conosco
il suo funzionamento interno, ma conferma che l'approccio "la cartuccia serve
un programma proprio, poi riavvia la console sul gioco" funziona su AES.

## 2. Scelta: stub di avvio servito dall'FPGA

1. **Accensione.** L'FPGA serve al 68k un'immagine di avvio da 1 KiB in RAM
   interna (`ng_boot.v`): all'inizio l'immagine di default scritta nella
   configurazione, poi quella costruita dall'MCU.
2. **L'immagine** (`tools/mkstub.py`, `firmware/ngsd_boot.c`) è l'intestazione
   del gioco stesso (primi 512 byte della P: vettori, `NEO-GEO`, codice di
   sicurezza), con `$114 = 2` (nessun logo) e il `JMP` di `$122` puntato allo
   stub a `$200`, più il programma `boot/stub.S` (60 byte) e un flag "pronto" a
   `$3FE`. Il codice di sicurezza non è nel repo: arriva dal gioco dell'utente.
3. **Lo stub** (a ogni ingresso in USER): se il flag è 0 salta a `SYSTEM_RETURN`
   senza fare altro; se è 1 copia una routine di 24 byte nella RAM di lavoro
   (`$100100`), la esegue, scrive la parola magica `$A5A5` a `$2FFFF0`, imposta
   lo stack e salta a `$C00402`: il BIOS riparte e questa volta trova il gioco.
4. **MCU** (`ngsd_load`): imposta `CTRL.STUB`, scrive l'immagine nella boot RAM,
   copia le regioni in SDRAM con i CRC, programma `SIZE_x`/`ADDR_x`, imposta
   `CTRL.RUN|STUB` e scrive il flag. Se qualcosa fallisce il flag resta 0 e
   `RUN` non viene mai impostato: la console resta nello stub (oggi senza
   messaggio d'errore).
5. **FPGA** (`ng_pbank.v`): in modalità stub, le letture di P1 sotto 1 KiB
   vengono dalla boot RAM; il resto, e tutta la finestra banchi, dalla SDRAM.
   La scrittura `$A5A5` a `$2FFFF0` azzera `STUB` **senza toccare il latch di
   bank** (verificato in simulazione) e da lì in poi tutta la P viene dalla SDRAM.

Esiste un'alternativa senza stub (lasciare la console in attesa con un pin):
scartata per quanto detto sopra sui pin di attesa.

## 3. Cosa è stato verificato

* Il programma si assembla (binutils m68k) e il disassemblato corrisponde allo
  schema sopra; il firmware C e `mkstub.py` producono la stessa immagine
  (verificato dal test del loader).
* Simulazione dell'intero percorso: immagine servita dalla boot RAM, flag 0 →
  1, letture sopra 1 KiB dalla SDRAM durante la modalità stub, scrittura
  magica, passaggio al gioco, latch di bank mantenuto (`test_system.py`).
* Il loader controlla che con un errore (profilo, CRC, layout) il flag non
  venga mai scritto e `RUN` non venga mai impostato.

## 4. Cosa NON è verificato (da provare su hardware o in emulatore)

* Che il BIOS AES richiami USER con continuità finché il flag è 0, e che
  chiudere ogni chiamata con `SYSTEM_RETURN` non faccia scattare il watchdog.
* Che il riavvio con `jmp $C00402` da dentro USER (stack reimpostato a
  `$10F300`, RAM `$100100` usata come trampolino) sia equivalente a un avvio a
  freddo: stato di LSPC, Z80, backup RAM, registri di sistema. L'alternativa
  è azionare davvero `RESET` (pin 33 del PROG, direzione non verificata) o una
  `reset` del 68k.
* Quanto tempo passa dall'accensione al primo controllo dell'intestazione: se
  è più breve dell'avvio dell'FPGA (configurazione) la console potrebbe vedere
  la cartuccia assente. `BOOT_HEX` precarica l'immagine di default nella
  configurazione ma questo va misurato.
* Che i giochi con `$114` diverso da 2 e NGH `0` (usato dagli homebrew:
  `spf2ng` ha `0x0539`) siano accettati dal BIOS: il wiki dice che `0000` è
  vietato.
* `ROMWAIT` permanente (1 stato di attesa) per coprire la latenza della SDRAM
  sulle letture di P: il margine reale è da misurare.

## 5. Come provarlo senza cartuccia

`python3 tools/mkstub.py gioco.p1 --swap16 -o boot.bin --ready` produce
l'immagine con il flag a 1. Il suo effetto su una console vera o in emulatore
si vede solo se la P viene servita da quella immagine; in un emulatore come
Geolith (con un BIOS legittimo) si può caricare un P1 da 1 MiB che contiene
quell'immagine in testa: dovrebbe avviarsi, passare dallo stub e riavviare in
loop, il che dimostrerebbe il percorso BIOS → USER → trampolino → riavvio fino
alla scrittura magica (che in emulatore non ha effetto).
