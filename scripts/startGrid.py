#!/usr/bin/env python

from __future__ import division

import subprocess, time, sys
from selenium import webdriver
import argparse

PHANTOMJS={'platform':'ANY', 'browserName':'phantomjs', 'javascriptEnabled':True}

SELENIUM='../tools/selenium-server-standalone-2.39.0.jar'
GRID_TEST_TIMEOUT=180
REMOTE_HUB='http://localhost:4445/wd/hub'
PHANTOM_PORT_START=8080
HUB_STARTUP_DELAY=60

# Command line arguments
parser = argparse.ArgumentParser(description='Start Selenium Grid')
parser.add_argument('-n', '--num', default=3, type=int, help="Number of PHANTOMJS nodes to start")
args=parser.parse_args()


# Set up the selenium grid


class Grid(object):
    def __init__(self, numNodes):
        if self.alreadyRunning():
            print 'Grid Already Running. Will not create a new one.'
            return

        print '#######################################\nNote: It takes > 3 min for the grid to become active.\n#######################################\n'
        self.numNodes = numNodes
        self.hub=None
        self.node=None
        
        self.hub=subprocess.Popen(["java", "-jar", SELENIUM,
                                   '-role','hub', 
                                   '-hubConfig', 'gridHubConfig.json'
                                   ])
        print 'Opened hub.  Pid: {0}'.format(self.hub.pid)
        sys.stdout.flush()
        print 'Going to wait for {0} seconds before luanching phantom...'.format(HUB_STARTUP_DELAY)
        time.sleep(HUB_STARTUP_DELAY) # It takes about 120 for the hub to start registering. Might as well wait so the hub is up when the node is spawned

        self.openPhantoms()

        print 'Finished setting up grid'
        self.testGrid()
        return  

    # Phantom is one instance per process / node.
    def openPhantoms(self):
        hubString=REMOTE_HUB.replace('/wd/hub','')  # phantom uses just the base part
        for i in range(self.numNodes):
            print 'Phantom: creating {0} of {1} nodes'.format(i+1, self.numNodes)
            port = PHANTOM_PORT_START + i
            subprocess.Popen(['phantomjs',
                            '--webdriver={0}'.format(port),
                            '--webdriver-selenium-grid-hub={0}'.format(hubString)
                            ])
            time.sleep(3) # Just in case


    
    def testGrid(self):
        print 'Grid: Testing...'
        t0=time.time()
        while time.time()-t0 < GRID_TEST_TIMEOUT:
            try:
                driver=webdriver.remote.webdriver.WebDriver(command_executor=REMOTE_HUB, desired_capabilities=PHANTOMJS)
                driver.quit()
                print 'Grid: PhantomJS works!'

                print 'Grid: Operational. Check {0}/grid/console for status'.format(REMOTE_HUB)
                return True
            except:
                print 'Grid: Testing...'
                if time.time()-t0 < GRID_TEST_TIMEOUT:
                    time.sleep(10)    
        
        print 'Grid: ###Error### - Connection timed out after {0:.0f} seconds'.format(time.time()-t0)
        return False
    
    def alreadyRunning(self):
        try: 
            driver=webdriver.remote.webdriver.WebDriver(command_executor=REMOTE_HUB, desired_capabilities=PHANTOMJS)
            driver.quit()
            return True
        except:
            return False
        
    
    
    def shutdown(self):
        print 'Shutting down grid:'
            
        try: 
            self.hub.terminate()
            print 'Killed hub'
            self.hub=None
        except:
            print ' (no hub to kill)'
            
        print 'Finished shutting down grid.'
        return
    

if __name__ == '__main__':
    grid = Grid(args.num)
    
    