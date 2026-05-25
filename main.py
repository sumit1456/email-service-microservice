import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
import httpx
from dotenv import load_dotenv

# Configure logging with premium formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger("email-service")

# Load environment variables
load_dotenv()

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "sumithatekar9@gmail.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Resume Maker")

if not BREVO_API_KEY:
    logger.warning("BREVO_API_KEY is not defined in environment variables!")

# Lifespan manager to manage the HTTP client lifecycle gracefully
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the async client with Brevo headers
    app.state.http_client = httpx.AsyncClient(
        base_url="https://api.brevo.com/v3",
        headers={
            "accept": "application/json",
            "api-key": BREVO_API_KEY or "",
            "content-type": "application/json"
        },
        timeout=15.0
    )
    logger.info("🚀 HTTP Client for Brevo API successfully initialized.")
    yield
    # Clean up and close client on shutdown
    await app.state.http_client.aclose()
    logger.info("🛑 HTTP Client successfully closed.")

app = FastAPI(
    title="Independent Email Microservice",
    description="Microservice to handle all transactional and template-based emails using Brevo API",
    version="1.0.0",
    lifespan=lifespan
)

# ─── PYDANTIC MODELS ─────────────────────────────────────────────────────────

class VerificationRequest(BaseModel):
    email: EmailStr = Field(..., description="Recipient email address")
    token: str = Field(..., description="Verification token")

class EmailRecipient(BaseModel):
    email: EmailStr = Field(..., description="Recipient email address")
    name: Optional[str] = Field(None, description="Optional name of the recipient")

class GenericEmailRequest(BaseModel):
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., min_length=1, description="Subject of the email")
    html_content: str = Field(..., min_length=1, description="HTML content body of the email")
    sender_name: Optional[str] = Field(None, description="Custom sender name (defaults to SENDER_NAME)")
    sender_email: Optional[EmailStr] = Field(None, description="Custom sender email (defaults to SENDER_EMAIL)")

# ─── ENDPOINTS ──────────────────────────────────────────────────────────────

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Simple health-check endpoint to verify if the service is alive and configured."""
    return {
        "status": "healthy",
        "service": "email-service",
        "brevo_configured": bool(BREVO_API_KEY)
    }

@app.post("/send-verification", status_code=status.HTTP_200_OK)
async def send_verification(request: VerificationRequest):
    """
    Sends a styled verification email to the user with a token.
    Replicates the exact HTML template used in ResumeMaker Java service.
    """
    if not BREVO_API_KEY:
        logger.error("Attempted to send verification email but BREVO_API_KEY is missing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service misconfigured: Brevo API Key is missing."
        )

    # 🔗 Replicate exact ResumeMaker verification URL format
    verify_link = f"http://localhost:5173/verify?token={request.token}"
    
    # 🧩 Beautifully styled HTML template exactly matching the original Java implementation
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; margin: 0; padding: 0;">
        <table width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
          <tr>
            <td style="padding: 40px; text-align: center;">
              <h1 style="color: #1a73e8; font-size: 28px; margin-bottom: 20px;">Verify Your Email</h1>
              <p style="font-size: 18px; color: #333;">Hi there 👋,</p>
              <p style="font-size: 16px; color: #555;">
                Thank you for signing up with <strong>Resume Maker</strong>!<br>
                Please verify your email address to activate your account.
              </p>
              <p style="margin: 30px 0;">
                <a href="{verify_link}" 
                   style="background-color: #1a73e8; color: #fff; padding: 14px 28px; border-radius: 6px; 
                          text-decoration: none; font-size: 18px; font-weight: bold;">
                   Verify My Email
                </a>
              </p>
              <p style="font-size: 14px; color: #777;">
                This link will expire in 24 hours.<br>
                If you didn’t create this account, you can safely ignore this message.
              </p>
              <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
              <p style="font-size: 13px; color: #aaa;">
                &copy; 2025 Resume Maker. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    payload = {
        "sender": {
            "email": SENDER_EMAIL,
            "name": SENDER_NAME
        },
        "to": [{"email": request.email}],
        "subject": "Verify your Resume Maker account",
        "htmlContent": html_content
    }

    logger.info(f"📨 Attempting to send verification email to {request.email}...")
    
    try:
        response = await app.state.http_client.post("/smtp/email", json=payload)
        
        if response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED):
            logger.info(f"✅ Verification email successfully sent to {request.email}. Brevo Response: {response.text}")
            return {
                "success": True,
                "message": f"Verification email sent successfully to {request.email}",
                "data": response.json()
            }
        else:
            logger.error(f"❌ Brevo API rejected email. Code: {response.status_code}, Detail: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Brevo service error: {response.text}"
            )
            
    except httpx.RequestError as exc:
        logger.error(f"❌ Connection error while calling Brevo API: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to communicate with the email sending provider: {str(exc)}"
        )

@app.post("/send-email", status_code=status.HTTP_200_OK)
async def send_generic_email(request: GenericEmailRequest):
    """
    Sends a generic customized HTML email.
    Provides complete flexibility for any external app calling this service.
    """
    if not BREVO_API_KEY:
        logger.error("Attempted to send email but BREVO_API_KEY is missing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service misconfigured: Brevo API Key is missing."
        )

    # Use custom sender details if provided, fallback to environment defaults
    final_sender_email = request.sender_email or SENDER_EMAIL
    final_sender_name = request.sender_name or SENDER_NAME

    payload = {
        "sender": {
            "email": str(final_sender_email),
            "name": final_sender_name
        },
        "to": [{"email": request.to_email}],
        "subject": request.subject,
        "htmlContent": request.html_content
    }

    logger.info(f"✉️ Attempting to send generic email to {request.to_email} with subject: '{request.subject}'...")

    try:
        response = await app.state.http_client.post("/smtp/email", json=payload)
        
        if response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED):
            logger.info(f"✅ Generic email successfully sent to {request.to_email}. Brevo Response: {response.text}")
            return {
                "success": True,
                "message": f"Email sent successfully to {request.to_email}",
                "data": response.json()
            }
        else:
            logger.error(f"❌ Brevo API rejected generic email. Code: {response.status_code}, Detail: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Brevo service error: {response.text}"
            )
            
    except httpx.RequestError as exc:
        logger.error(f"❌ Connection error while calling Brevo API: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to communicate with the email sending provider: {str(exc)}"
        )

if __name__ == "__main__":
    import uvicorn
    # Retrieve port and host configuration from environment
    port = int(os.getenv("PORT", 8081))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"⚡ Starting FastAPI Email Service on {host}:{port}...")
    uvicorn.run("main:app", host=host, port=port, reload=True)
