# Statistical Analysis

Analytic sample: **77,934 census tracts** with complete data on mental distress, walkability, income, rent burden, and renter share.

Outcome: CDC PLACES `MHLTH_CrudePrev`, the model-based percentage of adults reporting 14 or more days of poor mental health in the past 30 days. Predictors are described in `data/data_dictionary.md`.

## 1. Mental distress by walkability tier

| tier | n | mean distress (%) | median distress (%) | SD distress | mean walkability | mean income ($) | mean rent-burdened share (%) | mean renter share (%) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| low | 15855 | 17.233 | 17.200 | 2.483 | 4.474 | 79,208.783 | 42.579 | 18.386 |
| moderate | 55588 | 16.876 | 16.700 | 3.262 | 10.173 | 88,422.000 | 50.603 | 36.949 |
| high | 6491 | 16.861 | 16.400 | 3.417 | 16.388 | 89,821.104 | 51.567 | 59.729 |

- One-way ANOVA: F = 83.01, p < 0.001.
- Kruskal-Wallis (robust to skew): H = 400.13, p < 0.001.
- Effect size (eta-squared): 0.002126. The tier differences are statistically detectable at this sample size but explain a negligible share of the variation in mental distress.

## 2. Are walkable tracts less affordable?

Observed counts (rows = walkable, columns = affordable):

| walkable | False | True |
| --- | --- | --- |
| False | 36569 | 9815 |
| True | 29077 | 2473 |

Row percentages:

| walkable | False | True |
| --- | --- | --- |
| False | 78.8 | 21.2 |
| True | 92.2 | 7.8 |

Expected counts under independence:

| walkable | False | True |
| --- | --- | --- |
| False | 39,070.548 | 7,313.452 |
| True | 26,575.452 | 4,974.548 |

- Chi-square = 2,508.2, df = 1, p < 0.001.
- Cramer's V = 0.179.
- Interpretation: walkable tracts are substantially less likely to be affordable. Only 7.8% of walkable tracts are in the affordable group, compared with 21.2% of non-walkable tracts. This is consistent with the "walkable living as a luxury" framing, but the design is cross-sectional.

## 3. Regression models

The outcome is the tract mental-distress percentage. Continuous predictors are standardized (z-scores), so a one-unit change is one standard deviation. Heteroskedasticity-robust (HC1) standard errors are reported.

| model | term | coef | std_err | ci_low | ci_high | p_value |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Walkability only | Walkability (SD) | 0.0109 | 0.0110 | -0.0106 | 0.0324 | 0.322 |
| 2. Walkability + controls | Walkability (SD) | -0.4367 | 0.0107 | -0.4578 | -0.4157 | < 0.001 |
| 2. Walkability + controls | Median household income (SD) | -1.6911 | 0.0098 | -1.7102 | -1.6720 | < 0.001 |
| 2. Walkability + controls | Rent-burdened share (SD) | 0.0735 | 0.0085 | 0.0568 | 0.0903 | < 0.001 |
| 2. Walkability + controls | Renter share (SD) | 0.9135 | 0.0133 | 0.8874 | 0.9396 | < 0.001 |
| 3. Interaction with rent burden | Walkability (SD) | -0.4423 | 0.0107 | -0.4633 | -0.4212 | < 0.001 |
| 3. Interaction with rent burden | Median household income (SD) | -1.6714 | 0.0098 | -1.6906 | -1.6521 | < 0.001 |
| 3. Interaction with rent burden | Rent-burdened share (SD) | 0.1049 | 0.0093 | 0.0866 | 0.1232 | < 0.001 |
| 3. Interaction with rent burden | Renter share (SD) | 0.9193 | 0.0134 | 0.8931 | 0.9455 | < 0.001 |
| 3. Interaction with rent burden | Walkability x rent burden | 0.0976 | 0.0094 | 0.0791 | 0.1161 | < 0.001 |
| 4. Controls + state fixed effects | Walkability (SD) | -0.3679 | 0.0107 | -0.3889 | -0.3470 | < 0.001 |
| 4. Controls + state fixed effects | Median household income (SD) | -1.6952 | 0.0100 | -1.7148 | -1.6756 | < 0.001 |
| 4. Controls + state fixed effects | Rent-burdened share (SD) | 0.0692 | 0.0080 | 0.0534 | 0.0850 | < 0.001 |
| 4. Controls + state fixed effects | Renter share (SD) | 0.8740 | 0.0130 | 0.8485 | 0.8995 | < 0.001 |

