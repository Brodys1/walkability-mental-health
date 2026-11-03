# Data Dictionary

This project combines three public data sources at the census-tract level. The
analysis file is `data/processed/tracts_merged.csv` (all PLACES tracts) and the
complete-case analysis sample is `data/processed/tracts_analysis.csv`.

> **Reading the files:** `tract_id` and `county_fips` are zero-padded strings.
> Read them with `dtype={"tract_id": str, "county_fips": str}` so leading zeros
> are not lost. `cbsa_code` is also a string; it is blank for rural tracts
> outside a metropolitan or micropolitan statistical area.

## Sources

| Source | Provider | Vintage | Geography | Link |
| --- | --- | --- | --- | --- |
| CDC PLACES, census tract data | Centers for Disease Control and Prevention | 2025 release (2023 BRFSS model-based estimates) | 2020 census tract | <https://data.cdc.gov/d/yjkw-uj5s> |
| Smart Location Database v3 | U.S. Environmental Protection Agency | 2021 release (2018 ACS, 2019 boundaries) | 2010/2019 census block group | <https://www.epa.gov/smartgrowth/smart-location-mapping> |
| American Community Survey 5-year estimates | U.S. Census Bureau | 2020-2024 (2024 release) | 2020 census tract | <https://www.census.gov/data/developers/data-sets/acs-5year.html> |
| 2020-to-2010 tract relationship file | U.S. Census Bureau | 2020 | tract crosswalk | <https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_natl.txt> |

## Processed file columns

Missingness is reported for `tracts_merged.csv` (83,522 rows).

### Identifiers and geography

| Column | Type | Source | Missing | Description |
| --- | --- | --- | ---: | --- |
| `tract_id` | string | PLACES `TractFIPS` | 0 | 11-digit 2020 census tract GEOID (state + county + tract). |
| `state_abbr` | string | PLACES `StateAbbr` | 0 | Two-letter state abbreviation. |
| `state_name` | string | PLACES `StateDesc` | 0 | State name. |
| `county_name` | string | PLACES `CountyName` | 0 | County name (Connecticut uses planning-region names in the 2025 PLACES release). |
| `county_fips` | string | PLACES `CountyFIPS` | 0 | 5-digit county FIPS code. |
| `cbsa_code` | string | SLD `CBSA` | 5,985 (7.2%) | Core Based Statistical Area code. Blank for rural tracts outside a CBSA. |
| `cbsa_name` | string | SLD `CBSA_Name` | 5,985 (7.2%) | Core Based Statistical Area name. |

### Mental-health outcomes (CDC PLACES)

| Column | Type | Unit | Missing | Description |
| --- | --- | --- | ---: | --- |
| `total_population` | integer | people | 0 | Total tract population from the PLACES release. |
| `total_pop_18plus` | integer | people | 0 | Population aged 18 and older. |
| `mental_distress_pct` | float | percent | 4,707 (5.6%) | `MHLTH_CrudePrev`: model-based percentage of adults who report 14 or more days of poor mental health in the past 30 days (frequent mental distress). |
| `mental_distress_ci_low` | float | percent | 4,707 (5.6%) | Lower bound of the 95% crude-prevalence confidence interval. |
| `mental_distress_ci_high` | float | percent | 4,707 (5.6%) | Upper bound of the 95% crude-prevalence confidence interval. |
| `depression_pct` | float | percent | 4,707 (5.6%) | `DEPRESSION_CrudePrev`: model-based percentage of adults ever diagnosed with depression. |
| `depression_ci_low` | float | percent | 4,707 (5.6%) | Lower bound of the depression 95% confidence interval. |
| `depression_ci_high` | float | percent | 4,707 (5.6%) | Upper bound of the depression 95% confidence interval. |

PLACES suppresses or does not publish estimates for tracts with small adult
populations; those tracts have missing values for all model-based measures.
They remain in the merged file and are excluded from the analytic sample.

### Walkability (EPA Smart Location Database)

