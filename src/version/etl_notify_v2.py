import logging
import time
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Mock ETL Functions ===
def extract():
    logging.info("Starting data extraction...")
    # Simulate failure for testing
    # raise Exception("Failed to extract data from source")
    time.sleep(1)
    logging.info("Data extraction completed.")

def transform():
    logging.info("Starting data transformation...")
    time.sleep(1)
    logging.info("Data transformation completed.")

def load():
    logging.info("Starting data loading into warehouse...")
    time.sleep(1)
    logging.info("Data loading completed.")

# === Telegram Notification Function with Inline Button ===
def send_telegram_html_message_with_button(bot_token, chat_id, message_html, button_text, button_url):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_html,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[{
                "text": button_text,
                "url": button_url
            }]]
        }
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info("Telegram notification with button sent successfully.")
        else:
            logging.error(f"Failed to send Telegram message: {response.text}")
    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")

# === Main ETL Execution with Telegram Notification ===
def run_etl_pipeline():
    pipeline_name = "ETL Data Pipeline"
    TELEGRAM_BOT_TOKEN = "8031717013:AAEm6TNbR2FnTg4__8tD-E_XIXUqEw33Y1c"
    TELEGRAM_CHAT_ID = "460648943"
    LOG_FILE_URL = "https://senghong.streamlit.app/ "  # Replace with your hosted log URL

    start_time = datetime.now()
    logging.info(f"{pipeline_name} started at {start_time}.")

    try:
        extract()
        transform()
        load()
        status_text = "Success"
        status_emoji = "✅"
        error_details = ""
    except Exception as e:
        status_text = "Failed"
        status_emoji = "❌"
        error_details = f"\n⚠️ <b>Error:</b> <code>{str(e)}</code>"
        logging.error(f"ETL Pipeline failed: {e}", exc_info=True)

    end_time = datetime.now()
    duration = end_time - start_time

    # Build HTML message (no unsupported tags)
    message = f"""
📢 <b>{pipeline_name} Execution Report</b>

🕘 <b>Start Time:</b> {start_time.strftime('%Y-%m-%d %H:%M:%S')}
🕘 <b>End Time:</b> {end_time.strftime('%Y-%m-%d %H:%M:%S')}
⏱️ <b>Duration:</b> {str(duration).split('.')[0]}

🎯 <b>Status:</b> {status_emoji} <b>{status_text}</b>
{error_details}
"""

    button_text = "📄 View Full Logs"
    send_telegram_html_message_with_button(
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        message,
        button_text,
        LOG_FILE_URL
    )

    if status_text == "Failed":
        raise  # Re-raise exception after notification

# Run the ETL pipeline
if __name__ == "__main__":
    run_etl_pipeline()