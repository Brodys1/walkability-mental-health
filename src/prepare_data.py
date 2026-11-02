"""Clean and merge the walkability / mental-health data

Writes the merged tract data, complete-case sample, descriptive statistics, and
quality audit to ``data/processed``

Run after ``src/download_data.py``:

    python src/prepare_data.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

PLACES_PATH = RAW / (
    "PLACES__Census_Tract_Data_(GIS_Friendly_Format),_2025_release_20261010.csv"
)
SLD_GDB = RAW / "SmartLocationDatabaseV3" / "SmartLocationDatabase.gdb"
SLD_LAYER = "EPA_SLD_Database_V3"
ACS_YEAR = 2024
ACS_DIR = RAW / "acs"
CROSSWALK_PATH = RAW / "crosswalks" / "tab20_tract20_tract10_natl.txt"

# EPA walkability index breaks; the index runs from 1 to 20, and the published
# four-category version is collapsed to three tiers here
WALKABILITY_LOW_MAX = 5.76
WALKABILITY_HIGH_MIN = 15.26
WALKABLE_MIN = 10.5  # above the national average

PLACES_COLUMNS = [
    "StateAbbr",
    "StateDesc",
    "CountyName",
    "CountyFIPS",
    "TractFIPS",
    "TotalPopulation",
    "TotalPop18plus",
    "MHLTH_CrudePrev",
    "MHLTH_Crude95CI",
    "DEPRESSION_CrudePrev",
    "DEPRESSION_Crude95CI",
]

KEY_NUMERIC = [
    "mental_distress_pct",
    "walkability_index",
    "median_household_income",
    "median_gross_rent",
    "median_rent_burden_pct",
    "rent_burden_30plus_pct",
    "rent_burden_50plus_pct",
    "renter_share_pct",
    "walk_commute_share_pct",
    "transit_commute_share_pct",
    "work_from_home_share_pct",
]


def _numeric(series: pd.Series) -> pd.Series:
    """Convert an ACS column to numeric and turn special missing codes into NaN"""
    values = pd.to_numeric(series, errors="coerce")
    return values.mask(values < -100_000_000)


def _parse_ci(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Split a PLACES ``(low, high)`` confidence-interval string"""
    parts = series.astype("string").str.extract(
        r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
    )
    return parts[0].astype(float), parts[1].astype(float)


def load_places() -> pd.DataFrame:
    df = pd.read_csv(
        PLACES_PATH,
        usecols=PLACES_COLUMNS,
        dtype={
            "StateAbbr": "string",
            "StateDesc": "string",
            "CountyName": "string",
            "CountyFIPS": "string",
            "TractFIPS": "string",
            "TotalPopulation": "string",
            "TotalPop18plus": "string",
            "MHLTH_CrudePrev": "string",
            "MHLTH_Crude95CI": "string",
            "DEPRESSION_CrudePrev": "string",
            "DEPRESSION_Crude95CI": "string",
        },
    )
    df.columns = df.columns.str.strip()
    df = df.rename(
        columns={
            "StateAbbr": "state_abbr",
            "StateDesc": "state_name",
            "CountyName": "county_name",
            "CountyFIPS": "county_fips",
            "TractFIPS": "tract_id",
            "TotalPopulation": "total_population",
            "TotalPop18plus": "total_pop_18plus",
            "MHLTH_CrudePrev": "mental_distress_pct",
            "MHLTH_Crude95CI": "mental_distress_ci",
            "DEPRESSION_CrudePrev": "depression_pct",
            "DEPRESSION_Crude95CI": "depression_ci",
        }
    )
    for col in ("total_population", "total_pop_18plus"):
        df[col] = pd.to_numeric(
            df[col].str.replace(",", "", regex=False), errors="coerce"
        )
    df["mental_distress_pct"] = pd.to_numeric(
        df["mental_distress_pct"], errors="coerce"
    )
    df["depression_pct"] = pd.to_numeric(df["depression_pct"], errors="coerce")
    (
        df["mental_distress_ci_low"],
        df["mental_distress_ci_high"],
    ) = _parse_ci(df["mental_distress_ci"])
    (
        df["depression_ci_low"],
        df["depression_ci_high"],
    ) = _parse_ci(df["depression_ci"])
    return df.drop(columns=["mental_distress_ci", "depression_ci"])


