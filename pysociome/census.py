
import requests
import pandas as pd
import warnings

class CensusClient:
    """
    A simple client for fetching data from the US Census API.
    """
    BASE_URL = "https://api.census.gov/data"

    def __init__(self, key=None):
        if key is None:
            # Try to load from .env file in common locations
            key = self._load_key_from_env()
        self.key = key

    def _load_key_from_env(self):
        """Helper to find and read .env file for Census_API_KEY"""
        import os
        search_paths = [
            os.getcwd(), 
            os.path.dirname(os.getcwd()),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ]
        for path in search_paths:
            env_path = os.path.join(path, '.env')
            if os.path.exists(env_path):
                try:
                    with open(env_path, 'r') as f:
                        for line in f:
                            if 'Census_API_KEY' in line and '=' in line:
                                return line.split('=')[1].strip().strip('"').strip("'")
                except Exception:
                    pass
        return None

    def get_acs(self, year, variables, geography, state=None, county=None, survey="acs5"):
        """
        Fetch data from the American Community Survey (ACS).
        """
        url = f"{self.BASE_URL}/{year}/acs/{survey}"
        
        # Append 'E' to ACS variables if not present (Estimates)
        api_vars = []
        for v in variables:
            if "_" in v and not v.endswith(("E", "M", "A")):
                api_vars.append(v + "E")
            else:
                api_vars.append(v)

        params = {
            "get": "NAME," + ",".join(api_vars),
            "for": geography
        }
        
        if state:
            params["in"] = f"state:{state}"
            if county:
                params["in"] += f" county:{county}"
                
        if self.key:
            params["key"] = self.key
            
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Census API error: {response.status_code} - {response.text}")
            
        data = response.json()
        headers = data[0]
        df = pd.DataFrame(data[1:], columns=headers)
        
        # Map back API names to requested names
        name_map = dict(zip(api_vars, variables))
        df = df.rename(columns=name_map)
        
        # In ACS, GEOID is often split into state, county, tract, etc.
        # We need to construct a unified GEOID column.
        geo_cols = [c for c in df.columns if c not in variables and c != "NAME"]
        # Order of geo_cols matters for GEOID construction
        # state(2) + county(3) + tract(6) + block_group(1)
        
        # Simple heuristic to construct GEOID
        if "state" in df.columns:
            geoid = df["state"]
            if "county" in df.columns:
                geoid += df["county"]
                if "tract" in df.columns:
                    geoid += df["tract"]
                    if "block group" in df.columns:
                        geoid += df["block group"]
            df["GEOID"] = geoid
            
        # Convert variable columns to numeric
        for var in variables:
            df[var] = pd.to_numeric(df[var], errors='coerce')
            
        return df

    def get_decennial(self, year, variables, geography, state=None, county=None, sumfile="sf1"):
        """
        Fetch data from the Decennial Census.
        """
        if year == 2020:
            url = f"{self.BASE_URL}/{year}/dec/dhc"
        else:
            url = f"{self.BASE_URL}/{year}/dec/{sumfile}"
            
        params = {
            "get": "NAME," + ",".join(variables),
            "for": geography
        }
        
        if state:
            params["in"] = f"state:{state}"
            if county:
                params["in"] += f" county:{county}"
                
        if self.key:
            params["key"] = self.key
            
        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Census API error: {response.status_code} - {response.text}")
            
        data = response.json()
        headers = data[0]
        df = pd.DataFrame(data[1:], columns=headers)
        
        if "state" in df.columns:
            geoid = df["state"]
            if "county" in df.columns:
                geoid += df["county"]
                if "tract" in df.columns:
                    geoid += df["tract"]
                    if "block group" in df.columns:
                        geoid += df["block group"]
            df["GEOID"] = geoid
            
        for var in variables:
            df[var] = pd.to_numeric(df[var], errors='coerce')
            
        return df

def get_adi(geography, year, state=None, county=None, dataset="acs5", key=None, **kwargs):
    """
    Main entry point to fetch data and calculate ADI.
    """
    client = CensusClient(key=key)
    
    # This would normally need the logic from get_tidycensus.R to select variables
    # For now, let's assume we are doing ACS 5-year for recent years.
    
    # Simplified variable selection (would need to use pysociome.variables)
    # ... (logic to get variables based on year and dataset)
    
    # For demonstration, let's just use a placeholder
    warnings.warn("get_adi is a simplified version in this translation.")
    
    # In a real implementation, we'd call calculate_adi(raw_data)
    pass
