from __future__ import division
import logging, os, json

#
# Logging
#
logging.PROGRESS = 15
# noinspection PyUnresolvedReferences
logging.addLevelName(logging.PROGRESS, 'PROGRESS')
# noinspection PyUnresolvedReferences
def log_progress(self, msg, *args, **kws):
    if self.isEnabledFor(logging.PROGRESS):
        self._log(logging.PROGRESS, msg, args, **kws)
logging.Logger.progress=log_progress

SCRIPT_DIR=os.path.split(os.path.realpath(__file__))[0]

LOGFILE=os.path.join(SCRIPT_DIR, 'log', 'hnscrape.log')
LOGLEVEL=logging.INFO


PAGE_RETRY=5
PAGE_RETRY_WAIT=30

COUCH_SERVER='https://cs.cloudant.com'
COUCH_DB='news'

#
# Couch UN & PW must be set via command line args in the main module (eg: hnscrape.py)
#
COUCH_UN='NOT SET - SET VIA setCredentials()'
COUCH_PW='NOT SET - SET VIA setCredentials()'

COUCH_ID_VIEW='by/id'
SHORT_WAIT=15
LONG_WAIT=285
PAGES_TO_GET=todoList=[{'page':'http://news.ycombinator.com', 'depth':0, 'wait': SHORT_WAIT},  # depth 0 is page 1
              {'page':'http://news.ycombinator.com/news2', 'depth':0, 'wait': LONG_WAIT}]
STATS_HOURS=1

# For alerting - 1 line per error.
ERRORS_ONLY_LOG=os.path.join(SCRIPT_DIR, 'log', 'errors_only.log')

# hnmonitor
RUNFREQUENCY = 6  # hours (integer >= 1)
MAXERRORS = 4
NUMPOSTSPERPAGE=30  # Invariant, but put here so I don't hardcode
POSTERRORTHRESHOLD=.9  # Anything less than 80% will cause an alert


# Email
EMAIL_ADDR='noreply@zephyrzone.org'
EMAIL_PW='NOT SET - SET VIA setCredentials()'
EMAIL_PORT=80
SMTP_SERVER='smtpout.secureserver.net'
EMAIL_FROM=EMAIL_ADDR
EMAIL_RECIPIENTS=['rrosen326@gmail.com']
EMAIL_SUBJECT='hnscrape monitor results'
EMAIL_TEXT='hnscraper does not appear to be working properly.\nCheck log file (hnscrape.log) for details.\n'



#
# Testing
#
LOCAL_DEBUG=False
MOCK_PAGE=os.path.join(SCRIPT_DIR,  'test/pageSource')
HNMONITOR_FORCE_SEND=False    # Force sending

# Overrides For debugging
# LOGLEVEL=logging.DEBUG
# SHORT_WAIT=5
# LONG_WAIT=30
# STATS_HOURS=1/(3600/20)
# PAGES_TO_GET = todoList = [{'page': 'http://news.ycombinator.com', 'depth': 0, 'wait': SHORT_WAIT},  # depth 0 is page 1
#                            {'page': 'http://news.ycombinator.com/news2', 'depth': 0, 'wait': LONG_WAIT}]


'''
CouchDB Views
The database needs to be set up with the view: _design/by/id

==> This is in the hinsight couchapp directory

'''


def setCredentials(pw_file):
    """
    Sets the module's (global) COUCH_UN & COUCH_PW & EMAIL_PW variables
    """
    global COUCH_UN, COUCH_PW, EMAIL_PW

    with open(pw_file, 'r') as f:
        tmp = json.load(f)
        COUCH_UN = tmp['COUCH_UN']
        COUCH_PW = tmp['COUCH_PW']
        EMAIL_PW = tmp['EMAIL_PW']


