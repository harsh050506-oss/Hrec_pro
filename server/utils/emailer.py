from flask_mail import Message

def send_email(mail, to, subject, body):
    try:
        msg = Message(
            subject=subject,
            recipients=[to],
            body=body,
        )
        mail.send(msg)
        print("✅ Email sent to:", to)
    except Exception as e:
        print("❌ Email failed:", str(e))