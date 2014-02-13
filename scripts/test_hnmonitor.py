from hnmonitor import *
hnlogger=logger

import logging
logger=logging.getLogger('test')


def testEmail():
    print 'About to send mail'
    emailAlert('This is the body of the email.\nLine 2\n', debugLevel=4)
    print 'Sent mail successfully'


def loggingSetup():
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

if __name__=='__main__':
    loggingSetup()
    testEmail()