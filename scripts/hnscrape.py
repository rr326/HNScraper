from __future__ import division

import gevent
from gevent import monkey
from gevent import queue
import threading  # Must be after monkey.patch
if __name__=='__main__':
    # Do not monkey patch when a library - it messes up ipython (which I use for testing)
    monkey.patch_all()



import time, argparse, os, os.path, re, json, couchdb, requests
from urlparse import urljoin
from time import time as now
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pprint import  pformat
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
PAGE_RETRY=5
PAGE_RETRY_WAIT=30
COUCH_SERVER='https://rrosen326.cloudant.com'
COUCH_UN='matenedidearandisturpetw'
COUCH_PW='23pmLFJvWa0XhQ8mWxDxlElP'
COUCH_DB='hackernews'
COUCH_ID_VIEW='by/id'
SHORT_WAIT=15
LONG_WAIT=285
PAGES_TO_GET=todoList=[{'page':'http://news.ycombinator.com', 'depth':0, 'wait': SHORT_WAIT},  # depth 0 is page 1
              {'page':'http://news.ycombinator.com/news2', 'depth':0, 'wait': LONG_WAIT}]

def mymatch(regex, text, groupNum=1, retType=None):
    match=re.match(regex, text)
    if match:
        return match.group(groupNum)
    else:
        if retType=='empty_string':
            return ''
        elif retType=='zero_string':
            return '0'
        else:
            return text

def asInt(text):
    try:
        return int(text)
    except:
        return text



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

class HNWorkList(object):
    def __init__(self):
        self.todoList=PAGES_TO_GET
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

#
# HN Content Classes:
# HNPage
#    HNPostSnap - Snapshot of the post at a moment in time
#    HNPostSnap
#    ...
#   HNPostSnap (30/page)
# HNPost
#    <global data about the post: eg: Title, post time, href, highest ranking,  etc.>
#    history: [List of HNPostData that changes - eg: points, comments, ranking]

class HNPost(object):
    def __init__(self, postSnap=None, existingPostData=None):
        self.data={}
        self.globalFields=['id','title','href','author' , 'domain', 'created']
        if postSnap and existingPostData:
            raise Exception('HNPost - __init__ from postSnap OR existingPostData, not both')

        if postSnap:
            self.__newFromPostSnap(postSnap)
        elif existingPostData:
            self.data=existingPostData

    def __newFromPostSnap(self, postSnap):
        self.data['history']=[{}]
        for key in self.globalFields:
            if key in postSnap.data:
                self.data[key]=postSnap.data[key]
        for key in postSnap.data:
            if key not in self.globalFields:
                self.data['history'][0][key]=postSnap.data[key]

    def addNewSnap(self, postSnap):
        # First validate
        for key in self.globalFields:
            if key == 'created':
                continue  # Skip 'created' since it is inexact (eg: 1 hour ago)
            if self.data[key] != postSnap.data[key]:
                logger.warning('HNPost.addNewSnap: new data != old. key:{0}  old: {1}, new: {2}'.format(key, self.data[key], postSnap.data[key]))

        newHist={}
        for key in postSnap.data:
            if key not in self.globalFields:
                newHist[key]=postSnap.data[key]
        self.data['history'].append(newHist)

    def toJSON(self):
        return json.dumps(self.data)

    def __repr__(self):
        return pformat(self.data)

    def getData(self):
        return self.data

class HNPostSnap(object):
    def __init__(self, *postDataDicts):
        self.data={}
        for postDataDict in postDataDicts:
            self.add(postDataDict)

    def add(self, newDict):
        self.data.update(newDict)

    def __repr__(self):
        return pformat(self.data)

    def addOrUpdateCouch(self, db):
        view=db.view(COUCH_ID_VIEW, key=self.data['id'])
        if len(view)==0:
            # Create
            post=HNPost(postSnap=self)
        elif len(view)==1:
            # Update
            post=HNPost(existingPostData=view.rows[0].value)
            post.addNewSnap(self)
        else:
            raise Exception('HNPostSnap - multiple existing posts with id = {0}'.format(self.data['id']))
        # Save it
        db.update([post.getData()])


