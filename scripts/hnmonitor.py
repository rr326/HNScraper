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
import smtplib, argparse, daemon
from email.mime.text import MIMEText
from hnscrape import datetimeToStr

import config
logger = config.logging.getLogger('hnmonitor')

def loggingSetup(logfile, noScreen=False):
    log_level = config.logging.INFO # Hardcode, but run minimally

    logger.setLevel(log_level)

    # File logging
    h=config.logging.FileHandler(logfile)
    h.setLevel(log_level)
    formatter=config.logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
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

    if tooManyErrors or config.HNMONITOR_FORCE_SEND:
        message='checkErrors: tooManyErrors: {0}, MaxErrors = {1}. Actual Errors = {2}'.format(tooManyErrors, config.MAXERRORS, len(lines))
        logger.info(message)
        retval = {'tooManyErrors' : tooManyErrors, 'message': message}
    else:
        retval = None

    return retval

class CouchData(object):
    def __init__(self):
        self.last_seq=None
        couch = couchdb.Server(config.COUCH_SERVER)
        couch.resource.credentials = (config.COUCH_UN, config.COUCH_PW)
        self.db = couch[config.COUCH_DB]
        self.db.info()  # Will raise an error if it doesn't work
        logger.info('Connection to couch established')
        self.lastTimestamp=datetimeToStr(datetime.now()-timedelta(seconds=-2))
        self.setLastSeq()

    def setLastSeq(self):
        self.lastTimestamp = datetimeToStr(datetime.now() - timedelta(seconds=-2))
        results=self.db.changes(descending=True,limit=1)
        self.last_seq = results['last_seq']


    def getNumPostsAndUpdateSeq(self):
        try:
            retval=self.db.changes(since=self.last_seq, include_docs=True)
            numPosts=self.countUpdatesSince(retval.get('results'), self.lastTimestamp)
            self.last_seq = retval['last_seq']
            self.lastTimestamp = datetimeToStr(datetime.now() - timedelta(seconds=-2))
        except Exception as e:
            logger.error('getNumPostsAndUpdateSeq - failed. {0}'.format(e), exc_info=True)
            numPosts=-1
        return numPosts

    @staticmethod
    def countUpdatesSince(results, sinceDateStr):
        numUpdates = 0
        for result in results:
            doc = result.get('doc').get('history')
            if doc:
                for snap in doc:
                    if snap.get('timestamp_str') > sinceDateStr:
                        numUpdates += 1
        return numUpdates

    def getNumPostedTest(self, lastTimestamp=''):
        seq="202583-g1AAAAG3eJzLYWBgYMlgTmFQSElKzi9KdUhJMtfLTS3KLElMT9VLzskvTUnMK9HLSy3JAapkSmRIsv___39WBnMSA8Mm51ygGHtyUpqFYbIFEUag2mOCx54kByCZVA-36oQ92CpTY8NUQzNLIkwh3kt5LECSoQFIAW3bD7Hu9nSwdYYpaWYmhqkk-8yYoHUHINZBfXfQDmxdinmSial5EhEmZQEAMz6PmA"
        #retval = self.db.changes(descending=False, limit=4, since=seq, include_docs=True)
        retval = self.db.changes(descending=True, limit=100,  include_docs=True)
        return self.countUpdatesSince(retval.get('results'), lastTimestamp)


def checkPosts(couch, numHoursWaiting):
    numPosts=couch.getNumPostsAndUpdateSeq()

    totalWait = sum([todo['wait'] for todo in config.PAGES_TO_GET])
    runsPerHour = 60*60/totalWait
    pagesPerRun = len(config.PAGES_TO_GET)
    expectedPostsPerHour = runsPerHour * pagesPerRun  * config.NUMPOSTSPERPAGE
    numExpected = expectedPostsPerHour * numHoursWaiting * config.POSTERRORTHRESHOLD

    tooFewPosts = numPosts < expectedPostsPerHour * numHoursWaiting * config.POSTERRORTHRESHOLD

    if tooFewPosts or config.HNMONITOR_FORCE_SEND:
        message='checkPosts: tooFewPosts: {3}. Expected ~ {0} (threshold: {1:.1%}). Posted: {2}. TimePeriod: {4:.1g}hrs'.format(numExpected, config.POSTERRORTHRESHOLD, numPosts, tooFewPosts, numHoursWaiting)
        logger.info(message)
        retval= {'tooFewPosts' : tooFewPosts, 'message' : message}
    else:
        retval = None

    return retval

