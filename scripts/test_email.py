
import os
import sys
import datetime as dt
from email.message import EmailMessage
import smtplib
import ssl

# Add scripts to path to use _load_env_value from daily_agent
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))
from daily_agent import _load_env_value

def test_email():
    sender = _load_env_value("AGENT_EMAIL_FROM")
    recipient = _load_env_value("AGENT_EMAIL_TO")
    app_pw = _load_env_value("AGENT_EMAIL_APP_PASSWORD")
    
    print(f"Testing email from {sender} to {recipient}...")
    
    if not (sender and recipient and app_pw):
        print("Missing email configuration in .env")
        return

    msg = EmailMessage()
    msg["Subject"] = "[YouTube Engine] TEST EMAIL"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("This is a test email to verify the YouTube Engine notification system.")
    
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=60) as server:
            server.login(sender, app_pw)
            server.send_message(msg)
        print("SUCCESS: Test email sent!")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_email()
