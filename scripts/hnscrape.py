from __future__ import division

import gevent
from gevent import monkey
from gevent import queue
#import threading  # Must be after monkey.patch
if __name__=='__main__':
    # Do not monkey patch when a library - it messes up ipython (which I use for testing)
    monkey.patch_all()

import config

import re, json, couchdb, requests, daemon, argparse
from urlparse import urljoin
from time import time as now
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pprint import  pformat

# Global
logger = config.logging.getLogger('hnscrape')


# Keep success / fail stats by the hour
class StatLogger(object):
    def __init__(self):
        self.resetDate=datetime.now()
        self.numGot=0
        self.numPosted=0
        self.numErrors=0

    def __str__(self):
        return 'pagesDownloaded: {0:>4} snapsPosted: {1:>4} numErros: {2:>4} over last {3:.1g} hours'.format(self.numGot, self.numPosted, self.numErrors, (datetime.now() - self.resetDate).seconds/3600 )

    def addGot(self, num=1):
        self.numGot += num

    def addPosted(self, num):
        self.numPosted +=num

    def addError(self, num=1):
        self.numErrors+=num

    def resetStats(self):
        self.resetDate=datetime.now()
        self.numGot = 0
        self.numPosted = 0
        self.numErrors = 0

#
# Global
#
_stats=StatLogger()



# ------------------------------------------------------------------------

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
    except ValueError:
        return text

