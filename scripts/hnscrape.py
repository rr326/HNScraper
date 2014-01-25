from __future__ import division

import gevent
from gevent import monkey
from gevent import queue
from gevent import pool
monkey.patch_all()
import threading  # Must be after monkey.patch


import time, argparse, os, os.path, re, json, couchdb, requests
from urlparse import urljoin
from time import time as now
from bs4 import BeautifulSoup
from pprint import pprint
from random import randrange

import logging
logging.PROGRESS = 15
logging.addLevelName(logging.PROGRESS, 'PROGRESS')
def log_progress(self, msg, *args, **kws):
    if self.isEnabledFor(logging.PROGRESS):
        self._log(logging.PROGRESS, msg, args, **kws)
logging.Logger.progress=log_progress
logger = logging.getLogger(__name__)


LOGFILE='hnscrape.log'
LOGLEVEL=logging.DEBUG
HNSLEEP=30   # Wait 30 secs, min, between every scrape, so you don't get IP-banned
PAGE_RETRY=5
PAGE_RETRY_WAIT=15
COUCH_SERVER='https://rrosen326.cloudant.com'
COUCH_UN='matenedidearandisturpetw'
COUCH_PW='23pmLFJvWa0XhQ8mWxDxlElP'
COUCH_DB='hackernews'

def mymatch(regex, str, groupNum=1, retType=None):
    match=re.match(regex, str)
    if match:
        return match.group(groupNum)
    else:
        if retType=='empty_string':
            return ''
        elif retType=='zero_string':
            return '0'
        else:
            return str

def asInt(str):
    try:
        return int(str)
    except:
        return str



#
#
# Support functions
#
#

def loggingSetup(log_level, logfile):
    logger.setLevel(log_level)

    if logging.FileHandler not in [type(h) for h in logger.handlers] :
        fh=logging.FileHandler(logfile)
        fh.setLevel(log_level)
        formatter_file=logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter_file)
        logger.addHandler(fh)

    if logging.StreamHandler not in [type(h) for h in logger.handlers]:
        ch=logging.StreamHandler()
        ch.setLevel(log_level)
        formatter_screen=logging.Formatter('%(levelname)-8s %(message)s')
        ch.setFormatter(formatter_screen)
        logger.addHandler(ch)

    return

class HNWorkList():
    def __init__(self):
        self.todoList=[{'page':'http://news.ycombinator.com', 'depth':2},  # depth 0 is page 1
              {'page':'http://news.ycombinator.com/newest', 'depth':1}]
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
        if more == None:
            more=''
        if self.curDepth==0:
            url = self.todoList[self.curPage]['page']
        else:
            url = urljoin(self.todoList[self.curPage]['page'], more)
            #logger.debug('getUrl: {0} from {1} ## {2}'.format(url, self.todoList[self.curPage]['page'], more))
        self._setNext()
        return url,  self.todoList[self.curPage]['page'], self.curDepth




