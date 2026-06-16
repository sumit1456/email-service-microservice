import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List
import secrets
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
import httpx
import aio_pika
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

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "16.176.86.18")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USERNAME = os.getenv("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
# Queue names for different purposes
RABBITMQ_QUEUE_EMAIL_VERIFICATION = os.getenv("RABBITMQ_QUEUE_EMAIL_VERIFICATION", "email_verification_resumemaker")
RABBITMQ_QUEUE_RESUMEMAKER = os.getenv("RABBITMQ_QUEUE_RESUMEMAKER", "email_resumemaker_queue")
RABBITMQ_QUEUE_JOBALERTS = os.getenv("RABBITMQ_QUEUE_JOBALERTS", "jobalerts")
RUN_SCRAPER_BACKGROUND = os.getenv("RUN_SCRAPER_BACKGROUND", "false").lower() == "true"
SCRAPER_MIN_RUN_INTERVAL = int(os.getenv("SCRAPER_MIN_RUN_INTERVAL", "10"))

if not BREVO_API_KEY:
    logger.warning("BREVO_API_KEY is not defined in environment variables!")

# ─── RABBITMQ CONSUMER ───────────────────────────────────────────────────────

async def process_verification_message(message: aio_pika.abc.AbstractIncomingMessage, http_client: httpx.AsyncClient):
    """Process a single verification message from RabbitMQ."""
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            email = body.get("email")
            token = body.get("token")

            if not email or not token:
                logger.error(f"❌ Invalid message payload (missing email or token): {body}")
                return

            logger.info(f"📬 Received verification message from RabbitMQ for: {email}")

            # Build the verification link and HTML content
            verify_link = f"https://resume-maker-pro.netlify.app/verify?token={token}"
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
                        If you didn't create this account, you can safely ignore this message.
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

            brevo_payload = {
                "sender": {"email": SENDER_EMAIL, "name": SENDER_NAME},
                "to": [{"email": email}],
                "subject": "Verify your Resume Maker account",
                "htmlContent": html_content
            }

            response = await http_client.post("/smtp/email", json=brevo_payload)

            if response.status_code in (200, 201, 202):
                logger.info(f"✅ Verification email sent to {email}. Brevo Response: {response.text}")
            else:
                logger.error(f"❌ Brevo API rejected email for {email}. Code: {response.status_code}, Detail: {response.text}")

        except json.JSONDecodeError:
            logger.error(f"❌ Failed to decode RabbitMQ message body: {message.body}")
        except Exception as e:
            logger.error(f"❌ Error processing RabbitMQ message: {e}")


async def start_rabbitmq_consumer(app: FastAPI):
    """Connect to RabbitMQ and start consuming from the Resume Maker queue."""
    rabbitmq_url = f"amqp://{RABBITMQ_USERNAME}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    logger.info(f"🔐 RabbitMQ credentials - username: {RABBITMQ_USERNAME}, password: {RABBITMQ_PASSWORD}")
    retry_delay = 5

    while True:
        try:
            logger.info(f"🐇 Connecting to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}...")
            connection = await aio_pika.connect_robust(rabbitmq_url)
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)

            queue = await channel.declare_queue(RABBITMQ_QUEUE_RESUMEMAKER, durable=True)
            logger.info(f"✅ RabbitMQ consumer started. Listening on queue: '{RABBITMQ_QUEUE_RESUMEMAKER}'")

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    await process_verification_message(message, app.state.http_client)

        except aio_pika.exceptions.AMQPConnectionError as e:
            logger.error(f"❌ RabbitMQ connection failed: {e}. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
        except asyncio.CancelledError:
            logger.info("🛑 RabbitMQ consumer task cancelled. Shutting down...")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected RabbitMQ error: {e}. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)


