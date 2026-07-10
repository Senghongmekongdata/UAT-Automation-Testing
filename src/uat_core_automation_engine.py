# uat_core_automation_engine.py: Core library for ETL UAT testing.
import pandas as pd
import oracledb
from sqlalchemy import create_engine
from typing import Dict, Any, List, Tuple, Optional
import requests
import os
import datetime

# --- Oracle Client Initialization (Thick Mode) ---
try:
    # Initialize Oracle Client for Thick Mode to support multi-byte/national character sets (resolving DPY-3012)
    oracledb.init_oracle_client()
except oracledb.DatabaseError as e:
    print(f"Warning: Oracle Client Thick Mode not initialized (may fail if Thick mode is required): {e}")
    print("Please ensure Oracle Instant Client is installed if you encounter character set errors.")

# --- Telegram Alerting ---
def send_telegram_alert(message: str, config: Dict[str, str]):
    """Sends a text message to a Telegram bot."""
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token or not bot_token.strip():
        print("\n⚠️ Telegram alert skipped: Bot token not configured.")
        return
    if not chat_id or "YOUR_TELEGRAM_CHAT_ID" in chat_id or not chat_id.strip():
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

    if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN" in bot_token or not bot_token.strip():
        print("\n⚠️ Telegram document skipped: Bot token not configured.")
        return
    if not chat_id or "YOUR_TELEGRAM_CHAT_ID" in chat_id or not chat_id.strip():
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
            response = requests.post(api_url, data=payload, files=files, proxies=proxies, timeout=30)
            response.raise_for_status()
        print(f"\n✅ Successfully sent document '{os.path.basename(file_path)}' to Telegram.")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED to send Telegram document: {e}")
        try:
            print(f"  - Response: {response.text}")
        except NameError:
            pass
    except Exception as e:
        print(f"\n❌ An unexpected error occurred while sending document: {e}")


# --- Database Connection ---
def get_db_engine(config: Dict[str, Any], db_name: str):
    """Creates a SQLAlchemy engine for the Oracle database."""
    user = config.get('user')
    password = config.get('password')
    dsn = config.get('dsn')

    # Detailed config check
    missing_fields = []
    if not user: missing_fields.append("USER")
    if not password: missing_fields.append("PASSWORD")
    if not dsn: missing_fields.append("DSN")

    if missing_fields:
        print(f"❌ Error: {db_name} database configuration is missing fields: {', '.join(missing_fields)}")
        return None

    try:
        conn_string = f"oracle+oracledb://{user}:{password}@{dsn}"
        engine = create_engine(conn_string)
        # Test connection
        with engine.connect() as conn:
            print(f"Successfully created connection for {db_name} DSN: {dsn}")
        return engine
    except Exception as e:
        print(f"❌ Error creating SQLAlchemy engine for {db_name} DSN: {dsn}.")
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
        print(f"❌ An error occurred while fetching data: {e}")
        return pd.DataFrame()


# --- Test Scenarios ---
def test_row_count_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, test_name: str, telegram_config: dict, output_dir: Optional[str] = None) -> bool:
    """Test Case 1: Validates if the number of rows match and exports details if they don't."""
    print("\n--- Test 1: Row Count Validation ---")
    source_rows, dest_rows = len(source_df), len(dest_df)
    print(f"Source row count: {source_rows}")
    print(f"Destination row count: {dest_rows}")
    
    if source_rows == dest_rows:
        print("✅ PASSED: Row counts match.")
        return True
    else:
        print(f"❌ FAILED: Row counts do not match. Difference: {abs(source_rows - dest_rows)}")
        
        # Determine output file path
        row_count_filename = f'row_count_mismatch_{test_name.replace(" ", "_").lower()}.csv'
        if output_dir:
            row_count_filename = os.path.join(output_dir, row_count_filename)

        try:
            report_data = {
                'Metric': ['Source Row Count', 'Destination Row Count', 'Difference'],
                'Value': [source_rows, dest_rows, abs(source_rows - dest_rows)],
                'Status': ['N/A', 'N/A', 'MISMATCH' if source_rows != dest_rows else 'MATCH']
            }
            report_df = pd.DataFrame(report_data)
            report_df.to_csv(row_count_filename, index=False)
            print(f"  - ✅ Row count report saved to: {row_count_filename}")
            
            caption = f"📊 Row Count Mismatch Report for: *{test_name}*"
            send_telegram_document(row_count_filename, caption, telegram_config)
            
        except Exception as e:
            print(f"  - ❌ FAILED to save row count report: {e}")
        
        return False

