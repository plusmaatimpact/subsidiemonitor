# Plusmaat Subsidiemonitor

Website met de subsidiemonitor van Plusmaat Impact: een overzicht van alle gemeenten, een dashboard per gemeente en een Dataloket om gegevens aan te leveren. De site draait gratis op GitHub Pages en werkt zichzelf bij zodra je een ingevuld Excel-sjabloon uploadt.

## Wat er in deze map zit

| Bestand of map | Wat het is |
|---|---|
| `index.html` | Hoofdpagina: alle gemeenten, vergelijking en duiding, vergelijkbare gemeenten |
| `gemeente.html` | Dashboard van één gemeente, bijvoorbeeld `gemeente.html?g=Delft` |
| `dataloket.html` | Formats, Excel-sjablonen en controle van aan te leveren bestanden |
| `assets/` | Huisstijl (`plusmaat.css`), de dashboardruntime (`dash.js`) en instellingen (`config.js`) |
| `data/` | Alle gegevens als JSON-bestanden; de site leest alleen hieruit |
| `aanleveringen/` | Hier upload je ingevulde sjablonen; ze worden automatisch verwerkt |
| `scripts/verwerk.py` | Controleert en verwerkt aanleveringen |
| `scripts/haal_cbs.py` | Haalt Iv3-lasten en inwoners op bij het CBS |
| `.github/workflows/` | De twee automatische acties die de scripts draaien |

## Eenmalig: de site online zetten

Je hebt alleen een gratis GitHub-account nodig. Alles kan via de website van GitHub; je hoeft niets te installeren.

