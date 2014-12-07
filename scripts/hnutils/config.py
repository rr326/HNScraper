from __future__ import division

import logging
import os
import os.path
import json

#
# Helper functions
#
PROGRESS = 15
def add_progress_to_logging(logging_module):
    logging_module.PROGRESS = PROGRESS
    logging_module.addLevelName(logging_module.PROGRESS, 'PROGRESS')
    def log_progress(self, msg, *args, **kws):
        if self.isEnabledFor(logging_module.PROGRESS):
            self._log(logging_module.PROGRESS, msg, args, **kws)

    logging_module.Logger.progress = log_progress
    return

def test_log_dir(log_dir):
    try:
        fname = os.path.join(log_dir, 'test')
        with open(fname, 'w') as fp:
            fp.write('test')
        os.remove(fname)
    except IOError:
        logging.error('Couldnt write to log dir. Failing. {0}'.format(log_dir),
            exc_info=True)
        raise



#
# Main configuration
#

add_progress_to_logging(logging)

SCRIPT_DIR=os.path.normpath(os.path.join(os.path.split(os.path.realpath(__file__))[0],'../'))
LOG_DIR='/var/log/hind-cite-scraper/'
test_log_dir(LOG_DIR)

LOGFILE=os.path.join(LOG_DIR, 'hnscrape.log')
LOGLEVEL=PROGRESS

PAGE_RETRY=5
PAGE_RETRY_WAIT=30

servers = {
    'prod': {
        'COUCH_SERVER': 'https://cs.cloudant.com',
        'COUCH_DB': 'news'
    },
    'test': {
        'COUCH_SERVER': 'https://rrosen326.cloudant.com',
        'COUCH_DB': 'hind-cite'
    }
}

#
# Couch UN & PW must be set via command line args in the main module (eg: hnscrape.py)
#
COUCH_UN='NOT SET - SET VIA setCredentials()'
COUCH_PW='NOT SET - SET VIA setCredentials()'

COUCH_ID_VIEW='by/id'

NEW_NUMTOGET=60

# For alerting - 1 line per error.
ERRORS_ONLY_LOG=os.path.join(LOG_DIR, 'hnscrape_errors_only.log')

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
MOCK_PAGE=os.path.join(SCRIPT_DIR,  'test/pageSource')
HNMONITOR_FORCE_SEND=False    # Force sending

#
# Configuration overrides
#
LONG_WAIT = SHORT_WAIT = NEW_WAIT = STATS_HOURS = MOCK_INPUT = MOCK_OUTPUT = \
TEST_RUN = COUCH_SERVER = COUCH_DB = PAGES_TO_GET = None  # To help pycharm find the variables

# A config bundle must be set via command line arg and update_config()
configs = {
    "production": {
        "LOGLEVEL" : logging.INFO,
        "LONG_WAIT" : 285,
        "SHORT_WAIT": 15,
        "NEW_WAIT": 300,
        "STATS_HOURS": 1,
        "MOCK_INPUT": False,
        "MOCK_OUTPUT": False,
        "TEST_RUN": False,
        "server": "prod"
    },
    "test": {
        "LOGLEVEL" : logging.DEBUG,
        "LONG_WAIT" : 30,
        "SHORT_WAIT": 5,
        "NEW_WAIT": 300,
        "STATS_HOURS": 1/6,
        "MOCK_INPUT": False,
        "MOCK_OUTPUT": False,
        "TEST_RUN": True,
        "server": "test",
        "NEW_NUMTOGET": 60
    }
}


'''
*** Don't forget CouchDB Views ***
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


# This updates this modules globals based on a chosen configuration
def update_config(chosen_config, configs, servers):
    try:
        assert chosen_config in configs
    except AssertionError:
        logging.error('chosen_config ({0}) not in configs:\n{1}'.format(chosen_config, configs))
        raise
    config = configs[chosen_config]

    for key in config:
        if key is 'server':
            for field in servers[config[key]]:
                globals()[field] = servers[config[key]][field]
        else:
            globals()[key] = config[key]

    # Manually set PAGES TO GET
    globals()["PAGES_TO_GET"] = \
        [{'page': 'http://news.ycombinator.com/news', 'depth': 0,
          'wait': config['SHORT_WAIT']},
         {'page': 'http://news.ycombinator.com/news?p=2', 'depth': 0,
          'wait': config['LONG_WAIT']}
        ]

    msg = "\nConfiguration Bundle Set: {0}:\n==================\n".format(
        chosen_config)
    for key in configs["test"].keys() + ["PAGES_TO_GET"]:
        msg += "{0:20} {1}\n".format(key, globals().get(key))
    msg += '\n'
    logging.info(msg)

    return

