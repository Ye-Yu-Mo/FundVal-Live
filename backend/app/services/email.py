import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from ..config import Config

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, content: str, is_html: bool = False):
    """
    Send an email using SMTP settings from Config.
    """
    if not Config.SMTP_HOST or not Config.SMTP_USER:
        logger.warning("SMTP not configured. Skipping email send.")
        return False

    msg = MIMEMultipart()
    msg['From'] = Config.EMAIL_FROM
    msg['To'] = to_email
    msg['Subject'] = subject

    if is_html:
        msg.attach(MIMEText(content, 'html'))
    else:
        msg.attach(MIMEText(content, 'plain'))

    try:
        server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
