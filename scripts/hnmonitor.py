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

    tooManyErrors = len(lines) > config.MAXERRORS

    # Now reset the log file to empty
    with open(config.ERRORS_ONLY_LOG, 'w') as f:
        f.write('')

    if tooManyErrors:
        logger.info('CheckError returned too many errros. MaxErrors = {0}. Actual Errors = {1}'.format(config.MAXERRORS, len(lines)))

    return tooManyErrors

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

    if tooFewPosts:
        logger.info('checkPosts returned too few posts. Expected ~ {0} (threshold: {1:.1%}). Posted: {2}'.format(expectedPosts, config.POSTERRORTHRESHOLD, numPosts))

    return tooFewPosts

def alert(tooManyErrors, tooFewPosts):
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

if __name__ == '__main__':
    main()


