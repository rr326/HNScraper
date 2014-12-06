echo 'COPYING scraper apache'
rsync -zha -O --no-perms --stats --exclude=".DS_Store" --recursive -e "ssh -q -l ${MY_UN} -i ${MY_CRED_FILE}" ~/dev/scraper/apache_config/sites-available/ prod5.k2company.com:/etc/apache2/sites-available

echo 'COPYING scraper site'
rsync -zha -O --no-perms --stats --exclude=".DS_Store" --recursive -e "ssh -q -l ${MY_UN} -i ${MY_CRED_FILE}" ~/dev/scraper/src/ prod5.k2company.com:/var/www/hind-cite-scraper

echo 'COPYING scraper code'
rsync -zha -O --no-perms --stats --exclude=".DS_Store" --recursive -e "ssh -q -l ${MY_UN} -i ${MY_CRED_FILE}" ~/dev/scraper/scripts/ prod5.k2company.com:/opt/hind-cite-scraper

echo 'COPYING scraper credentials'
scp -i ${MY_CRED_FILE}  ${HIND_CITE_CRED_FILE} ${MY_UN}@prod5.k2company.com:/opt/hind-cite-credentials.json
