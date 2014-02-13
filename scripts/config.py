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

# For alerting - 1 line per error.
ERRORS_ONLY_LOG=os.path.join(SCRIPT_DIR, 'log', 'errors_only.log')

# hnmonitor config
RUNFREQUENCY = 1 # 6  # hours
MAXERRORS = 4
NUMPOSTSPERPAGE=30  # Invariant, but put here so I don't hardcode

print '*************** Setting threshold to 1.5 for testing.'
POSTERRORTHRESHOLD=.8  # Anything less than 80% will cause an alert
POSTERRORTHRESHOLD=1.5  # Anything less than 80% will cause an alert

# Email
EMAIL_ADDR='noreply@zephyrzone.org'
EMAIL_PW='84bc29x'

EMAIL_PORT=80
SMTP_SERVER='smtpout.secureserver.net'
EMAIL_FROM=EMAIL_ADDR
EMAIL_RECIPIENTS=['rrosen326@gmail.com', 'ross_rosen@yahoo.com']
EMAIL_SUBJECT='hnscrape monitor results'
EMAIL_TEXT='hnscrape monitor:\n======================\nhnscraper does not appear to be working properly.\nCheck log file (hnscrape.log) for details.\n\n'




# Overrides For debugging
# LOCAL_DEBUG=True
# SHORT_WAIT=5
# LONG_WAIT=5
# STATS_HOURS=1/(3600/20)
# PAGES_TO_GET = todoList = [{'page': 'http://news.ycombinator.com', 'depth': 0, 'wait': SHORT_WAIT},  # depth 0 is page 1
#                            {'page': 'http://news.ycombinator.com/news2', 'depth': 0, 'wait': LONG_WAIT}]


'''
CouchDB Views
The database needs to be set up with the following views. (This is here to capture via source control.)
_design/by/id
function(doc) {
    if (doc.id) {
        emit(doc.id, doc);
    }
}

'''
