"""Descriptive and inferential statistics for the analytic tract sample

Writes tier summaries, correlations, regression results, and a results report to
``data/processed``

Run after ``src/prepare_data.py``:

    python src/analyze_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
ANALYSIS_PATH = PROCESSED / "tracts_analysis.csv"

FOCAL_PREDICTORS = [
    "walkability_index_z",
    "median_household_income_z",
    "rent_burden_30plus_pct_z",
    "renter_share_pct_z",
    "walkability_index_z:rent_burden_30plus_pct_z",
]
CORRELATION_VARS = [
    "mental_distress_pct",
    "depression_pct",
    "walkability_index",
    "median_household_income",
    "median_gross_rent",
    "median_rent_burden_pct",
    "rent_burden_30plus_pct",
    "renter_share_pct",
    "walk_commute_share_pct",
    "transit_commute_share_pct",
    "work_from_home_share_pct",
]


def load_analysis() -> pd.DataFrame:
    df = pd.read_csv(
        ANALYSIS_PATH,
        dtype={"tract_id": str, "county_fips": str, "cbsa_code": str},
    )
    required = [
        "mental_distress_pct",
        "walkability_index",
        "median_household_income",
        "rent_burden_30plus_pct",
        "renter_share_pct",
        "state_abbr",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Analysis file is missing columns: {missing}")
    return df


def add_standardized_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in [
        "walkability_index",
        "median_household_income",
        "rent_burden_30plus_pct",
        "renter_share_pct",
    ]:
        df[f"{col}_z"] = (df[col] - df[col].mean()) / df[col].std(ddof=0)
    return df


def tier_summary(df: pd.DataFrame) -> pd.DataFrame:
    order = ["low", "moderate", "high"]
    summary = (
        df.groupby("walkability_tier", observed=True)
        .agg(
            n=("mental_distress_pct", "size"),
            mean_distress=("mental_distress_pct", "mean"),
            median_distress=("mental_distress_pct", "median"),
            sd_distress=("mental_distress_pct", "std"),
            mean_walkability=("walkability_index", "mean"),
            mean_income=("median_household_income", "mean"),
            mean_rent_burden=("rent_burden_30plus_pct", "mean"),
            mean_renter_share=("renter_share_pct", "mean"),
        )
        .reindex(order)
    )
    summary.index.name = "walkability_tier"
    return summary


def run_tests(df: pd.DataFrame) -> dict:
    groups = [
        group["mental_distress_pct"].to_numpy()
        for _, group in df.groupby("walkability_tier", observed=True)
    ]
    f_stat, anova_p = stats.f_oneway(*groups)
    kruskal_stat, kruskal_p = stats.kruskal(*groups)

    grand_mean = df["mental_distress_pct"].mean()
    ss_between = sum(len(group) * (group.mean() - grand_mean) ** 2 for group in groups)
    ss_total = ((df["mental_distress_pct"] - grand_mean) ** 2).sum()
    eta_squared = ss_between / ss_total

    quadrant = pd.crosstab(df["walkable"], df["affordable"])
    chi2, chi2_p, dof, expected = stats.chi2_contingency(quadrant)
    n = quadrant.to_numpy().sum()
    cramers_v = np.sqrt(chi2 / (n * (min(quadrant.shape) - 1)))

    return {
        "anova_f": f_stat,
        "anova_p": anova_p,
        "kruskal_h": kruskal_stat,
        "kruskal_p": kruskal_p,
        "eta_squared": eta_squared,
        "chi2": chi2,
        "chi2_p": chi2_p,
        "chi2_dof": dof,
        "cramers_v": cramers_v,
        "quadrant": quadrant,
        "expected": expected,
    }


def fit_models(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    models = {
        "1. Walkability only": "mental_distress_pct ~ walkability_index_z",
        "2. Walkability + controls": (
            "mental_distress_pct ~ walkability_index_z + median_household_income_z "
            "+ rent_burden_30plus_pct_z + renter_share_pct_z"
        ),
        "3. Interaction with rent burden": (
            "mental_distress_pct ~ walkability_index_z * rent_burden_30plus_pct_z "
            "+ median_household_income_z + renter_share_pct_z"
        ),
        "4. Controls + state fixed effects": (
            "mental_distress_pct ~ walkability_index_z + median_household_income_z "
            "+ rent_burden_30plus_pct_z + renter_share_pct_z + C(state_abbr)"
        ),
    }

    rows = []
    fit_info = {}
    for name, formula in models.items():
        result = smf.ols(formula, data=df).fit(cov_type="HC1")
        fit_info[name] = {
            "r_squared": result.rsquared,
            "adj_r_squared": result.rsquared_adj,
            "n": int(result.nobs),
        }
        for term in FOCAL_PREDICTORS:
            if term not in result.params:
                continue
            ci_low, ci_high = result.conf_int().loc[term]
            rows.append(
                {
                    "model": name,
                    "term": term,
                    "coef": result.params[term],
                    "std_err": result.bse[term],
                    "p_value": result.pvalues[term],
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "r_squared": result.rsquared,
                    "n": int(result.nobs),
                }
            )
    return pd.DataFrame(rows), fit_info


def _markdown_table(df: pd.DataFrame, floatfmt: str = "{:,.3f}") -> str:
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


def _format_p(value: float) -> str:
    if value < 0.001:
        return "< 0.001"
    return f"{value:.3f}"


def _p_text(value: float) -> str:
    if value < 0.001:
        return "p < 0.001"
    return f"p = {value:.3f}"


def write_report(
    df: pd.DataFrame,
    tiers: pd.DataFrame,
    tests: dict,
    regressions: pd.DataFrame,
    fit_info: dict,
    correlations: pd.DataFrame,
) -> None:
    quadrant = tests["quadrant"]
    expected = pd.DataFrame(
        tests["expected"],
        index=quadrant.index,
        columns=quadrant.columns,
    )
    quadrant_pct = quadrant.div(quadrant.sum(axis=1), axis=0) * 100

    tier_table = tiers.reset_index().rename(
        columns={
            "walkability_tier": "tier",
            "mean_distress": "mean distress (%)",
            "median_distress": "median distress (%)",
            "sd_distress": "SD distress",
            "mean_walkability": "mean walkability",
            "mean_income": "mean income ($)",
            "mean_rent_burden": "mean rent-burdened share (%)",
            "mean_renter_share": "mean renter share (%)",
        }
    )

    regression_table = regressions.copy()
    regression_table["term"] = regression_table["term"].map(
        {
            "walkability_index_z": "Walkability (SD)",
            "median_household_income_z": "Median household income (SD)",
            "rent_burden_30plus_pct_z": "Rent-burdened share (SD)",
            "renter_share_pct_z": "Renter share (SD)",
            "walkability_index_z:rent_burden_30plus_pct_z": "Walkability x rent burden",
        }
    )
    regression_table = regression_table[
        ["model", "term", "coef", "std_err", "ci_low", "ci_high", "p_value"]
    ]
    regression_table["p_value"] = regression_table["p_value"].map(_format_p)

    fit_table = pd.DataFrame(
        [
            {
                "model": name,
                "n": info["n"],
                "R-squared": info["r_squared"],
                "adjusted R-squared": info["adj_r_squared"],
            }
            for name, info in fit_info.items()
        ]
    )

    text = f"""# Statistical Analysis

