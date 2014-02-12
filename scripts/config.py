from __future__ import division
import logging
logging.PROGRESS = 15
logging.addLevelName(logging.PROGRESS, 'PROGRESS')
def log_progress(self, msg, *args, **kws):
    if self.isEnabledFor(logging.PROGRESS):
        self._log(logging.PROGRESS, msg, args, **kws)
logging.Logger.progress=log_progress

import os
SCRIPT_DIR=os.path.split(os.path.realpath(__file__))[0]

LOGFILE=os.path.join(SCRIPT_DIR, 'log', 'hnscrape.log')
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
STATS_HOURS=1
LOCAL_DEBUG=False
MOCK_PAGE=os.path.join(SCRIPT_DIR,  'test/pageSource')



# Overrides For debugging
# LOCAL_DEBUG=True
# SHORT_WAIT=5
# LONG_WAIT=5
# STATS_HOURS=1/(3600/20)
# PAGES_TO_GET = todoList = [{'page': 'http://news.ycombinator.com', 'depth': 0, 'wait': SHORT_WAIT},  # depth 0 is page 1
#                            {'page': 'http://news.ycombinator.com/news2', 'depth': 0, 'wait': LONG_WAIT}]