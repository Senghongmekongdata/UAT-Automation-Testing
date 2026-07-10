# run_uat.py: General runner for configuration-driven UAT test automation.
import os
import sys
import json
from dotenv import load_dotenv
from src import uat_core_automation_engine

def print_help():
    print("Usage: python run_uat.py <project_folder_name> [test_case_name]")
    print("Example: python run_uat.py svbo")
    print("Example: python run_uat.py svbo DIM_SVBO_ACCOUNT")

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    project_dir = sys.argv[1]
    filter_test_name = sys.argv[2] if len(sys.argv) > 2 else None

    # Resolve paths
    project_path = os.path.abspath(project_dir)
    config_file = os.path.join(project_path, "test_cases.json")
    validation_output_dir = os.path.join(project_path, "data_validation")

    if not os.path.isdir(project_path):
        print(f"❌ Error: Project directory '{project_dir}' does not exist.")
        sys.exit(1)

    if not os.path.exists(config_file):
        print(f"❌ Error: Configuration file 'test_cases.json' not found in '{project_dir}'.")
        sys.exit(1)

    # Load environment variables
    load_dotenv(override=True)

    # Extract configs
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

    # Load test cases from JSON
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
    except Exception as e:
        print(f"❌ Error: Failed to parse '{config_file}': {e}")
        sys.exit(1)

    # Filter test case if requested
    if filter_test_name:
        test_cases = [tc for tc in test_cases if tc.get("name") == filter_test_name]
        if not test_cases:
            print(f"⚠️ No test case found matching: {filter_test_name}")
            sys.exit(0)

    print("=" * 70)
    print(f"Starting UAT Test Suite for Project: {os.path.basename(project_path)}")
    print(f"Total test cases configured: {len(test_cases)}")
    print(f"Discrepancy reports will be saved to: {validation_output_dir}")
    print("=" * 70)

    final_results = []

    for i, test in enumerate(test_cases):
        name = test.get("name")
        source_query = test.get("source_query")
        dest_query = test.get("dest_query")
        primary_key = test.get("primary_key", ["id"])

        print(f"\n[{i+1}/{len(test_cases)}] Executing Table Test: {name}")
        
        try:
            is_success = uat_core_automation_engine.run_test(
                test_name=name,
                source_config=source_config,
                dest_config=dest_config,
                telegram_config=telegram_config,
                source_query=source_query,
                dest_query=dest_query,
                primary_key=primary_key,
                output_dir=validation_output_dir
            )
            final_results.append({"name": name, "passed": is_success, "error": None})
        except Exception as e:
            print(f"❌ Error running test case '{name}': {e}")
            final_results.append({"name": name, "passed": False, "error": str(e)})

    # --- Print Final Summary Report ---
    print("\n" + "=" * 20 + " FINAL RUN SUMMARY REPORT " + "=" * 20)
    passed_count = 0
    for res in final_results:
        status = "PASS ✅" if res["passed"] else "FAIL ❌"
        err_msg = f" (Error: {res['error']})" if res["error"] else ""
        print(f"Table Test: {res['name']:<40} Status: {status}{err_msg}")
        if res["passed"]:
            passed_count += 1
            
    failed_count = len(test_cases) - passed_count
    
    print("-" * 66)
    print(f"Total Tests Run: {len(test_cases)} | Passed: {passed_count} | Failed: {failed_count}")
    print("=" * 66)

if __name__ == "__main__":
    main()