class HNPage(object):
    def __init__(self, html, pageName, pageDepth):
        self.timestamp=now()
        self.timestamp_str=datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        self.pageName=pageName
        self.pageDepth=pageDepth
        self.html=html
        self.postSnaps=[]
        self.more=None
        self.soup=None

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
            res0 = self.processPostTitle(trs[i*3])
            res1 = self.processPostPoints(trs[i*3+1])
            # Skip tr[2] - just a spacer
            postSnap=HNPostSnap(res0, res1)
            postSnap.add({'pagerow': i})
            postSnap.add({'timestamp': self.timestamp})
            postSnap.add({'timestamp_str': self.timestamp_str})
            # Only add pageName if not a news page
            if self.pageName[:27] != 'http://news.ycombinator.com':
                postSnap.add({'pageName':self.pageName})

            self.postSnaps.append(postSnap)

        if not trs[91].find('a').text=='More':
            raise Exception('No More on page. trs[91]: {0}'.format(trs[91].prettify()))
        else:
            self.more=trs[91].find('a').attrs['href']
        return

    def processPostTitle(self, soup):
        d={}
        try:
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
            logger.debug('processPostTitle - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d


    def processPostPoints(self, soup):
        d={}
        try:
            tds=soup.contents
            if len(tds) != 2:
                logger.error('processArticlePoints Aborting - Unexpected number of tds in article body: {0}. Expected 2. Body: \n{1}'.format(len(tds), soup.prettify()))
                return d
            if tds[1].span: # jobs have no points
                d['points']=asInt(mymatch('([0-9]*) points',tds[1].span.text))
                d['author']=mymatch('user\?id=(.*)',tds[1].find_all('a')[0].attrs['href'])
                d['comments']=asInt(mymatch('([0-9]*) comments', tds[1].find_all('a')[1].text, retType='zero_string')) # 'Discuss' has no comments
                match=re.match('\s*([0-9]*) ([^ ]*) ago.*', tds[1].contents[3])
                if match:
                    if match.group(2)[:6]=='minute':
                        created=datetime.fromtimestamp(self.timestamp)-timedelta(minutes=int(match.group(1)))
                    elif match.group(2)[:4]=='hour':
                        created=datetime.fromtimestamp(self.timestamp)-timedelta(hours=int(match.group(1)))
                    elif match.group(2)[:3]=='day':
                        created=datetime.fromtimestamp(self.timestamp)-timedelta(days=int(match.group(1)))
                    else:
                        logger.warning('processPostPoints - unexpected create time: {0}'.format(match.group(0)))
                        created=None

                    if created:
                        created=created.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        created=match.group(0)

                else:
                    logger.warning('processArticlesPoints - unexpected create time failed to match: {0}'.format(tds[1].contents[3]))
                    created=tds[1].contents[3]
                d['created']=created
        except Exception as e:
            logger.debug('processArticlePoints - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d

    def json(self):
        return json.dumps([post.json() for post in self.postSnaps])


def getPage(url):
    r={'ok':False}

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

    if r.ok:
        logger.progress('GOT:    {0}'.format(url))
        return r.content
    else:
        raise Exception('getPage. Unable to get page {0}. Failed {1} times.'.format(url, PAGE_RETRY))

def getHNWorker(postHNQueue):
    workList=HNWorkList()

    more=''
    while True:
        url, page, depth, wait_time = workList.getUrl(more)
        try:
            more=None
            pageSource=getPage(url)
            hnPage=HNPage(pageSource, page, depth)
            postHNQueue.put(hnPage)
            more=hnPage.more
        except Exception as e:
            logger.warning('getHNWorker: Failed on page {0}. Skipping page.'.format(url))
        # Note - you need, at least, a sleep(0) since none of this is blocking, even though it is monkey patched
        gevent.sleep(wait_time)

    return

def postHNWorker(postHNQueue):
    couch=couchdb.Server(COUCH_SERVER)
    couch.resource.credentials=(COUCH_UN, COUCH_PW)
    db=couch[COUCH_DB]
    db.info()  # Test connection before catching exceptions.
    logger.info('PostHNWorker: Connection with couchdb established.')

    while True:
        try:
            hnPage = postHNQueue.get(block=True, timeout=None)
            for postSnap in hnPage.postSnaps:
                try:
                    postSnap.addOrUpdateCouch(db)
                except Exception as e:
                    logger.error('postHNWorker. Failure posting rec to couch. id: {0}'.format(postSnap.data['id'] if 'id' in postSnap.data else '<id not found>'))
                    logger.error('  >> data: \n{0}'.format(pformat(postSnap.data)))
        except Exception as e:
            logger.error('postHNWorker - postHNQueue.get errored: {0}'.format(e))

    return


def main():
    logger.info('hnscrape: starting.')

    jobs=[]

    postHNQueue=gevent.queue.Queue()
    jobs.append(gevent.spawn(postHNWorker, postHNQueue))
    jobs.append(gevent.spawn(getHNWorker, postHNQueue))


    gevent.joinall(jobs)

# Need to add the following to a helper function.
# Permissions: (read/write) matenedidearandisturpetw
# _design/by
# {
#   "_id": "_design/by",
#   "_rev": "1-0b319125d8d1a3af8251801544d650c9",
#   "value": {
#     "rev": "1-0b319125d8d1a3af8251801544d650c9"
#   },
#   "key": "_design/by"
# }


if __name__=='__main__':
    loggingSetup(LOGLEVEL, LOGFILE)
    main()