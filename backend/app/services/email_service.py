import resend
import logging
from app.config import settings
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    sender_email = settings.EMAILS_FROM_EMAIL
    smtp_user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD
    smtp_server = settings.SMTP_HOST
    smtp_port = int(settings.SMTP_PORT)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(smtp_user, password)

            message = MIMEMultipart("alternative")
            message["From"] = f"{settings.EMAILS_FROM_NAME} <{sender_email}>"
            message["To"] = to_email
            message["Subject"] = subject

            message.attach(MIMEText(html_content, "html"))

            server.sendmail(
                sender_email,
                [to_email],
                message.as_string()
            )

        return True

    except Exception as e:
        logger.exception(f"SMTP send failed: {e}")
        raise


def send_reset_password_email(email_to: str, token: str, user_name: str = "User") -> bool:
    """Sends password reset HTML email via SMTP containing token and reset link."""
    reset_url = f"{settings.frontend_base_url}/reset-password?token={token}"
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

    try:
        print(f"[SMTP SENDING] Sending password reset email to {email_to}...")

        send_email(
            to_email=email_to,
            subject=subject,
            html_content=html_content
        )

        logger.info(f"Password reset email sent successfully to {email_to}")
        print(f"[SMTP SUCCESS] Password reset email sent to {email_to}")

        return True

    except Exception as e:
        logger.error(f"Failed to send email to {email_to}: {str(e)}")
        print(f"[SMTP ERROR] Failed to send email to {email_to}: {str(e)}")
        print(f"[FALLBACK RESET LINK] User: {email_to} -> Link: {reset_url}")

        return False


def send_user_invite_email(email_to: str, role: str = "Member", invite_url: str = None) -> bool:
    """Sends Organization User Invitation HTML email via SMTP."""

    if not invite_url:
        invite_url = f"{settings.frontend_base_url}/accept-invite"

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
        print(f"[SMTP INVITE SENDING] Sending invitation email to {email_to}...")

        send_email(
            to_email=email_to,
            subject=subject,
            html_content=html_content
        )

        logger.info(f"Invitation email sent successfully to {email_to}")

        print(f"[SMTP INVITE SUCCESS] Invitation email sent to {email_to}")

        return True

    except Exception as e:
        logger.error(f"Failed to send invitation email to {email_to}: {str(e)}")

        print(f"[SMTP INVITE ERROR] Failed to send invitation email to {email_to}: {str(e)}")

        return False

def send_magic_link_email(email_to: str, token: str, user_name: str = "User") -> bool:
    """Sends Passwordless Magic Link HTML email via SMTP."""

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
        print(f"[SMTP MAGIC LINK SENDING] Sending magic link email to {email_to}...")

        send_email(
            to_email=email_to,
            subject=subject,
            html_content=html_content
        )

        logger.info(f"Magic link email sent successfully to {email_to}")

        print(f"[SMTP MAGIC LINK SUCCESS] Magic link email sent to {email_to}")

        return True

    except Exception as e:
        logger.error(f"Failed to send magic link email to {email_to}: {str(e)}")

        print(f"[SMTP MAGIC LINK ERROR] Failed to send email to {email_to}: {str(e)}")

        return False