# main.py
import os
import datetime
import pandas as pd
import requests
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, List, Tuple, Optional

# --- Oracle Client Initialization (Recommended for Thick Mode) ---
try:
    # If lib_dir is not specified, it will look for the client in the system path.
    import oracledb
    oracledb.init_oracle_client()
    print("Oracle Client initialized successfully (Thick Mode).")
except Exception as e:
    print(f"Could not initialize Oracle Client in Thick Mode: {e}")
    print("Continuing in Thin Mode. If you encounter connection issues, ensure Oracle Instant Client is installed.")


# --- Configuration ---
# It's recommended to use environment variables for security.
# Example DSN: your_host:1521/your_sid
SOURCE_DB_CONFIG = {
    'user': 'your_source_user',
    'password': 'your_source_password',
    'dsn': 'your_source_host:1521/your_source_sid'
}

DW_DB_CONFIG = {
    'user': 'your_dw_user',
    'password': 'your_dw_password',
    'dsn': 'your_dw_host:1521/your_dw_sid'
}

TELEGRAM_CONFIG = {
    'bot_token': os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN'),
    'chat_id': os.environ.get('TELEGRAM_CHAT_ID', 'YOUR_TELEGRAM_CHAT_ID')
}


# --- Telegram Alerting Functions ---
def send_telegram_alert(message: str, config: Dict[str, str]):
    """Sends a text message to a Telegram bot."""
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token or not chat_id or "YOUR_TELEGRAM_CHAT_ID" in chat_id:
        print("\n⚠️ Telegram alert skipped: Bot token or Chat ID not configured.")
        return
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        print("\n✅ Successfully sent Telegram alert.")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED to send Telegram alert: {e}")

def send_telegram_document(file_path: str, caption: str, config: Dict[str, str]):
    """Sends a document/file to a Telegram bot."""
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token or not chat_id or "YOUR_TELEGRAM_CHAT_ID" in chat_id:
        print("\n⚠️ Telegram document skipped: Bot token or Chat ID not configured.")
        return
    if not os.path.exists(file_path):
        print(f"\n❌ FAILED to send Telegram document: File not found at {file_path}")
        return

    api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
    try:
        with open(file_path, 'rb') as doc:
            files = {'document': doc}
            response = requests.post(api_url, data=payload, files=files, timeout=30)
            response.raise_for_status()
            print(f"\n✅ Successfully sent document '{os.path.basename(file_path)}' to Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED to send Telegram document: {e}")
        if response:
             print(f"   - Response: {response.text}")


# --- Database Functions ---
def get_db_engine(config: Dict[str, Any], db_name: str):
    """Creates a SQLAlchemy engine for the Oracle database."""
    try:
        conn_string = f"oracle+oracledb://{config['user']}:{config['password']}@{config['dsn']}"
        engine = create_engine(conn_string)
        with engine.connect():
            print(f"Successfully created SQLAlchemy engine for {db_name} DSN: {config['dsn']}")
        return engine
    except Exception as e:
        print(f"Error creating SQLAlchemy engine for {db_name} DSN: {config.get('dsn')}.")
        print(e)
        return None

def extract_data_as_dataframe(query: str, engine) -> pd.DataFrame:
    """Extracts data from the database using a given query and a SQLAlchemy engine."""
    if engine is None: return pd.DataFrame()
    try:
        print(f"Executing query: {query}")
        df = pd.read_sql(query, engine)
        # Standardize column names to lowercase for easier comparison
        df.columns = [col.lower() for col in df.columns]
        print(f"Successfully extracted {len(df)} rows.")
        return df
    except Exception as e:
        print(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

def load_data_to_dw(engine, dataframe: pd.DataFrame, table_name: str, if_exists='append'):
    """Loads a pandas DataFrame into a specified table in the data warehouse."""
    if engine is None:
        print("Loading failed: Data warehouse engine is not available.")
        return
    if dataframe.empty:
        print("No data to load. The DataFrame is empty.")
        return
    try:
        print(f"Loading {len(dataframe)} rows into table: {table_name}...")
        dataframe.to_sql(table_name, con=engine, if_exists=if_exists, index=False, chunksize=1000)
        print(f"Successfully loaded data into {table_name}.")
    except Exception as e:
        print(f"Error loading data into {table_name}: {e}")


# --- Validation Test Functions ---
def test_row_count_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, test_name: str) -> bool:
    """Test Case 1: Validates if the number of rows match."""
    print("\n--- Test 1: Row Count Validation ---")
    source_rows, dest_rows = len(source_df), len(dest_df)
    print(f"Source row count: {source_rows}, Destination row count: {dest_rows}")
    if source_rows == dest_rows:
        print("✅ PASSED: Row counts match.")
        return True
    else:
        print(f"❌ FAILED: Row counts do not match. Difference: {abs(source_rows - dest_rows)}")
        return False

