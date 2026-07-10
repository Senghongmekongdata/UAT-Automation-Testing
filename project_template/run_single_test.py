# run_single_test.py: Helper script to execute a single test case from test_cases.json.
import os
import sys
import json
from dotenv import load_dotenv

# Set project root to path for src import
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from src import uat_core_automation_engine

def print_usage():
    print("Usage: python run_single_test.py <test_case_name>")
    print("Example: python run_single_test.py DIM_SAMPLE_ACCOUNT")

def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    test_case_name = sys.argv[1]
    
    # Resolve paths relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(current_dir, "test_cases.json")
    validation_output_dir = os.path.join(current_dir, "data_validation")

    if not os.path.exists(config_file):
        print(f"❌ Error: 'test_cases.json' configuration file not found in '{current_dir}'.")
        sys.exit(1)

    # Load environment variables
    load_dotenv(os.path.join(project_root, '.env'))

    # Load test cases
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    except Exception as e:
        print(f"❌ Error: Failed to parse '{config_file}': {e}")
        sys.exit(1)

    # Match case
    matched_cases = [tc for tc in test_cases if tc.get("name") == test_case_name]
    if not matched_cases:
        print(f"❌ Error: No test case found matching name '{test_case_name}'.")
        available_names = [tc.get("name") for tc in test_cases]
        print(f"Available test cases: {available_names}")
        sys.exit(1)

    test = matched_cases[0]
    
    # Setup configs
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

    print(f"Running individual table test: {test_case_name}")
    is_success = uat_core_automation_engine.run_test(
        test_name=test.get("name"),
        source_config=source_config,
        dest_config=dest_config,
        telegram_config=telegram_config,
        source_query=test.get("source_query"),
        dest_query=test.get("dest_query"),
        primary_key=test.get("primary_key", ["id"]),
        output_dir=validation_output_dir
    )

    if is_success:
        print(f"\n✅ {test_case_name} UAT test passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {test_case_name} UAT test failed! (Mismatch files generated inside 'data_validation/')")
        sys.exit(1)

if __name__ == "__main__":
    main()
