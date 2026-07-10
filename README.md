# UAT Test Automation Framework

An optimized, configuration-driven automated testing suite designed to validate data equivalence between source schemas (e.g., transactional databases) and target destination schemas (e.g., Data Warehouse DWH schemas). 

This framework compares data schemas, data types, row counts, and performs fast row-by-row cell value validation. When mismatches are found, detailed CSV discrepancy reports are generated and automatically dispatched to stakeholders via Telegram alerts.

---

## 📂 Project Architecture

```
automation_app/
│
├── .env                          # Local database credentials & Telegram tokens (git-ignored)
├── .env.example                  # Template configuration keys
├── run_uat.py                    # Root multi-test suite orchestrator
├── README.md                     # Framework documentation (this file)
│
├── src/                          # CORE TESTING ENGINE
│   ├── __init__.py               # Package aliases for backwards compatibility
│   └── uat_core_automation_engine.py # Core connection, validation, and Telegram dispatch logic
│
└── project_template/             # PROJECT TEMPLATE (Copy this for a new database sync project)
    ├── data_validation/          # Destination for generated mismatch CSV files
    ├── test_cases.json           # JSON mapping of table queries and primary keys
    └── run_single_test.py        # Helper to execute a single test case locally
```

## ⚙️ Prerequisites & Installation

Before running the UAT testing suite, configure your environment with the following dependencies:

