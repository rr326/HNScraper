from datetime import datetime

# Keep success / fail stats by the hour
class StatLogger(object):
    def __init__(self):
        self.resetDate=datetime.now()
        self.numGot=0
        self.numPosted=0
        self.numErrors=0

    def __str__(self):
        return 'pagesDownloaded: {0:>4} snapsPosted: {1:>4} numErros: {2:>4} over last {3:.1g} hours'.format(self.numGot, self.numPosted, self.numErrors, (datetime.now() - self.resetDate).seconds/3600 )

    def addGot(self, num=1):
        self.numGot += num

    def addPosted(self, num):
        self.numPosted +=num

    def addError(self, num=1):
        self.numErrors+=num

    def resetStats(self):
        self.resetDate=datetime.now()
        self.numGot = 0
        self.numPosted = 0
        self.numErrors = 0

stats=StatLogger()