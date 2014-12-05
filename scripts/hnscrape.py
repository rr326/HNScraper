from __future__ import division

from gevent import monkey
from gevent import queue

import gevent

#import threading  # Must be after monkey.patch
from hnutils import config
from hnutils.newhn_classes import newGetHNPosts

if __name__=='__main__':
    # Do not monkey patch when a library - it messes up ipython (which I use for testing)
    monkey.patch_all()

import couchdb, daemon, argparse
from urlparse import urljoin

from datetime import timedelta
from pprint import  pformat
import logging
from hnutils.scrape_stats import stats
from hnutils.hn_classes import HNPage
from hnutils.scrape_read import getPage


# Global
logger = logging.getLogger() # Make sure you are using the root logger


def loggingSetup(log_level, logfile, errorsOnlyLog, noScreen=False):
    logger.setLevel(log_level)
    logging.getLogger('requests').setLevel(logging.WARN)  # requests is logging connections I don't want to see

    # File logging
    h=config.logging.FileHandler(logfile)
    h.setLevel(log_level)
    formatter= config.logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    h.setFormatter(formatter)
    logger.addHandler(h)

    if not noScreen:
        # Stdout
        h= config.logging.StreamHandler()
        h.setLevel(log_level)
        formatter= config.logging.Formatter('%(levelname)s - %(message)s')
        h.setFormatter(formatter)
        logger.addHandler(h)

    # Errors only - don't display message since I only want 1 line per error
    h= config.logging.FileHandler(errorsOnlyLog)
    h.setLevel(config.logging.ERROR)
    formatter= config.logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - Line: %(lineno)s', datefmt='%Y-%m-%d %H:%M:%S')
    h.setFormatter(formatter)
    logger.addHandler(h)

    return

class HNWorkList(object):
    def __init__(self):
        self.todoList= config.PAGES_TO_GET
        self.curPage=0
        self.curDepth=0
        self.numPages=len(self.todoList)

    def _setNext(self):
        if self.curDepth < self.todoList[self.curPage]['depth']:
            # Next will be same page, deeper
            self.curDepth += 1
        else:
            self.curDepth = 0
            self.curPage = (self.curPage + 1) % self.numPages

    def getUrl(self, more):
        if more is None:
            more=''
        if self.curDepth==0:
            url = self.todoList[self.curPage]['page']
        else:
            url = urljoin(self.todoList[self.curPage]['page'], more)
            #logger.debug('getUrl: {0} from {1} ## {2}'.format(url, self.todoList[self.curPage]['page'], more))
        wait = self.todoList[self.curPage]['wait']
        self._setNext()
        return url,  self.todoList[self.curPage]['page'], self.curDepth, wait


def getHNWorker(postHNQueue):
    workList=HNWorkList()

    more=''
    while True:
        url, page, depth, wait_time = workList.getUrl(more)
        # noinspection PyBroadException
        try:
            more=None
            pageSource=getPage(url)
            hnPage=HNPage(pageSource, page, depth)
            postHNQueue.put(hnPage)
            more=hnPage.more
        except Exception:
            logger.error('getHNWorker: Failed on page {0}. Skipping page.'.format(url))
        # Note - you need, at least, a sleep(0) since none of this is blocking, even though it is monkey patched
        gevent.sleep(wait_time)

    return

def postHNWorker(postHNQueue):
    couch=couchdb.Server(config.COUCH_SERVER)
    couch.resource.credentials=(config.COUCH_UN, config.COUCH_PW)
    db=couch[config.COUCH_DB]
    db.info()  # Test connection before catching exceptions.
    logger.info('PostHNWorker: Connection with couchdb established.')

    while True:
        try:
            hnPage = postHNQueue.get(block=True, timeout=None)
            i=0
            for postSnap in hnPage.postSnaps:
                try:
                    postSnap.addOrUpdateCouch(db, hnPage.is_test_data)
                    i+=1
                except Exception as e:
                    logger.error('postHNWorker. Failure posting rec to couch. id: {0}'.format(postSnap.data['id'] if 'id' in postSnap.data else '<id not found>'))
                    logger.error('  >> e: {1}\n  data: \n{0}'.format(pformat(postSnap.data), e))
            logger.progress('POSTED: {0} records to couch'.format(i))
            if config.MOCK_OUTPUT:
                logger.warn('postHNWorker: MOCKED - not actually posting')
            stats.addPosted(i)
        except Exception as e:
            logger.error('postHNWorker - postHNQueue.get errored: {0}'.format(e))
            stats.addError()


    return


