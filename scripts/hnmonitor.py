"""
Monitoring application.

This runs as a separate app from hnscrape to make sure it is running properly.
It will send an email if:
    * The database is not being updated as expected
    * Hnscrape is reporting more than a few errors
"""

from __future__ import division
from time import sleep
from datetime import datetime, timedelta
import couchdb
import smtplib, json, argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

import config
logger = config.logging.getLogger(__name__)

def loggingSetup(logfile):
    log_level = config.logging.INFO # Hardcode, but run minimally

    logger.setLevel(log_level)

    # File logging
    h=config.logging.FileHandler(logfile)
    h.setLevel(log_level)
    formatter=config.logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    h.setFormatter(formatter)
    logger.addHandler(h)

    return

def firstSleepTime(curHour = datetime.now().hour):
    # Note: parameter curHour is for testing.

    f = config.RUNFREQUENCY

    nextHrFn = lambda cur: ((cur // f + 1) * f)
    nextHr = nextHrFn(curHour)
    c = datetime.now()
    curTime  = datetime(c.year, c.month, c.day, curHour, c.minute, c.second)
    nextTime = datetime(c.year, c.month, c.day)+timedelta(hours=nextHr)

    numSeconds = (nextTime - curTime).total_seconds()

    # For debugging
    # print 'firstSleepTime: curHour: {2}  nextHr: {0}, nextTime: {1}, totalSeconds: {3}, totalSecs in hours: {4:.1g}'.format(nextHr, nextTime, curHour, numSeconds, numSeconds/3600)

    # for i in range(24):
    #     firstSleepTime(i)

    return numSeconds

def checkErrors():
    with open(config.ERRORS_ONLY_LOG, 'r') as f:
        lines=f.readlines()

    # Now reset the log file to empty
    with open(config.ERRORS_ONLY_LOG, 'w') as f:
        f.write('')

    tooManyErrors = len(lines) > config.MAXERRORS

    if True: # (for debugging) tooManyErrors:
        message='checkErrors: tooManyErrors: {0}, MaxErrors = {1}. Actual Errors = {2}'.format(tooManyErrors, config.MAXERRORS, len(lines))
        logger.info(message)

    if tooManyErrors:
        retval = {'tooManyErrors' : True, 'message': message}
    else:
        retval = None

    return None

class CouchData(object):
    def __init__(self):
        couch = couchdb.Server(config.COUCH_SERVER)
        couch.resource.credentials = (config.COUCH_UN, config.COUCH_PW)
        self.db = couch[config.COUCH_DB]
        self.db.info()  # Will raise an error if it doesn't work
        logger.info('Connection to couch established')
        self.setLastSeq()

    def setLastSeq(self):
        results=self.db.changes(descending=True,limit=1)
        self.last_seq = results['last_seq']


    def getNumPostsAndUpdateSeq(self):
        results=self.db.changes(since=self.last_seq)
        numPosts=len(results.get('results'))
        self.last_seq = results['last_seq']
        return numPosts


def checkPosts(couch):
    numPosts=couch.getNumPostsAndUpdateSeq()

    totalWait = sum([todo['wait'] for todo in config.PAGES_TO_GET])
    pagesPerHour = 60*60/totalWait
    expectedPosts = pagesPerHour * config.NUMPOSTSPERPAGE

    tooFewPosts = numPosts < expectedPosts * config.POSTERRORTHRESHOLD

    #print 'checkPosts: numPost: {0}, totalWait: {1}, pagesPerHour: {2}, expectedPosts: {3}, threshold: {4:.1%} tooFewPosts: {5}'.format(numPosts, totalWait, pagesPerHour, expectedPosts, config.POSTERRORTHRESHOLD, tooFewPosts)

    if True: # For debugging tooFewPosts:
        message='checkPosts: tooFewPosts: {3}. Expected ~ {0} (threshold: {1:.1%}). Posted: {2}'.format(expectedPosts, config.POSTERRORTHRESHOLD, numPosts, tooFewPosts)
        logger.info(message)

    if tooFewPosts:
        retval= {'tooFewPosts' : True, 'message' : message}

    return retval

def sendMail(eFrom=None, eTo=None, eSubject=None, eText=None, dry_run=False):
    if not eFrom or not eTo or not eSubject or not eText or  type(eTo)=='list':
        raise Exception('Error - invalid arguments. eFrom={0}, eTo={1}, eSubject={2}, eText={3}'.format(eFrom, eTo, eSubject, eText[:20]+'...' if type(eText==str) else type(eText)))

    if dry_run:
        logger.info('sendMail: Skipping (called with dry_run)')
        return

    msg=MIMEText(eText)
    msg['Subject']= eSubject
    msg['From']=eFrom
    msg['To']=', '.join(eTo)

    textPart=MIMEText(config.EMAIL_TEXT)


    logger.info('Sending mail...')
    print 'sending mail'
    server=smtplib.SMTP(config.SMTP_SERVER, config.EMAIL_PORT, timeout=10, debug)
    server.set_debuglevel(4)
    server.starttls()
    server.login(config.EMAIL_ADDR, config.EMAIL_PW)
    server.sendmail(eFrom, eTo, msg.as_string())
    server.quit()
    print 'done sending mail'
    logger.info('Sent mail successfully')

def getDefaults():
    return {
        'From' : config.EMAIL_ADDR,
        'To': config.EMAIL_RECIPIENTS,
        'Subject':config.EMAIL_SUBJECT,
        'dry_run':False
    }

def emailAlert(message):
    defaults = getDefaults()

    sendMail(
        eFrom=defaults['From'],
        eTo=defaults['To'],
        eSubject=defaults['Subject'],
        eText=message,
        dry_run=defaults['dry_run'],
        )

    return

def alert(tooManyErrors, tooFewPosts):
    message = config.EMAIL_TEXT+'\n'
    if tooManyErrors:
        message+=tooManyErrors['message']+'\n'
    if tooFewPosts:
        message+=tooFewPosts['message']+'\n'

    emailAlert(message)
    return

def main():
    loggingSetup(config.LOGFILE)
    logger.info('hnmonitor: starting')
    couch=CouchData()

    logger.info('First time - going to sleep until: {0}'.format(datetime.now()+timedelta(seconds=firstSleepTime())))
    #sleep(firstSleepTime())
    sleep(1)
    while True:
        logger.info('Awake and running')
        tooManyErrors=checkErrors()
        tooFewPosts=checkPosts(couch)

        if tooManyErrors or tooFewPosts:
            alert(tooManyErrors, tooFewPosts)

        exit()
    logger.info('hnmonitor: terminating')
    return

def testEmail():
    print 'About to send mail'
    emailAlert('This is the body of the email.\nLine 2\n')
    print 'Sent mail successfully'

if __name__ == '__main__':
    #main()
    testEmail()


