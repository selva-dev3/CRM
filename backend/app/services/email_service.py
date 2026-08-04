import logging
from app.config import settings
import requests

logger = logging.getLogger(__name__)


# Default sender for Resend sandbox mode (no custom domain verified yet).
# In sandbox mode, Resend only lets you send emails using this address,
# and only to the email address you signed up to Resend with.
# Once you verify your own domain on resend.com/domains, replace this
# with e.g. "Enterprise CRM Support <noreply@yourdomain.com>".


def send_email(
    to_email: str,
    subject: str,
    html_content: str
) -> bool:

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json",
    }

    payload = {
        "sender": {
            "name": settings.EMAILS_FROM_NAME,
            "email": settings.EMAILS_FROM_EMAIL,
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code in (200, 201):
            logger.info(f"Email sent successfully to {to_email}")
            print(f"[BREVO SUCCESS] Email sent to {to_email}")
            return True

        logger.error(
            f"Brevo Error {response.status_code}: {response.text}"
        )

        print(
            f"[BREVO ERROR] {response.status_code}: {response.text}"
        )

        return False

    except Exception as e:
        logger.exception(f"Brevo API failed: {e}")
        print(f"[BREVO ERROR] {e}")
        return False


def send_reset_password_email(
    email_to: str,
    token: str,
    user_name: str = "User"
) -> bool:
    """Sends password reset HTML email via Brevo API."""

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    subject = f"{settings.PROJECT_NAME} - Password Reset Request"

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

            <p>
                We received a request to reset your password for
                <strong>{settings.PROJECT_NAME}</strong>.
            </p>

            <p>
                This link is valid for
                {settings.RESET_TOKEN_EXPIRE_MINUTES} minutes.
            </p>

            <a href="{reset_url}" class="btn">
                Reset My Password
            </a>

            <br><br>

            <p>Reset Token:</p>

            <code style="background:#f3f4f6;padding:6px 12px;border-radius:4px;">
                {token}
            </code>

            <div class="footer">
                <p>If you didn't request this reset, ignore this email.</p>
                <p>&copy; 2026 {settings.PROJECT_NAME}</p>
            </div>

        </div>
    </body>
    </html>
    """

    try:
        print(f"[BREVO RESET] Sending password reset email to {email_to}...")

        success = send_email(
            to_email=email_to,
            subject=subject,
            html_content=html_content,
        )

        if success:
            logger.info(f"Password reset email sent successfully to {email_to}")
            print(f"[BREVO SUCCESS] Password reset email sent to {email_to}")
        else:
            logger.error(f"Password reset email failed for {email_to}")
            print(f"[BREVO FAILED] Password reset email failed for {email_to}")

        return success

    except Exception as e:
        logger.exception(f"Password reset email error: {e}")
        print(f"[BREVO ERROR] {e}")
        return False

def send_user_invite_email(
    email_to: str,
    role: str = "Member",
    invite_url: str = None
) -> bool:
    """Sends Organization User Invitation HTML email via Brevo API."""

    if not invite_url:
        invite_url = f"{settings.FRONTEND_URL}/accept-invite"

    subject = f"You're Invited to Join {settings.PROJECT_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .btn {{ display: inline-block; padding: 12px 24px; background-color: #10b981; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; }}
            .footer {{ font-size: 12px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Team Member Invitation</h2>

            <p>Hello,</p>

            <p>
                You have been invited to join
                <strong>{settings.PROJECT_NAME}</strong>
                as a
                <strong>{role}</strong>.
            </p>

            <p>
                Click the button below to accept your invitation
                and complete your account setup.
            </p>

            <a href="{invite_url}" class="btn">
                Accept Invitation
            </a>

            <br><br>

            <p>If the button doesn't work, use this link:</p>

            <a href="{invite_url}">
                {invite_url}
            </a>

            <div class="footer">
                <p>
                    If you were not expecting this invitation,
                    you can safely ignore this email.
                </p>

                <p>
                    &copy; 2026 {settings.PROJECT_NAME}. All rights reserved.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        print(f"[BREVO INVITE] Sending invitation email to {email_to}...")

        success = send_email(
            to_email=email_to,
            subject=subject,
            html_content=html_content
        )

        if success:
            logger.info(f"Invitation email sent successfully to {email_to}")
            print(f"[BREVO SUCCESS] Invitation email sent to {email_to}")
        else:
            logger.error(f"Invitation email failed for {email_to}")
            print(f"[BREVO FAILED] Invitation email failed for {email_to}")

        return success

    except Exception as e:
        logger.exception(f"Invitation email error: {e}")
        print(f"[BREVO ERROR] {e}")
        return False

def send_magic_link_email(
    email_to: str,
    token: str,
    user_name: str = "User"
) -> bool:
    """Sends Passwordless Magic Link HTML email via Brevo API."""

    magic_url = f"{settings.FRONTEND_URL}/magic-link?token={token}"
    subject = f"{settings.PROJECT_NAME} - Your Passwordless Login Link"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; background: #ffffff; padding: 30px; border-radius: 8px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .btn {{ display: inline-block; padding: 12px 24px; background-color: #8b5cf6; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; }}
            .footer {{ font-size: 12px; color: #6b7280; margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">

            <h2>Passwordless Magic Link Login</h2>

            <p>Hello {user_name},</p>

            <p>
                Click the button below to log in to your
                <strong>{settings.PROJECT_NAME}</strong>
                account instantly without entering a password.
            </p>

            <a href="{magic_url}" class="btn">
                Log In to CRM
            </a>

            <br><br>

            <p>If the button doesn't work, use this link:</p>

            <a href="{magic_url}">
                {magic_url}
            </a>

            <br><br>

            <p>Magic Token:</p>

            <code style="background:#f3f4f6;padding:6px 12px;border-radius:4px;font-size:16px;">
                {token}
            </code>

            <div class="footer">
                <p>
                    If you did not request this magic login link,
                    please ignore this email.
                </p>

                <p>
                    &copy; 2026 {settings.PROJECT_NAME}. All rights reserved.
                </p>
            </div>

        </div>
    </body>
    </html>
    """

    try:
        print(f"[BREVO MAGIC LINK] Sending magic link email to {email_to}...")

        success = send_email(
            to_email=email_to,
            subject=subject,
            html_content=html_content
        )

        if success:
            logger.info(f"Magic link email sent successfully to {email_to}")
            print(f"[BREVO SUCCESS] Magic link email sent to {email_to}")
        else:
            logger.error(f"Magic link email failed for {email_to}")
            print(f"[BREVO FAILED] Magic link email failed for {email_to}")

        return success

    except Exception as e:
        logger.exception(f"Magic link email error: {e}")
        print(f"[BREVO ERROR] {e}")
        return False