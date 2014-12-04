import config
from firebase import firebase
firebase = firebase.FirebaseApplication('https://hacker-news.firebaseio.com', None)
import logging
from datetime import datetime

def newGetHNPosts():
    try:
        topstories = firebase.get('/v0/topstories', None)
        for storyid in topstories:
            story = firebase.get('v0/item', storyid)
            story['doc_type'] = 'post' if \
                not config.MOCK_INPUT and not config.MOCK_OUTPUT and not config.TEST_RUN
            story['created'] = datetime.fromtimestamp(story['time'])


    except Exception as e:
        logging.error('newGetHNPosts exception: {0}'.format(e))


    return []