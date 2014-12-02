from time import time as now
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
from pprint import pformat
import config
import logging
import re


def mymatch(regex, text, groupNum=1, retType=None):
    match = re.match(regex, text)
    if match:
        return match.group(groupNum)
    else:
        if retType == 'empty_string':
            return ''
        elif retType == 'zero_string':
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
            logging.debug('Local debug. Not posting to Couch. '
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
            logging.error('HNPage. Failed to parse page: {0}:{1}. Error:\n{2}\nHtml:\n******\n{3}\n*******'.format(
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
                logging.error('processArticleTitle Aborting - Unexpected number of tds in article body: {0}. Expected 3. Body: \n{1}'.format(len(tds), soup.prettify()))
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
            logging.debug('processPostTitle - Error:\n{0}\n{1}'.format(e, soup.prettify()))

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
                logging.warning('processPostPoints - unexpected create time: {0}'.format(match.group(0)))
                created=None

            if created:
                created=datetimeToStr(created)
            else:
                created=match.group(0)
        else:
            logging.warning('processTimeStr - unexpected create time - failed to match: {0}'.format(timeStr))
            created=timeStr
        return created

    def processPostPoints(self, soup):
        d={}
        try:
            tds=soup.contents
            if len(tds) != 2:
                logging.error('processArticlePoints Aborting - Unexpected number of tds in article body: {0}. Expected 2. Body: \n{1}'.format(len(tds), soup.prettify()))
                return d
            if tds[1].span: # Non-jobs post
                d['points']=asInt(mymatch('([0-9]*) points',tds[1].span.text))
                d['author']=mymatch('user\?id=(.*)',tds[1].find_all('a')[0].attrs['href'])
                d['comments']=asInt(mymatch('([0-9]*) comments', tds[1].find_all('a')[1].text, retType='zero_string')) # 'Discuss' has no comments
                d['created']=self.processTimeStr(tds[1].contents[3])
            else: # jobs have no points
                d['created']=self.processTimeStr(tds[1].text)
        except Exception as e:
            logging.debug('processArticlePoints - Error:\n{0}\n{1}'.format(e, soup.prettify()))

        return d

    def json(self):
        return json.dumps([post.json() for post in self.postSnaps])