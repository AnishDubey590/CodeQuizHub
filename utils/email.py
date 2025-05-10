# File: CodeQuizHub/utils/email.py
from flask import current_app, render_template
from flask_mail import Message # Assuming Flask-Mail
from .. import mail # Assuming mail is initialized in CodeQuizHub/__init__.py
import threading

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Failed to send email: {e}")

def send_email(subject, recipients, text_body, html_body):
    app = current_app._get_current_object()
    msg = Message(subject, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    thr = threading.Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr

def send_invitation_email(recipient, inviter_name, org_name, role_name, invitation_link):
    subject = f"Invitation to join {org_name} on CodeQuiz Hub"
    text_body = render_template('email/org_invitation.txt', # Make sure templates/email/ exists
                                inviter_name=inviter_name,
                                org_name=org_name,
                                role_name=role_name,
                                invitation_link=invitation_link)
    html_body = render_template('email/org_invitation.html', # Make sure templates/email/ exists
                                inviter_name=inviter_name,
                                org_name=org_name,
                                role_name=role_name,
                                invitation_link=invitation_link)
    current_app.logger.info(f"Attempting to send invitation email to {recipient}")
    send_email(subject, [recipient], text_body, html_body)