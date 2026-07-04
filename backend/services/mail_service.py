import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

def send_email(subject, recipient, html_body):
    """
    Core function to send emails. Uses SMTP if configured, 
    otherwise logs to logs/emails_sent.log and console.
    """
    smtp_server = getattr(Config, 'SMTP_SERVER', None)
    smtp_port = getattr(Config, 'SMTP_PORT', 587)
    smtp_user = getattr(Config, 'SMTP_USER', None)
    smtp_password = getattr(Config, 'SMTP_PASSWORD', None)

    # 1. SMTP Sending if configured
    if smtp_server and smtp_user and smtp_password:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            print(f"SMTP: Sent email to {recipient} with subject '{subject}'")
            return True
        except Exception as e:
            print(f"SMTP error sending email to {recipient}: {e}")
            # Fall back to logging

    # 2. Local Logging (Fallback / Dev environment helper)
    log_dir = os.path.join(Config.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'emails_sent.log')
    
    log_entry = f"""
==================================================
📧 EMAIL SENT (MOCK LOG)
Date/Time: 2026-07-03
To: {recipient}
Subject: {subject}
--------------------------------------------------
{html_body}
==================================================
"""
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write email to log file: {e}")
        
    print(f"📧 [Mock Email] Sent to {recipient} | Subject: {subject} (Check logs/emails_sent.log)")
    return True

def send_match_notification(owner_email, owner_name, finder_email, finder_name, lost_item, found_item, score, secure_link):
    """
    Sends match notifications to both owner and finder for high confidence matches.
    """
    lost_name = lost_item['item_name']
    found_name = found_item['item_name']
    location = lost_item['location']
    image_url = found_item.get('image_path', '')
    
    # Format image path for display
    img_tag = ""
    if image_url:
        if image_url.startswith('http'):
            img_tag = f'<img src="{image_url}" style="max-width:250px;border-radius:10px;margin:15px 0;" alt="Found Item Image">'
        else:
            img_tag = f'<img src="http://localhost:5000/{image_url}" style="max-width:250px;border-radius:10px;margin:15px 0;" alt="Found Item Image">'

    # Owner email body
    owner_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <h2 style="color: #2563eb; font-weight: bold; margin-bottom: 5px;">Potential Match Found!</h2>
        <p style="color: #64748b; margin-top: 0;">Hi {owner_name},</p>
        <p>Our AI Matching Engine has found a high-confidence match for your reported lost item: <strong>{lost_name}</strong>.</p>
        
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Matching Item:</strong> {found_name}</p>
            <p style="margin: 5px 0;"><strong>Match Confidence:</strong> <span style="color: #10b981; font-weight: bold;">{score}%</span></p>
            <p style="margin: 5px 0;"><strong>Found Location:</strong> {found_item['location']}</p>
            {img_tag}
        </div>
        
        <p>To protect your privacy, contact details are hidden by default. You can request the finder's contact details or start a secure real-time chat via the link below:</p>
        
        <a href="{secure_link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin: 15px 0;">Request Contact & View Match</a>
        
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">FindIt Lost & Found Platform - Reconnecting belongings securely.</p>
    </div>
    """
    send_email(f"Match Alert ({score}% Match): '{lost_name}'", owner_email, owner_html)

    # Finder email body
    finder_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <h2 style="color: #0d9488; font-weight: bold; margin-bottom: 5px;">Your Found Item Has a Match!</h2>
        <p style="color: #64748b; margin-top: 0;">Hi {finder_name},</p>
        <p>Someone has reported a lost item that closely matches the item you found: <strong>{found_name}</strong>.</p>
        
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 5px 0;"><strong>Lost Item:</strong> {lost_name}</p>
            <p style="margin: 5px 0;"><strong>Match Confidence:</strong> <span style="color: #10b981; font-weight: bold;">{score}%</span></p>
            <p style="margin: 5px 0;"><strong>Lost Location:</strong> {location}</p>
        </div>
        
        <p>The owner has been notified and may request contact with you shortly. You can manage requests and start a chat via your dashboard:</p>
        
        <a href="{secure_link}" style="display: inline-block; background-color: #0d9488; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; margin: 15px 0;">View Matching Item</a>
        
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">FindIt Lost & Found Platform - Reconnecting belongings securely.</p>
    </div>
    """
    send_email(f"Potential Owner Found ({score}% Match): '{found_name}'", finder_email, finder_html)

def send_otp(recipient_email, username, otp):
    """
    Dispatches an OTP verification code.
    """
    otp_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
        <h2 style="color: #2563eb; font-weight: bold; margin-bottom: 5px;">Verify Your Account</h2>
        <p style="color: #64748b; margin-top: 0;">Hi {username},</p>
        <p>Thank you for using FindIt. Please use the following One-Time Password (OTP) to complete your verification or login request:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #1e3a8a; background-color: #eff6ff; padding: 10px 25px; border-radius: 8px; border: 1px solid #bfdbfe;">
                {otp}
            </span>
        </div>
        
        <p style="color: #64748b; font-size: 14px;">This code is valid for 10 minutes. If you did not request this code, please ignore this email.</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">FindIt Lost & Found Platform</p>
    </div>
    """
    send_email("FindIt OTP Verification Code", recipient_email, otp_html)
