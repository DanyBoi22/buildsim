# DistrictGenerator – Erkenntnisse zur Abbildung realer Gebäude

## 1. Was bedeutet `area` in DG?

`area` ist **nicht die Gebäudegrundfläche** sondern referenzierte Gesamtfläche von allen Wohnungen.

Bei den TABULA-Archetypen wird die angegebene Fläche mit **baujahrsabhängigen TABULA-Faktoren** in Dach-, Boden- und Wandflächen umgerechnet.

Für ein MFH gilt vereinfacht:

```text
Grundfläche_DG = area × Grundflächenfaktor
Dachfläche_DG  = area × Dachflächenfaktor
```

Beispiel MFH, Baujahr 1995–2001:

```text
Grundflächenfaktor = 0,33976
Dachflächenfaktor  = 0,33976
```

Bei einer realen Grundfläche von 130 m² könnte man daher theoretisch rückwärts rechnen:

```text
area_DG = 130 / 0,33976 ≈ 382,6 m²
```

Damit würde DG ungefähr 130 m² Grund- und Dachfläche erzeugen.

**Wichtig:** `area_DG` ist damit eine für die DG-Archetypgeometrie kalibrierte Eingangsgröße und nicht automatisch die reale Wohn-/Geschossfläche.

---

## 2. PV-Fläche

DG berechnet die PV-Leistung direkt aus der tabelarisch kalkulierten (`area_roof`) und den beiden PV-Nutzungsfaktoren:

```python
generation_PV[t] = area_roof * (1 - kappa_corr) * (
    eta_PV1[t] * SunRad1[0][t] * usageFactorPV1
    + eta_PV2[t] * SunRad2[0][t] * usageFactorPV2
)
```

Daraus folgt:

- PV-Fläche Seite 1 = `area_roof × f_PV1`
- PV-Fläche Seite 2 = `area_roof × f_PV2`
- Gesamt-PV-Fläche = `area_roof × (f_PV1 + f_PV2)`
- `f_PV1 + f_PV2` darf höchstens 1 sein.

### Beispiel

MFH, Baujahr 1995, `area = 520 m²`:

- TABULA-Dachfaktor = `0,33976`
- DG-Dachfläche = `520 × 0,33976 = 176,6752 m²`
- bei `f_PV1 = 0,4` und `f_PV2 = 0,4`:
  - PV Seite 1 = 70,67 m²
  - PV Seite 2 = 70,67 m²
  - Gesamt-PV = 141,34 m²

Bei einer realen Grundfläche von 130 m² kann man die reale PV geignete Fläche von 100 m² durch die Faktoren `f_PV1` und `f_PV2` angeben: 

```text
100 = 130 * (f_PV1 + f_PV2)
```

Somit ähnlich wie bei `area_DG` kann man die nötigen Faktoren für die PV ebenfalls rückwärts rechnen.

```text
f_PV1 + f_PV2 = 100 / 130 ≈ 0.77
```

Also die Summe von `f_PV1` und `f_PV2` soll 0.77 ergeben damit die PV_Fläche 100 m² beträgt. Da bei MFH das Dach meistens flach ist, genügt `f_PV1` auf 0.77 und `f_PV2` auf 0 zu setzten.  

---

## 3. Was wird von DG zufällig erzeugt?

Ohne den Quelcode zu verändern werden unter anderem folgende Werte statistisch bzw. zufällig erzeugt:

- **Anzahl der Geschosse** bei MFH/AB
- **Anzahl der Wohnungen** bei MFH/AB
- **Bewohnerzahl pro Wohnung**

Die Wohnungszahl wird über eine zufällige statistische Wohnungsgrößenklasse bestimmt. Die Bewohnerzahl wird anschließend ebenfalls statistisch pro Wohnung erzeugt.

---

## 4. Welche realen GIS-Daten können verwendet werden?

### Ohne den Quellcode von DG zu verändern kann man folgende Daten verwenden:

- Gebäudetyp
- Baujahr / Baualtersklasse
- reale Grundfläche / Gebäude-Footprint
- reale Dachfläche
- Geignete PV-Fläche
- ggf. Dachausrichtung

Die reale Grundfläche kann dabei für DG über die bekannten TABULA-Faktoren in eine passende `area_DG` zurückgerechnet werden.

Die reale Dach-/PV-Fläche kann anschließend über passende `f_PV1` / `f_PV2` in die vorhandene DG-PV-Berechnung eingebracht werden.

Der Vorteil ist, dass die Archetypen nicht verändert werden und den tabelarischen Daten entsprechen.

Nachteil ist, dass Berechnungen z.B. von Wärmebedarf sich auf komplett unterschiedliche Gebäudegeometrie basieren und somit wahrscheinlich stark von der Realität abweichen. 

### Mit Quellcode Veränderungen von DG können die folgenden Daten übernommen werden:

- Geschosszahl
- Gebäudehöhe

Somit kann DG die echte Gebäudegeometrie übernehmen und basierend darauf die Berechnungen durchführen. Allerdings kann so ein Eingriff unbekannte Folgen für das gesamte Pipeline haben und unerwartete Probleme und Unzustimmigkeiten verursachen. 

### Nicht zuverlässig allein aus den GIS-Daten ableitbar:

- tatsächliche Wohnungszahl
- tatsächliche Bewohnerzahl
- Heizsystem
- Warmwassersystem
- tatsächlicher Sanierungszustand

Alle diese Daten können nur angenommen werden. 

ToDo:
- Wrapper mit Datenaufbereitung für DG
- 1 CSV pro Gebäude mit Profilen
- Außen Temperatur pro Zeiteinheit raussuchen
- Kleine präsi DG + GIS Karten