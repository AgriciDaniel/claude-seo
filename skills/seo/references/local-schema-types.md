<!-- Updated: 2026-03-23 -->
# Local Schema Types & Industry-Specific Patterns (March 2026)

Schema is NOT a direct ranking factor (Confirmed: John Mueller, Gary Illyes). It indirectly impacts visibility through rich results (43% CTR increase, Webstix case study), better entity understanding, and AI search features.

---

## Google-Supported LocalBusiness Subtypes

### Food & Dining

| Schema Type | Use For |
|-------------|---------|
| `Restaurant` | Full-service restaurants |
| `CafeOrCoffeeShop` | Coffee shops, cafes |
| `BarOrPub` | Bars, pubs, taverns |
| `Bakery` | Bakeries |
| `FastFoodRestaurant` | Fast food, quick service |
| `IceCreamShop` | Ice cream, frozen yogurt |
| `FoodEstablishment` | Generic food (avoid if specific subtype exists) |

### Healthcare

| Schema Type | Use For |
|-------------|---------|
| `MedicalClinic` | Clinics, urgent care (eligible for rich results) |
| `Hospital` | Hospitals (eligible for rich results) |
| `Dentist` | Dental offices (eligible for rich results) |
| `Physician` | Individual doctor pages (use with Person) |
| `Optician` | Eye care, optical shops |
| `Pharmacy` | Pharmacies |
| `MedicalBusiness` | Generic medical (avoid if specific subtype exists) |

### Legal

| Schema Type | Use For | Notes |
|-------------|---------|-------|
| `LegalService` | Law firms, legal practices | **Correct type** |
| ~~`Attorney`~~ | ~~Individual attorneys~~ | **DEPRECATED by Schema.org. Use `LegalService` + `Person`** |

### Home Services

| Schema Type | Use For |
|-------------|---------|
| `Plumber` | Plumbing services |
| `Electrician` | Electrical services |
| `HVACBusiness` | Heating, ventilation, AC |
| `RoofingContractor` | Roofing |
| `GeneralContractor` | General contracting |
| `HousePainter` | Painting services |
| `Locksmith` | Locksmith services |
| `MovingCompany` | Moving services |
| `HomeAndConstructionBusiness` | Generic (avoid if specific subtype exists) |

### Real Estate

| Schema Type | Use For | Notes |
|-------------|---------|-------|
| `RealEstateAgent` | Both agents AND brokerages | No `RealEstateBrokerage` type exists |

### Automotive

| Schema Type | Use For |
|-------------|---------|
| `AutoDealer` | Sales departments |
| `AutoRepair` | Service departments |
| `AutoPartsStore` | Parts departments |

### Other Common Local Types

`AnimalShelter`, `BeautySalon`, `ChildCare`, `DaySpa`, `DryCleaningOrLaundry`, `EmergencyService`, `EmploymentAgency`, `EntertainmentBusiness`, `FinancialService`, `FireStation`, `FurnitureStore`, `GasStation`, `GolfCourse`, `GovernmentOffice`, `HealthClub`, `Hotel`, `InsuranceAgency`, `Library`, `LodgingBusiness`, `NightClub`, `PetStore`, `PoliceStation`, `PostOffice`, `RecyclingCenter`, `ShoppingCenter`, `SkiResort`, `SportsActivityLocation`, `Store`, `TouristInformationCenter`, `TravelAgency`, `VeterinaryCare`

---

## Required vs Recommended Properties

Per Google Developers documentation (updated December 10, 2025, Confirmed).

### Required (Minimum)

| Property | Type | Notes |
|----------|------|-------|
| `name` | Text | Business name, must match GBP exactly |
| `address` | PostalAddress | With streetAddress, addressLocality, addressRegion, postalCode |

### Recommended

| Property | Type | Notes |
|----------|------|-------|
| `aggregateRating` | AggregateRating | Rating summary with reviewCount |
| `geo` | GeoCoordinates | **Minimum 5 decimal places** (Confirmed, ~1.1m accuracy) |
| `openingHoursSpecification` | OpeningHoursSpecification | Standard, late-night, 24h, seasonal |
| `telephone` | Text | Must match GBP and page NAP |
| `url` | URL | Canonical URL for this location |
| `priceRange` | Text | Under 100 characters |
| `image` | URL | Business photo |
| `review` | Review | Individual reviews |
| `department` | LocalBusiness | For nested departments (auto dealers) |
| `menu` | URL or Menu | Restaurants only |
| `servesCuisine` | Text | Restaurants only |

### SAB-Specific

| Property | Type | Notes |
|----------|------|-------|
| `areaServed` | Place/GeoShape | NOT in Google's official recommended list but supported by Schema.org. Industry-recommended for SABs. Use named cities with `sameAs` links to Wikipedia/Wikidata. |

---

## Industry-Specific Schema Patterns

### Restaurant
```
Restaurant (or specific subtype)
  + Menu > MenuSection > MenuItem (name, price, nutrition, suitableForDiet)
  + ReserveAction (booking capabilities)
  + OrderAction (takeout/delivery)
  + servesCuisine, acceptsReservations
```
Note: Google Food Ordering (GFO) direct checkout discontinued June 2024. "Order Online" button now redirects to third-party platforms.

