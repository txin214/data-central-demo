"""
Custom email backend for Google Workspace using OAuth2 authentication.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import base64
import json
import os
from pathlib import Path


class GmailOAuth2Backend(BaseEmailBackend):
    """
    Email backend that uses OAuth2 to authenticate with Gmail/Google Workspace SMTP.
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        self.port = getattr(settings, 'EMAIL_PORT', 587)
        self.use_tls = getattr(settings, 'EMAIL_USE_TLS', True)
        self.username = getattr(settings, 'EMAIL_HOST_USER', '')
        self.password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', self.username)
        
        # OAuth2 settings
        self.oauth2_credentials_path = getattr(
            settings, 
            'GMAIL_OAUTH2_CREDENTIALS_PATH', 
            os.path.join(settings.BASE_DIR, 'gmail_credentials.json')
        )
        self.oauth2_token_path = getattr(
            settings,
            'GMAIL_OAUTH2_TOKEN_PATH',
            os.path.join(settings.BASE_DIR, 'gmail_token.json')
        )
    
    def _get_oauth2_access_token(self):
        """
        Get OAuth2 access token from stored credentials.
        Returns the access token string or None if unavailable.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            # Scopes required for Gmail SMTP
            SCOPES = ['https://www.googleapis.com/auth/gmail.send']
            
            creds = None
            
            # Load existing token if available
            if os.path.exists(self.oauth2_token_path):
                creds = Credentials.from_authorized_user_file(self.oauth2_token_path, SCOPES)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # Refresh the token
                    creds.refresh(Request())
                else:
                    # Run OAuth2 flow to get new token
                    if not os.path.exists(self.oauth2_credentials_path):
                        raise FileNotFoundError(
                            f"OAuth2 credentials file not found at {self.oauth2_credentials_path}. "
                            "Please download credentials.json from Google Cloud Console."
                        )
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.oauth2_credentials_path, 
                        SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(self.oauth2_token_path, 'w') as token:
                    token.write(creds.to_json())
            
            return creds.token
            
        except Exception as e:
            if not self.fail_silently:
                raise
            return None
    
    def _smtp_authenticate_oauth2(self, smtp_conn, access_token):
        """
        Authenticate SMTP connection using OAuth2.
        """
        # Get the email address from credentials or settings
        email_address = self.username or self.from_email
        if not email_address:
            raise ValueError("EMAIL_HOST_USER or DEFAULT_FROM_EMAIL must be set")
        
        # OAuth2 SMTP authentication format
        auth_string = f'user={email_address}\x01auth=Bearer {access_token}\x01\x01'
        auth_string = base64.b64encode(auth_string.encode()).decode()
        
        # Send AUTH command
        code, response = smtp_conn.docmd('AUTH', 'XOAUTH2 ' + auth_string)
        if code != 235:
            raise smtplib.SMTPAuthenticationError(code, response)
    
    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects and return the number sent.
        """
        if not email_messages:
            return 0
        
        # Get OAuth2 access token
        access_token = self._get_oauth2_access_token()
        if not access_token:
            if not self.fail_silently:
                raise Exception("Failed to obtain OAuth2 access token")
            return 0
        
        num_sent = 0
        try:
            # Create SMTP connection
            connection = smtplib.SMTP(self.host, self.port)
            connection.set_debuglevel(0)  # Set to 1 for debug output
            
            if self.use_tls:
                connection.starttls()
            
            # Authenticate using OAuth2
            self._smtp_authenticate_oauth2(connection, access_token)
            
            # Send each message
            for message in email_messages:
                sent = self._send_message(connection, message)
                if sent:
                    num_sent += 1
            
            connection.quit()
            
        except Exception as e:
            if not self.fail_silently:
                raise
            return num_sent
        
        return num_sent
    
    def _send_message(self, connection, message):
        """
        Send a single EmailMessage using the SMTP connection.
        """
        try:
            # Create MIME message
            msg = MIMEMultipart('alternative')
            msg['From'] = message.from_email or self.from_email
            msg['To'] = ', '.join(message.to)
            if message.cc:
                msg['Cc'] = ', '.join(message.cc)
            if message.bcc:
                msg['Bcc'] = ', '.join(message.bcc)
            msg['Subject'] = message.subject
            
            # Add body
            if message.body:
                if message.content_subtype == 'html':
                    msg.attach(MIMEText(message.body, 'html'))
                else:
                    msg.attach(MIMEText(message.body, 'plain'))
            
            # Add attachments
            for attachment in message.attachments:
                if isinstance(attachment, tuple):
                    filename, content, mimetype = attachment
                    part = MIMEBase(*mimetype.split('/', 1))
                    part.set_payload(content)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}'
                    )
                    msg.attach(part)
            
            # Send the message
            recipients = list(message.to)
            if message.cc:
                recipients.extend(message.cc)
            if message.bcc:
                recipients.extend(message.bcc)
            
            connection.sendmail(
                msg['From'],
                recipients,
                msg.as_string()
            )
            
            return True
            
        except Exception as e:
            if not self.fail_silently:
                raise
            return False

