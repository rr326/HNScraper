import config
from firebase import firebase
firebase = firebase.FirebaseApplication('https://hacker-news.firebaseio.com', None)
import logging
from datetime import datetime
from gevent.pool import Group
from pprint import pformat
from hn_classes import datetimeToStr
from time import time as now


class Stories(object):
    def __init__(self, storyids):
        self.timestamp = now()
        self.timestamp_str = datetimeToStr(datetime.utcfromtimestamp(self.timestamp))


        self.storyids = storyids
        self.postSnaps = self.getPostSnaps()
        self.supplementPostSnaps()
        self.doComments()
        self.removeKids()

    def __len__(self):
        return len(self.postSnaps)

    def __repr__(self):
        return pformat(self.postSnaps)

    def getPostSnaps(self):
        """
        return a list of story dicts
        """

        logging.debug('getPostSnaps: about to get {0} postSnaps'.format(len(self.storyids)))

        group = Group()
        getstory = lambda storyid: firebase.get('/v0/item', storyid)

        stories = group.map(getstory, self.storyids)

        return stories

    def doComments(self):
        # Right now, just going to set to 0
        for postSnap in self.postSnaps:
            postSnap['comments'] = 0

    def supplementPostSnaps(self):
        # Updates postSnaps in a story list
        for rank, postSnap in enumerate(self.postSnaps, start=1):
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
        for snap in self.postSnaps:
            if 'kids' in snap:
                del snap['kids']


def newGetHNPosts():
    try:
        topstories = firebase.get('/v0/topstories', None)
        stories = Stories(topstories[:config.NEW_NUMTOGET])

    except Exception as e:
        logging.error('newGetHNPosts exception: {0}'.format(e))
    else:
        logging.log(config.logging.PROGRESS,'GOT:  {0} records'.format(len(stories)))
        print(stories)

    exit()

    return stories