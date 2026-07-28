
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
from sklearn.preprocessing import StandardScaler
import warnings

def calculate_adi(data_raw, keep_indicators=False):
    """
    Calculate ADI and ADI-3 from census data.

    Parameters:
    -----------
    data_raw : pd.DataFrame
        Raw census data with variable names as columns, OR a DataFrame already 
        containing the 15 ADI indicators.
    keep_indicators : bool, default False
        Whether to keep the component indicators in the output.

    Returns:
    --------
    pd.DataFrame
        DataFrame with ADI and ADI-3 indices.
    """
    if not isinstance(data_raw, pd.DataFrame):
        raise ValueError("data_raw must be a pandas DataFrame")

    df = data_raw.copy()

    # --- ACS sentinel value replacement ---
    # The Census Bureau uses specific negative integer codes in ACS estimates to
    # indicate unavailable, non-applicable, or non-computable values:
    #   -666666666  not available
    #   -888888888  not applicable
    #   -999999999  median falls in lowest/highest interval
    #   -222222222  too few sample cases
    #   -333333333  base is zero or rounds to zero
    # See: https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html
    #
    # These codes must be replaced with NaN before PCA. Without this step,
    # sentinel values (e.g. -666666666) in median dollar variables
    # (medianFamilyIncome, medianMortgage, medianRent, medianHouseValue) become
    # extreme outliers (~10^6 standard deviations) after StandardScaler, which
    # completely destroys the Financial Strength sub-index.
    _SENTINELS = {-666666666, -888888888, -999999999, -222222222, -333333333}
    numeric_cols = df.select_dtypes(include="number").columns
    sentinel_mask = df[numeric_cols].isin(_SENTINELS)
    sentinel_count = sentinel_mask.sum().sum()
    if sentinel_count > 0:
        df[numeric_cols] = df[numeric_cols].where(~sentinel_mask, other=np.nan)
        warnings.warn(
            f"calculate_adi: replaced {sentinel_count:,} ACS sentinel values "
            f"(-666666666, -888888888, etc.) with NaN. These indicate "
            f"unavailable/suppressed Census estimates.",
            UserWarning,
            stacklevel=2,
        )

    # Identify total households column
    try:
        total_hh_col = get_total_hh_colname(df)
        nonzero_hh = df[total_hh_col] != 0
    except ValueError:
        # If total households column not found, assume all rows are valid or check for a generic 'total_households'
        if 'total_households' in df.columns:
            total_hh_col = 'total_households'
            nonzero_hh = df[total_hh_col] != 0
        elif 'housing_occupied_units' in df.columns:
            total_hh_col = 'housing_occupied_units'
            nonzero_hh = df[total_hh_col] != 0
        else:
            warnings.warn("Total households column not found. Assuming all rows have > 0 households.")
            nonzero_hh = pd.Series(True, index=df.index)
            total_hh_col = None

    # Handle common descriptive column names
    mapping = {
        'income_household_median': 'medianHouseholdIncome',
        'housing_monthly_costs_mortgage_median': 'medianMortgage',
        'rent_gross_median': 'medianRent',
        'housing_value_median': 'medianHouseValue',
        'poverty_families_pct': 'pctFamiliesInPoverty',
        'housing_owner_occupied_pct': 'pctOwnerOccupiedHousing',
        'unemployed_rate_pct': 'pctPeopleUnemployed',
        'education_high_school_pct': 'pctPeopleWithAtLeastHSEducation',
        'education_bachelors_pct': 'pctPeopleWithBachelorDegree',
        'housing_units_total': 'B25003_001', # Just to help calculate_indicators if needed
        'housing_owner_occupied_units': 'B25003_002',
    }
    
    # Target indicators for scaling (those that should be ratios)
    ratio_indicators = [
        'pctFamiliesInPoverty', 'pctOwnerOccupiedHousing', 
        'pctPeopleLivingBelow150PctFederalPovertyLevel',
        'pctHouseholdsWithChildrenThatAreSingleParent', 'pctHouseholdsWithNoVehicle',
        'pctPeopleWithWhiteCollarJobs', 'pctPeopleUnemployed',
        'pctPeopleWithAtLeastHSEducation', 'pctPeopleWithLessThan9thGradeEducation',
        'pctHouseholdsWithOverOnePersonPerRoom'
    ]

    for old_col, new_col in mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df[new_col] = df[old_col]
            
            # Scale percentages to ratios if they appear to be in 0-100 range
            if new_col in ratio_indicators and df[new_col].max() > 1.0:
                df[new_col] = df[new_col] / 100.0

    # Ensure NAME column exists
    if 'NAME' not in df.columns:
        if 'GEOID' in df.columns:
            df['NAME'] = "Area " + df['GEOID'].astype(str)
        else:
            df['NAME'] = df.index.astype(str)

    # Calculate 15 ADI indicators
    try:
        indicators = calculate_indicators(df)
    except ValueError:
        # Check if df already contains the 15 indicators (or enough for imputation)
        required_indicators = [
            "medianFamilyIncome", "medianMortgage", "medianRent", "medianHouseValue",
            "pctFamiliesInPoverty", "pctOwnerOccupiedHousing", 
            "ratioThoseMakingUnder10kToThoseMakingOver50k", "pctPeopleLivingBelow150PctFederalPovertyLevel",
            "pctHouseholdsWithChildrenThatAreSingleParent", "pctHouseholdsWithNoVehicle",
            "pctPeopleWithWhiteCollarJobs", "pctPeopleUnemployed",
            "pctPeopleWithAtLeastHSEducation", "pctPeopleWithLessThan9thGradeEducation",
            "pctHouseholdsWithOverOnePersonPerRoom"
        ]
        
        # Fallback for income variable name
        income_var = "medianFamilyIncome"
        if "medianHouseholdIncome" in df.columns and "medianFamilyIncome" not in df.columns:
            income_var = "medianHouseholdIncome"
            required_indicators[0] = income_var
            
        if any(c in df.columns for c in required_indicators):
            # Use what's available and let imputer handle the rest
            indicators = df.reindex(columns=required_indicators)
        else:
            raise ValueError("Data missing at least one variable necessary to calculate ADI, and no indicators found.")

    # Filter to nonzero households for PCA
    indicators_hh_only = indicators[nonzero_hh].copy()
    
    if len(indicators_hh_only) < 30:
        warnings.warn("Calculating ADI from fewer than 30 locations. Trustworthiness may be low.")
        
    # Imputation
    if indicators_hh_only.isnull().any().any():
        # IterativeImputer fails if a column is all NaN. 
        # Fill all-NaN columns with 0 and warn.
        all_nan_cols = indicators_hh_only.columns[indicators_hh_only.isnull().all()]
        if len(all_nan_cols) > 0:
            warnings.warn(f"The following indicators are entirely missing and will be filled with 0: {list(all_nan_cols)}")
            indicators_hh_only[all_nan_cols] = 0.0
            
        if indicators_hh_only.isnull().any().any():
            imputer = IterativeImputer(max_iter=50, random_state=0)
            imputed_data = imputer.fit_transform(indicators_hh_only)
            indicators_hh_only.iloc[:, :] = imputed_data
            print("Single imputation performed")

    # Define variable sets for ADI and ADI-3
    income_var = indicators_hh_only.columns[0] # medianFamilyIncome or medianHouseholdIncome
    
    variable_sets = {
        "ADI": {
            income_var: -1,
            "medianMortgage": -1,
            "medianRent": -1,
            "medianHouseValue": -1,
            "pctFamiliesInPoverty": 1,
            "pctOwnerOccupiedHousing": -1,
            "ratioThoseMakingUnder10kToThoseMakingOver50k": 1,
            "pctPeopleLivingBelow150PctFederalPovertyLevel": 1,
            "pctHouseholdsWithChildrenThatAreSingleParent": 1,
            "pctHouseholdsWithNoVehicle": 1,
            "pctPeopleWithWhiteCollarJobs": -1,
            "pctPeopleUnemployed": 1,
            "pctPeopleWithAtLeastHSEducation": -1,
            "pctPeopleWithLessThan9thGradeEducation": 1,
            "pctHouseholdsWithOverOnePersonPerRoom": 1
        },
        "Financial_Strength": {
            income_var: 1,
            "medianMortgage": 1,
            "medianRent": 1,
            "medianHouseValue": 1,
            "pctPeopleWithWhiteCollarJobs": 1
        },
        "Economic_Hardship_and_Inequality": {
            "pctFamiliesInPoverty": 1,
            "pctOwnerOccupiedHousing": -1,
            "ratioThoseMakingUnder10kToThoseMakingOver50k": 1,
            "pctPeopleLivingBelow150PctFederalPovertyLevel": 1,
            "pctHouseholdsWithChildrenThatAreSingleParent": 1,
            "pctHouseholdsWithNoVehicle": 1,
            "pctPeopleUnemployed": 1
        },
        "Educational_Attainment": {
            "pctPeopleWithAtLeastHSEducation": 1,
            "pctPeopleWithLessThan9thGradeEducation": -1,
            "pctHouseholdsWithOverOnePersonPerRoom": -1
        }
    }

    results = pd.DataFrame(index=df.index)
    results['GEOID'] = df['GEOID']
    results['NAME'] = df['NAME']
    
    loadings_dict = {}

    for name, expected_signs in variable_sets.items():
        cols = list(expected_signs.keys())
        signs = np.array(list(expected_signs.values()))
        
        # PCA on subset
        data_subset = indicators_hh_only[cols]
        
        # In R, psych::principal(x) uses the correlation matrix by default.
        # To match this in sklearn, we must use the correlation matrix.
        # Alternatively, Standardize and then PCA is equivalent to PCA on correlation matrix 
        # BUT we need to scale the scores correctly.
        
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data_subset)
        
        # R's psych::principal uses the correlation matrix.
        # We'll compute the correlation matrix and run PCA on it
        corr_matrix = np.corrcoef(data_scaled, rowvar=False)
        # Handle cases where correlation might be NaN due to zero variance
        corr_matrix = np.nan_to_num(corr_matrix)
        
        pca = PCA(n_components=1)
        pca.fit(data_scaled)
        
        # Get scores: in R psych::principal, scores are (scaled_data * loadings)
        # which is equivalent to pca.transform(data_scaled)
        scores = pca.transform(data_scaled).flatten()
        loadings = pca.components_[0]
        
        # Signage flipper
        # signage_flipper <- sign(sum(sign(fit$loadings) * expected_signs))
        signage_flipper = np.sign(np.sum(np.sign(loadings) * signs))
        
        # Standardize scores to mean 0, sd 1
        scores_std = (scores - np.mean(scores)) / np.std(scores)
        
        # Scale to mean 100, sd 20
        final_scores = scores_std * signage_flipper * 20 + 100
        
        res_col = np.full(len(df), np.nan)
        res_col[nonzero_hh] = final_scores
        results[name] = res_col
        
        loadings_dict[name] = pd.DataFrame({
            'factor': cols,
            'loading': loadings
        })

    if keep_indicators:
        final_df = pd.concat([results, indicators, df.drop(columns=['GEOID', 'NAME'], errors='ignore')], axis=1)
    else:
        final_df = results

    # Store loadings in metadata if needed (mimicking R attributes)
    final_df.attrs['loadings'] = loadings_dict
    
    return final_df