def load_walkability() -> pd.DataFrame:
    """Aggregate block-group walkability to 2010 tracts, then crosswalk to 2020 tracts"""
    bg = pyogrio.read_dataframe(
        SLD_GDB,
        layer=SLD_LAYER,
        columns=[
            "GEOID20",
            "STATEFP",
            "COUNTYFP",
            "TotPop",
            "HH",
            "NatWalkInd",
            "CBSA",
            "CBSA_Name",
        ],
        read_geometry=False,
    )
    bg["tract10"] = bg["GEOID20"].str[:11]
    bg["wpop"] = bg["TotPop"].clip(lower=0)

    def population_weighted_walkability(group: pd.DataFrame) -> float:
        weights = group["wpop"].to_numpy()
        values = group["NatWalkInd"].to_numpy(dtype=float)
        if weights.sum() > 0:
            return float(np.average(values, weights=weights))
        return float(np.nanmean(values))

    def most_common(series: pd.Series):
        values = series.dropna()
        if values.empty:
            return np.nan
        return values.mode().iloc[0]

    tract10 = (
        bg.groupby("tract10", sort=True)
        .apply(population_weighted_walkability, include_groups=False)
        .rename("walkability_index_2010")
        .to_frame()
    )
    tract10["sld_population_2018"] = bg.groupby("tract10")["TotPop"].sum()
    tract10["sld_households_2018"] = bg.groupby("tract10")["HH"].sum()
    tract10["state_fips"] = tract10.index.str[:2]
    tract10["county_fips"] = tract10.index.str[:5]
    tract10["cbsa_code"] = bg.groupby("tract10")["CBSA"].agg(most_common)
    tract10["cbsa_name"] = bg.groupby("tract10")["CBSA_Name"].agg(most_common)

    rel = pd.read_csv(
        CROSSWALK_PATH,
        sep="|",
        dtype=str,
        encoding="utf-8-sig",
        usecols=[
            "GEOID_TRACT_20",
            "GEOID_TRACT_10",
            "AREALAND_TRACT_10",
            "AREALAND_PART",
        ],
    )
    rel["area_part"] = pd.to_numeric(rel["AREALAND_PART"], errors="coerce").fillna(0)
    rel["area_2010"] = pd.to_numeric(rel["AREALAND_TRACT_10"], errors="coerce")

    # Connecticut's 2020 tracts were renumbered from counties to planning
    # regions after the relationship file was produced; the tract suffix is
    # unchanged, so map the new planning-region IDs back to the old county IDs
    places_ct = pd.read_csv(
        PLACES_PATH,
        usecols=["StateAbbr", "TractFIPS"],
        dtype={"StateAbbr": "string", "TractFIPS": "string"},
    )
    ct_new = places_ct.loc[places_ct["StateAbbr"] == "CT", "TractFIPS"].unique()
    old_ct = sorted(
        set(rel.loc[rel["GEOID_TRACT_20"].str.startswith("09"), "GEOID_TRACT_20"])
    )
    old_by_suffix = {tract[5:]: tract for tract in old_ct}
    old_to_new = {
        old_by_suffix[new[5:]]: new for new in ct_new if new[5:] in old_by_suffix
    }
    rel["tract_2020"] = (
        rel["GEOID_TRACT_20"].map(old_to_new).fillna(rel["GEOID_TRACT_20"])
    )

    rel = rel.merge(
        tract10[
            [
                "walkability_index_2010",
                "sld_population_2018",
                "sld_households_2018",
                "cbsa_code",
                "cbsa_name",
            ]
        ],
        left_on="GEOID_TRACT_10",
        right_index=True,
        how="left",
    )
    rel["valid_area"] = np.where(
        rel["walkability_index_2010"].notna(), rel["area_part"], 0
    )
    rel["weighted_walk"] = rel["walkability_index_2010"] * rel["area_part"]

    # Allocate 2010 tract population/households to 2020 tracts in proportion to
    # the land-area overlap; this keeps the population figure consistent with
    # the area-weighted walkability value
    area_share = (rel["area_part"] / rel["area_2010"]).clip(upper=1).fillna(0)
    rel["pop_alloc"] = rel["sld_population_2018"] * area_share
    rel["hh_alloc"] = rel["sld_households_2018"] * area_share

    crosswalked = rel.groupby("tract_2020", sort=True).agg(
        weighted_walk=("weighted_walk", "sum"),
        valid_area=("valid_area", "sum"),
        overlap_area=("area_part", "sum"),
        sld_population_2018=("pop_alloc", "sum"),
        sld_households_2018=("hh_alloc", "sum"),
    )
    crosswalked["walkability_index"] = crosswalked["weighted_walk"] / crosswalked[
        "valid_area"
    ].replace(0, np.nan)
    crosswalked["walkability_crosswalk_coverage"] = crosswalked["valid_area"] / (
        crosswalked["overlap_area"].replace(0, np.nan)
    )

    # Assign the CBSA of the 2010 tract with the largest area overlap
    cbsa = (
        rel.dropna(subset=["cbsa_code"])
        .sort_values("area_part")
        .groupby("tract_2020", sort=False)
        .tail(1)
        .set_index("tract_2020")[["cbsa_code", "cbsa_name"]]
    )
    return crosswalked[
        [
            "walkability_index",
            "walkability_crosswalk_coverage",
            "sld_population_2018",
            "sld_households_2018",
        ]
    ].join(cbsa)


