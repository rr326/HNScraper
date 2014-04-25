# HNScraper

Tools for scraping Hacker News and uploading to Cloudant.

## Files

* hnscrape.py - this is the main scraper application
* hnmonitor.py - this monitors hnscrape and emails a list of administrators if there are too many errors or too few posts (ie: something is wrong)
* config.py - main configuration file
* *.conf - configuration for upstart (ie: run as a service on ubuntu)
* hn_credentials.json - SAMPLE pw file
* scripts/log/hnscrape.log - main log file
* /var/log/upstart/hn*.log - upstart log files
* init_upstart.sh - script to make it easier to update upstart

## Installation

1. Install python 2.7 and all used libraries (using pip). Feel free to use a virtualenv.
2. Modify config.py
3. Setup whatever you want to autorun these two functions. (Use the --daemon argument) If using upstart:
    * git pull origin master
    * sudo cp scripts/hn_credentials.json /etc   (Note - this is the default location. If you change this location,
    need to also modify it in *.conf)
    * Update /etc/hn_credentials.json with proper passwords
    * sudo scripts/init_upstart.sh

4. Monitor the log files a bit to make sure all is well, then you're done
   * When first running hnscrape,  in config.py set LOGLEVEL=logging.PROGRESS
   * When you are confident all is well, set LOGLEVEL=logging.INFO


## Todo

* >> TODO: Remove alert debugging

* Move scripts from Ross' digitalocean server to cloudant server
* Get cloudant email address and pw for hnmonitor
* Put cloudant email pw in credentials.json (and change name to credentials)
* Prune git repo history and make a public version (http://stackoverflow
.com/questions/4515580/how-do-i-remove-the-old-history-from-a-git-repository)


## Notes - hnscrape

* PG says you should be able to scrape 'a couple a minute'. Doing that I quickly got ip-banned. Now we do 2 pages every 5 minutes, and don't seem to have any problems.
* We scrape news.ycombinator.com/news & news.ycombintor.com/news2
* If he changes the format, we'll get an alert with a bunch of errors. Then we need to look at the error log, figure out what's wrong, take into account that new format, and restart. I don't know if there are no more gotchas out there, or they will happen regularly. We just have to watch it.
* One slight oddity: each record has a id field from hn.  Jobs postings, however, do not always publish their internal id, so I use the href for those few records.

