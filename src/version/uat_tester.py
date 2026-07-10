# uat_tester.py: Core library for ETL UAT testing.
import pandas as pd
import oracledb
from sqlalchemy import create_engine
from typing import Dict, Any, List, Tuple, Optional
import requests
import os
import datetime

# --- Oracle Client Initialization (Thick Mode) ---
try:
    # If lib_dir is not specified, it will look for the client in the system path.
    oracledb.init_oracle_client()
except oracledb.DatabaseError as e:
    print(f"Error initializing Oracle Client: {e}")
    print("Please ensure Oracle Instant Client is installed and configured correctly.")
    exit()

# --- Telegram Alerting ---
def send_telegram_alert(message: str, config: Dict[str, str]):
    """Sends a text message to a Telegram bot."""
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token:
        print("\n⚠️ Telegram alert skipped: Bot token not configured.")
        return
    if not chat_id or "YOUR_TELEGRAM_CHAT_ID" in chat_id:
        print("\n⚠️ Telegram alert skipped: Chat ID not configured.")
        return

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
    proxies = {"http": None, "https": None}
    try:
        response = requests.post(api_url, json=payload, proxies=proxies, timeout=10)
        response.raise_for_status()
        print("\n✅ Successfully sent Telegram alert.")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED to send Telegram alert: {e}")

def send_telegram_document(file_path: str, caption: str, config: Dict[str, str]):
    """Sends a document/file to a Telegram bot."""
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token:
        print("\n⚠️ Telegram document skipped: Bot token not configured.")
        return
    if not chat_id or "YOUR_TELEGRAM_CHAT_ID" in chat_id:
        print("\n⚠️ Telegram document skipped: Chat ID not configured.")
        return
    if not os.path.exists(file_path):
        print(f"\n❌ FAILED to send Telegram document: File not found at {file_path}")
        return

    api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    payload = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
    proxies = {"http": None, "https": None}
    try:
        with open(file_path, 'rb') as doc:
            files = {'document': doc}
            # Use 'data' for payload and 'files' for the file upload
            response = requests.post(api_url, data=payload, files=files, proxies=proxies, timeout=30)
            response.raise_for_status()
        print(f"\n✅ Successfully sent document '{os.path.basename(file_path)}' to Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED to send Telegram document: {e}")
        print(f"  - Response: {response.text}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred while sending document: {e}")


# --- Database Connection ---
def get_db_engine(config: Dict[str, Any], db_name: str):
    """Creates a SQLAlchemy engine for the Oracle database."""
    try:
        user = config.get('user')
        password = config.get('password')
        dsn = config.get('dsn')

        if not all([user, password, dsn]):
            print(f"Error: {db_name} database configuration is missing required fields.")
            return None

        conn_string = f"oracle+oracledb://{user}:{password}@{dsn}"
        engine = create_engine(conn_string)
        with engine.connect() as conn:
            print(f"Successfully created SQLAlchemy engine for {db_name} DSN: {dsn}")
        return engine
    except Exception as e:
        print(f"Error creating SQLAlchemy engine for {db_name} DSN: {config.get('dsn')}.")
        print(e)
        return None

def fetch_data_as_dataframe(query: str, engine) -> pd.DataFrame:
    """Fetches data from the database using a given query and a SQLAlchemy engine."""
    if engine is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql(query, engine)
        df.columns = [col.lower() for col in df.columns]
        return df
    except Exception as e:
        print(f"An error occurred while fetching data: {e}")
        return pd.DataFrame()

# --- Test Scenarios ---
def test_row_count_match(source_df: pd.DataFrame, dest_df: pd.DataFrame) -> bool:
    """Test Case 1: Validates if the number of rows match."""
    print("\n--- Test 1: Row Count Validation ---")
    source_rows, dest_rows = len(source_df), len(dest_df)
    print(f"Source row count: {source_rows}")
    print(f"Destination row count: {dest_rows}")
    if source_rows == dest_rows:
        print("✅ PASSED: Row counts match.")
        return True
    else:
        print(f"❌ FAILED: Row counts do not match. Difference: {abs(source_rows - dest_rows)}")
        return False