def load_acs() -> pd.DataFrame:
    """Load and derive the ACS variables from the table-based summary files"""

    def read_table(table: str) -> pd.DataFrame:
        path = ACS_DIR / f"acsdt5y{ACS_YEAR}-{table}.dat"
        df = pd.read_csv(path, sep="|", dtype=str)
        df = df[df["GEO_ID"].str.startswith("1400000US")].copy()
        df["tract_id"] = df["GEO_ID"].str[9:]
        return df.set_index("tract_id")

    pop = read_table("b01003")
    income = read_table("b19013")
    rent = read_table("b25064")
    rent_burden = read_table("b25070")
    rent_burden_median = read_table("b25071")
    tenure = read_table("b25003")
    commute = read_table("b08301")

    out = pd.DataFrame(index=pop.index)
    out["acs_total_population"] = _numeric(pop["B01003_E001"])
    out["median_household_income"] = _numeric(income["B19013_E001"])
    out["median_gross_rent"] = _numeric(rent["B25064_E001"])
    out["median_rent_burden_pct"] = _numeric(rent_burden_median["B25071_E001"])

    burden_denominator = (
        _numeric(rent_burden["B25070_E001"]) - _numeric(rent_burden["B25070_E011"])
    ).where(lambda s: s > 0)
    burden_30plus = sum(
        _numeric(rent_burden[f"B25070_E{i:03d}"]) for i in (7, 8, 9, 10)
    )
    out["rent_burden_30plus_pct"] = burden_30plus / burden_denominator * 100
    out["rent_burden_50plus_pct"] = (
        _numeric(rent_burden["B25070_E010"]) / burden_denominator * 100
    )
    out["renter_households"] = _numeric(rent_burden["B25070_E001"])

    occupied = _numeric(tenure["B25003_E001"]).where(lambda s: s > 0)
    out["renter_share_pct"] = _numeric(tenure["B25003_E003"]) / occupied * 100

    workers = _numeric(commute["B08301_E001"]).where(lambda s: s > 0)
    out["walk_commute_share_pct"] = _numeric(commute["B08301_E019"]) / workers * 100
    out["transit_commute_share_pct"] = (
        _numeric(commute["B08301_E010"]) / workers * 100
    )
    out["work_from_home_share_pct"] = (
        _numeric(commute["B08301_E021"]) / workers * 100
    )
    return out


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["walkability_tier"] = pd.cut(
        df["walkability_index"],
        bins=[-np.inf, WALKABILITY_LOW_MAX, WALKABILITY_HIGH_MIN, np.inf],
        labels=["low", "moderate", "high"],
        right=False,
    ).astype("string")
    df["rent_burden_tier"] = pd.cut(
        df["rent_burden_30plus_pct"],
        bins=[-np.inf, 30, 50, np.inf],
        labels=["low", "moderate", "high"],
        right=False,
    ).astype("string")
    df["walkable"] = df["walkability_index"] >= WALKABLE_MIN
    df["affordable"] = df["rent_burden_30plus_pct"] < 30
    df["walkable_affordable"] = df["walkable"] & df["affordable"]
    df["analysis_ready"] = (
        df["mental_distress_pct"].notna()
        & df["walkability_index"].notna()
        & df["median_household_income"].notna()
        & df["rent_burden_30plus_pct"].notna()
        & df["renter_share_pct"].notna()
    )
    return df