class HNPage():
    def __init__(self, html, pageName, pageDepth):
        self.timestamp=now()
        self.pageName=pageName
        self.pageDepth=pageDepth
        self.html=html
        self.articles=[]
        self.more=None

        try:
            self.processHNPage()
        except Exception as e:
            logger.error('HNPage. Failed to parse page: {0}:{1}. Error:\n{2}\nHtml:\n******\n{3}\n*******'.format(
                self.pageName, self.pageDepth, e, self.html))


    def processHNPage(self):
        self.soup = BeautifulSoup(self.html)
        tbls = self.soup.find_all('table')
        if not tbls or len(tbls)<3:
            raise Exception('processHNPage - expected tbls >3. Got: {0}\npageName: {2}, pageDepth: {3}\n******\n{1}\n*******'.format(len(tbls), self.html, self.pageName, self.pageDepth))
        tbl2=tbls[2]
        trs=tbl2.find_all('tr')

        if not trs:
            raise Exception('processHNPage - no trs!')
        if len(trs) != 92:
            raise Exception('Unexpected length of main body: {0} (expected 92)'.format(len(trs)))

        for i in range(30):
            res0 = self.processArticleTitle(trs[i*3])
            res1 = self.processArticlePoints(trs[i*3+1])
            # Skip tr[2] - just a spacer
            res0.update(res1)
            res0['pagerow']=i
            res0['timestamp']=self.timestamp
            res0['pageName']=self.pageName
            res0['pageDepth']=self.pageDepth
            self.articles.append(res0)

        if not trs[91].find('a').text=='More':
            raise Exception('No More on page. trs[91]: {0}'.format(trs[91].prettify()))
        else:
            self.more=trs[91].find('a').attrs['href']
        return

    def processArticleTitle(self, soup):
        try:
            d={}
            tds=soup.contents
            if len(tds) != 3:
                logger.error('processArticleTitle Aborting - Unexpected number of tds in article body: {0}. Expected 3. Body: \n{1}'.format(len(tds), soup.prettify()))
                return d
            d['rank']=asInt(mymatch('([0-9]*)\.', tds[0].text))
            if tds[1].a: # Jobs have empty tds[1]
                d['id']=mymatch('up_([0-9]*)',tds[1].a.attrs['id'])

            d['title']=tds[2].a.text
            d['href']=tds[2].a.attrs['href']
            if tds[2].span:
                d['domain']=str(mymatch(' *\(([^)]*)\) *', tds[2].span.text))
        except Exception as e:
            logger.debug('processArticleTitle - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d


    def processArticlePoints(self, soup):
        try:
            d={}
            tds=soup.contents
            if len(tds) != 2:
                logger.error('processArticlePoints Aborting - Unexpected number of tds in article body: {0}. Expected 2. Body: \n{1}'.format(len(tds), soup.prettify()))
                return d
            if tds[1].span: # jobs have no points
                d['points']=asInt(mymatch('([0-9]*) points',tds[1].span.text))
                d['author']=mymatch('user\?id=(.*)',tds[1].find_all('a')[0].attrs['href'])
                d['comments']=asInt(mymatch('([0-9]*) comments', tds[1].find_all('a')[1].text, retType='zero_string')) # 'Discuss' has no comments
        except Exception as e:
            logger.debug('processArticlePoints - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d

    def json(self):
        return json.dumps(self.articles)

# Only for debugging
global pageSource
pageSource=None

def getPage(url):
    # Stubbing this
    logger.debug('getPage: {0}'.format(url))
    global pageSource
    # if pageSource:
    #     return pageSource
    for i in range(PAGE_RETRY):
        try:
            r = requests.get(url)
            if not r.ok:
                logger.warning('getPage. requests returned not ok.  status_code: {0}. reason: {1}  Url: {2}'.format(r.status_code, r.reason,  url))
                gevent.sleep(PAGE_RETRY_WAIT)
                continue
            else:
                break
        except Exception as e:
            logger.error('getPage: requests raised an error: {0}'.format(e))
            gevent.sleep(PAGE_RETRY_WAIT)
            continue
        raise Exception('getPage. Unable to get page {0}. Failed {1} times.'.format(url, PAGE_RETRY))

    pageSource = r.content
    return r.content

def getHNWorker(postHNQueue):
    workList=HNWorkList()

    more=''
    while True:
        url, page, depth = workList.getUrl(more)
        try:
            more=None
            pageSource=getPage(url)
            hnPage=HNPage(pageSource, page, depth)
            postHNQueue.put(hnPage.json())
            more=hnPage.more
        except Exception as e:
            logger.warning('getHNWorker: Failed on page {0}. Skipping page.'.format(url))
        # Note - you need, at least, a sleep(0) since none of this is blocking, even though it is monkey patched
        gevent.sleep(HNSLEEP)

    return

def postHNWorker(postHNQueue):
    couch=couchdb.Server(COUCH_SERVER)
    couch.resource.credentials=(COUCH_UN, COUCH_PW)
    db=couch[COUCH_DB]
    test=db.info()  # Test connection before catching exceptions.
    logger.info('PostHNWorker: Connection with couchdb established.')

    while True:
        try:
            text = postHNQueue.get(block=True, timeout=None)
            recs=json.loads(text)

            i=0
            for rec in recs:
                db.create(rec)
                i+=1
            logger.progress('Posted {0} records to couch.'.format(i))
        except Exception as e:
            logger.error('PostHNWorker - failed to post data to couch. Error: {0}'.format(e))

    return


def main():
    print 'in main'
    jobs=[]

    postHNQueue=gevent.queue.Queue()
    jobs.append(gevent.spawn(postHNWorker, postHNQueue))
    jobs.append(gevent.spawn(getHNWorker, postHNQueue))


    gevent.joinall(jobs)

    print 'leaving main'


if __name__=='__main__':
    loggingSetup(LOGLEVEL, LOGFILE)
    main()