Analytic sample: **{len(df):,} census tracts** with complete data on mental distress, walkability, income, rent burden, and renter share.

Outcome: CDC PLACES `MHLTH_CrudePrev`, the model-based percentage of adults reporting 14 or more days of poor mental health in the past 30 days. Predictors are described in `data/data_dictionary.md`.

## 1. Mental distress by walkability tier

{_markdown_table(tier_table)}

- One-way ANOVA: F = {tests['anova_f']:,.2f}, {_p_text(tests['anova_p'])}.
- Kruskal-Wallis (robust to skew): H = {tests['kruskal_h']:,.2f}, {_p_text(tests['kruskal_p'])}.
- Effect size (eta-squared): {tests['eta_squared']:.6f}. The tier differences are statistically detectable at this sample size but explain a negligible share of the variation in mental distress.

## 2. Are walkable tracts less affordable?

Observed counts (rows = walkable, columns = affordable):

{_markdown_table(quadrant.reset_index())}

Row percentages:

{_markdown_table(quadrant_pct.reset_index(), floatfmt="{:.1f}")}

Expected counts under independence:

{_markdown_table(expected.reset_index())}

- Chi-square = {tests['chi2']:,.1f}, df = {tests['chi2_dof']}, {_p_text(tests['chi2_p'])}.
- Cramer's V = {tests['cramers_v']:.3f}.
- Interpretation: walkable tracts are substantially less likely to be affordable. Only {quadrant_pct.loc[True, True]:.1f}% of walkable tracts are in the affordable group, compared with {quadrant_pct.loc[False, True]:.1f}% of non-walkable tracts. This is consistent with the "walkable living as a luxury" framing, but the design is cross-sectional.

## 3. Regression models