| Column | Type | Unit | Missing | Description |
| --- | --- | --- | ---: | --- |
| `walkability_index` | float | index, 1-20 | 20 (0.02%) | Population-weighted mean of the EPA National Walkability Index (`NatWalkInd`) for the block groups in the tract. Higher values mean more walkable built environments. |
| `walkability_crosswalk_coverage` | float | proportion, 0-1 | 0 | Share of the tract's overlapping land area that had a valid 2010-tract walkability value. Values below 1 indicate incomplete crosswalk coverage. |
| `sld_population_2018` | float | people | 0 | Population allocated from the SLD's 2018 block-group population to the 2020 tract by land-area overlap. |
| `sld_households_2018` | float | households | 0 | Households allocated from the SLD's 2018 block-group households to the 2020 tract by land-area overlap. |

The EPA index combines four built-environment components: intersection density,
proximity to transit, employment mix, and household/employment mix. It is a
measure of the built environment, not of safety, sidewalk quality, or actual
walking behavior.

### Housing and socioeconomic variables (ACS 5-year)

All ACS estimates are from the 2020-2024 5-year release and are expressed in
2024 inflation-adjusted dollars where applicable.

| Column | Type | Unit | Missing | ACS table | Description |
| --- | --- | --- | ---: | --- | --- |
| `acs_total_population` | float | people | 14 (0.02%) | B01003 | Total population. |
| `median_household_income` | float | 2024 dollars | 621 (0.7%) | B19013 | Median household income in the past 12 months. Top-coded at $250,001. |
| `median_gross_rent` | float | 2024 dollars | 4,242 (5.1%) | B25064 | Median gross rent among renter-occupied units paying cash rent. |
| `median_rent_burden_pct` | float | percent | 2,813 (3.4%) | B25071 | Median gross rent as a percentage of household income among renter-occupied units paying cash rent. |
| `rent_burden_30plus_pct` | float | percent | 578 (0.7%) | B25070 | Percentage of renter households spending 30% or more of income on gross rent. Denominator excludes the "not computed" category. |
| `rent_burden_50plus_pct` | float | percent | 578 (0.7%) | B25070 | Percentage of renter households spending 50% or more of income on gross rent (severe burden). |
| `renter_households` | float | households | 14 (0.02%) | B25070 | Renter-occupied housing units in the rent-burden universe. |
| `renter_share_pct` | float | percent | 238 (0.3%) | B25003 | Renter-occupied units as a percentage of all occupied units. |
| `walk_commute_share_pct` | float | percent | 145 (0.2%) | B08301 | Workers 16+ who usually walked to work. |
| `transit_commute_share_pct` | float | percent | 145 (0.2%) | B08301 | Workers 16+ who usually used public transportation (excluding taxis and ride-hailing). |
| `work_from_home_share_pct` | float | percent | 145 (0.2%) | B08301 | Workers 16+ who worked from home. |

Formulas:

```text
rent_burden_30plus_pct = (B25070_E007 + B25070_E008 + B25070_E009 + B25070_E010)
                         / (B25070_E001 - B25070_E011) * 100

rent_burden_50plus_pct = B25070_E010 / (B25070_E001 - B25070_E011) * 100

renter_share_pct       = B25003_E003 / B25003_E001 * 100

walk_commute_share_pct = B08301_E019 / B08301_E001 * 100
transit_commute_share_pct = B08301_E010 / B08301_E001 * 100
work_from_home_share_pct  = B08301_E021 / B08301_E001 * 100
```

ACS special missing codes (`-555555555`, `-666666666`, `-999999999`, and other
values below -100,000,000) were converted to missing. Percentages with a zero
denominator are missing rather than zero.

### Derived analysis variables

