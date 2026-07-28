
# pysociome

> Operationalizing Social Determinants of Health (SDoH) Data in Python.

`pysociome` is a Python translation of the original R package [`sociome`](https://cran.r-project.org/package=sociome). It provides a flexible and powerful framework for calculating the **Area Deprivation Index (ADI)** and **Berg Indices (ADI-3)** for US geographic areas (states, counties, tracts, block groups, and ZCTAs).

## Features

- **ADI Calculation**: Replicates the original Singh (2003) algorithm using Principal Component Analysis (PCA).
- **ADI-3 (Berg Indices)**: Automatically calculates the three sub-indices:
  - **Financial Strength**
  - **Economic Hardship and Inequality**
  - **Educational Attainment**
- **Imputation**: Handles missing census data using iterative multivariate imputation (MICE-equivalent).
- **Census Integration**: Built-in client to fetch data directly from the US Census Bureau APIs (ACS and Decennial).
- **Relativity**: Allows for custom reference populations by providing specific GEOIDs.

## Installation

### From Source
To install `pysociome` locally:

```bash
git clone https://github.com/ulfsri/fireRisk-pysociome.git
cd fireRisk-pysociome
pip install .
```

### For Development
If you want to make changes to the code:

```bash
pip install -e .
```

## Setup: Census API Key

`pysociome` fetches data directly from the [US Census Bureau API](https://www.census.gov/data/developers.html), which requires a **free API key**.

### Step 1 — Get a key
Register at **https://api.census.gov/data/key_signup.html** and a key will be emailed to you immediately (free, no approval needed).

### Step 2 — Add the key to your project

Copy the included template to a `.env` file in your project directory:

```bash
cp .env.template .env
```

Then open `.env` and replace the placeholder with your real key:

```bash
# .env
Census_API_KEY = your_actual_key_here
```

`CensusClient` automatically searches for this file in the current working directory and its parents — no further configuration needed.

> **Security note:** `.env` is listed in `.gitignore` and will never be committed to version control. Never share or commit your Census API key.

### Alternative: pass the key directly in code

```python
from pysociome import CensusClient

client = CensusClient(key="your_actual_key_here")
```

---

## Quick Start

### 1. Calculate ADI from a DataFrame
If you already have a pandas DataFrame with census variables:

```python
import pandas as pd
from pysociome import calculate_adi

# Load your census data
df = pd.read_csv('your_census_data.csv')

# Calculate ADI and ADI-3
results = calculate_adi(df)

# Show results
print(results[['GEOID', 'NAME', 'ADI', 'Financial_Strength']])
```

### 2. Fetch Data and Calculate
After setting up your Census API key (see above), use `CensusClient` to fetch ACS data and compute ADI in one workflow:

```python
from pysociome import CensusClient, calculate_adi

# Loads key automatically from .env
client = CensusClient()

# Fetch 2022 ACS 5-year data for all tracts in Ohio (State FIPS 39)
raw_data = client.get_acs(
    year=2022,
    variables=["B19113_001", "B25088_002"],
    geography="tract:*",
    state="39"
)

# Calculate ADI and sub-indices
results = calculate_adi(raw_data)
print(results[['GEOID', 'NAME', 'ADI', 'Financial_Strength']])
```

## The 15 ADI Indicators

The package automatically calculates 15 socioeconomic indicators from raw Census variables. Below is the mapping for the **American Community Survey (ACS)**:

| Indicator | Target Name | Primary ACS Variables Used |
| :--- | :--- | :--- |
| **Median Family Income** | `medianFamilyIncome` | `B19113_001` (or `B19013_001`) |
| **Median Monthly Mortgage** | `medianMortgage` | `B25088_002` |
| **Median Gross Rent** | `medianRent` | `B25064_001` |
| **Median Home Value** | `medianHouseValue` | `B25077_001` |
| **% Families in Poverty** | `pctFamiliesInPoverty` | `B17010_002` / `B17010_001` |
| **% Owner-Occupied Housing** | `pctOwnerOccupiedHousing` | `B25003_002` / `B25003_001` |
| **Income Disparity** | `ratioThoseMakingUnder10kToThoseMakingOver50k` | `B19001_002`, `B19001_011` to `B19001_017` |
| **% Below 150% Poverty** | `pctPeopleLivingBelow150PctFederalPovertyLevel` | `C17002_002` to `005` / `C17002_001` |
| **% Single Parent (w/ kids)** | `pctHouseholdsWithChildrenThatAreSingleParent` | `B11005_005` / `B11005_002` |
| **% Households No Vehicle** | `pctHouseholdsWithNoVehicle` | `B25044_003`, `B25044_010` / `B25044_001` |
| **% White Collar Jobs** | `pctPeopleWithWhiteCollarJobs` | `C24010_003`, `C24010_039` / `C24010_001` |
| **% Unemployment Rate** | `pctPeopleUnemployed` | `B23025_005` / `B23025_003` |
| **% HS Education or Higher** | `pctPeopleWithAtLeastHSEducation` | `B15003_017` to `025` / `B15003_001` |
| **% < 9th Grade Education** | `pctPeopleWithLessThan9thGradeEducation` | `B15003_002` to `012` / `B15003_001` |
| **% Crowded Housing** | `pctHouseholdsWithOverOnePersonPerRoom` | `B25014_005` to `007`, `011` to `013` / `B25014_001` |

*Note: For block groups in 2015-2016, the package automatically substitutes `B19013_001` (Median Household Income) for `B19113_001` (Median Family Income) as per Census Bureau recommendations.*

## Dependencies

- `pandas`
- `numpy`
- `scikit-learn`
- `requests`

## Authors & Credits

This package was written by **Hossein Lotfi**. It is a Python translation of the original `sociome` R package developed by Nik Krieger, Jarrod Dalton, Cindy Wang, and Adam Perzynski.

The development of the original software was supported by a research grant from the National Institutes of Health/National Institute on Aging (Grant Number: 5R01AG055480-02).

## License

This project is licensed under the MIT License - see the LICENSE file for details.
