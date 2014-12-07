# hind-cite-scraper

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

1. Install [servi](https://github.com/rr326/servi)
1. Credentials
    * Create an hn_credentials.json with proper UN/PW, based on scripts/hn_credentials.
    * Save it somewhere OUTSIDE any git repo
    * Point to it with an environment variable: eg: export HIND_CITE_CRED_FILE="/xxx/PASSWORDS/hn_credentials.json"
1. Test it all on vagrant
    * vagrant up
    * run it with --config test (test config bundle)
1. Push it live
    * servi rans -p prod
    * scripts/pushtoprod.sh
1. Monitor the log files a bit to make sure all is well, then you're done
   * When first running hnscrape,  in config.py set LOGLEVEL=logging.PROGRESS
   * When you are confident all is well, set LOGLEVEL=logging.INFO


## Todo

* BIG BUG:
    * Make sure scraper sets timestamp str IN UTC.  Right now, if the server is in local time, the timestamp str will also be local time, which is a giant mess.
* Comments - with the new firebase API, getting the comment counts requires a lot of API calls. Not doing it. Hopefully they will come up with an easier way.



## Notes - hnscrape
* Originally this scraped the home page and page 2
* Now this uses new hacker news api from firebase: https://github.com/HackerNews/API
* The data has a giant hole from 10/5/14 - 12/5/14 - I apparently turned off the scraper and monitor when 
  doing some server maintenance and didn't realize it.  Ooops!
  