def test_column_match(source_df: pd.DataFrame, dest_df: pd.DataFrame) -> bool:
    """Test Case 2: Validates if the column names and count match."""
    print("\n--- Test 2: Column Schema Validation ---")
    source_cols, dest_cols = sorted(list(source_df.columns)), sorted(list(dest_df.columns))
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
            print(f"  - Columns missing in destination: {list(missing_in_dest)}")
        if extra_in_dest:
            print(f"  - Extra columns in destination: {list(extra_in_dest)}")
        return False

def test_data_type_match(source_df: pd.DataFrame, dest_df: pd.DataFrame) -> bool:
    """Test Case 3: Validates if the data types of corresponding columns match."""
    print("\n--- Test 3: Data Type Validation ---")
    source_types, dest_types = source_df.dtypes.to_dict(), dest_df.dtypes.to_dict()
    mismatched_types = {}
    for col, s_type in source_types.items():
        d_type = dest_types.get(col)
        if str(s_type) != str(d_type):
            mismatched_types[col] = {'source': str(s_type), 'destination': str(d_type)}
    if not mismatched_types:
        print("✅ PASSED: Data types are consistent across all columns.")
        return True
    else:
        print("❌ FAILED: Data type mismatches found.")
        for col, types in mismatched_types.items():
            print(f"  - Column '{col}': Source type is {types['source']}, Destination type is {types['destination']}")
        return False

