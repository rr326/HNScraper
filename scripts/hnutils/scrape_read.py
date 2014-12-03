import logging

import requests
import gevent

from scrape_stats import stats
import config


logging.basicConfig()
logger = logging.getLogger(__name__)

def getPage(url, localDebug):
    if localDebug:
        logger.warning('LOCAL DEBUG IS CHANGED - NOT USING MOCK DATA (raw data instead)')
        if False:
            logger.warning('getPage(): MOCKED - using static file.')
            with open(config.MOCK_PAGE, 'r') as f:
                content = f.read()
            stats.addGot()
            logger.warning('getPage(): mock - adding error to stats even with no error')
            stats.addError()
            return content

    r={'ok':False}

    for i in range(config.PAGE_RETRY):
        try:
            r = requests.get(url)
            if not r.ok:
                logger.warning('getPage. requests returned not ok.  status_code: {0}. reason: {1}  Url: {2}'.format(r.status_code, r.reason,  url))
                gevent.sleep(config.PAGE_RETRY_WAIT)
                continue
            else:
                break
        except Exception as e:
            logger.error('getPage: requests raised an error: {0}'.format(e))
            gevent.sleep(config.PAGE_RETRY_WAIT)
            continue

    if r.ok:
        logger.log(config.logging.PROGRESS, 'GOT:    {0}'.format(url))
        stats.addGot()
        return r.content
    else:
        stats.addError()
        raise Exception('getPage. Unable to get page {0}. Failed {1} times.'.format(url, config.PAGE_RETRY))