1. **Maak een account** op [github.com](https://github.com) als je dat nog niet hebt.
2. **Maak een repository.** Klik rechtsboven op **+** → **New repository**.
   - Naam: bijvoorbeeld `subsidiemonitor`.
   - Kies **Public**. GitHub Pages is gratis voor openbare repositories. Wil je een privé-repository, dan heb je GitHub Pro of een organisatie-abonnement nodig; de site zelf is dan nog steeds openbaar.
   - Klik op **Create repository**.
3. **Upload de bestanden.** Klik op **uploading an existing file**.
   - Pak de zip uit op je computer.
   - Sleep de **inhoud** van de map (niet de map zelf) naar het uploadvak, inclusief de verborgen map `.github` en het bestand `.nojekyll`.
     - Mac: druk in Finder op Cmd+Shift+. om verborgen bestanden te zien.
     - Windows: zet in Verkenner **Beeld → Verborgen items** aan.
   - Klik op **Commit changes**.
   - Komt de map `.github` niet mee? Maak dan in GitHub zelf twee bestanden aan via **Add file → Create new file**: `.github/workflows/verwerk-aanleveringen.yml` en `.github/workflows/vernieuw-cbs.yml`. Plak er de inhoud uit de zip in.
4. **Zet GitHub Pages aan.**
   - Ga naar **Settings → Pages**.
   - Kies bij **Source** voor **Deploy from a branch**.
   - Kies branch **main** en map **/ (root)**, en klik op **Save**.
   - Na een minuut of twee staat de site op `https://<gebruikersnaam>.github.io/subsidiemonitor/`.
5. **Geef de automatische acties schrijfrechten.**
   - Ga naar **Settings → Actions → General**.
   - Kies onder **Workflow permissions** voor **Read and write permissions** en klik op **Save**.
6. **Stel de uploadknop in.**
   - Open `assets/config.js` en klik op het potloodje.
   - Vervang `GEBRUIKER/subsidiemonitor` door je eigen gebruikersnaam en repositorynaam, bijvoorbeeld `plusmaat/subsidiemonitor`.
   - Klik op **Commit changes**.

### Eigen domein (bijvoorbeeld monitor.plusmaat.nl)

1. **Bij GitHub:** ga naar **Settings → Pages → Custom domain**, vul `monitor.plusmaat.nl` in en klik op **Save**.
2. **Bij je domeinbeheerder:** maak een **CNAME**-record aan van `monitor` naar `<gebruikersnaam>.github.io`.
3. **Beveiliging:** zet na een paar minuten **Enforce HTTPS** aan.

## Gegevens bijwerken

1. Ga op de site naar **Dataloket** en kies de soort gegevens.
2. Klik op **Download Excel-sjabloon** en vul het tabblad **Gegevens** in.
3. Sleep het ingevulde bestand in het controlevak op de pagina. Je ziet meteen of er fouten in staan. Het bestand blijft dan nog op je eigen computer.
4. Geef het bestand een naam die begint met de soort, bijvoorbeeld `subsidieposten-delft-2027.xlsx`.
5. Klik op **Open uploadpagina op GitHub**. Je kunt ook in de repository naar de map `aanleveringen` gaan en **Add file → Upload files** kiezen.
6. Sleep het bestand erin, kies **Commit directly to the main branch** en klik op **Commit changes**.
7. De actie **Verwerk aanleveringen** start vanzelf. Onder het tabblad **Actions** zie je hoe het gaat.
   - Na 1 à 2 minuten is de data bijgewerkt.
   - Na nog een minuut is ook de site bijgewerkt.
   - Het resultaat staat onderaan het Dataloket onder **Verwerkte aanleveringen**.
8. Bevat het bestand toch fouten, dan wordt het naar `aanleveringen/afgewezen/` verplaatst en verandert er niets. De reden staat in het logboek.

| Bestandsnaam begint met | Wat er gebeurt |
|---|---|
| `subsidieposten` | Vervangt alle posten van dezelfde gemeente en hetzelfde jaar |
| `gemeentegegevens` | Werkt een gemeente bij of voegt een nieuwe toe; die krijgt meteen een kaart en een dashboard |
| `impactstudies` | Werkt een studie bij of voegt er een toe; de instelling moet in de posten staan |
| `vergelijkingsgemeenten` | Vervangt de vergelijkingsgemeenten van een gemeente |
| `centrumregios` | Werkt een centrumregio bij |
| `studievormen` | Vervangt de prijslijst in het aanvraagpaneel |
| `verwijderingen` | Verwijdert een gemeente, de posten of studie van één instelling, een vergelijkingsgemeente of een centrumregio |

Upload bij voorkeur **één bestand per keer**. Lever je een nieuwe gemeente aan? Doe dan eerst de gemeentegegevens, daarna de subsidieposten.

### Een wijziging terugdraaien

Elke verwerking is een aparte wijziging (commit) in GitHub.

1. Ga naar het tabblad **Code** en klik op **Commits**.
2. Open de commit **Aanleveringen verwerkt** die je ongedaan wilt maken.
3. Klik rechtsboven op de drie puntjes en kies **Revert**. Lukt dat niet in de browser, gebruik dan GitHub Desktop: rechtsklik op de commit en kies **Revert changes in commit**.

Ook een verwijdering is zo terug te halen.

### CBS-gegevens vernieuwen

De lasten per taakveld (Iv3), de toegerekende overhead en de inwonertallen worden opgehaald bij het CBS:
- **Automatisch:** op 1 maart en 1 september.
- **Handmatig:** via **Actions → Vernieuw CBS-gegevens → Run workflow**. Laat het jaar leeg voor de nieuwste begroting.

Doe dit ook nadat je een nieuwe gemeente of een nieuwe vergelijkingsgemeente hebt toegevoegd.

## Hoe de vergelijking werkt

- **Vergelijkingsgemeenten:** gekozen met AMIGO (VNG / Waar staat je gemeente) op integraal profiel, sociaal domein en SES, aangevuld met omvang en centrumfunctie.
- **Maatstaf:** de Iv3-lasten per taakveldcluster per inwoner (CBS, begroting). Daarin staan mutaties in reserves, financiële transacties en interne verrekeningen niet.
- **Correctie 1, overhead:** taakveld 0.4 wordt naar rato van de directe lasten over de taakvelden verdeeld. Zo maakt het niet uit of een gemeente een taak zelf uitvoert of uitbesteedt.
- **Correctie 2, centrumtaken:** opvang en beschermd wonen (taakvelden 6.811 en 6.812) worden per inwoner van de centrumregio berekend.
- **Let op:** de subsidielijsten zelf verschillen per gemeente in reikwijdte. Vergelijk gemeenten daarom op de Iv3-tabbladen, niet op de subsidietotalen.

## Wat de site niet doet

- **Geen inlog.** Alles op de site is openbaar. Zet er dus geen vertrouwelijke gegevens in, zoals offertes of persoonsgegevens. Afschermen kan met bijvoorbeeld Cloudflare Access voor het domein.
- **Aanvraagknop:** de knop "Aanvraag opstellen in e-mail" opent een e-mail zonder ontvanger. Wil je een vast adres? Zoek in `gemeente.html` naar `mailto:?subject` en zet je adres direct achter `mailto:`.
- **Duidingstabel:** de tabel "Subsidie per inwoner per domein" op het tabblad Vergelijking en duiding gaat vast over Rotterdam, Den Haag en Delft. Een nieuwe gemeente verschijnt wel op de kaarten, in de grafieken en op het tabblad Vergelijkbare gemeenten.

## Bronnen

- Gemeentebegrotingen: Rotterdam 2027, Den Haag en Delft (jaar aangenomen als 2027).
- CBS: Gemeenten onbewerkte Iv3-data (CC BY 4.0) en Bevolkingsontwikkeling per maand (37230ned).
- VNG / Waar staat je gemeente: AMIGO.
- AlleCijfers: demografie.