Model fit:

| model | n | R-squared | adjusted R-squared |
| --- | --- | --- | --- |
| 1. Walkability only | 77934 | 0.0000 | -0.0000 |
| 2. Walkability + controls | 77934 | 0.4931 | 0.4931 |
| 3. Interaction with rent burden | 77934 | 0.4939 | 0.4939 |
| 4. Controls + state fixed effects | 77934 | 0.5830 | 0.5827 |

Key findings:

- **Raw association is essentially zero.** In model 1, walkability alone has a coefficient of 0.0109 percentage points per SD (p = 0.322). The bivariate correlation is 0.003.
- **Controls change the sign.** After adjusting for income, rent burden, and renter share, higher walkability is associated with lower mental distress (model 2 coefficient -0.437 percentage points per SD). This is a suppression pattern: walkable tracts tend to have higher income and higher renter shares, which work in opposite directions.
- **Income is the strongest correlate.** A one-SD increase in median household income is associated with about 1.69 percentage points lower mental distress, far larger than the walkability coefficient.
- **Rent burden moderates the association.** The interaction term in model 3 is positive (0.0976, p < 0.001), meaning the negative walkability association weakens as the rent-burdened share rises.
- **State context matters.** Adding state fixed effects raises R-squared from 0.493 to 0.583. The walkability coefficient remains negative, so the result is not solely a state-level artifact.

## 4. Correlation matrix

| variable | mental_distress_pct | depression_pct | walkability_index | median_household_income | median_gross_rent | median_rent_burden_pct | rent_burden_30plus_pct | renter_share_pct | walk_commute_share_pct | transit_commute_share_pct | work_from_home_share_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mental_distress_pct | 1.000 | 0.564 | 0.003 | -0.670 | -0.469 | 0.145 | 0.148 | 0.443 | 0.164 | -0.030 | -0.516 |
| depression_pct | 0.564 | 1.000 | -0.228 | -0.302 | -0.412 | -0.094 | -0.084 | 0.030 | 0.073 | -0.287 | -0.191 |
| walkability_index | 0.003 | -0.228 | 1.000 | 0.039 | 0.329 | 0.182 | 0.184 | 0.548 | 0.237 | 0.374 | 0.218 |
| median_household_income | -0.670 | -0.302 | 0.039 | 1.000 | 0.703 | -0.163 | -0.178 | -0.415 | -0.094 | 0.005 | 0.602 |
| median_gross_rent | -0.469 | -0.412 | 0.329 | 0.703 | 1.000 | 0.124 | 0.103 | -0.042 | 0.016 | 0.158 | 0.540 |
| median_rent_burden_pct | 0.145 | -0.094 | 0.182 | -0.163 | 0.124 | 1.000 | 0.850 | 0.160 | 0.047 | 0.079 | -0.024 |
| rent_burden_30plus_pct | 0.148 | -0.084 | 0.184 | -0.178 | 0.103 | 0.850 | 1.000 | 0.185 | 0.047 | 0.077 | -0.041 |
| renter_share_pct | 0.443 | 0.030 | 0.548 | -0.415 | -0.042 | 0.160 | 0.185 | 1.000 | 0.359 | 0.377 | -0.084 |
| walk_commute_share_pct | 0.164 | 0.073 | 0.237 | -0.094 | 0.016 | 0.047 | 0.047 | 0.359 | 1.000 | 0.254 | 0.047 |
| transit_commute_share_pct | -0.030 | -0.287 | 0.374 | 0.005 | 0.158 | 0.079 | 0.077 | 0.377 | 0.254 | 1.000 | 0.070 |
| work_from_home_share_pct | -0.516 | -0.191 | 0.218 | 0.602 | 0.540 | -0.024 | -0.041 | -0.084 | 0.047 | 0.070 | 1.000 |

## 5. Interpretation and limitations

- These are associational estimates from one cross-section. They do not identify a causal effect of walkability or housing costs.
- PLACES mental-distress values are model-based small-area estimates. Their uncertainty is not propagated into the regression, so standard errors are optimistic.
- The walkability index measures the built environment, not safety, sidewalk quality, or actual walking.
- The rent-burden measure is a tract-level share of renters spending 30% or more of income on rent. It is not a household-level indicator.
- The ecological fallacy applies: tract averages do not describe individuals, and residents select into neighborhoods.
- The data sources describe different periods (SLD 2018/2019, ACS 2020-2024, PLACES 2025 release).