def get_total_hh_colname(df):
    possible_cols = ["P018001", "P015001", "P0030001", "B11005_001", "P16_001N"]
    intersect = [c for c in possible_cols if c in df.columns]
    if len(intersect) != 1:
        raise ValueError(f"Data must have exactly one of {possible_cols}")
    return intersect[0]

def calculate_indicators(df):
    if "B17010_001" in df.columns:
        return factors_from_acs(df)
    elif "P077001" in df.columns:
        return factors_from_2000_decennial(df)
    elif "P107A001" in df.columns:
        return factors_from_1990_decennial(df)
    else:
        raise ValueError("Data missing at least one variable necessary to calculate ADI.")

def factors_from_acs(df):
    data = df.copy()
    
    # Handle C24010_040 vs C24010_039
    if "C24010_040" in data.columns:
        if "C24010_039" in data.columns:
            warnings.warn("Both C24010_039 and C24010_040 present. Using C24010_039.")
        else:
            data = data.rename(columns={"C24010_040": "C24010_039"})
            
    # Handle median income
    if "B19013_001" in data.columns and "B19113_001" not in data.columns:
        warnings.warn("Median household income (B19013_001) used in place of family income (B19113_001).")
        data = data.rename(columns={"B19013_001": "B19113_001"})
        median_income_name = "medianHouseholdIncome"
    else:
        median_income_name = "medianFamilyIncome"

    # Decennial 2010/2020 replacement logic
    if "B25003_001" not in data.columns:
        if "H003002" in data.columns:
            data = data.rename(columns={
                "H003002": "B25003_001",
                "H014002": "B25003_002",
                "P020002": "B11005_002",
                "P020008": "B11005_005"
            })
        else:
            data = data.rename(columns={
                "H3_002N": "B25003_001",
                "H10_002N": "B25003_002"
            })
            data["B11005_005"] = data["P20_011N"] + data["P20_017N"]
            data["B11005_002"] = data["B11005_005"] + data["P20_003N"] + data["P20_006N"]

    # Handle B23025 vs B23001
    if "B23025_005" not in data.columns:
        male_unemp = ["B23001_008", "B23001_015", "B23001_022", "B23001_029", "B23001_036", 
                      "B23001_043", "B23001_050", "B23001_057", "B23001_064", "B23001_071", 
                      "B23001_076", "B23001_081", "B23001_086"]
        female_unemp = ["B23001_094", "B23001_101", "B23001_108", "B23001_115", "B23001_122", 
                        "B23001_129", "B23001_136", "B23001_143", "B23001_150", "B23001_157", 
                        "B23001_162", "B23001_167", "B23001_172"]
        data["B23025_005"] = data[male_unemp + female_unemp].sum(axis=1)
        
        male_labor = ["B23001_006", "B23001_013", "B23001_020", "B23001_027", "B23001_034", 
                      "B23001_041", "B23001_048", "B23001_055", "B23001_062", "B23001_069", 
                      "B23001_074", "B23001_079", "B23001_084"]
        female_labor = ["B23001_092", "B23001_099", "B23001_106", "B23001_113", "B23001_120", 
                        "B23001_127", "B23001_134", "B23001_141", "B23001_148", "B23001_155", 
                        "B23001_160", "B23001_165", "B23001_170"]
        data["B23025_003"] = data[male_labor + female_labor].sum(axis=1)

    # Education
    if "B15002_001" in data.columns:
        less9 = ["B15002_003", "B15002_020", "B15002_004", "B15002_021", 
                 "B15002_005", "B15002_022", "B15002_006", "B15002_023"]
        highschool = ["B15002_011", "B15002_028", "B15002_012", "B15002_029", 
                      "B15002_013", "B15002_030", "B15002_014", "B15002_031", 
                      "B15002_015", "B15002_032", "B15002_016", "B15002_033", 
                      "B15002_017", "B15002_034", "B15002_018", "B15002_035"]
        data["Nless9thgrade"] = data[less9].sum(axis=1)
        data["Nhighschoolup"] = data[highschool].sum(axis=1)
        data["B15003_001"] = data["B15002_001"]
    else:
        less9 = ["B15003_002", "B15003_003", "B15003_004", "B15003_005", "B15003_006", 
                 "B15003_007", "B15003_008", "B15003_009", "B15003_010", "B15003_011", "B15003_012"]
        highschool = ["B15003_017", "B15003_018", "B15003_019", "B15003_020", 
                      "B15003_021", "B15003_022", "B15003_023", "B15003_024", "B15003_025"]
        data["Nless9thgrade"] = data[less9].sum(axis=1)
        data["Nhighschoolup"] = data[highschool].sum(axis=1)

    # Indicator Calculations
    res = pd.DataFrame(index=data.index)
    res[median_income_name] = data["B19113_001"]
    res["medianMortgage"] = data["B25088_002"]
    res["medianRent"] = data["B25064_001"]
    res["medianHouseValue"] = data["B25077_001"]
    res["pctFamiliesInPoverty"] = data["B17010_002"] / data["B17010_001"]
    res["pctOwnerOccupiedHousing"] = data["B25003_002"] / data["B25003_001"]
    
    inc_over_50 = data[["B19001_011", "B19001_012", "B19001_013", "B19001_014", 
                        "B19001_015", "B19001_016", "B19001_017"]].sum(axis=1)
    res["ratioThoseMakingUnder10kToThoseMakingOver50k"] = np.log(100 * (data["B19001_002"] / inc_over_50))
    
    less150pov = data[["C17002_002", "C17002_003", "C17002_004", "C17002_005"]].sum(axis=1)
    res["pctPeopleLivingBelow150PctFederalPovertyLevel"] = less150pov / data["C17002_001"]
    
    res["pctHouseholdsWithChildrenThatAreSingleParent"] = data["B11005_005"] / data["B11005_002"]
    res["pctHouseholdsWithNoVehicle"] = (data["B25044_003"] + data["B25044_010"]) / data["B25044_001"]
    res["pctPeopleWithWhiteCollarJobs"] = (data["C24010_003"] + data["C24010_039"]) / data["C24010_001"]
    res["pctPeopleUnemployed"] = data["B23025_005"] / data["B23025_003"]
    res["pctPeopleWithAtLeastHSEducation"] = data["Nhighschoolup"] / data["B15003_001"]
    res["pctPeopleWithLessThan9thGradeEducation"] = data["Nless9thgrade"] / data["B15003_001"]
    
    crowded = data[["B25014_005", "B25014_006", "B25014_007", "B25014_011", "B25014_012", "B25014_013"]].sum(axis=1)
    res["pctHouseholdsWithOverOnePersonPerRoom"] = crowded / data["B25014_001"]
    
    # Replace non-finite with NaN
    res = res.replace([np.inf, -np.inf], np.nan)
    
    return res