The outcome is the tract mental-distress percentage. Continuous predictors are standardized (z-scores), so a one-unit change is one standard deviation. Heteroskedasticity-robust (HC1) standard errors are reported.

{_markdown_table(regression_table, floatfmt="{:,.4f}")}

Model fit:

{_markdown_table(fit_table, floatfmt="{:,.4f}")}

Key findings:

- **Raw association is essentially zero.** In model 1, walkability alone has a coefficient of {regressions.loc[(regressions['model'] == '1. Walkability only') & (regressions['term'] == 'walkability_index_z'), 'coef'].iloc[0]:,.4f} percentage points per SD ({_p_text(regressions.loc[(regressions['model'] == '1. Walkability only') & (regressions['term'] == 'walkability_index_z'), 'p_value'].iloc[0])}). The bivariate correlation is {correlations.loc['mental_distress_pct', 'walkability_index']:.3f}.
- **Controls change the sign.** After adjusting for income, rent burden, and renter share, higher walkability is associated with lower mental distress (model 2 coefficient {regressions.loc[(regressions['model'] == '2. Walkability + controls') & (regressions['term'] == 'walkability_index_z'), 'coef'].iloc[0]:,.3f} percentage points per SD). This is a suppression pattern: walkable tracts tend to have higher income and higher renter shares, which work in opposite directions.
- **Income is the strongest correlate.** A one-SD increase in median household income is associated with about {abs(regressions.loc[(regressions['model'] == '2. Walkability + controls') & (regressions['term'] == 'median_household_income_z'), 'coef'].iloc[0]):,.2f} percentage points lower mental distress, far larger than the walkability coefficient.
- **Rent burden moderates the association.** The interaction term in model 3 is positive ({regressions.loc[(regressions['model'] == '3. Interaction with rent burden') & (regressions['term'] == 'walkability_index_z:rent_burden_30plus_pct_z'), 'coef'].iloc[0]:,.4f}, {_p_text(regressions.loc[(regressions['model'] == '3. Interaction with rent burden') & (regressions['term'] == 'walkability_index_z:rent_burden_30plus_pct_z'), 'p_value'].iloc[0])}), meaning the negative walkability association weakens as the rent-burdened share rises.
- **State context matters.** Adding state fixed effects raises R-squared from {fit_info['2. Walkability + controls']['r_squared']:.3f} to {fit_info['4. Controls + state fixed effects']['r_squared']:.3f}. The walkability coefficient remains negative, so the result is not solely a state-level artifact.

## 4. Correlation matrix

{_markdown_table(correlations.reset_index().rename(columns={"index": "variable"}), floatfmt="{:,.3f}")}

## 5. Interpretation and limitations

- These are associational estimates from one cross-section. They do not identify a causal effect of walkability or housing costs.
- PLACES mental-distress values are model-based small-area estimates. Their uncertainty is not propagated into the regression, so standard errors are optimistic.
- The walkability index measures the built environment, not safety, sidewalk quality, or actual walking.
- The rent-burden measure is a tract-level share of renters spending 30% or more of income on rent. It is not a household-level indicator.
- The ecological fallacy applies: tract averages do not describe individuals, and residents select into neighborhoods.
- The data sources describe different periods (SLD 2018/2019, ACS 2020-2024, PLACES 2025 release).
"""
    (PROCESSED / "statistical_tests.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    if argv:
        raise SystemExit(f"Unexpected arguments: {argv}")
    df = load_analysis()
    df = add_standardized_columns(df)

    tiers = tier_summary(df)
    tests = run_tests(df)
    correlations = df[CORRELATION_VARS].corr()
    regressions, fit_info = fit_models(df)

    tiers.to_csv(PROCESSED / "walkability_tier_summary.csv")
    correlations.to_csv(PROCESSED / "correlation_matrix.csv")
    tests["quadrant"].to_csv(PROCESSED / "quadrant_counts.csv")
    regressions.to_csv(PROCESSED / "regression_results.csv", index=False)
    write_report(df, tiers, tests, regressions, fit_info, correlations)

    print(f"Analysis sample: {len(df):,} tracts")
    print(
        f"ANOVA: F = {tests['anova_f']:,.2f}, p = {tests['anova_p']:.3g}, "
        f"eta-squared = {tests['eta_squared']:.6f}"
    )
    print(
        f"Chi-square: {tests['chi2']:,.1f}, p = {tests['chi2_p']:.3g}, "
        f"Cramer's V = {tests['cramers_v']:.3f}"
    )
    print("Regression results:")
    print(
        regressions[
            ["model", "term", "coef", "p_value"]
        ].to_string(index=False)
    )
    print("Wrote data/processed/statistical_tests.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