def test_data_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, primary_key_cols: List[str], test_name: str) -> Tuple[bool, Optional[str]]:
    """
    Test Case 4: Validates if data values match and exports mismatches.
    Returns a tuple: (bool: pass/fail, str: path to mismatch file or None).
    """
    print("\n--- Test 4: Data Value Validation ---")
    if source_df.empty or dest_df.empty:
        print("⚠️ SKIPPED: One or both DataFrames are empty.")
        return False, None
    if not sorted(list(source_df.columns)) == sorted(list(dest_df.columns)):
        print("❌ FAILED: Column schemas do not match. Cannot perform data validation.")
        return False, None
    
    dest_df = dest_df[source_df.columns]
    try:
        source_df_sorted = source_df.sort_values(by=primary_key_cols).reset_index(drop=True)
        dest_df_sorted = dest_df.sort_values(by=primary_key_cols).reset_index(drop=True)
    except KeyError as e:
        print(f"❌ FAILED: Primary key column '{e}' not found in one of the DataFrames.")
        return False, None

    for col in source_df_sorted.columns:
        if 'datetime' in str(source_df_sorted[col].dtype):
             source_df_sorted[col] = pd.to_datetime(source_df_sorted[col]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        if 'datetime' in str(dest_df_sorted[col].dtype):
             dest_df_sorted[col] = pd.to_datetime(dest_df_sorted[col]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')

        if source_df_sorted[col].dtype == 'object':
            source_df_sorted[col] = source_df_sorted[col].astype(str).str.strip().fillna('')
        if dest_df_sorted[col].dtype == 'object':
            dest_df_sorted[col] = dest_df_sorted[col].astype(str).str.strip().fillna('')

    try:
        diff = source_df_sorted.compare(dest_df_sorted, align_axis=0)
        if diff.empty:
            print("✅ PASSED: All data values match between source and destination.")
            return True, None
        else:
            print(f"❌ FAILED: Data mismatch found in {len(diff)} row(s).")
            mismatch_filename = f'mismatches_{test_name.replace(" ", "_").lower()}.csv'
            try:
                # Get the primary keys for the mismatched rows using the diff index
                pk_df = source_df_sorted.loc[diff.index, primary_key_cols]
                # Join the primary keys with the difference dataframe
                diff_with_pk = pk_df.join(diff)
                diff_with_pk.to_csv(mismatch_filename, index=False)
                print(f"  - ✅ Full mismatch report saved to: {mismatch_filename}")
                return False, mismatch_filename # Return status and the filename
            except Exception as e:
                print(f"  - ❌ FAILED to save mismatch report: {e}")
                return False, None # Failed to save, so no file to send
    except Exception as e:
        print(f"❌ FAILED: An error occurred during data comparison: {e}")
        return False, None


# --- Main Execution Function ---
def run_test(test_name: str, source_config: dict, dest_config: dict, telegram_config: dict, source_query: str, dest_query: str, primary_key: list) -> bool:
    """
    Executes a full UAT test case and returns True for overall pass, False for fail.
    Sends a summary report and any mismatch files to Telegram.
    """
    print(f"=============== Starting Test: {test_name} ===============")
    start_time = datetime.datetime.now()
    
    source_engine = get_db_engine(source_config, "Source")
    dest_engine = get_db_engine(dest_config, "Destination")
    
    test_passed = False # Default to fail
    mismatch_file_path = None # To store the path of the generated mismatch CSV
    
    if source_engine and dest_engine:
        print("\nFetching data from source...")
        source_dataframe = fetch_data_as_dataframe(source_query, source_engine)
        
        print("Fetching data from destination...")
        dest_dataframe = fetch_data_as_dataframe(dest_query, dest_engine)

        if not source_dataframe.empty and not dest_dataframe.empty:
            row_count_passed = test_row_count_match(source_dataframe, dest_dataframe)
            column_match_passed = test_column_match(source_dataframe, dest_dataframe)
            
            if column_match_passed:
                dtype_match_passed = test_data_type_match(source_dataframe, dest_dataframe)
                # Capture both the pass/fail status and the potential mismatch file path
                data_match_passed, mismatch_file_path = test_data_match(source_dataframe, dest_dataframe, primary_key, test_name)
            else:
                print("\n⚠️ SKIPPED: Data Type and Data Value tests due to column mismatch.")
                dtype_match_passed = data_match_passed = False
            
            # Determine overall test status
            if all([row_count_passed, column_match_passed, dtype_match_passed, data_match_passed]):
                 test_passed = True

            overall_status = "PASS ✅" if test_passed else "FAIL ❌"

            # --- Reporting Section ---
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            
            timing_report = (
                f"*--- Execution Time ---*\n"
                f"Start: `{start_time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"End:   `{end_time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"Duration: `{str(duration).split('.')[0]}`\n"
            )
            profile_report = (
                f"*--- Data Profile Report ---*\n"
                f"Source:      `{len(source_dataframe)} rows, {len(source_dataframe.columns)} cols`\n"
                f"Destination: `{len(dest_dataframe)} rows, {len(dest_dataframe.columns)} cols`\n"
            )
            data_match_report_line = f"Data Value Match: *{'PASS ✅' if data_match_passed else 'FAIL ❌'}*"
            if not data_match_passed and mismatch_file_path:
                data_match_report_line += f" (see attached file)"

            summary_report = (
                f"*--- Test Summary ---*\n"
                f"Row Count Match:    *{'PASS ✅' if row_count_passed else 'FAIL ❌'}*\n"
                f"Column Match:       *{'PASS ✅' if column_match_passed else 'FAIL ❌'}*\n"
                f"Data Type Match:    *{'PASS ✅' if dtype_match_passed else 'FAIL ❌'}*\n"
                f"{data_match_report_line}\n"
            )
            
            final_message = (f"🚨 *UAT Report: {test_name}* 🚨\n\n"
                             f"*Overall Status: {overall_status}*\n\n"
                             f"{timing_report}\n{profile_report}\n{summary_report}")

        else:
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            final_message = f"🚨 *UAT Report: {test_name}* 🚨\n\n*Overall Status: FAIL ❌*\n\nCould not perform tests as one or both dataframes were empty."

        # Send the main text report
        send_telegram_alert(final_message, telegram_config)
        
        # If a mismatch file was created, send it as a separate document
        if mismatch_file_path:
            caption = f"📄 Mismatch data for test: *{test_name}*"
            send_telegram_document(mismatch_file_path, caption, telegram_config)

        source_engine.dispose()
        dest_engine.dispose()
        print("\nSQLAlchemy engines disposed.")
    
    else:
        print("\nCould not create database engines. Test aborted.")

    print(f"=============== Finished Test: {test_name} ===============\n")
    return test_passed