### 1. Install Oracle Instant Client (Required for Thick Mode)
Because the validation suite handles database schemas with multi-byte or national character sets, the core engine initializes in **Oracle Thick Mode**. 
- Download the free **Instant Client Basic** or **Basic Light** package for your OS from the [Oracle Instant Client Downloads page](https://www.oracle.com/database/technologies/instant-client.html).
- Extract the zip file (e.g. to `C:\oracle\instantclient` on Windows).
- Add the folder path to your system's `PATH` environment variable so Python can locate the client DLLs.

### 2. Set Up dependencies
Run the following commands to set up a Python virtual environment and install the required packages:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install pandas sqlalchemy oracledb requests python-dotenv
```

---

## 🚀 Quick Start Guide

### 1. Configure the Environment
Copy `.env.example` to a new file named `.env` in the root folder, and fill in the Oracle DSNs and Telegram configurations:
```env
# Database Source Configuration
SOURCE_USER=your_source_db_user
SOURCE_PASSWORD=your_source_db_password
SOURCE_DSN=host:port/service_name

# Database Target Configuration
DEST_USER=your_target_db_user
DEST_PASSWORD=your_target_db_password
DEST_DSN=host:port/service_name

# Telegram Alerts Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 2. Define Test Cases (`test_cases.json`)
Instead of duplicating Python runner scripts, define all database validations inside the project's `test_cases.json` file as objects in a JSON array. You can easily add more tables by adding new elements to the array.

For example, here is a configuration containing both `DIM_ACCOUNT` and `DIM_CUSTOMER`:
```json
[
  {
    "name": "DIM_ACCOUNT",
    "source_query": "SELECT ID, ACCOUNT_NUMBER, STATUS FROM MAIN.ACC_ACCOUNT",
    "dest_query": "SELECT ID, ACCOUNT_NUMBER, STATUS FROM TARGET_SCHEMA.DIM_ACCOUNT",
    "primary_key": ["id"]
  },
  {
    "name": "DIM_CUSTOMER",
    "source_query": "SELECT ID, CUSTOMER_NUMBER, REG_DATE, STATUS FROM MAIN.COM_CUSTOMER",
    "dest_query": "SELECT ID, CUSTOMER_NUMBER, REG_DATE, STATUS FROM TARGET_SCHEMA.DIM_CUSTOMER",
    "primary_key": ["id"]
  }
]
```

> [!TIP]
> **Composite / Compound Primary Keys:**
> If a table uses a composite primary key (multiple columns to identify a unique row), simply specify all key columns inside the `"primary_key"` array. The validation engine will automatically use all configured columns to sort and align the datasets before cell checks:
> ```json
> "primary_key": ["id", "part_key"]
> ```


### 3. Run the Automations

#### Option A: Run a Complete Project Suite
Run all configured tables inside a project folder (e.g. the `project_a/` folder) from the project root:
```bash
python run_uat.py project_a
```

#### Option B: Run a Single Table Test from the Root
Run only one specific test case by suffixing its name:
```bash
python run_uat.py project_a DIM_ACCOUNT
```

#### Option C: Run Locally inside a Project Folder
Navigate to the project folder and use the boilerplate runner:
```bash
cd project_a
python run_single_test.py DIM_ACCOUNT
```

> [!NOTE]
> **What is `DIM_ACCOUNT` in the commands above?**
>
> `DIM_ACCOUNT` is the **Test Case Identifier**. It matches the `"name"` key defined inside your project's `test_cases.json` file.
> 
> **How do users know what to input here?**
> 1. Check the list of `"name"` keys defined inside your [project_a/test_cases.json](project_a/test_cases.json) configuration file.
> 2. If you input an invalid name (or omit it), the script will automatically output a friendly list of all available test names in that folder. For example:
>    ```text
>    ❌ Error: No test case found matching name 'INVALID_NAME'.
>    Available test cases: ['DIM_ACCOUNT', 'DIM_CARD']
>    ```

#### Option D: Programmatic Execution using Pure Python (Without JSON)
If you prefer to write dedicated Python scripts for your validations (e.g., to perform custom data preprocessing or manual step orchestration), you can import the core automation engine directly:

```python
import os
import sys
from dotenv import load_dotenv

# Ensure the root directory is in the import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import uat_core_automation_engine

# Load credentials
load_dotenv()

source_config = {
    "user": os.getenv("SOURCE_USER"),
    "password": os.getenv("SOURCE_PASSWORD"),
    "dsn": os.getenv("SOURCE_DSN") 
}

dest_config = {
    "user": os.getenv("DEST_USER"),
    "password": os.getenv("DEST_PASSWORD"),
    "dsn": os.getenv("DEST_DSN")
}

telegram_config = {
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID")
}

# Run the test
is_success = uat_core_automation_engine.run_test(
    test_name="DIM_ACCOUNT",
    source_config=source_config,
    dest_config=dest_config,
    telegram_config=telegram_config,
    source_query="SELECT ID, ACCOUNT_NUMBER, STATUS FROM MAIN.ACC_ACCOUNT",
    dest_query="SELECT ID, ACCOUNT_NUMBER, STATUS FROM TARGET_SCHEMA.DIM_ACCOUNT",
    primary_key=["id"],
    output_dir="./data_validation"
)
```

---

## 🔍 Validation Steps

When a test executes, the core engine runs four standard checks in sequence. The flowchart below describes how success and failure branches are tracked, how mismatch reports are generated, and how reports are compiled and dispatched to Telegram:

```text
                  ┌─────────────────────────────────┐
                  │       1. Start Table Test       │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │ Query Source & Destination DBs  │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    2. Row Count Validation      ├──────────┐
                  └────────────────┬────────────────┘          │
                                   │ (Success)                 │ (Failure)
                                   ▼                           ▼
                  ┌─────────────────────────────────┐  ┌───────────────┐
                  │   3. Column Schema Validation   │  │ Generate Row  │
                  └────────────────┬────────────────┘  │ Mismatch CSV  │
                                   │                   └───────┬───────┘
                                   │ (Success)                 │
                                   ▼                           │
                  ┌─────────────────────────────────┐          │
                  │     4. Data Type Validation     │          │
                  └────────────────┬────────────────┘          │
                                   │                           │
                                   │ (Success)                 │
                                   ▼                           │
                  ┌─────────────────────────────────┐          │
                  │    5. Data Value Validation     │          │
                  └────────────────┬────────────────┘          │
                                   │                           │
                                   ▼                           │
                  ┌─────────────────────────────────┐          │
                  │  Any Mismatch CSVs Generated?   │◄─────────┘
                  └────────┬───────────────┬────────┘
                           │ (Yes)         │ (No)
                           ▼               ▼
             ┌─────────────────────────┐ ┌─────────────────────────┐
             │ 1. Save Mismatch CSVs   │ │ Send Telegram Success   │
             │    to:                  │ │ Summary Report text     │
             │    <project_dir>/       │ └─────────────────────────┘
             │    data_validation/     │
             │                         │
             │ 2. Send Telegram Failure│
             │    Summary Report text  │
             │    + Attach CSV files   │
             └─────────────────────────┘
```

* **Discrepancy Reports**: Any failure during these checkpoints generates detailed CSVs (such as `row_count_mismatch_*.csv`, `column_mismatch_*.csv`, `datatype_mismatch_*.csv`, `detailed_mismatches_*.csv`) in the project's `<project_dir>/data_validation/` directory.
* **Telegram Notifications**: Regardless of pass or fail, a timing report, data profile (row/column sizes), and status summary is sent to the Telegram channel at the completion of each table execution. Mismatch reports are sent as document uploads.

### Detailed Step-by-Step Flow Narrative:

1. **Connection & Fetching**: 
   The testing engine establishes connections to both the Source and Target Oracle databases using SQLAlchemy. It queries both tables into memory as Pandas DataFrames and automatically normalizes all column headers to lowercase.
2. **Step 1 - Row Count Validation**: 
   The engine validates that the exact number of rows returned from both queries matches. If there is a mismatch:
   - A `row_count_mismatch_*.csv` file containing the source vs. target row count difference is written to the local `data_validation/` folder.
   - The overall test status is flagged as `FAIL` (but execution continues to check schema discrepancies).
3. **Step 2 - Column Schema Validation**: 
   The engine verifies that the list of expected columns matches exactly. If columns do not match:
   - An analysis of missing columns (absent in destination) and extra columns is saved to `column_mismatch_*.csv`.
   - **Important**: If the column lists do not match, the system automatically skips the downstream Data Type and Data Value checks (since columns are not aligned, value comparisons cannot occur) and jumps directly to Telegram reporting.
4. **Step 3 - Data Type Validation**: 
   If columns align, the engine compares the data types of matching columns (e.g. integer vs string). Any data type mismatch is logged in a `datatype_mismatch_*.csv` report.
5. **Step 4 - Data Value Validation**: 
   The engine performs a vectorized, row-by-row cell value comparison:
   - It standardizes date/datetime formats, rounds floats to 5 decimal places to avoid false-positive rounding errors, and trims whitespace.
   - It sorts both dataframes by the configured primary key(s) to align rows correctly.
   - It checks cell values and logs exact row indices, column names, source values, and destination values for differences, plus logs missing rows and extra rows. The output is written to a `detailed_mismatches_*.csv` file.
6. **Telegram Dispatch**:
   Once all test scenarios are complete:
   - If any discrepancy CSV files were generated, the system sends a **Failure Summary Message** to Telegram and uploads all generated CSV reports as document attachments.
   - If no discrepancy CSV files exist, it sends a **Success Summary Message** to Telegram.

---

## 💡 Engine Features & Optimizations

### Vectorized Cell Comparison
Data value comparisons are vectorized using Pandas stacking operations rather than slow element-by-element nested loops. This reduces comparison runtimes for tables with hundreds of thousands of rows to seconds.

### Float Precision Guard
Float values are automatically rounded to 5 decimal places during checking to prevent floating-point rounding variations (precision differences) from reporting false-positive mismatches.

### Oracle Client Thick Mode
The engine initializes Oracle Client in **Thick Mode** via `oracledb.init_oracle_client()`. This ensures Oracle's national character set conversions execute correctly (resolving the `DPY-3012` error).