def test_data_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, primary_key_cols: List[str], test_name: str) -> Tuple[bool, Optional[str]]:
    """Test Case 2: Validates if data values match and exports detailed mismatches."""
    print("\n--- Test 2: Data Value Validation ---")
    if not primary_key_cols:
        print("⚠️ SKIPPED: Primary key is required for data validation.")
        return True, None # Skip if no PK is defined

    # Ensure columns are in the same order and exist
    if not sorted(list(source_df.columns)) == sorted(list(dest_df.columns)):
        print("❌ FAILED: Column schemas do not match. Cannot perform data validation.")
        return False, None
    dest_df = dest_df[source_df.columns]

    try:
        # Set index for efficient comparison
        source_df = source_df.set_index(primary_key_cols).sort_index()
        dest_df = dest_df.set_index(primary_key_cols).sort_index()
    except KeyError as e:
        print(f"❌ FAILED: Primary key column '{e}' not found in one of the DataFrames.")
        return False, None

    # Find rows that are not in the destination (missing) or source (extra)
    missing_rows = source_df[~source_df.index.isin(dest_df.index)]
    extra_rows = dest_df[~dest_df.index.isin(source_df.index)]

    # Find rows with different values
    common_keys = source_df.index.intersection(dest_df.index)
    source_common = source_df.loc[common_keys]
    dest_common = dest_df.loc[common_keys]
    
    # Compare only non-identical rows
    comparison = source_common.compare(dest_common, align_axis=1, keep_equal=False).dropna(how='all')
    
    if missing_rows.empty and extra_rows.empty and comparison.empty:
        print("✅ PASSED: All data values match.")
        return True, None
    else:
        print("❌ FAILED: Data mismatches found.")
        mismatch_filename = f'data_mismatches_{test_name.replace(" ", "_").lower()}.xlsx'
        with pd.ExcelWriter(mismatch_filename) as writer:
            if not comparison.empty:
                print(f" - Found {len(comparison)} rows with differing values.")
                comparison.to_excel(writer, sheet_name='Value_Differences')
            if not missing_rows.empty:
                print(f" - Found {len(missing_rows)} rows missing from destination.")
                missing_rows.to_excel(writer, sheet_name='Missing_in_Destination')
            if not extra_rows.empty:
                print(f" - Found {len(extra_rows)} extra rows in destination.")
                extra_rows.to_excel(writer, sheet_name='Extra_in_Destination')
        print(f"   - Detailed mismatch report saved to: {mismatch_filename}")
        return False, mismatch_filename


# --- Main ETL and Validation Process ---
def run_etl_and_validation(test_name: str, source_table: str, dest_table: str, primary_key: List[str], if_exists='replace'):
    """
    Executes a full ETL and UAT test case.
    """
    print(f"\n=============== Starting ETL & Validation: {test_name} ===============")
    start_time = datetime.datetime.now()
    
    source_engine = get_db_engine(SOURCE_DB_CONFIG, "Source")
    dest_engine = get_db_engine(DW_DB_CONFIG, "Destination")
    
    if not (source_engine and dest_engine):
        print("\nCould not create database engines. Process aborted.")
        return

    # 1. EXTRACT
    print("\n--- Step 1: Extracting data from Source ---")
    source_query = f"SELECT * FROM {source_table}"
    source_df = extract_data_as_dataframe(source_query, source_engine)

    # 2. LOAD
    print("\n--- Step 2: Loading data to Destination ---")
    load_data_to_dw(dest_engine, source_df, dest_table, if_exists=if_exists)

    # 3. VALIDATE
    print("\n--- Step 3: Validating loaded data ---")
    print("Re-fetching data for validation...")
    dest_query = f"SELECT * FROM {dest_table}"
    dest_df = extract_data_as_dataframe(dest_query, dest_engine)

    # Run tests
    row_count_passed = test_row_count_match(source_df, dest_df, test_name)
    data_match_passed, mismatch_file = test_data_match(source_df, dest_df, primary_key, test_name)
    
    # 4. REPORT
    print("\n--- Step 4: Generating and Sending Report ---")
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    overall_status = "PASS ✅" if row_count_passed and data_match_passed else "FAIL ❌"

    summary_report = (
        f"🚨 *ETL & Validation Report: {test_name}* 🚨\n\n"
        f"*Overall Status: {overall_status}*\n\n"
        f"*--- Execution Summary ---*\n"
        f"Start Time: `{start_time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"End Time:   `{end_time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"Duration:   `{str(duration).split('.')[0]}`\n\n"
        f"*--- Data Profile ---*\n"
        f"Source (`{source_table}`): `{len(source_df)} rows`\n"
        f"Destination (`{dest_table}`): `{len(dest_df)} rows`\n\n"
        f"*--- Validation Results ---*\n"
        f"Row Count Match: *{'PASS ✅' if row_count_passed else 'FAIL ❌'}*\n"
        f"Data Value Match:  *{'PASS ✅' if data_match_passed else 'FAIL ❌'}*"
    )
    
    send_telegram_alert(summary_report, TELEGRAM_CONFIG)
    if mismatch_file:
        caption = f"🔍 Data Mismatch Report for *{test_name}*"
        send_telegram_document(mismatch_file, caption, TELEGRAM_CONFIG)

    source_engine.dispose()
    dest_engine.dispose()
    print("\nSQLAlchemy engines disposed.")
    print(f"=============== Finished: {test_name} ===============\n")


if __name__ == "__main__":
    # --- CONFIGURE AND RUN YOUR JOB HERE ---
    run_etl_and_validation(
        test_name="Sales Data ETL",
        source_table="sales_data",      # Table name in the source database
        dest_table="fact_sales",        # Table name in the destination DW
        primary_key=['sale_id', 'product_id'], # List of column(s) that form the unique key
        if_exists='replace'             # 'replace' for full reloads, 'append' for incremental
    )
