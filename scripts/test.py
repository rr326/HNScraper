from hnscrape import *

with open('testpage.html','r') as f:
    html=f.read()

page=HNPage(html,'TESTPAGE',2)
