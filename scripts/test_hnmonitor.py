from hnmonitor import *
from hnscrape import datetimeToStr

hnlogger=logger

import logging
logger=logging.getLogger('test')


def testEmail():
    print 'About to send mail'
    emailAlert('This is the body of the email.\nLine 2\n', debugLevel=4)
    print 'Sent mail successfully'


def loggingSetupLocal():
    log_level = config.logging.DEBUG # Hardcode, but run minimally

    logger.setLevel(log_level)

    # File logging
    h=config.logging.StreamHandler()
    h.setLevel(log_level)
    formatter=config.logging.Formatter('%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    h.setFormatter(formatter)
    logger.addHandler(h)
    hnlogger.addHandler(h)

    return

def testNumPosted():
    couchData=CouchData()
    numPosted=couchData.getNumPostedTest()
    print 'testNumPosted - numPosted: {0}'.format(numPosted)

    for i in range(5):
        numPosted = couchData.getNumPostedTest(lastTimestamp=datetimeToStr(datetime.now()-timedelta(hours=i)))
        print 'Numposted in last {0} hours: {1}: timestamp: {2}'.format(i, numPosted, datetimeToStr(datetime.now()-timedelta(hours=i)))


if __name__=='__main__':
    loggingSetupLocal()
    # testEmail()
    testNumPosted()