def factors_from_2000_decennial(df):
    data = df.copy()
    res = pd.DataFrame(index=data.index)
    
    res["medianFamilyIncome"] = data["P077001"]
    res["medianMortgage"] = data["H091001"]
    res["medianRent"] = data["H063001"]
    res["medianHouseValue"] = data["H085001"]
    res["pctFamiliesInPoverty"] = data["P090002"] / data["P090001"]
    res["pctOwnerOccupiedHousing"] = data["H004002"] / data["H004001"]
    
    inc_over_50 = data[["P052011", "P052012", "P052013", "P052014", "P052015", "P052016", "P052017"]].sum(axis=1)
    res["ratioThoseMakingUnder10kToThoseMakingOver50k"] = np.log(100 * (data["P052002"] / inc_over_50))
    
    less150pov = data[["P088002", "P088003", "P088004", "P088005", "P088006"]].sum(axis=1)
    res["pctPeopleLivingBelow150PctFederalPovertyLevel"] = less150pov / data["P088001"]
    
    res["pctHouseholdsWithChildrenThatAreSingleParent"] = data["P019005"] / data["P019002"]
    res["pctHouseholdsWithNoVehicle"] = (data["H044003"] + data["H044010"]) / data["H044001"]
    res["pctPeopleWithWhiteCollarJobs"] = (data["P050003"] + data["P050050"]) / data["P050001"]
    
    unemp_labor = data["P043007"] + data["P043014"]
    all_labor = data["P043005"] + data["P043012"]
    res["pctPeopleUnemployed"] = unemp_labor / all_labor
    
    highschool = data[["P037011", "P037028", "P037012", "P037029", "P037013", "P037030", 
                       "P037014", "P037031", "P037015", "P037032", "P037016", "P037033", 
                       "P037017", "P037034", "P037018", "P037035"]].sum(axis=1)
    res["pctPeopleWithAtLeastHSEducation"] = highschool / data["P037001"]
    
    less9 = data[["P037003", "P037020", "P037004", "P037021", "P037005", "P037022", "P037006", "P037023"]].sum(axis=1)
    res["pctPeopleWithLessThan9thGradeEducation"] = less9 / data["P037001"]
    
    crowded = data[["H020005", "H020006", "H020007", "H020011", "H020012", "H020013"]].sum(axis=1)
    res["pctHouseholdsWithOverOnePersonPerRoom"] = crowded / data["H020001"]
    
    return res.replace([np.inf, -np.inf], np.nan)

