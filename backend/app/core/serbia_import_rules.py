"""
serbia_import_rules.py
----------------------
Provjera podobnosti vozila za uvoz i registraciju u Srbiji.

Koristiti za:
  - listing kartice (brzi status)
  - detail stranicu (detaljna analiza)
  - kalkulator uvoza

Status vrijednosti:
  eligible        → Može uvoz u Srbiju
  needs_check     → Potrebna dodatna provjera
  not_recommended → Verovatno nije moguće / ne preporučuje se
  oldtimer        → Oldtimer izuzetak (30+ godina)
"""

from dataclasses import dataclass, field
from typing import Optional

CURRENT_YEAR = 2026


@dataclass
class SerbiaEligibilityResult:
    eligible_status: str          # eligible | needs_check | not_recommended | oldtimer
    label: str                    # Kratki label za UI
    emoji: str                    # 🟢 🟠 🔴 🟣
    reason: str                   # Objašnjenje
    warnings: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    carina_pct: float = 5.0       # Procenat carine (0 za EV)

    def to_dict(self) -> dict:
        return {
            "eligible_status": self.eligible_status,
            "label":           self.label,
            "emoji":           self.emoji,
            "reason":          self.reason,
            "warnings":        self.warnings,
            "missing_data":    self.missing_data,
            "carina_pct":      self.carina_pct,
        }