async def run_scraper_background_loop(app: FastAPI):
    """Background task to run the job scraper at configured intervals."""
    logger.info("⏳ Background job-scraper thread runner started.")
    # Wait 10 seconds before first run to let everything initialize
    await asyncio.sleep(10)
    
    import sys
    import os
    import importlib.util
    
    scraper_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job-scraper")
    module_path = os.path.join(scraper_dir, "main.py")
    
    if scraper_dir not in sys.path:
        sys.path.insert(0, scraper_dir)
        
    try:
        spec = importlib.util.spec_from_file_location("job_scraper_main", module_path)
        job_scraper_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_scraper_main)
        run_job_scraper = job_scraper_main.run_job_scraper
    except Exception as e:
        logger.error(f"❌ Could not import run_job_scraper: {e}")
        return

    while True:
        try:
            logger.info("⚡ Background Scraper: Triggering scheduled job scraper run...")
            # run_job_scraper is synchronous and does network IO. Use to_thread to avoid blocking event loop.
            await asyncio.to_thread(run_job_scraper)
        except Exception as e:
            logger.error(f"❌ Error during background scraper execution: {e}")
            
        sleep_seconds = SCRAPER_MIN_RUN_INTERVAL * 60
        logger.info(f"⏳ Background Scraper: Next run scheduled in {SCRAPER_MIN_RUN_INTERVAL} minutes.")
        await asyncio.sleep(sleep_seconds)


# Lifespan manager to manage the HTTP client and RabbitMQ consumer lifecycle
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

    # Setup RabbitMQ Connection for publishing
    rabbitmq_url = f"amqp://{RABBITMQ_USERNAME}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"
    try:
        app.state.rabbitmq_connection = await aio_pika.connect_robust(rabbitmq_url)
        app.state.rabbitmq_channel = await app.state.rabbitmq_connection.channel()
        await app.state.rabbitmq_channel.declare_queue(RABBITMQ_QUEUE_JOBALERTS, durable=True)
        logger.info(f"✅ RabbitMQ publisher started. Ready to publish to queue: '{RABBITMQ_QUEUE_JOBALERTS}'")
    except Exception as e:
        logger.error(f"❌ Failed to connect to RabbitMQ for publishing: {e}")
        app.state.rabbitmq_connection = None
        app.state.rabbitmq_channel = None

    # Start the RabbitMQ consumer as a background task
    consumer_task = asyncio.create_task(start_rabbitmq_consumer(app))
    logger.info("🐇 RabbitMQ consumer background task launched.")

    # Start the background scraper task if enabled
    scraper_task = None
    if RUN_SCRAPER_BACKGROUND:
        scraper_task = asyncio.create_task(run_scraper_background_loop(app))
        logger.info("⚡ Background job scraper task launched.")

    yield

    # Clean up: cancel tasks and close connections
    consumer_task.cancel()
    if scraper_task:
        scraper_task.cancel()
        
    try:
        await consumer_task
        if scraper_task:
            await scraper_task
    except asyncio.CancelledError:
        pass
        
    await app.state.http_client.aclose()
    
    if app.state.rabbitmq_connection:
        await app.state.rabbitmq_connection.close()
        logger.info("🛑 RabbitMQ publisher connection closed.")
        
    logger.info("🛑 HTTP Client and RabbitMQ consumer successfully closed.")


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
    jobs: Optional[List[dict]] = Field(None, description="Optional raw list of jobs for downstream queues")


# ─── ENDPOINTS ──────────────────────────────────────────────────────────────

@app.get("/ping", status_code=status.HTTP_200_OK)
async def ping():
    """Simple ping-pong endpoint to verify if the server is awake."""
    return "pong"

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

    # Build verification URL
    verify_link = f"https://resume-maker-pro.netlify.app/verify?token={request.token}"
    
    # Styled HTML email template
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; margin: 0; padding: 0;">
        <table width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
          <tr>
            <td style="padding: 40px; text-align: center;">
              <h1 style="color: #1a73e8; font-size: 28px; margin-bottom: 20px;">Verify Your Email</h1>
              <p style="font-size: 18px; color: #333;">Hi there 👋,</p>
              <p style="font-size: 16px; color: #555;">
                Thank you for signing up!<br/>
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
        "subject": "Verify your account",
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
            
            # If jobs list is present, publish the details to RabbitMQ jobalerts queue
            if request.jobs and hasattr(app.state, "rabbitmq_channel") and app.state.rabbitmq_channel:
                try:
                    message_payload = {
                        "to_email": request.to_email,
                        "subject": request.subject,
                        "jobs": request.jobs
                    }
                    await app.state.rabbitmq_channel.default_exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(message_payload).encode(),
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                        ),
                        routing_key=RABBITMQ_QUEUE_JOBALERTS
                    )
                    logger.info(f"📬 Successfully published {len(request.jobs)} jobs to RabbitMQ queue: '{RABBITMQ_QUEUE_JOBALERTS}'")
                except Exception as e:
                    logger.error(f"❌ Failed to publish job alert to RabbitMQ: {e}")

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
