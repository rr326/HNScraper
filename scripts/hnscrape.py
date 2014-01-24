from __future__ import division

import gevent
from gevent import monkey
from gevent import queue
from gevent import pool
monkey.patch_all()
import threading  # Must be after monkey.patch


import time, argparse, os, os.path, re, requests
from time import time as now
from bs4 import BeautifulSoup
from pprint import pprint

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

def processArticleTitle(html):
    try:
        d={}
        tds=html.contents
        if len(tds) != 3:
            raise Exception('Unexpected number of tds in article body: {0}. Expected 3. Body: \n{1}'.format(len(tds), html))

        d['rank']=asInt(mymatch('([0-9]*)\.', tds[0].text))
        if tds[1].a: # Jobs have empty tds[1]
            d['id']=mymatch('up_([0-9]*)',tds[1].a.attrs['id'])

        d['title']=tds[2].a.text
        d['href']=tds[2].a.attrs['href']
        if tds[2].span:
            d['domain']=str(mymatch(' *\(([^)]*)\) *', tds[2].span.text))
    except Exception as e:
        print 'Error:\n{0}\n{1}'.format(e, html)

    return d


def processArticlePoints(html):
    try:
        d={}
        tds=html.contents
        if len(tds) != 2:
            raise Exception('Unexpected number of tds in article points line: {0}. Expected 2. Body: \n{1}'.format(len(tds), html))

        if tds[1].span: # jobs have no points
            d['points']=asInt(mymatch('([0-9]*) points',tds[1].span.text))
            d['author']=mymatch('user\?id=(.*)',tds[1].find_all('a')[0].attrs['href'])
            d['comments']=asInt(mymatch('([0-9]*) comments', tds[1].find_all('a')[1].text, retType='zero_string')) # 'Discuss' has no comments
    except Exception as e:
        print 'Error:\n{0}\n{1}'.format(e, html)

    return d

def processHNPage(html):
    soup = BeautifulSoup(html)
    tbl2 = soup.find_all('table')[2]
    trs=tbl2.find_all('tr')

    if len(trs) != 92:
        raise Exception('Unexpected length of main body: {0} (expected 92)'.format(len(trs)))


    articles=[]
    for i in range(30):
        res0 = processArticleTitle(trs[i*3])
        res1 = processArticlePoints(trs[i*3+1])
        # Skip tr[2] - just a spacer
        res0.update(res1)
        res0['pagerow']=i
        articles.append(res0)

    if not trs[91].find('a').text=='More':
        raise Exception('No More on page. trs[91]: {0}'.format(trs[91].prettify()))
    else:
        more=trs[91].find('a').attrs['href']

    return articles, more, soup

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
        self.todoList=[{'page':'http://news.ycombinator.com/', 'depth':2},  # depth 0 is page 1
              {'page':'http://news.ycombinator.com/newest/', 'depth':1}]
        self.curPage=0
        self.curDepth=0
        self.numPages=len(self.todoList)

    def getNext(self):
        retval = (self.todoList[self.curPage]['page'],self.curDepth)
        if self.curDepth < self.todoList[self.curPage]['depth']:
            # Next will be same page, deeper
            self.curDepth += 1
        else:
            self.curDepth = 0
            self.curPage = (self.curPage + 1) % self.numPages
        logger.debug('getNext: {0}'.format(retval))
        return retval



def getHNWorker(postHNQueue):
    print 'in getHNWorker'
    workList=HNWorkList()

    #while True:
    for i in range(50):
        page, depth = workList.getNext()
        postHNQueue.put(page)

    return

def postHNWorker(postHNQueue):
    print 'in postHNWorker'
    while True:
        text = postHNQueue.get(block=True, timeout=None)
        # Stub for now
        fname='../data/hnpage_{0}'.format(now())
        with open(fname, 'w') as f:
            logger.info('WRITE: {0}'.format(fname))
            f.write(text)

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