import sys
import json
import httpx

BASE_URL = "http://localhost:8081"
TEST_EMAIL = "sumithatekar9@gmail.com"

def run_tests():
    print("🚀 Running email service test suite...")
    print(f"🎯 Target email: {TEST_EMAIL}\n")
    
    # 1. Verify health check first
    try:
        health_resp = httpx.get(f"{BASE_URL}/health")
        if health_resp.status_code == 200:
            print("✅ Health Check Successful!")
            print(json.dumps(health_resp.json(), indent=2))
        else:
            print(f"❌ Health Check failed (status {health_resp.status_code}): {health_resp.text}")
            return
    except httpx.RequestError as exc:
        print(f"❌ Failed to reach Email Service at {BASE_URL}: {exc}")
        print("💡 Make sure the email-service is running by typing: python main.py")
        sys.exit(1)

    # 2. Test Verification Email
    print(f"\n📧 Sending Verification Email to {TEST_EMAIL}...")
    try:
        verification_payload = {
            "email": TEST_EMAIL,
            "token": "verification-token-sumit-12345"
        }
        resp = httpx.post(
            f"{BASE_URL}/send-verification",
            json=verification_payload,
            timeout=20.0
        )
        if resp.status_code == 200:
            print("✅ Verification Email Sent successfully!")
            print(json.dumps(resp.json(), indent=2))
        else:
            print(f"❌ Verification Email sending failed (status {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ Error while testing verification endpoint: {e}")

    # 3. Test Generic HTML Email
    print(f"\n✉️ Sending Generic Custom HTML Email to {TEST_EMAIL}...")
    try:
        generic_payload = {
            "to_email": TEST_EMAIL,
            "subject": "Greetings from your new FastAPI Service!",
            "html_content": """
            <html>
                <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f9;">
                    <div style="max-width: 600px; margin: auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05);">
                        <h2 style="color: #4f46e5;">Welcome Sumit!</h2>
                        <p style="font-size: 16px; color: #374151;">
                            This is an automated test from your newly initialized independent <strong>FastAPI Email Service</strong>.
                        </p>
                        <p style="font-size: 15px; color: #4b5563;">
                            Everything is working securely and asynchronously. You can now use this endpoint to send custom emails from any of your backend systems!
                        </p>
                        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                        <span style="font-size: 12px; color: #9ca3af;">Sent by Antigravity AI Engine</span>
                    </div>
                </body>
            </html>
            """,
            "sender_name": "FastAPI Email Service"
        }
        resp = httpx.post(
            f"{BASE_URL}/send-email",
            json=generic_payload,
            timeout=20.0
        )
        if resp.status_code == 200:
            print("✅ Generic Email Sent successfully!")
            print(json.dumps(resp.json(), indent=2))
        else:
            print(f"❌ Generic Email sending failed (status {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ Error while testing generic email endpoint: {e}")

if __name__ == "__main__":
    run_tests()