def newGetHNWorker(HNQueue):
    while True:
        try:
            posts = newGetHNPosts()
            HNQueue.put(posts)
        except Exception as e:
            logger.error('newGetHNWorker: Failed. Error {0}'.format(e))
        gevent.sleep(config.NEW_WAIT)

    return

def newPostHNWorker(HNQueue):
    # couch=couchdb.Server(config.COUCH_SERVER)
    # couch.resource.credentials=(config.COUCH_UN, config.COUCH_PW)
    # db=couch[config.COUCH_DB]
    # db.info()  # Test connection before catching exceptions.
    # logger.info('newPostHNWorker: Connection with couchdb established.')
    #
    # while True:
    #     try:
    #         posts = HNQueue.get(block=True, timeout=None)
    #         i=0
    #         for postSnap in hnPage.stories:
    #             try:
    #                 postSnap.addOrUpdateCouch(db, hnPage.is_test_data)
    #                 i+=1
    #             except Exception as e:
    #                 logger.error('newpostHNWorker. Failure posting rec to couch. id: {0}'.format(postSnap.data['id'] if 'id' in postSnap.data else '<id not found>'))
    #                 logger.error('  >> e: {1}\n  data: \n{0}'.format(pformat(postSnap.data), e))
    #         logger.progress('POSTED: {0} records to couch'.format(i))
    #         if config.MOCK_OUTPUT:
    #             logger.warn('newpostHNWorker: MOCKED - not actually posting')
    #         stats.addPosted(i)
    #     except Exception as e:
    #         logger.error('newpostHNWorker - HNQueue.get errored: {0}'.format(e))
    #         stats.addError()


    return



def statsWorker():
    """Wake up every hour and log stats, and then reset them"""
    logger.info('STATS: Starting. Will report out every {0:.1g} hours'.format(
        config.STATS_HOURS))
    while True:
        gevent.sleep(timedelta(hours=config.STATS_HOURS).total_seconds())
        logger.info('STATS: {0}'.format(stats))
        stats.resetStats()

    return




# noinspection PyShadowingNames
def main(args):
    loggingSetup(config.LOGLEVEL, config.LOGFILE, config.ERRORS_ONLY_LOG, noScreen=args.daemon or args.nostdout )
    logger.info('hnscrape: starting. Daemon-mode = {0}'.format(args.daemon))

    jobs=[]

    # postHNQueue=gevent.queue.Queue()
    # jobs.append(gevent.spawn(getHNWorker, postHNQueue))
    # jobs.append(gevent.spawn(postHNWorker, postHNQueue))
    # jobs.append(gevent.spawn(statsWorker))

    newHNQueue = gevent.queue.Queue()
    jobs.append(gevent.spawn(newGetHNWorker, newHNQueue))
    jobs.append(gevent.spawn(postHNWorker, newHNQueue))


    gevent.joinall(jobs)

    logger.info('hnscrape: terminating.')
    return


# noinspection PyShadowingNames
def parseArgs():
    description = '''
    Scrape news.ycombinator.com and save in Cloudant. Configuration in config.py. Run with --daemon and run continuously as a daemon. Use upstart to run as service and autostart. Also run hnmonitor to monitor the functioning and alert administrator if errors. See README.md for more information.
    '''

    parser = argparse.ArgumentParser(add_help=True, description=description)
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--nostdout', action='store_true', help='Run without printing to stdout')
    parser.add_argument('--pwfile', help='json file with COUCH_UN & COUCH_PW keys ', required=True)
    parser.add_argument('--config',
        help='named configuration bundle (in config.py) to use ', required=True)

    args = parser.parse_args()

    return args

if __name__ == '__main__':
    args = parseArgs()
    config.setCredentials(args.pwfile)
    if args.config:
        config.update_config(args.config, config.configs, config.servers)

    if args.daemon:
        with daemon.DaemonContext():
            main(args)
    else:
        main(args)



# TODO: Should encode JOBS with a date or something - there is going to be a collision otherwise
