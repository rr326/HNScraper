import config
from firebase import firebase
firebase = firebase.FirebaseApplication('https://hacker-news.firebaseio.com', None)
import logging
from datetime import datetime
from gevent.pool import Group
from pprint import pformat


class Stories(object):
    def __init__(self, storyids):
        self.storyids = storyids
        self.stories = self.getStories()
        self.supplementStories()

    def __len__(self):
        return len(self.stories)

    def __repr__(self):
        return pformat(self.stories)

    def getStories(self):
        """
        return a list of story dicts
        """

        logging.debug('getStories: about to get {0} stories'.format(len(self.storyids)))

        group = Group()
        getstory = lambda storyid: firebase.get('/v0/item', storyid)

        stories = group.map(getstory, self.storyids)

        return stories

    def supplementStories(self):
        # Updates stories in a story list
        for story in self.stories:
            story['doc_type'] = 'post' if \
                not config.MOCK_INPUT and not config.MOCK_OUTPUT and not config.TEST_RUN \
                else 'test_data'
            story['created'] = datetime.fromtimestamp(story['time'])
            story['source'] = 'firebase'


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