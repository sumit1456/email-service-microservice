import time
import datetime
import httpx
from typing import List, Dict, Any
import config
from filter import _parse_posted_date

def build_job_card_html(job: Dict[str, Any]) -> str:
    """Generates a premium glassmorphic HTML card for a single job listing."""
    title = job.get("title", "Software Intern")
    company = job.get("company", "Tech Company")
    location = job.get("location", "India / Remote")
    stipend = job.get("stipend", "Not Disclosed")
    posted_date = job.get("posted_date", "Recently")
    url = job.get("url")
    listing_url = job.get("listing_url")
    source = job.get("source", "Scraper")

    if url == "#":
        url = None
    if listing_url == "#":
        listing_url = None

    # Check if the posting is very recent (<= 3 days)
    is_new = False
    if posted_date:
        if posted_date.strip().lower() == "recently":
            is_new = True
        else:
            try:
                parsed_date = _parse_posted_date(posted_date)
                if parsed_date:
                    age_days = (datetime.date.today() - parsed_date).days
                    if age_days <= 3:
                        is_new = True
            except Exception:
                pass

    new_badge = ""
    if is_new:
        new_badge = '<span style="background-color: #10b981; color: #ffffff; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-left: 6px; text-transform: uppercase; vertical-align: middle;">New ✨</span>'

    # Set badge colors based on platform
    source_colors = {
        "Internshala":     {"bg": "#e0f2fe", "text": "#0369a1"},  # light blue
        "Naukri":          {"bg": "#fef3c7", "text": "#b45309"},  # amber
        "Wellfound":       {"bg": "#f3e8ff", "text": "#6b21a8"},  # purple
        "Cutshort":        {"bg": "#dcfce7", "text": "#15803d"},  # green
        "We Work Remotely":{"bg": "#ffedd5", "text": "#c2410c"},  # orange
        "Remotive":        {"bg": "#e0e7ff", "text": "#4338ca"},  # indigo
        "Hacker News":     {"bg": "#ffebd6", "text": "#d84315"},  # deep orange
        # ── New platforms ─────────────────────────────────────────
        "Remote OK":       {"bg": "#d1fae5", "text": "#065f46"},  # emerald
        "Arbeitnow":       {"bg": "#fce7f3", "text": "#9d174d"},  # pink
        "Jobicy":          {"bg": "#ede9fe", "text": "#5b21b6"},  # violet
        "Unstop":          {"bg": "#fff7ed", "text": "#c2410c"},  # warm orange
        "Indeed India":    {"bg": "#dbeafe", "text": "#1d4ed8"},  # blue
        "YC Startups":     {"bg": "#fef9c3", "text": "#854d0e"},  # yellow
    }

    colors = source_colors.get(source, {"bg": "#f3f4f6", "text": "#374151"})

    # Determine action buttons HTML
    buttons = []
    if url:
        buttons.append(f"""
            <a href="{url}" target="_blank" style="background: linear-gradient(135deg, #6366f1, #4f46e5); color: #ffffff; padding: 8px 16px; font-size: 13px; font-weight: 700; text-decoration: none; border-radius: 6px; display: inline-block; text-align: center; margin-right: 10px; margin-bottom: 8px;">
                Apply Now 🚀
            </a>
        """)
    if listing_url and listing_url != url:
        buttons.append(f"""
            <a href="{listing_url}" target="_blank" style="background: #334155; border: 1px solid #475569; color: #f8fafc; padding: 8px 16px; font-size: 13px; font-weight: 700; text-decoration: none; border-radius: 6px; display: inline-block; text-align: center; margin-bottom: 8px;">
                View Listing 🔗
            </a>
        """)
    if not buttons:
        buttons.append(f"""
            <a href="#" style="background: #334155; color: #94a3b8; padding: 8px 16px; font-size: 13px; font-weight: 700; text-decoration: none; border-radius: 6px; display: inline-block; text-align: center; cursor: not-allowed; pointer-events: none;">
                No Link Available
            </a>
        """)
    buttons_html = "\n".join(buttons)

    return f"""
    <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 20px; font-family: 'Inter', sans-serif;">
        <!-- Header row: Title and Source -->
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="vertical-align: top;">
                    <h3 style="color: #f8fafc; font-size: 18px; margin: 0 0 4px 0; font-weight: 700; font-family: 'Inter', sans-serif;">{title}</h3>
                    <p style="color: #a5b4fc; font-size: 14px; font-weight: 600; margin: 0 0 12px 0;">🏢 {company}</p>
                </td>
                <td style="vertical-align: top; text-align: right; width: 120px;">
                    <span style="background-color: {colors['bg']}; color: {colors['text']}; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 20px; display: inline-block; text-transform: uppercase;">
                        {source}
                    </span>
                </td>
            </tr>
        </table>

        <!-- Metadata Section -->
        <div style="margin-bottom: 16px;">
            <table cellpadding="0" cellspacing="0" style="font-size: 13px; color: #94a3b8; line-height: 1.8;">
                <tr>
                    <td style="padding-right: 15px;">📍 <strong>Location:</strong> {location}</td>
                    <td style="padding-right: 15px;">💰 <strong>Stipend:</strong> {stipend}</td>
                </tr>
                <tr>
                    <td colspan="2">📅 <strong>Posted:</strong> {posted_date}{new_badge}</td>
                </tr>
            </table>
        </div>

        <!-- Action Row -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top: 15px; border-top: 1px solid #334155; padding-top: 15px;">
            <tr>
                <td>
                    {buttons_html}
                </td>
            </tr>
        </table>
    </div>
    """

