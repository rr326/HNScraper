import config
from firebase import firebase
firebase = firebase.FirebaseApplication('https://hacker-news.firebaseio.com', None)
import logging
from datetime import datetime
from gevent.pool import Group
from pprint import pformat
from hn_classes import datetimeToStr, HNPostSnap
from time import time as now

logger = logging.getLogger(__name__)

class Stories(object):
    def __init__(self, storyids):
        self.timestamp = now()
        self.timestamp_str = datetimeToStr(datetime.utcfromtimestamp(self.timestamp))

        self.is_test_data=config.MOCK_OUTPUT or config.MOCK_INPUT or config.TEST_RUN

        self.storyids = storyids
        self.stories = self.getStories()
        self.supplementStories()
        self.doComments()
        self.removeKids()

        self.postSnaps=[]
        self.storiesToPostSnaps()

    def __len__(self):
        return len(self.stories)

    def __repr__(self):
        return pformat(self.stories)

    def getStories(self):
        """
        return a list of story dicts
        """

        logger.debug('getStories: about to get {0} stories'.format(len(self.storyids)))

        group = Group()
        getstory = lambda storyid: firebase.get('/v0/item', storyid)

        stories = group.map(getstory, self.storyids)

        return stories

    def doComments(self):
        # Right now, just going to set to 0
        for postSnap in self.stories:
            postSnap['comments'] = 0

    def supplementStories(self):
        # Updates stories in a story list
        for rank, postSnap in enumerate(self.stories, start=1):
            postSnap['doc_type'] = 'post' if \
                not config.MOCK_INPUT and not config.MOCK_OUTPUT and not config.TEST_RUN \
                else 'test_data'
            postSnap['created'] = datetimeToStr(datetime.fromtimestamp(postSnap['time']))
            postSnap['source'] = 'firebase'
            postSnap['rank'] = rank
            postSnap['timestamp_str'] = self.timestamp_str

            if 'domain' not in postSnap:
                postSnap['domain'] = 'NOT.SET'

            # Rename to match what hind-cite expects
            postSnap['points'] = postSnap.pop('score', None)
            postSnap['href'] = postSnap.pop('url', None)
            postSnap['author'] = postSnap.pop('by', None)

    def removeKids(self):
        for snap in self.stories:
            if 'kids' in snap:
                del snap['kids']

    def storiesToPostSnaps(self):
        for story in self.stories:
            postSnap = HNPostSnap(story)
            self.postSnaps.append(postSnap)


def newGetHNPosts():
    stories = None
    try:
        topstories = firebase.get('/v0/topstories', None)
        stories = Stories(topstories[:config.NEW_NUMTOGET])

    except Exception as e:
        logger.error('newGetHNPosts exception: {0}'.format(e))
    else:
        logger.progress('GOT:  {0} records'.format(len(stories)))


    return stories