### Healthcare
```
MedicalClinic (or Hospital, Dentist)
  + Physician pages: Person + medicalSpecialty + hospitalAffiliation + hasCredential
  + MedicalSpecialty (helps match "hip replacement surgery" to relevant pages)
  + sameAs: link to NPI Registry entry and medical board page
```
**HIPAA constraint**: Cannot confirm/deny reviewer is a patient in review responses. Fine precedent: $30,000 (Manasa Health Center, 2023).

### Legal
```
LegalService (NOT Attorney -- deprecated)
  + Person on attorney bio pages: jobTitle, worksFor, alumniOf, hasCredential (bar admissions)
  + makesOffer > Service (one per practice area)
  + Practitioner GBP: unique phone per attorney, not sole lawyer at firm
```
Note: Reviews follow practitioner listing when attorney changes firms.

### Home Services
```
Specific subtype (Plumber, Electrician, etc.)
  + areaServed: named cities with sameAs to Wikipedia/Wikidata
  + Service on individual service pages, linked via provider
  + hasOfferCatalog for service listings
```
**SAB note**: Service area in GBP does NOT currently impact rankings -- rankings based on verification address (Sterling Sky, March 2025).

### Real Estate
```
RealEstateAgent (for both agent and brokerage)
  + Person on agent pages: memberOf (brokerage), credentials
  + RealEstateListing + SingleFamilyResidence/Apartment + Offer (pricing)
  + Event for open houses with organizing agent
```
Note: No `RealEstateBrokerage` type exists on Schema.org.

### Automotive
```
AutoDealer (sales)
  + Car/Vehicle: VIN, mileage, fuelType, vehicleTransmission
  + Offer: price, priceCurrency, availability
  + Separate GBP: AutoRepair (service), AutoPartsStore (parts)
```
**VehicleListing deprecated June 12, 2025** (Confirmed). Use Car + Offer instead. Feed-based Vehicle Listings via Google Merchant Center still functional.

---

## Industry-Specific Citation Sources

### Restaurant
Yelp, TripAdvisor (1B+ reviews), OpenTable (DA + bookings), DoorDash, UberEats, Grubhub, Foursquare (powers Apple Maps, Uber)

### Healthcare
Healthgrades (50% of Americans who see a doctor visit), Zocdoc (booking + lead gen), WebMD physician directory (high DA), Vitals, Doximity (80% of US physicians), NPI Registry (entity verification source of truth), state medical board directories

### Legal
FindLaw (DA~91, dofollow), Martindale-Hubbell (DA~84, peer review since 1868), Avvo (1-10 ratings, auto-created from bar data), Justia (DA~70, free profiles), Super Lawyers (top 5%, selection-based), state bar directories (entity verification)

Note: Internet Brands (KKR) owns Avvo + Martindale + Lawyers.com + Nolo. Thomson Reuters owns FindLaw + Super Lawyers + LawInfo.

### Home Services
Thumbtack ($400M revenue 2024, integrations with ChatGPT/Alexa/Zillow), BBB, Nextdoor, Yelp. **Declining**: Angi (revenue -30% from 2022 peak), Porch (pivoted to insurance), Houzz (pivoted to SaaS)

### Real Estate
Zillow (44% of all RE search traffic, integrated into ChatGPT Oct 2025), Homes.com (#2, overtook Realtor.com, 100M monthly visitors), Realtor.com, Redfin (acquired by Rocket Companies Mar 2025), local MLS sites

### Automotive
Cars.com, AutoTrader, CarGurus, DealerRater (reviews syndicate to Cars.com + OEM sites, supports salesperson ratings), Edmunds, Kelley Blue Book (pricing authority), OEM manufacturer dealer locators (entity verification)

---

## Multi-Location Schema Pattern

```json
// Homepage: Organization with branchOf references
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://example.com/#org",
  "name": "Brand Name",
  "url": "https://example.com"
}

// Each location page: individual LocalBusiness
{
  "@context": "https://schema.org",
  "@type": "Dentist",
  "@id": "https://example.com/locations/downtown/#location",
  "name": "Brand Name - Downtown",
  "branchOf": { "@id": "https://example.com/#org" },
  "address": { ... },
  "geo": { "latitude": "40.71234", "longitude": "-74.00567" },
  "telephone": "+1-555-123-4567",
  "openingHoursSpecification": [ ... ]
}
```

Use `@id` for unique identifiers per location. Subdirectory structure recommended: `domain.com/locations/city-name/` (subdirectory consolidates link equity better than subdomain, Bruce Clay study: 50%+ traffic lift).

---

## Deprecated/Invalid Local Schema

| Type | Status | Date | Use Instead |
|------|--------|------|-------------|
| `Attorney` | Deprecated by Schema.org | -- | `LegalService` + `Person` |
| `VehicleListing` | Rich results removed | June 12, 2025 | `Car` + `Offer` |
| `HowTo` | Rich results removed | September 2023 | None |
| `SpecialAnnouncement` | Deprecated | July 31, 2025 | None |