def build_digest_html(jobs: List[Dict[str, Any]]) -> str:
    """Generates the full premium email body template containing the job cards."""
    cards_html = "\n".join([build_job_card_html(job) for job in jobs])
    
    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            body {{
                font-family: 'Inter', Arial, sans-serif;
                background-color: #0b0f19;
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body style="font-family: 'Inter', Arial, sans-serif; background-color: #0b0f19; margin: 0; padding: 0; -webkit-font-smoothing: antialiased;">
        <table width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b0f19; padding: 40px 10px;">
            <tr>
                <td align="center">
                    <table width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #0f172a; border-radius: 16px; border: 1px solid #1e293b; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);">
                        
                        <!-- Premium Gradient Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1e1b4b, #311042); padding: 40px 30px; text-align: center; border-bottom: 1px solid #334155;">
                                <h1 style="background: linear-gradient(to right, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; color: #818cf8; font-size: 26px; font-weight: 700; margin: 0 0 10px 0; font-family: 'Inter', sans-serif;">
                                    Java Internship Digest 🚀
                                </h1>
                                <p style="color: #94a3b8; font-size: 14px; margin: 0; font-weight: 500;">
                                    We found <strong>{len(jobs)}</strong> new curated Java / Software Developer internships matching your criteria.
                                </p>
                            </td>
                        </tr>

                        <!-- Content Section -->
                        <tr>
                            <td style="padding: 30px 24px;">
                                {cards_html}
                            </td>
                        </tr>

                        <!-- Premium Footer -->
                        <tr>
                            <td style="background-color: #0b0f19; padding: 25px 30px; text-align: center; border-top: 1px solid #1e293b; font-size: 12px; color: #475569;">
                                <p style="margin: 0 0 8px 0; font-weight: 600;">Job Scraper Microservice</p>
                                <p style="margin: 0; font-size: 11px;">
                                    This automated digest was generated according to your filters: 
                                    <strong>Java / Spring Boot</strong> developer internships in <strong>Pune / Remote</strong>.
                                </p>
                                <hr style="margin: 15px auto; border: none; border-top: 1px solid #1e293b; max-width: 150px;">
                                <p style="margin: 0; font-size: 10px; color: #334155;">
                                    &copy; {time.strftime('%Y')} Resume Maker Pro. All rights reserved.
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

def send_notification(jobs: List[Dict[str, Any]], db: Any = None):
    """Sends the job digest to the FastAPI email microservice."""
    if not jobs:
        print("[INFO] No new jobs to notify. Skipping email dispatch.")
        return

    # Check daily email limit
    emails_sent_today = 0
    if db is not None:
        current_date = time.strftime("%Y-%m-%d")
        last_email_date = db.get_metadata("last_email_sent_date")
        
        # Reset count if it's a new day
        if last_email_date != current_date:
            db.set_metadata("last_email_sent_date", current_date)
            db.set_metadata("emails_sent_today", "0")
        else:
            try:
                emails_sent_today = int(db.get_metadata("emails_sent_today") or "0")
            except ValueError:
                emails_sent_today = 0
                
        if emails_sent_today >= config.MAX_EMAILS_PER_DAY:
            print(f"[WARN] Daily email limit reached ({config.MAX_EMAILS_PER_DAY}). Skipping email dispatch.")
            return

    print(f"[EMAIL] Formatting digest for {len(jobs)} listings...")
    html_content = build_digest_html(jobs)
    
    subject = f"🚀 {len(jobs)} New Java Internships Found ({time.strftime('%b %d')})"
    
    payload = {
        "to_email": config.RECIPIENT_EMAIL,
        "subject": subject,
        "html_content": html_content,
        "sender_name": config.SENDER_NAME,
        "sender_email": config.SENDER_EMAIL,
        "jobs": jobs
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    print(f"[EMAIL] Calling Email Service: {config.EMAIL_SERVICE_URL}")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(config.EMAIL_SERVICE_URL, json=payload, headers=headers)
            if response.status_code in (200, 201):
                print(f"[OK] Email Digest sent successfully! Response: {response.text}")
                # Increment email sent count
                if db is not None:
                    db.set_metadata("emails_sent_today", str(emails_sent_today + 1))
            else:
                print(f"[ERROR] Email Service failed to accept payload. Code: {response.status_code}, Detail: {response.text}")
    except Exception as e:
        print(f"[ERROR] Error communicating with Email Service: {e}")
