import pandas as pd
import oracledb  # Using the official Oracle Database driver for Python
from typing import Dict, Any, List

# --- Oracle Client Initialization (Thick Mode) ---
# The DPY-3012 error indicates the database's national character set is not supported
# by python-oracledb in its default "Thin" mode.
# To resolve this, we enable "Thick" mode by initializing the Oracle Client.
#
# IMPORTANT: You must have Oracle Instant Client installed and its path
# configured for this to work. Download it from the Oracle website.
# If the client libraries are not in your system's path, you must provide the location.
# Example: oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_21_13")
try:
    # If lib_dir is not specified, it will look for the client in the system path.
    oracledb.init_oracle_client()
except oracledb.DatabaseError as e:
    print("Error initializing Oracle Client. Please ensure Oracle Instant Client is installed and configured correctly.")
    print(e)
    # Exit if the client can't be initialized, as connections will likely fail.
    exit()

SOURCE_CONFIG = {
    "user": "dguser",
    "password": "Dguser#1234",
    "dsn": "172.19.128.243:1521/custdm" 
}

DESTINATION_CONFIG = {
    "user": "dguser",
    "password": "Dguser#1234",
    "dsn": "172.19.128.243:1521/custdm"
}

# --- Database Connection ---

def get_db_connection(config: Dict[str, Any]):
    """
    Establishes a connection to the Oracle database using the provided configuration.
    
    Args:
        config: A dictionary containing database connection parameters.
        
    Returns:
        A database connection object.
    """
    try:
        conn = oracledb.connect(**config)
        print(f"Successfully connected to Oracle database using DSN: {config.get('dsn')}")
        return conn
    except oracledb.DatabaseError as e:
        print(f"Error connecting to Oracle database: {config.get('dsn')}. Please check connection details.")
        print(e)
        return None