| Column | Type | Missing | Description |
| --- | --- | ---: | --- |
| `walkability_tier` | string | 20 (0.02%) | `low` if index < 5.76; `moderate` if 5.76 to < 15.26; `high` if >= 15.26. These are the EPA index categories collapsed from four groups to three. |
| `rent_burden_tier` | string | 578 (0.7%) | `low` if fewer than 30% of renters are cost-burdened; `moderate` if 30% to < 50%; `high` if >= 50%. This is a tract-level share, not a household-level category. |
| `walkable` | boolean | 0 | `True` if `walkability_index >= 10.5` (above the national average). |
| `affordable` | boolean | 0 | `True` if fewer than 30% of renter households spend 30% or more of income on rent. |
| `walkable_affordable` | boolean | 0 | `True` if both `walkable` and `affordable`. |
| `analysis_ready` | boolean | 0 | `True` if the tract has non-missing `mental_distress_pct`, `walkability_index`, `median_household_income`, `rent_burden_30plus_pct`, and `renter_share_pct`. |

## Analytic sample

`data/processed/tracts_analysis.csv` contains the 77,934 tracts with
`analysis_ready = True` (93.3% of the 83,522 PLACES tracts). The main reasons
for exclusion are missing PLACES mental-distress estimates (4,707 tracts) and
missing ACS covariates.

## Raw files

| Path | Description |
| --- | --- |
| `data/raw/PLACES__Census_Tract_Data_(GIS_Friendly_Format),_2025_release_20261010.csv` | CDC PLACES 2025 census-tract release, 83,522 rows x 88 columns. |
| `data/raw/SmartLocationDatabaseV3/SmartLocationDatabase.gdb` | EPA Smart Location Database v3 file geodatabase, layer `EPA_SLD_Database_V3`, 220,739 block groups. |
| `data/raw/acs/acsdt5y2024-b01003.dat` | ACS 2024 5-year total population (B01003). |
| `data/raw/acs/acsdt5y2024-b08301.dat` | ACS 2024 5-year means of transportation to work (B08301). |
| `data/raw/acs/acsdt5y2024-b19013.dat` | ACS 2024 5-year median household income (B19013). |
| `data/raw/acs/acsdt5y2024-b25003.dat` | ACS 2024 5-year tenure (B25003). |
| `data/raw/acs/acsdt5y2024-b25064.dat` | ACS 2024 5-year median gross rent (B25064). |
| `data/raw/acs/acsdt5y2024-b25070.dat` | ACS 2024 5-year gross rent as a percentage of household income (B25070). |
| `data/raw/acs/acsdt5y2024-b25071.dat` | ACS 2024 5-year median gross rent as a percentage of household income (B25071). |
| `data/raw/crosswalks/tab20_tract20_tract10_natl.txt` | Census 2020-to-2010 tract relationship file. |

The raw files are not tracked in Git; run `python src/download_data.py` to
recreate them.

## Raw PLACES columns used

| Raw column | Processed column |
| --- | --- |
| `StateAbbr` | `state_abbr` |
| `StateDesc` | `state_name` |
| `CountyName` | `county_name` |
| `CountyFIPS` | `county_fips` |
| `TractFIPS` | `tract_id` |
| `TotalPopulation` | `total_population` |
| `TotalPop18plus` | `total_pop_18plus` |
| `MHLTH_CrudePrev` | `mental_distress_pct` |
| `MHLTH_Crude95CI` | `mental_distress_ci_low`, `mental_distress_ci_high` |
| `DEPRESSION_CrudePrev` | `depression_pct` |
| `DEPRESSION_Crude95CI` | `depression_ci_low`, `depression_ci_high` |

The remaining PLACES columns describe other chronic conditions and health
behaviors and are not used in the current analysis. See the CDC PLACES data
documentation for their definitions.

## Raw SLD columns used

| Raw column | Processed column |
| --- | --- |
| `GEOID20` | Used to derive the 2010 tract ID (first 11 digits). |
| `TotPop` | Population weight for `walkability_index`; also allocated to `sld_population_2018`. |
| `HH` | Allocated to `sld_households_2018`. |
| `NatWalkInd` | `walkability_index` (population-weighted mean). |
| `CBSA` | `cbsa_code` (CBSA with the largest area overlap). |
| `CBSA_Name` | `cbsa_name` (CBSA with the largest area overlap). |

See the EPA Smart Location Database technical documentation for the full list of
SLD fields.
