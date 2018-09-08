#!/usr/bin/python

import sys
import smtplib

receiver = 'youremail@yourprovider.com'
sender = 'kswatch@kswatch'
smtpserver = 'localhost'
smtpuser = ''
smtppassword = ''
smtptls = True
smtpstarttls = False

if len(sys.argv) > 1:
    url = sys.argv[1]
else:
    url = ''

message = '''From: %s
To: %s
Subject: Limited pledge available!

A limited pledge has become available.
%s
''' % (sender, receiver, url)

try:
    if smtptls:
        smtp = smtplib.SMTP_SSL(smtpserver)
    else:
        smtp = smtplib.SMTP(smtpserver)
    if smtpstarttls:
        smtp.starttls()
    if smtpuser != '':
        smtp.login(smtpuser, smtppassword)
    smtp.sendmail(sender, [receiver], message)
    print "Successfully sent email"
except smtplib.SMTPException:
    print "Error: unable to send email"
