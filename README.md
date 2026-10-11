# Walkability and Mental Health

> Analyzing how neighborhood walkability and housing affordability relate to mental health across U.S. census tracts

## Authors

- **Brody Smith** ([@Brodys1](https://github.com/Brodys1))

## Project Description

This study aims to determine whether walkable communities correlate with better mental health, while also examining how housing affordability affects that association. Data from the EPA National Walkability Index and CDC PLACES will be merged to create a set of variables reflecting the walkability of each census tract and the prevalence of frequent mental distress. Using Census ACS variables for rent, rent burden, and income, the study will explore whether the relationship between walkability and mental health holds after accounting for housing costs. It will produce a set of static graphics and an interactive dashboard that allows users to explore these variables at the census tract level. Additionally, the study will assess the limitations of this approach, namely the use of modeled health data, the ecological fallacy, and the possibility of residential self-selection.

## Project Outline / Plan

### Interface Plan

- Interactive dashboard (HTML file built with Plotly)
- Filters for state or metro area, walkability score, and rent burden
- Scatter plot of walkability vs. mental distress, with tract details on hover

### Data Collection and Storage Plan

- Sources:
  - [EPA National Walkability Index](https://www.epa.gov/smartgrowth/smart-location-mapping) (block group level)
  - [CDC PLACES census tract data](https://data.cdc.gov/d/yjkw-uj5s) (frequent mental distress)
  - [Census ACS 5-year estimates](https://www.census.gov/data/developers/data-sets/acs-5year.html) (rent, rent burden, income)
- Download each source as CSV or through the Census API using a Python script
- Join the datasets on census tract ID
- Store raw files in `data/raw/` (not tracked by Git) and the cleaned, merged file in `data/processed/`

### Data Analysis and Visualization Plan

- Clean the merged data and document each decision
- Calculate descriptive statistics for all key variables
- Run an ANOVA across walkability groups and a regression controlling for income and rent burden
- Create static visualizations, including a box plot, scatter plot, and heatmap
- Build the interactive dashboard and write a bias and limitations discussion

## Repository Structure

```
.
├── dashboard.html
├── data
│   ├── data_dictionary.md
│   ├── processed
│   └── raw         # Not tracked
├── figures
├── LICENSE
├── notebooks
├── README.md
└── src
    └── download_data.py
```

## License

This project is released under the MIT License. See the [LICENSE](LICENSE) file for details.
