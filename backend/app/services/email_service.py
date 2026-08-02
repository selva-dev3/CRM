import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.config import settings

logger = logging.getLogger(__name__)

def send_reset_password_email(email_to: str, token: str, user_name: str = "User") -> bool:
    """Sends password reset HTML email via Gmail SMTP containing token and reset link."""
    reset_url = f"http://localhost:3000/reset-password?token={token}"
    subject = f"{settings.PROJECT_NAME} - Password Reset Request"
    
    sender_email = settings.SMTP_USER or settings.EMAILS_FROM_EMAIL or "selvakumar.dev3@gmail.com"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .btn {{ display: inline-block; padding: 12px 24px; background-color: #2563eb; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; }}
            .footer {{ font-size: 12px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Password Reset Request</h2>
            <p>Hello {user_name},</p>
            <p>We received a request to reset your password for your <strong>{settings.PROJECT_NAME}</strong> account.</p>
            <p>Click the button below to set a new password. This link is valid for {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes:</p>
            <a href="{reset_url}" class="btn">Reset My Password</a>
            <p style="margin-top: 25px;">Or copy and paste this reset token into the application:</p>
            <code style="background: #f3f4f6; padding: 6px 12px; border-radius: 4px; font-size: 16px;">{token}</code>
            <div class="footer">
                <p>If you did not request a password reset, please ignore this email.</p>
                <p>&copy; 2026 {settings.PROJECT_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{sender_email}>"
    message["To"] = email_to
    message.attach(MIMEText(html_content, "html"))

    try:
        smtp_host = settings.SMTP_HOST or "smtp.gmail.com"
        smtp_port = int(settings.SMTP_PORT or 587)
        smtp_user = settings.SMTP_USER or "selvakumar.dev3@gmail.com"
        smtp_pass = settings.SMTP_PASSWORD or "cxwromupefrpeovz"

        print(f"[SMTP SENDING] Connecting to {smtp_host}:{smtp_port} for recipient {email_to}...")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, [email_to], message.as_string())
        
        logger.info(f"Password reset email sent successfully to {email_to}")
        print(f"[SMTP SUCCESS] Real password reset email sent to {email_to} via Gmail SMTP!")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email_to}: {str(e)}")
        print(f"[SMTP ERROR] Failed to send email to {email_to}: {str(e)}")
        print(f"[FALLBACK RESET LINK] User: {email_to} -> Link: {reset_url}")
        return False