def fetch_data_as_dataframe(query: str, conn) -> pd.DataFrame:
    """
    Fetches data from the database using a given query and returns it as a pandas DataFrame.
    
    Args:
        query: The SQL query to execute.
        conn: The database connection object.
        
    Returns:
        A pandas DataFrame containing the query results.
    """
    if conn is None:
        return pd.DataFrame()
    try:
        # pandas can read SQL directly into a DataFrame, which is often simpler
        df = pd.read_sql(query, conn)
        # pd.read_sql automatically handles column names. Column names in Oracle are often uppercase.
        # For consistency, we can convert them to lowercase.
        df.columns = [col.lower() for col in df.columns]
        return df
    except Exception as e:
        print(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

# --- Test Scenarios ---

def test_row_count_match(source_df: pd.DataFrame, dest_df: pd.DataFrame) -> bool:
    """
    Test Case 1: Validates if the number of rows match between source and destination.
    """
    print("\n--- Test 1: Row Count Validation ---")
    source_rows = len(source_df)
    dest_rows = len(dest_df)
    
    print(f"Source row count: {source_rows}")
    print(f"Destination row count: {dest_rows}")
    
    if source_rows == dest_rows:
        print("✅ PASSED: Row counts match.")
        return True
    else:
        print(f"❌ FAILED: Row counts do not match. Difference: {abs(source_rows - dest_rows)}")
        return False

def test_column_match(source_df: pd.DataFrame, dest_df: pd.DataFrame) -> bool:
    """
    Test Case 2: Validates if the column names and count match between source and destination.
    """
    print("\n--- Test 2: Column Schema Validation ---")
    source_cols = sorted(list(source_df.columns))
    dest_cols = sorted(list(dest_df.columns))
    
    print(f"Source columns ({len(source_cols)}): {source_cols}")
    print(f"Destination columns ({len(dest_cols)}): {dest_cols}")
    
    if source_cols == dest_cols:
        print("✅ PASSED: Column names and count match.")
        return True
    else:
        print("❌ FAILED: Columns do not match.")
        missing_in_dest = set(source_cols) - set(dest_cols)
        extra_in_dest = set(dest_cols) - set(source_cols)
        if missing_in_dest:
            print(f"   - Columns missing in destination: {list(missing_in_dest)}")
        if extra_in_dest:
            print(f"   - Extra columns in destination: {list(extra_in_dest)}")
        return False

def test_data_type_match(source_df: pd.DataFrame, dest_df: pd.DataFrame) -> bool:
    """
    Test Case 3: Validates if the data types of corresponding columns match.
    """
    print("\n--- Test 3: Data Type Validation ---")
    source_types = source_df.dtypes.to_dict()
    dest_types = dest_df.dtypes.to_dict()

    mismatched_types = {}
    # Assuming columns have already been validated by test_column_match
    for col, s_type in source_types.items():
        d_type = dest_types.get(col)
        # Note: Pandas type inference can be complex. For instance, Oracle's NUMBER
        # could become int64 or float64. This test performs a direct dtype check.
        # For a more lenient check, you could group numeric types.
        if str(s_type) != str(d_type):
            mismatched_types[col] = {'source': str(s_type), 'destination': str(d_type)}

    if not mismatched_types:
        print("✅ PASSED: Data types are consistent across all columns.")
        return True
    else:
        print("❌ FAILED: Data type mismatches found.")
        for col, types in mismatched_types.items():
            print(f"   - Column '{col}': Source type is {types['source']}, Destination type is {types['destination']}")
        return False

def test_data_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, primary_key_cols: List[str]) -> bool:
    """
    Test Case 4: Validates if the data values for each row and column match.
    """
    print("\n--- Test 4: Data Value Validation ---")
    
    if source_df.empty or dest_df.empty:
        print("⚠️ SKIPPED: One or both DataFrames are empty. Cannot perform data validation.")
        return False

    if not sorted(list(source_df.columns)) == sorted(list(dest_df.columns)):
        print("❌ FAILED: Column schemas do not match. Cannot perform data validation.")
        return False
    
    dest_df = dest_df[source_df.columns]

    try:
        source_df_sorted = source_df.sort_values(by=primary_key_cols).reset_index(drop=True)
        dest_df_sorted = dest_df.sort_values(by=primary_key_cols).reset_index(drop=True)
    except KeyError as e:
        print(f"❌ FAILED: Primary key column '{e}' not found in one of the DataFrames.")
        return False

    # Convert object columns to string to avoid comparison errors on mixed types
    for col in source_df_sorted.columns:
        if source_df_sorted[col].dtype == 'object':
            source_df_sorted[col] = source_df_sorted[col].astype(str).fillna('')
        if dest_df_sorted[col].dtype == 'object':
            dest_df_sorted[col] = dest_df_sorted[col].astype(str).fillna('')

    try:
        diff = source_df_sorted.compare(dest_df_sorted)
        
        if diff.empty:
            print("✅ PASSED: All data values match between source and destination.")
            return True
        else:
            print(f"❌ FAILED: Data mismatch found in {len(diff)} row(s).")
            print("   - Displaying first 5 differences:")
            print(diff.head())
            return False
            
    except Exception as e:
        print(f"❌ FAILED: An error occurred during data comparison.")
        print(f"   - Error: {e}")
        return False

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting ETL Test Automation Suite for Oracle...")
    
    source_conn = get_db_connection(SOURCE_CONFIG)
    dest_conn = get_db_connection(DESTINATION_CONFIG)
    
    if source_conn and dest_conn:
        
        # IMPORTANT: Replace with your actual table names and queries.
        source_query = "SELECT ACCOUNT_ID, ACCOUNT_NAME FROM ETL_USER.DIM_ACCOUNT"
        dest_query = "SELECT ACCOUNT_ID, ACCOUNT_NAME FROM ETL_USER.DIM_ACCOUNT"
        
        print("\nFetching data from source...")
        source_dataframe = fetch_data_as_dataframe(source_query, source_conn)
        
        print("Fetching data from destination...")
        dest_dataframe = fetch_data_as_dataframe(dest_query, dest_conn)

        if not source_dataframe.empty and not dest_dataframe.empty:
            row_count_passed = test_row_count_match(source_dataframe, dest_dataframe)
            column_match_passed = test_column_match(source_dataframe, dest_dataframe)
            
            # Only proceed with data-level tests if columns match
            if column_match_passed:
                dtype_match_passed = test_data_type_match(source_dataframe, dest_dataframe)
                
                # IMPORTANT: Specify the primary key column(s) in lowercase.
                primary_key = ['account_id'] 
                data_match_passed = test_data_match(source_dataframe, dest_dataframe, primary_key)
            else:
                # If columns don't match, skip the subsequent tests
                print("\n⚠️ SKIPPED: Data Type and Data Value tests skipped due to column mismatch.")
                dtype_match_passed = False
                data_match_passed = False

            print("\n--- Test Summary ---")
            print(f"Row Count Test:      {'PASS' if row_count_passed else 'FAIL'}")
            print(f"Column Match Test:   {'PASS' if column_match_passed else 'FAIL'}")
            print(f"Data Type Match Test:{'PASS' if dtype_match_passed else 'FAIL'}")
            print(f"Data Value Match Test: {'PASS' if data_match_passed else 'FAIL'}")

        else:
            print("\nCould not perform tests as one or both dataframes are empty.")

        source_conn.close()
        dest_conn.close()
        print("\nDatabase connections closed.")
        
    print("\nETL Test Automation Suite finished.")