def factors_from_1990_decennial(df):
    data = df.copy()
    res = pd.DataFrame(index=data.index)
    
    res["medianFamilyIncome"] = data["P107A001"]
    res["medianMortgage"] = data["H052A001"]
    res["medianRent"] = data["H043A001"]
    res["medianHouseValue"] = data["H023B001"]
    
    pov_cols = ["P1230013", "P1230014", "P1230015", "P1230016", "P1230017", "P1230018", 
                "P1230019", "P1230020", "P1230021", "P1230022", "P1230023", "P1230024"]
    res["pctFamiliesInPoverty"] = data[pov_cols].sum(axis=1) / data["P0040001"]
    res["pctOwnerOccupiedHousing"] = data["H0030001"] / data["H0020001"]
    
    inc_under_10 = data["P0800001"] + data["P0800002"]
    inc_over_50 = data[["P0800019", "P0800020", "P0800021", "P0800022", "P0800023", "P0800024", "P0800025"]].sum(axis=1)
    res["ratioThoseMakingUnder10kToThoseMakingOver50k"] = np.log(100 * inc_under_10 / inc_over_50)
    
    less150pov = data[["P1210001", "P1210002", "P1210003", "P1210004", "P1210005"]].sum(axis=1)
    total_pov = less150pov + data[["P1210006", "P1210007", "P1210008", "P1210009"]].sum(axis=1)
    res["pctPeopleLivingBelow150PctFederalPovertyLevel"] = less150pov / total_pov
    
    one_parent = data["P0180002"] + data["P0180003"]
    all_children = one_parent + data[["P0180001", "P0180004", "P0180005"]].sum(axis=1)
    res["pctHouseholdsWithChildrenThatAreSingleParent"] = one_parent / all_children
    
    no_vehicle = data["H0410001"] + data["H0410003"]
    total_vehicle = no_vehicle + data["H0410002"] + data["H0410004"]
    res["pctHouseholdsWithNoVehicle"] = no_vehicle / total_vehicle
    
    res["pctPeopleWithWhiteCollarJobs"] = (data["P0780001"] + data["P0780002"]) / (data["P0700002"] + data["P0700006"])
    
    unemp = data["P0700003"] + data["P0700007"]
    labor = unemp + data["P0700002"] + data["P0700006"]
    res["pctPeopleUnemployed"] = unemp / labor
    
    highschool = data[["P0570003", "P0570004", "P0570005", "P0570006", "P0570007"]].sum(axis=1)
    total_edu = highschool + data["P0570001"] + data["P0570002"]
    res["pctPeopleWithAtLeastHSEducation"] = highschool / total_edu
    res["pctPeopleWithLessThan9thGradeEducation"] = data["P0570001"] / total_edu
    
    crowded = data[["H0210003", "H0210004", "H0210005"]].sum(axis=1)
    total_crowd = crowded + data["H0210001"] + data["H0210002"]
    res["pctHouseholdsWithOverOnePersonPerRoom"] = crowded / total_crowd
    
    return res.replace([np.inf, -np.inf], np.nan)