def datetimeToStr(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def loggingSetup(log_level, logfile, errorsOnlyLog, noScreen=False):
    logger.setLevel(log_level)

    # File logging
    h=config.logging.FileHandler(logfile)
    h.setLevel(log_level)
    formatter=config.logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    h.setFormatter(formatter)
    logger.addHandler(h)

    if not noScreen:
        # Stdout
        h=config.logging.StreamHandler()
        h.setLevel(log_level)
        formatter=config.logging.Formatter('%(levelname)s - %(message)s')
        h.setFormatter(formatter)
        logger.addHandler(h)

    # Errors only - don't display message since I only want 1 line per error
    h=config.logging.FileHandler(errorsOnlyLog)
    h.setLevel(config.logging.ERROR)
    formatter=config.logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - Line: %(lineno)s', datefmt='%Y-%m-%d %H:%M:%S')
    h.setFormatter(formatter)
    logger.addHandler(h)

    return

class HNWorkList(object):
    def __init__(self):
        self.todoList=config.PAGES_TO_GET
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
    # noinspection PyDictCreation
    def __init__(self, postSnap=None, existingPostData=None):
        self.data={}
        self.data['doc_type']='post'
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
            self.data['history'][0][key]=postSnap.data[key]

    def addNewSnap(self, postSnap):
        newHist={}

        # First validate
        for key in self.globalFields:
            if key == 'created':
                continue  # Skip 'created' since it is inexact (eg: 1 hour ago)
            if key not in postSnap.data:
                postSnap.data[key]=None
            if key not in self.data:
                self.data[key]=None
            if postSnap.data[key] !=  self.data[key]:
                # Keep track of changes to global fields, and use latest value in globals
                self.data[key] = postSnap.data[key]
                newHist[key]=postSnap.data[key]
                if key+'_changes' in self.data:
                    self.data[key+'_changes'] += 1
                else:
                    self.data[key+'_changes'] = 1

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

    def markAsTest(self):
        self.data['doc_type'] = 'test_data'

class HNPostSnap(object):
    def __init__(self, *postDataDicts):
        self.data={}
        for postDataDict in postDataDicts:
            self.add(postDataDict)

    def add(self, newDict):
        self.data.update(newDict)

    def __repr__(self):
        return pformat(self.data)

    def addOrUpdateCouch(self, db, localDebug, is_test_data):
        view=db.view(config.COUCH_ID_VIEW, key=self.data['id'])
        if len(view)==0:
            # Create
            post=HNPost(postSnap=self)
        elif len(view)==1:
            # Update
            post=HNPost(existingPostData=view.rows[0].value)
            post.addNewSnap(self)
        else:
            raise Exception('HNPostSnap - multiple existing posts with id = {0}'.format(self.data['id']))

        if localDebug:
            # Mock - don't actually post.
            post.markAsTest()
            logger.debug('Local debug. Not posting to Couch. '
                         'WOULD post:\n{0}'.format(pformat(post.getData())))
            return
        else:  # Save it
            if is_test_data:
                post.markAsTest()
            db.update([post.getData()])


class HNPage(object):
    def __init__(self, html, pageName, pageDepth, is_test_data):
        self.timestamp=now()
        self.timestamp_str=datetimeToStr(datetime.utcfromtimestamp(self.timestamp))
        self.pageName=pageName
        self.pageDepth=pageDepth
        self.html=html
        self.postSnaps=[]
        self.more=None
        self.soup=None
        self.is_test_data=is_test_data

        try:
            self.processHNPage()
        except Exception as e:
            logger.error('HNPage. Failed to parse page: {0}:{1}. Error:\n{2}\nHtml:\n******\n{3}\n*******'.format(
                self.pageName, self.pageDepth, e, self.html))


    def processHNPage(self):
        self.soup = BeautifulSoup(self.html)
        tbls = self.soup.find_all('table')
        if not tbls or len(tbls)<3 or len(tbls) > 5:
            raise Exception('processHNPage - expected tbls ==4 or 5. Got: {0}\npageName: {2}, pageDepth: {3}\n******\n{1}\n*******'.format(len(tbls), self.html, self.pageName, self.pageDepth))
        # Normally there are 4 tbls. But sometimes he puts a header tbl in.
        tblMain = tbls[2] if len(tbls) == 4 else tbls[3]
        trs=tblMain.find_all('tr')

        if not trs:
            raise Exception('processHNPage - no trs!')
        if len(trs) != 92:
            raise Exception('Unexpected length of main body: {0} (expected 92)'.format(len(trs)))

        for i in range(30):
            res0 = self.processPostTitle(trs[i*3])
            res1 = self.processPostPoints(trs[i*3+1])
            # Skip tr[2] - just a spacer
            postSnap=HNPostSnap(res0, res1)
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

    @staticmethod
    def processPostTitle(soup):
        d={}
        try:
            tds=soup.contents
            if len(tds) != 3:
                logger.error('processArticleTitle Aborting - Unexpected number of tds in article body: {0}. Expected 3. Body: \n{1}'.format(len(tds), soup.prettify()))
                return d
            d['rank']=asInt(mymatch('([0-9]*)\.', tds[0].text))
            d['title']=tds[2].a.text
            d['href']=tds[2].a.attrs['href']

            # Fix hrefs (item?id=7356084 ==> https://news.ycombinator.com/item?id=7356084)
            matchHrefID = re.match('item\?id=([0-9]{7,10})', tds[2].a.attrs['href'])
            if matchHrefID:
                d['href'] = 'https://news.ycombinator.com/{0}'.format(tds[2].a.attrs['href'])

            # Set ids
            if tds[1].a:
                d['id']=mymatch('up_([0-9]*)',tds[1].a.attrs['id'])
            else:  # Jobs have empty tds[1].
                if matchHrefID:
                    # Found a job with id pattern: href="item?id=7219911'
                    d['id']=matchHrefID.group(1)
                else:
                    # Found job with no id available. Use href + title for id and hope it is invariant
                    d['id']='JOB: '+d['href'] + d['title']

            if tds[2].span:
                d['domain']=str(mymatch(' *\(([^)]*)\) *', tds[2].span.text))
        except Exception as e:
            logger.debug('processPostTitle - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d

    def processTimeStr(self, timeStr):
        match=re.match('\s*([0-9]*) ([^ ]*) ago.*', timeStr)
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
                created=datetimeToStr(created)
            else:
                created=match.group(0)
        else:
            logger.warning('processTimeStr - unexpected create time - failed to match: {0}'.format(timeStr))
            created=timeStr
        return created

    def processPostPoints(self, soup):
        d={}
        try:
            tds=soup.contents
            if len(tds) != 2:
                logger.error('processArticlePoints Aborting - Unexpected number of tds in article body: {0}. Expected 2. Body: \n{1}'.format(len(tds), soup.prettify()))
                return d
            if tds[1].span: # Non-jobs post
                d['points']=asInt(mymatch('([0-9]*) points',tds[1].span.text))
                d['author']=mymatch('user\?id=(.*)',tds[1].find_all('a')[0].attrs['href'])
                d['comments']=asInt(mymatch('([0-9]*) comments', tds[1].find_all('a')[1].text, retType='zero_string')) # 'Discuss' has no comments
                d['created']=self.processTimeStr(tds[1].contents[3])
            else: # jobs have no points
                d['created']=self.processTimeStr(tds[1].text)
        except Exception as e:
            logger.debug('processArticlePoints - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d

    def json(self):
        return json.dumps([post.json() for post in self.postSnaps])


def getPage(url, localDebug):
    if localDebug:
        logger.warning('LOCAL DEBUG IS CHANGED - NOT USING MOCK DATA (raw data instead)')
        if False:
            logger.warning('getPage(): MOCKED - using static file.')
            with open(config.MOCK_PAGE, 'r') as f:
                content = f.read()
            _stats.addGot()
            logger.warning('getPage(): mock - adding error to stats even with no error')
            _stats.addError()
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
        logger.progress('GOT:    {0}'.format(url))
        _stats.addGot()
        return r.content
    else:
        _stats.addError()
        raise Exception('getPage. Unable to get page {0}. Failed {1} times.'.format(url, config.PAGE_RETRY))

def getHNWorker(postHNQueue, localDebug):
    workList=HNWorkList()

    more=''
    while True:
        url, page, depth, wait_time = workList.getUrl(more)
        # noinspection PyBroadException
        try:
            more=None
            pageSource=getPage(url, localDebug)
            hnPage=HNPage(pageSource, page, depth, is_test_data=localDebug)
            postHNQueue.put(hnPage)
            more=hnPage.more
        except Exception:
            logger.error('getHNWorker: Failed on page {0}. Skipping page.'.format(url))
        # Note - you need, at least, a sleep(0) since none of this is blocking, even though it is monkey patched
        gevent.sleep(wait_time)

    return

def postHNWorker(postHNQueue, localDebug):
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
                    postSnap.addOrUpdateCouch(db, localDebug, hnPage.is_test_data)
                    i+=1
                except Exception as e:
                    logger.error('postHNWorker. Failure posting rec to couch. id: {0}'.format(postSnap.data['id'] if 'id' in postSnap.data else '<id not found>'))
                    logger.error('  >> e: {1}\n  data: \n{0}'.format(pformat(postSnap.data), e))
            logger.progress('POSTED: {0} records to couch'.format(i))
            if localDebug:
                logger.warn('postHNWorker: MOCKED - not actually posting')
            _stats.addPosted(i)
        except Exception as e:
            logger.error('postHNWorker - postHNQueue.get errored: {0}'.format(e))
            _stats.addError()


    return

def statsWorker():
    """Wake up every hour and log stats, and then reset them"""
    logger.info('STATS: Starting. Will report out every {0:.1g} hours'.format(config.STATS_HOURS))
    while True:
        gevent.sleep(timedelta(hours=config.STATS_HOURS).total_seconds())
        logger.info('STATS: {0}'.format(_stats))
        _stats.resetStats()

    return




# noinspection PyShadowingNames
def main(args):
    loggingSetup(config.LOGLEVEL, config.LOGFILE, config.ERRORS_ONLY_LOG, noScreen=args.daemon or args.nostdout )
    logger.info('hnscrape: starting. Daemon-mode = {0}'.format(args.daemon))

    jobs=[]

    postHNQueue=gevent.queue.Queue()
    jobs.append(gevent.spawn(getHNWorker, postHNQueue, config.LOCAL_DEBUG))
    jobs.append(gevent.spawn(postHNWorker, postHNQueue, config.LOCAL_DEBUG))
    jobs.append(gevent.spawn(statsWorker))

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

    args = parser.parse_args()

    return args

if __name__ == '__main__':
    args = parseArgs()
    config.setCredentials(args.pwfile)

    if args.daemon:
        with daemon.DaemonContext():
            main(args)
    else:
        main(args)



# TODO: Should encode JOBS with a date or something - there is going to be a collision otherwise
