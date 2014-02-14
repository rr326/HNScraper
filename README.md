# HNScraper

Tools for scraping Hacker News and uploading to Cloudant.

## Files

* hnscrape.py - this is the main scraper application
* hnmonitory.py - this monitors hnscrape and emails a list of administrators if there are too many errors or too few posts (ie: something is wrong)
* config.py - main configuration file
* *.conf - configuration for upstart (ie: run as a service on ubuntu)
* scripts/log/hnscrape.log - main log file
* /var/log/upstart/hn*.log - upstart log files

## Installation

1. Install python 2.7 and all used libraries (using pip). Feel free to use a virtualenv.
2. Modify config.py
3. Setup whatever too you want to autorun these two functions. (Use the --daemon argument) If using upstart:
   * Just modify hn*.conf with the appropriate directories
   * sudo cp *.conf /etc/init
   * sudo initctl reload-configuration
   * sudo start hnscrape
   * sudo start hnmonitor
   * sudo status hnscrape
   * sudo status hnmonitor
4. Monitor the log files a bit to make sure all is well, then you're done
   * When first running hnscrape,  in config.py set LOGLEVEL=logging.PROGRESS
   * When you are confident all is well, set LOGLEVEL=logging.INFO


## Todo

* >> TODO: Remove alert debugging

* Move scripts from Ross' digitalocean server to cloudant server
* Fix some data problems
  * Old data - there were a few bugs that I fixed and should clean the old data
  * Test data - there is a bunch of test data from teh last few days I need to remove
* Get cloudant email address and pw for hnmonitor
* Then, use the data!

## Notes - hnscrape

* PG says you should be able to scrape 'a couple a minute'. Doing that I quickly got ip-banned. Now we do 2 pages every 5 minutes, and don't seem to have any problems.
* We scrape news.ycombinator.com/news & news.ycombintor.com/news2
* The scraping works, but is not resilient. The program SHOULD continue to work without crashing, but I'm not 100% certain of that.
* If he changes the format, we'll get an alert with a bunch of errors. Then we need to look at the error log, figure out what's wrong, take into account that new format, and restart. I don't know if there are no more gotchas out there, or they will happen regularly. We just have to watch it.
* One slight oddity: each record has a id field from hn.  Jobs postings, however, do not always publish their internal id, so I use the href for those few records.

