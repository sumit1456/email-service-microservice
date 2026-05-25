# Independent Email Microservice 📨

A self-contained, high-performance, asynchronous **FastAPI** email service that interfaces with the **Brevo API (SMTP v3)**. Built to send verification links and generic custom HTML emails seamlessly for any application.

---

## ⚡ Features

- **Asynchronous Execution**: Uses `httpx.AsyncClient` with connection-pooling for ultra-fast, concurrent HTTP requests.
- **FastAPI /docs integration**: Interactive Swagger UI auto-documentation available out-of-the-box.
- **Verification Template**: Pre-built verification email template matching the original `ResumeMaker` style.
- **Generic Email Support**: Exposes a flexible general-purpose endpoint to send custom HTML contents.
- **Robust Validation**: Implements `pydantic` schemas for structured request body validation (with strict email format checks via `EmailStr`).
- **Comprehensive Logging**: Detailed log format tracking every outbound delivery.

---

## 🛠️ Getting Started

### 1. Requirements

- Python 3.8 or higher installed on your system.

### 2. Installation

1. Navigate to the `email-service` directory:
   ```bash
   cd email-service
   ```
2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   * **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   * **Windows (Command Prompt)**:
     ```cmd
     .\venv\Scripts\activate.bat
     ```
   * **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Environment Setup

Ensure your `.env` file has the following configurations:
```env
BREVO_API_KEY=your-brevo-api-key-here
SENDER_EMAIL=sumithatekar9@gmail.com
SENDER_NAME=Resume Maker
PORT=8081
HOST=0.0.0.0
```

---

## 🚀 Running the Service

Start the FastAPI application with `uvicorn`:
```bash
python main.py
```
Or run directly through `uvicorn`:
```bash
uvicorn main:app --host 0.0.0.0 --port 8081 --reload
```

Once running, you can access:
- **Interactive API Docs (Swagger UI)**: [http://localhost:8081/docs](http://localhost:8081/docs)
- **Alternative Docs (ReDoc)**: [http://localhost:8081/redoc](http://localhost:8081/redoc)
- **Health Check**: [http://localhost:8081/health](http://localhost:8081/health)

---

## 📂 API Reference

### 1. Verification Email

- **Endpoint**: `POST /send-verification`
- **Request Body**:
  ```json
  {
    "email": "recipient@example.com",
    "token": "verification-token-xyz-123"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Verification email sent successfully to recipient@example.com",
    "data": { ... }
  }
  ```

### 2. Generic Custom Email

- **Endpoint**: `POST /send-email`
- **Request Body**:
  ```json
  {
    "to_email": "recipient@example.com",
    "subject": "Greetings from New App!",
    "html_content": "<h1>Hello!</h1><p>This is a custom email template.</p>",
    "sender_name": "My New App",       // Optional
    "sender_email": "sender@domain.com"  // Optional
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Email sent successfully to recipient@example.com",
    "data": { ... }
  }
  ```
