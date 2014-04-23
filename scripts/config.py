from __future__ import division
import logging, os

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
# Note - this requires environment variables
# eg: .bshrc contains export HN_UN='XXXX'
#
if ('HN_UN' not in os.environ or 'HN_PW' not in os.environ):
    print '*'*80+'\n'+'You must set HN_UN & HN_PW as environment variables (in .bashrc)\n'+'*'*80
    raise Exception('Error - You must set HN_UN & HN_PW as environment variables (in .bashrc) ')

COUCH_UN=os.environ['HN_UN']
COUCH_PW=os.environ['HN_PW']

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
EMAIL_PW='84bc29x'
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
# LONG_WAIT=5
# STATS_HOURS=1/(3600/20)
# PAGES_TO_GET = todoList = [{'page': 'http://news.ycombinator.com', 'depth': 0, 'wait': SHORT_WAIT},  # depth 0 is page 1
#                            {'page': 'http://news.ycombinator.com/news2', 'depth': 0, 'wait': LONG_WAIT}]


'''
CouchDB Views
The database needs to be set up with the view: _design/by/id

==> This is in the hinsight couchapp directory

'''