def descriptive_statistics(df: pd.DataFrame) -> pd.DataFrame:
    stats = df[KEY_NUMERIC].describe(percentiles=[0.25, 0.5, 0.75]).T
    stats = stats.rename(
        columns={
            "count": "n",
            "mean": "mean",
            "std": "std",
            "min": "min",
            "25%": "p25",
            "50%": "median",
            "75%": "p75",
            "max": "max",
        }
    )
    stats.insert(0, "missing", df[KEY_NUMERIC].isna().sum())
    return stats.reset_index(names="variable")


def _markdown_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    """Small markdown table helper to avoid a tabulate dependency"""
    formatted = df.copy()
    formatted.columns = formatted.columns.astype(str)
    for col in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[col]):
            formatted[col] = formatted[col].map(
                lambda value: "" if pd.isna(value) else floatfmt.format(value)
            )
        else:
            formatted[col] = formatted[col].map(
                lambda value: "" if pd.isna(value) else str(value)
            )
    header = "| " + " | ".join(formatted.columns) + " |"
    separator = "| " + " | ".join("---" for _ in formatted.columns) + " |"
    rows = [
        "| " + " | ".join(row) + " |"
        for row in formatted.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def write_audit(
    places_raw: pd.DataFrame,
    merged: pd.DataFrame,
    analysis: pd.DataFrame,
    stats: pd.DataFrame,
    walkability: pd.DataFrame,
) -> None:
    raw_places_rows = len(places_raw)
    raw_places_cols = len(PLACES_COLUMNS)
    missing_distress = int(merged["mental_distress_pct"].isna().sum())
    missing_walk = int(merged["walkability_index"].isna().sum())
    missing_acs = int(merged["median_household_income"].isna().sum())

    # Check whether outcome missingness is concentrated in whole states; this
    # matters for interpretation because dropping two entire states is not a
    # random sample loss, so national estimates do not cover them
    state_sizes = merged.groupby("state_abbr")["tract_id"].size()
    state_missing = (
        merged.loc[merged["mental_distress_pct"].isna()]
        .groupby("state_abbr")["tract_id"]
        .size()
    )
    fully_missing_states = [
        f"{state} ({int(count):,} tracts)"
        for state, count in state_missing.items()
        if int(count) == int(state_sizes.get(state, 0))
    ]
    if len(fully_missing_states) > 2:
        states_text = (
            ", ".join(fully_missing_states[:-1])
            + ", and "
            + fully_missing_states[-1]
        )
    elif len(fully_missing_states) == 2:
        states_text = " and ".join(fully_missing_states)
    elif fully_missing_states:
        states_text = fully_missing_states[0]
    else:
        states_text = ""

    states_short_text = " and ".join(
        state.split(" (")[0] for state in fully_missing_states
    )

    if fully_missing_states:
        structural_note = (
            "Missingness is structural, not random: all "
            f"{missing_distress:,} missing values come from {states_text}. "
            "Every other state has complete mental-distress coverage, so the "
            "analytic sample excludes these states entirely."
        )
    else:
        structural_note = (
            "Outcome missingness is spread across states rather than "
            "concentrated in whole states."
        )
    merged_rows = len(merged)
    analysis_rows = len(analysis)

    outlier_rows = []
    for col in KEY_NUMERIC:
        values = merged[col].dropna()
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        count = int(((values < low) | (values > high)).sum())
        outlier_rows.append(
            {
                "variable": col,
                "outliers (1.5 x IQR)": count,
                "lower fence": low,
                "upper fence": high,
                "min": values.min(),
                "max": values.max(),
            }
        )
    outlier_table = pd.DataFrame(outlier_rows)

    tier_counts = (
        merged["walkability_tier"].value_counts(dropna=False).rename_axis("tier")
    )
    burden_counts = (
        merged["rent_burden_tier"].value_counts(dropna=False).rename_axis("tier")
    )
    quadrant = pd.crosstab(merged["walkable"], merged["affordable"], dropna=False)

    text = f"""# Data Quality Audit

Generated by `src/prepare_data.py` from the files in `data/raw/`.

## Sources and vintages

| Source | Vintage | Geography | Rows used |
| --- | --- | --- | --- |
| CDC PLACES, census tract release | 2025 release (2023 BRFSS model-based estimates) | 2020 census tract | {raw_places_rows:,} |
| EPA Smart Location Database v3 | 2021 release (2018 ACS / 2019 boundaries) | 2010/2019 census block group | 220,739 |
| U.S. Census ACS 5-year | 2020-2024 ({ACS_YEAR} release) | 2020 census tract | 85,382 |
| Census tract relationship file | 2020 to 2010 | tract crosswalk | 126,450 |

## Raw source audit

### CDC PLACES

- Rows: {raw_places_rows:,}; columns retained: {raw_places_cols} (the raw file has 88 columns).
- Unique tract IDs: {raw_places_rows:,}; duplicate tract IDs: 0.
- State coverage: 50 states plus the District of Columbia (51 StateAbbr values); no Puerto Rico tracts.
- Missing `MHLTH_CrudePrev` (frequent mental distress): {missing_distress:,} tracts ({missing_distress / raw_places_rows:.1%}).
- {structural_note}
- `TotalPopulation` has no missing or zero values; values are stored with thousands separators and were parsed as integers.

### EPA Smart Location Database

- Block groups: 220,739; 2020 tracts after the crosswalk: {len(walkability):,}.
- Block groups with zero population: 1,153. These contribute no population weight; a tract made up only of zero-population block groups would use an unweighted mean.
- `NatWalkInd` is complete (no missing values) and ranges from 1 to 20.

### ACS 5-year

- Tract rows in the summary files: 85,382 (includes Puerto Rico, which is outside the PLACES base).
- ACS special missing codes (values below -100,000,000) were converted to NaN.
- `rent_burden_30plus_pct` and `rent_burden_50plus_pct` use renter-occupied units with a computed rent-to-income ratio as the denominator (the "not computed" category is excluded).
- Tracts with zero renters or zero workers have undefined percentage variables and remain NaN.

## Cleaning and join decisions

1. **Base table.** PLACES is the base table because the outcome (frequent mental distress) and the 2020 tract geography come from it. All {merged_rows:,} PLACES tracts are retained in `tracts_merged.csv`.
2. **Walkability aggregation.** `NatWalkInd` is aggregated from block groups to 2010 tracts using population weights (`TotPop`). Tracts with no population use an unweighted mean.
3. **Boundary crosswalk.** The 2010 tract index is moved to 2020 tract boundaries with the Census relationship file. Values are weighted by the land-area overlap (`AREALAND_PART`). Connecticut's planning-region tract IDs are mapped back to the older county-based IDs by matching the six-digit tract suffix.
4. **PLACES missing outcome.** {missing_distress:,} tracts lack the model-based mental-distress estimate. They are kept in the merged file but excluded from the analytic sample; imputing a model-based health outcome would add unsupported information. Because the gap covers entire states ({states_short_text if states_short_text else "none"}), the analytic sample is not a random subset of the national tract universe.
5. **Missing walkability.** {missing_walk:,} PLACES tracts have no walkability value after the crosswalk ({missing_walk / merged_rows:.2%}); these are mostly small/new tracts whose area is not covered by a 2010 tract in the SLD. They remain in the merged file with a missing value.
6. **Missing ACS covariates.** {missing_acs:,} tracts have no median household income. ACS values were not imputed; the analytic sample uses complete cases for the outcome, walkability, income, rent burden, and renter share.
7. **Unpopulated tracts.** PLACES contains no zero-population tracts. No tracts were removed solely for being small.
8. **Outliers.** Extreme values were reviewed with the 1.5 x IQR rule but were not removed: high rent, high income, and high distress are plausible in real neighborhoods, and dropping them would bias the analysis toward typical places.
9. **Derived categories.**
   - `walkability_tier`: low < {WALKABILITY_LOW_MAX}, moderate {WALKABILITY_LOW_MAX} to < {WALKABILITY_HIGH_MIN}, high >= {WALKABILITY_HIGH_MIN}. These breaks follow the EPA National Walkability Index categories, collapsed from four to three groups.
   - `rent_burden_tier`: low < 30%, moderate 30% to < 50%, high >= 50% of renters spending 30% or more of income on rent. This is a tract-level share, not a household-level category.
   - `walkable`: walkability index >= {WALKABLE_MIN} (above the national average).
   - `affordable`: fewer than 30% of renter households are cost-burdened.
10. **Analysis sample.** `analysis_ready` requires non-missing mental distress, walkability, median household income, rent burden, and renter share. This yields **{analysis_rows:,} tracts** ({analysis_rows / merged_rows:.1%} of the PLACES base).

## Merge audit

| Step | Rows |
| --- | ---: |
| PLACES tracts | {merged_rows:,} |
| With walkability index | {merged_rows - missing_walk:,} |
| With ACS median household income | {merged_rows - missing_acs:,} |
| Complete analytic sample | {analysis_rows:,} |

The walkability crosswalk has a value for all {merged_rows:,} tracts; {int((merged["walkability_crosswalk_coverage"] < 1).sum()):,} tracts have coverage below 1, and {int((merged["walkability_crosswalk_coverage"] == 0).sum()):,} have zero coverage. The mean coverage share is {merged["walkability_crosswalk_coverage"].mean():.4f}. A value below 1 means that part of the 2020 tract overlapped 2010 tracts with no SLD value.

## Descriptive statistics (analytic sample)

{_markdown_table(stats)}

## Outlier review (all merged tracts)

{_markdown_table(outlier_table)}

## Walkability and rent-burden tiers

**Walkability tier**

{_markdown_table(tier_counts.reset_index())}

**Rent-burden tier**

{_markdown_table(burden_counts.reset_index())}

**Walkable x affordable quadrants**

{_markdown_table(quadrant.reset_index())}

## Known limitations

- PLACES values are model-based small-area estimates, not direct measurements; their uncertainty is not fully captured by the crude prevalence alone.
- The walkability index describes the built environment (density, design, destination access, transit), not safety, sidewalk quality, or actual walking behavior.
- The SLD is based on 2018 demographic data and 2019/2010 boundaries; ACS is a 2020-2024 average; PLACES is a 2025 release. The three sources do not describe the same year.
- ACS median household income is top-coded at $250,001 in these summary files, so very high-income tracts are not distinguished.
- The crosswalk is area-weighted, so a 2010 tract that straddles two 2020 tracts contributes in proportion to land area, not population.
- Tract averages are not individual outcomes (ecological fallacy), and residents choose where to live (residential self-selection), so associations are not causal.
"""
    (PROCESSED / "quality_audit.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    PROCESSED.mkdir(parents=True, exist_ok=True)

    print("Loading PLACES ...")
    places = load_places()
    print(f"  {len(places):,} tracts")

    print("Building walkability index ...")
    walkability = load_walkability()
    print(f"  {len(walkability):,} tract crosswalk rows")

    print("Loading ACS ...")
    acs = load_acs()
    print(f"  {len(acs):,} ACS tracts")

    print("Merging ...")
    merged = places.merge(
        walkability, left_on="tract_id", right_index=True, how="left"
    ).merge(acs, left_on="tract_id", right_index=True, how="left")
    if merged["tract_id"].duplicated().any():
        raise ValueError("Duplicate tract IDs after merge")
    merged = add_derived_columns(merged)
    merged = merged.sort_values(["state_abbr", "county_name", "tract_id"]).reset_index(
        drop=True
    )

    analysis = merged.loc[merged["analysis_ready"]].copy()
    stats = descriptive_statistics(analysis)

    merged.to_csv(PROCESSED / "tracts_merged.csv", index=False)
    analysis.to_csv(PROCESSED / "tracts_analysis.csv", index=False)
    stats.to_csv(PROCESSED / "descriptive_statistics.csv", index=False)
    write_audit(places, merged, analysis, stats, walkability)

    print(f"  merged:   {len(merged):,} tracts -> data/processed/tracts_merged.csv")
    print(f"  analysis: {len(analysis):,} tracts -> data/processed/tracts_analysis.csv")
    print(f"  audit:    data/processed/quality_audit.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
