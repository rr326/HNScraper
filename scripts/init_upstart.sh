#!/bin/sh

# Set up upstart with modified configuration
# Run as sudo
cp *.conf /etc/init
initctl reload-configuration
start hnmonitor
start hnscrape