def sendMail(eFrom=None, eTo=None, eSubject=None, eText=None, dry_run=False, debugLevel=0):
    if not eFrom or not eTo or not eSubject or not eText or  type(eTo)=='list':
        raise Exception('Error - invalid arguments. eFrom={0}, eTo={1}, eSubject={2}, eText={3}'.format(eFrom, eTo, eSubject, eText[:20]+'...' if type(eText==str) else type(eText)))

    if dry_run:
        logger.info('sendMail: Skipping (called with dry_run)')
        return

    msg=MIMEText(eText)
    msg['Subject']= eSubject
    msg['From']=eFrom
    msg['To']=', '.join(eTo)

    try:
        server=smtplib.SMTP(config.SMTP_SERVER, config.EMAIL_PORT)
        server.set_debuglevel(debugLevel)
        #server.starttls()
        server.login(config.EMAIL_ADDR, config.EMAIL_PW)
        server.sendmail(eFrom, eTo, msg.as_string())
        server.quit()
        logger.info('Sent mail successfully')
    except Exception as e:
        logger.error('sendMail: error sending mail to {0}. Error code: {1}'.format(eTo, e))

def getDefaults():
    return {
        'From' : config.EMAIL_ADDR,
        'To': config.EMAIL_RECIPIENTS,
        'Subject':config.EMAIL_SUBJECT,
        'dry_run':False
    }

def emailAlert(message, debugLevel=0):
    defaults = getDefaults()

    sendMail(
        eFrom=defaults['From'],
        eTo=defaults['To'],
        eSubject=defaults['Subject'],
        eText=message,
        dry_run=defaults['dry_run'],
        debugLevel=debugLevel
        )

    return

def alert(tooManyErrors, tooFewPosts):
    message = config.EMAIL_TEXT+'\n'
    if config.HNMONITOR_FORCE_SEND:
        message+='** config.HNMONITOR_FORCE_SEND == True **\n'
    if tooManyErrors:
        message+='  >>' + tooManyErrors['message']+'\n'
    if tooFewPosts:
        message+='  >>' + tooFewPosts['message']+'\n'

    emailAlert(message)
    return


# noinspection PyShadowingNames
def main(args):
    loggingSetup(config.LOGFILE, noScreen=args.daemon or args.nostdout)
    logger.info('hnmonitor: starting. Daemon-mode = {0}'.format(args.daemon))

    couch=CouchData()

    logger.info('First time - going to sleep until: {0}'.format(datetime.now()+timedelta(seconds=firstSleepTime())))
    sleepTime=firstSleepTime()
    sleep(sleepTime)
    while True:
        logger.info('Awake and running')
        tooManyErrors=checkErrors()
        tooFewPosts=checkPosts(couch, sleepTime/60/60)

        if tooManyErrors or tooFewPosts or config.HNMONITOR_FORCE_SEND:
            alert(tooManyErrors, tooFewPosts)
        else:
            logger.info('All is well - no alert needed. Going back to sleep for {0} hours'.format(config.RUNFREQUENCY))


        sleepTime=config.RUNFREQUENCY*60*60
        sleep(sleepTime)
    logger.info('hnmonitor: terminating')
    return


# noinspection PyShadowingNames
def parseArgs():
    description = '''
    Monitor hnscrape process and send email alert if not hnscrape is not functioning properly (either too many errors, or too few posts to database). Configuration in config.py
    '''

    parser=argparse.ArgumentParser(add_help=True, description=description)
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--nostdout', action='store_true', help='Run without printing to stdout')

    args=parser.parse_args()

    return args

if __name__ == '__main__':
    args=parseArgs()
    if args.daemon:
        with daemon.DaemonContext():
            print 'Running as daemon'
            main(args)
    else:
        main(args)



