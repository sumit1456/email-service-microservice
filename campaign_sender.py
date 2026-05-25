from __future__ import print_function
import os
import time
from pprint import pprint
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv

# Load configurations from .env
load_dotenv()

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "shatekar10@gmail.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Resume Maker")

if not BREVO_API_KEY:
    print("❌ Error: BREVO_API_KEY is not set in your .env file!")
    exit(1)

# Configure API key authorization: api-key
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = BREVO_API_KEY

# Instantiate the API client
api_instance = sib_api_v3_sdk.EmailCampaignsApi(sib_api_v3_sdk.ApiClient(configuration))

def create_and_send_campaign():
    print(f"📣 Creating classic email campaign with Brevo SDK...")
    print(f"👤 Sender: {SENDER_NAME} <{SENDER_EMAIL}>")
    
    # Define the campaign settings
    email_campaigns = sib_api_v3_sdk.CreateEmailCampaign(
        name="Campaign sent via the API",
        subject="My subject",
        sender={"name": SENDER_NAME, "email": SENDER_EMAIL},
        # Content that will be sent
        html_content="Congratulations! You successfully sent this example campaign via the Brevo API.",
        # Select the recipients (replace listIds with your actual Brevo list IDs)
        recipients={"listIds": [2, 7]},
        # Schedule the sending (Must be a future UTC date format)
        scheduled_at="2026-12-31 12:00:00"
    )

    try:
        # Create an email campaign
        api_response = api_instance.create_email_campaign(email_campaigns)
        print("✅ Campaign created successfully!")
        pprint(api_response)
    except ApiException as e:
        print("❌ Exception when calling EmailCampaignsApi->create_email_campaign: %s\n" % e)

if __name__ == "__main__":
    create_and_send_campaign()