def test_column_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, test_name: str, telegram_config: dict, output_dir: Optional[str] = None) -> bool:
    """Test Case 2: Validates if the column names and count match and exports details if they don't."""
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
        
        column_mismatch_filename = f'column_mismatch_{test_name.replace(" ", "_").lower()}.csv'
        if output_dir:
            column_mismatch_filename = os.path.join(output_dir, column_mismatch_filename)

        try:
            all_columns = sorted(set(source_cols + dest_cols))
            report_data = []
            
            for col in all_columns:
                in_source = col in source_cols
                in_dest = col in dest_cols
                status = 'MATCH' if (in_source and in_dest) else 'MISMATCH'
                
                report_data.append({
                    'Column_Name': col,
                    'In_Source': 'Yes' if in_source else 'No',
                    'In_Destination': 'Yes' if in_dest else 'No',
                    'Status': status,
                    'Issue': 'Missing in Destination' if (in_source and not in_dest) 
                           else 'Extra in Destination' if (not in_source and in_dest) 
                           else 'OK'
                })
            
            report_df = pd.DataFrame(report_data)
            report_df.to_csv(column_mismatch_filename, index=False)
            print(f"  - ✅ Column mismatch report saved to: {column_mismatch_filename}")
            
            caption = f"📋 Column Schema Mismatch Report for: *{test_name}*"
            send_telegram_document(column_mismatch_filename, caption, telegram_config)
            
        except Exception as e:
            print(f"  - ❌ FAILED to save column mismatch report: {e}")
        
        return False

def test_data_type_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, test_name: str, telegram_config: dict, output_dir: Optional[str] = None) -> bool:
    """Test Case 3: Validates if the data types of corresponding columns match and exports details if they don't."""
    print("\n--- Test 3: Data Type Validation ---")
    source_types, dest_types = source_df.dtypes.to_dict(), dest_df.dtypes.to_dict()
    mismatched_types = {}
    
    for col, s_type in source_types.items():
        d_type = dest_types.get(col)
        if d_type is not None and str(s_type) != str(d_type):
            mismatched_types[col] = {'source': str(s_type), 'destination': str(d_type)}
    
    if not mismatched_types:
        print("✅ PASSED: Data types are consistent across all columns.")
        return True
    else:
        print("❌ FAILED: Data type mismatches found.")
        for col, types in mismatched_types.items():
            print(f"  - Column '{col}': Source type is {types['source']}, Destination type is {types['destination']}")
        
        dtype_mismatch_filename = f'datatype_mismatch_{test_name.replace(" ", "_").lower()}.csv'
        if output_dir:
            dtype_mismatch_filename = os.path.join(output_dir, dtype_mismatch_filename)

        try:
            common_columns = set(source_types.keys()) & set(dest_types.keys())
            report_data = []
            
            for col in sorted(common_columns):
                s_type = str(source_types[col])
                d_type = str(dest_types[col])
                status = 'MATCH' if s_type == d_type else 'MISMATCH'
                
                report_data.append({
                    'Column_Name': col,
                    'Source_DataType': s_type,
                    'Destination_DataType': d_type,
                    'Status': status
                })
            
            report_df = pd.DataFrame(report_data)
            report_df.to_csv(dtype_mismatch_filename, index=False)
            print(f"  - ✅ Data type mismatch report saved to: {dtype_mismatch_filename}")
            
            caption = f"🔢 Data Type Mismatch Report for: *{test_name}*"
            send_telegram_document(dtype_mismatch_filename, caption, telegram_config)
            
        except Exception as e:
            print(f"  - ❌ FAILED to save data type mismatch report: {e}")
        
        return False

