#!/bin/sh

# Set up upstart with modified configuration
# Run as sudo
# Note - be sure to have properly set up passwords in /etc/couch_pw.json

cp hnscrape.conf hnmonitor.conf /etc/init
initctl reload-configuration

service hnmonitor stop
service hnmonitor start
service hnscrape stop
service hnscrape start

# Wait a few seconds to give them a chance to fail, if they are going to
sleep 5s

echo 'Status of hnmonitor and hnscrape'
echo '================================'
status hnmonitor
status hnscrape