def check_serbia_eligibility(
    year:          Optional[int]   = None,
    fuel_type:     Optional[str]   = None,
    euro_standard: Optional[str]   = None,
    co2:           Optional[float] = None,
    engine_cc:     Optional[int]   = None,
) -> SerbiaEligibilityResult:
    """
    Provjeri da li vozilo može biti uvezeno i registrovano u Srbiji.

    Ulazni podaci:
        year          — godište (int, npr. 2019)
        fuel_type     — gorivo: 'diesel' | 'petrol' | 'electric' | 'hybrid' | 'lpg' | 'cng'
        euro_standard — Euro norma: 'Euro 4' | 'Euro 5' | 'Euro 6' itd. (opciono)
        co2           — CO₂ emisija g/km (opciono)
        engine_cc     — zapremina motora u cm³ (opciono)

    Vraća:
        SerbiaEligibilityResult
    """

    missing_data: list[str] = []
    warnings:     list[str] = []

    # ── 1. Električna vozila ──────────────────────────────────────────────────
    if fuel_type == "electric":
        return SerbiaEligibilityResult(
            eligible_status = "eligible",
            label           = "Može uvoz u Srbiju",
            emoji           = "🟢",
            reason          = "Električna vozila se uvoze bez carine u Srbiju (0% carina). "
                              "Potrebna je COC dokumentacija i tehnički pregled.",
            warnings        = [
                "Provjeri kompatibilnost punjača (tip 2 / CCS standard).",
                "Baterijska garancija može biti ograničena van EU.",
            ],
            carina_pct = 0.0,
        )

    # ── 2. Oldtimer izuzetak (30+ godina) ────────────────────────────────────
    if year:
        vehicle_age = CURRENT_YEAR - year
        if vehicle_age >= 30:
            return SerbiaEligibilityResult(
                eligible_status = "oldtimer",
                label           = "Oldtimer izuzetak",
                emoji           = "🟣",
                reason          = f"Vozilo ({year}) je starije od 30 godina — može se uvesti "
                                  f"kao oldtimer pod posebnim uslovima i uz posebnu registraciju.",
                warnings        = [
                    "Registracija kao oldtimer zahtijeva poseban tehnički pregled.",
                    "Godišnja kilometraža može biti ograničena za oldtimer tablice.",
                    "Provjeriti važeće propise MUP-a Srbije za oldtimer vozila.",
                ],
                carina_pct = 5.0,
            )

    # ── 3. Euro norma (ako je dostupna) ──────────────────────────────────────
    if euro_standard:
        euro_norm = euro_standard.lower().replace(" ", "").replace("-", "")
        if any(n in euro_norm for n in ["euro6", "euro5"]):
            return SerbiaEligibilityResult(
                eligible_status = "eligible",
                label           = "Može uvoz u Srbiju",
                emoji           = "🟢",
                reason          = f"Vozilo ispunjava {euro_standard} normu — nema ograničenja "
                                  f"za uvoz i registraciju u Srbiji.",
                warnings        = _standard_warnings(fuel_type),
                carina_pct      = 5.0,
            )
        elif "euro4" in euro_norm:
            return SerbiaEligibilityResult(
                eligible_status = "eligible",
                label           = "Može uvoz u Srbiju",
                emoji           = "🟢",
                reason          = f"Vozilo ispunjava Euro 4 normu — moguće je uvesti u Srbiju.",
                warnings        = _standard_warnings(fuel_type) + [
                    "Euro 4 je minimalna preporučena norma. Provjeri COC dokument.",
                ],
                carina_pct = 5.0,
            )
        elif "euro3" in euro_norm:
            return SerbiaEligibilityResult(
                eligible_status = "needs_check",
                label           = "Potrebna dodatna provjera",
                emoji           = "🟠",
                reason          = "Vozilo je Euro 3 norma — uvoz je moguć ali može biti "
                                  "otežan pri tehničkom pregledu i registraciji.",
                warnings        = [
                    "Euro 3 vozila mogu imati problem pri tehničkom pregledu.",
                    "Preporučuje se konsultacija sa carinskim agentem pre kupovine.",
                    "Provjeri da li vozilo zadovoljava lokalne emisione standarde.",
                ],
                carina_pct = 5.0,
            )
        else:
            return SerbiaEligibilityResult(
                eligible_status = "not_recommended",
                label           = "Verovatno nije moguće / ne preporučuje se",
                emoji           = "🔴",
                reason          = f"Vozilo ima {euro_standard} normu — uvoz u Srbiju je "
                                  f"vjerovatno nemoguć ili nepraktičan.",
                warnings        = [
                    "Stare emisione norme ne zadovoljavaju tehničke uslove.",
                    "Registracija ovakvog vozila u Srbiji je vrlo otežana.",
                ],
                carina_pct = 5.0,
            )

    # ── 4. Procjena na osnovu godišta (bez Euro norme) ───────────────────────
    if year:
        if year >= 2011:
            return SerbiaEligibilityResult(
                eligible_status = "eligible",
                label           = "Može uvoz u Srbiju",
                emoji           = "🟢",
                reason          = f"Vozilo ({year}) vjerovatno zadovoljava Euro 5 ili Euro 6 normu "
                                  f"— uvoz u Srbiju je moguć.",
                warnings        = _standard_warnings(fuel_type) + [
                    "Preporučuje se pribaviti COC dokument za potvrdu Euro norme.",
                ],
                missing_data = ["Euro norma nije navedena u oglasu"],
                carina_pct   = 5.0,
            )
        elif year >= 2006:
            return SerbiaEligibilityResult(
                eligible_status = "eligible",
                label           = "Može uvoz u Srbiju",
                emoji           = "🟢",
                reason          = f"Vozilo ({year}) vjerovatno zadovoljava Euro 4 normu.",
                warnings        = _standard_warnings(fuel_type) + [
                    "Provjeri COC dokument ili potvrdu proizvođača za Euro normu.",
                    "Euro 4 je minimalna preporučena norma za uvoz.",
                ],
                missing_data = ["Euro norma nije navedena u oglasu"],
                carina_pct   = 5.0,
            )
        elif year >= 2001:
            return SerbiaEligibilityResult(
                eligible_status = "needs_check",
                label           = "Potrebna dodatna provjera",
                emoji           = "🟠",
                reason          = f"Vozilo ({year}) vjerovatno je Euro 3 norma — uvoz je "
                                  f"moguć ali zahtijeva dodatnu provjeru dokumentacije.",
                warnings        = [
                    "Provjeri Euro normu u COC dokumentu prije kupovine.",
                    "Euro 3 vozila mogu imati poteškoće pri registraciji.",
                    "Konsultuj carinskog agenta ili MUP Srbije.",
                ],
                missing_data = ["Euro norma nije navedena u oglasu"],
                carina_pct   = 5.0,
            )
        else:
            return SerbiaEligibilityResult(
                eligible_status = "not_recommended",
                label           = "Verovatno nije moguće / ne preporučuje se",
                emoji           = "🔴",
                reason          = f"Vozilo ({year}) je vjerovatno Euro 1 ili Euro 2 norma "
                                  f"— uvoz u Srbiju nije preporučljiv.",
                warnings        = [
                    "Stara vozila teško prolaze tehnički pregled u Srbiji.",
                    "Razmotri oldtimer status ako je vozilo 30+ godina.",
                ],
                carina_pct = 5.0,
            )

    # ── 5. Nema dovoljno podataka ─────────────────────────────────────────────
    missing_data.append("Godište nije navedeno u oglasu")
    missing_data.append("Euro norma nije navedena u oglasu")

    return SerbiaEligibilityResult(
        eligible_status = "needs_check",
        label           = "Potrebna dodatna provjera",
        emoji           = "🟠",
        reason          = "Nedostaju ključni tehnički podaci za procjenu podobnosti uvoza.",
        warnings        = [
            "Prije kupovine obavezno provjeri Euro normu (COC dokument).",
            "Kontaktiraj prodavca za tehničke specifikacije.",
        ],
        missing_data = missing_data,
        carina_pct   = 5.0,
    )


def _standard_warnings(fuel_type: Optional[str]) -> list[str]:
    """Standardna upozorenja koja vrijede za većinu vozila."""
    base = [
        "Obavezno pribavi COC dokument ili potvrdu o tehničkim karakteristikama.",
        "Provjeri servisnu istoriju i stanje vozila prije kupovine.",
    ]
    if fuel_type == "diesel":
        base.append("Za dizel vozila provjeri stanje DPF filtera — zamjena je skupa.")
    return base