def test_data_match(source_df: pd.DataFrame, dest_df: pd.DataFrame, primary_key_cols: List[str], test_name: str, telegram_config: dict, output_dir: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Test Case 4: Validates if data values match and exports detailed mismatches.
    Uses vectorized Pandas comparisons to optimize execution speed on large datasets.
    """
    print("\n--- Test 4: Data Value Validation ---")
    if source_df.empty or dest_df.empty:
        print("⚠️ SKIPPED: One or both DataFrames are empty.")
        return False, None
    if not sorted(list(source_df.columns)) == sorted(list(dest_df.columns)):
        print("❌ FAILED: Column schemas do not match. Cannot perform data validation.")
        return False, None
    
    # Ensure columns order matches
    dest_df = dest_df[source_df.columns]
    
    try:
        source_df_sorted = source_df.sort_values(by=primary_key_cols).reset_index(drop=True)
        dest_df_sorted = dest_df.sort_values(by=primary_key_cols).reset_index(drop=True)
    except KeyError as e:
        print(f"❌ FAILED: Primary key column '{e}' not found in one of the DataFrames.")
        return False, None

    # Normalization & standardization (Dates, Object types, Float precision)
    for col in source_df_sorted.columns:
        # 1. Standardize date formats to microsecond accuracy string formats
        if 'datetime' in str(source_df_sorted[col].dtype):
            source_df_sorted[col] = pd.to_datetime(source_df_sorted[col]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        if 'datetime' in str(dest_df_sorted[col].dtype):
            dest_df_sorted[col] = pd.to_datetime(dest_df_sorted[col]).dt.strftime('%Y-%m-%d %H:%M:%S.%f')

        # 2. Round float columns to 5 decimal places to avoid precision errors
        if pd.api.types.is_float_dtype(source_df_sorted[col]):
            source_df_sorted[col] = source_df_sorted[col].round(5)
        if pd.api.types.is_float_dtype(dest_df_sorted[col]):
            dest_df_sorted[col] = dest_df_sorted[col].round(5)

        # 3. Strip whitespace and fill missing/NaN values
        if source_df_sorted[col].dtype == 'object':
            source_df_sorted[col] = source_df_sorted[col].astype(str).str.strip().fillna('')
        if dest_df_sorted[col].dtype == 'object':
            dest_df_sorted[col] = dest_df_sorted[col].astype(str).str.strip().fillna('')

    try:
        mismatched_rows = []
        total_mismatches = 0
        common_len = min(len(source_df_sorted), len(dest_df_sorted))

        # Perform vectorized diff mask for common length
        if common_len > 0:
            source_common = source_df_sorted.iloc[:common_len]
            dest_common = dest_df_sorted.iloc[:common_len]
            
            # Vectorized comparison mask (returns True where values differ)
            diff_mask = (source_common != dest_common)
            
            # Ignore primary keys in mismatch report columns
            for pk in primary_key_cols:
                if pk in diff_mask.columns:
                    diff_mask[pk] = False
            
            # Stack to get only indices and columns with differences
            diff_series = diff_mask.stack()
            diff_coords = diff_series[diff_series].index
            
            # Populate mismatch rows
            for idx, col in diff_coords:
                source_val = source_common.loc[idx, col]
                dest_val = dest_common.loc[idx, col]
                
                entry = {
                    'Row_Index': int(idx),
                    'Column_Name': col,
                    'Source_Value': source_val,
                    'Destination_Value': dest_val,
                }
                # Attach primary keys to report
                for pk_col in primary_key_cols:
                    entry[pk_col] = source_common.loc[idx, pk_col]
                mismatched_rows.append(entry)
                total_mismatches += 1

        # Check for missing/extra rows outside common length
        if len(source_df_sorted) > common_len:
            for idx in range(common_len, len(source_df_sorted)):
                for col in source_df_sorted.columns:
                    entry = {
                        'Row_Index': idx,
                        'Column_Name': col,
                        'Source_Value': source_df_sorted.iloc[idx][col],
                        'Destination_Value': 'MISSING_ROW',
                    }
                    for pk_col in primary_key_cols:
                        entry[pk_col] = source_df_sorted.iloc[idx][pk_col]
                    mismatched_rows.append(entry)
                    total_mismatches += 1

        if len(dest_df_sorted) > common_len:
            for idx in range(common_len, len(dest_df_sorted)):
                for col in dest_df_sorted.columns:
                    entry = {
                        'Row_Index': idx,
                        'Column_Name': col,
                        'Source_Value': 'MISSING_ROW',
                        'Destination_Value': dest_df_sorted.iloc[idx][col],
                    }
                    for pk_col in primary_key_cols:
                        entry[pk_col] = dest_df_sorted.iloc[idx][pk_col]
                    mismatched_rows.append(entry)
                    total_mismatches += 1

        if not mismatched_rows:
            print("✅ PASSED: All data values match between source and destination.")
            return True, None
        else:
            unique_rows_with_mismatches = len(set(row['Row_Index'] for row in mismatched_rows))
            print(f"❌ FAILED: Data mismatch found in {unique_rows_with_mismatches} row(s) with {total_mismatches} field-level differences.")
            
            mismatch_filename = f'detailed_mismatches_{test_name.replace(" ", "_").lower()}.csv'
            if output_dir:
                mismatch_filename = os.path.join(output_dir, mismatch_filename)

            try:
                mismatch_df = pd.DataFrame(mismatched_rows)
                cols_order = primary_key_cols + ['Row_Index', 'Column_Name', 'Source_Value', 'Destination_Value']
                mismatch_df = mismatch_df[cols_order]
                
                mismatch_df.to_csv(mismatch_filename, index=False)
                print(f"  - ✅ Detailed mismatch report saved to: {mismatch_filename}")
                
                caption = f"🔍 Detailed Data Mismatch Report for: *{test_name}*\n{unique_rows_with_mismatches} rows, {total_mismatches} field differences"
                send_telegram_document(mismatch_filename, caption, telegram_config)
                
                return False, mismatch_filename
            except Exception as e:
                print(f"  - ❌ FAILED to save detailed mismatch report: {e}")
                return False, None
                
    except Exception as e:
        print(f"❌ FAILED: An error occurred during data comparison: {e}")
        return False, None


# --- Main Execution Function ---
def run_test(
    test_name: str, 
    source_config: dict, 
    dest_config: dict, 
    telegram_config: dict, 
    source_query: str, 
    dest_query: str, 
    primary_key: list,
    output_dir: Optional[str] = None
) -> bool:
    """
    Executes a full UAT test case and returns True for overall pass, False for fail.
    Saves discrepancy reports to data_validation folder and alerts Telegram.
    """
    print(f"=============== Starting Test: {test_name} ===============")
    start_time = datetime.datetime.now()
    
    # Create output directory if specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    source_engine = get_db_engine(source_config, "Source")
    dest_engine = get_db_engine(dest_config, "Destination")
    
    test_passed = False
    mismatch_files = []
    
    if source_engine and dest_engine:
        print("\nFetching data from source...")
        source_dataframe = fetch_data_as_dataframe(source_query, source_engine)
        
        print("Fetching data from destination...")
        dest_dataframe = fetch_data_as_dataframe(dest_query, dest_engine)

        if not source_dataframe.empty and not dest_dataframe.empty:
            dtype_match_passed = False
            data_match_passed = False
            data_mismatch_file = None
            
            # Executing standard assertions
            row_count_passed = test_row_count_match(source_dataframe, dest_dataframe, test_name, telegram_config, output_dir)
            column_match_passed = test_column_match(source_dataframe, dest_dataframe, test_name, telegram_config, output_dir)
            
            if column_match_passed:
                dtype_match_passed = test_data_type_match(source_dataframe, dest_dataframe, test_name, telegram_config, output_dir)
                data_match_passed, data_mismatch_file = test_data_match(source_dataframe, dest_dataframe, primary_key, test_name, telegram_config, output_dir)
                if data_mismatch_file:
                    mismatch_files.append(data_mismatch_file)
            else:
                print("\n⚠️ SKIPPED: Data Type and Data Value tests due to column mismatch.")
                dtype_match_passed = data_match_passed = False
                data_mismatch_file = None
            
            if all([row_count_passed, column_match_passed, dtype_match_passed, data_match_passed]):
                 test_passed = True

            overall_status = "PASS ✅" if test_passed else "FAIL ❌"

            # Performance duration calculation
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
            
            row_count_line = f"Row Count Match:    *{'PASS ✅' if row_count_passed else 'FAIL ❌'}*"
            column_match_line = f"Column Match:       *{'PASS ✅' if column_match_passed else 'FAIL ❌'}*"
            dtype_match_line = f"Data Type Match:    *{'PASS ✅' if dtype_match_passed else 'FAIL ❌'}*"
            data_match_line = f"Data Value Match:   *{'PASS ✅' if data_match_passed else 'FAIL ❌'}*"
            
            if not row_count_passed:
                row_count_line += " (📊 report sent)"
            if not column_match_passed:
                column_match_line += " (📋 report sent)"
            if not dtype_match_passed:
                dtype_match_line += " (🔢 report sent)"
            if not data_match_passed and data_mismatch_file:
                data_match_line += " (🔍 detailed report sent)"

            summary_report = (
                f"*--- Test Summary ---*\n"
                f"{row_count_line}\n"
                f"{column_match_line}\n"
                f"{dtype_match_line}\n"
                f"{data_match_line}\n"
            )
            
            final_message = (f"🚨 *UAT Report: {test_name}* 🚨\n\n"
                              f"*Overall Status: {overall_status}*\n\n"
                              f"{timing_report}\n{profile_report}\n{summary_report}")

        else:
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            final_message = f"🚨 *UAT Report: {test_name}* 🚨\n\n*Overall Status: FAIL ❌*\n\nCould not perform tests as one or both dataframes were empty."

        send_telegram_alert(final_message, telegram_config)

        source_engine.dispose()
        dest_engine.dispose()
        print("\nSQLAlchemy engines disposed.")
    
    else:
        print("\nCould not create database engines. Test aborted.")

    print(f"=============== Finished Test: {test_name} ===============\n")
    return test_passed
