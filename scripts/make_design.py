import config
import couchdb
from pprint import pprint


design_by= {
  "_id": "_design/by",
  "views": {
    "id": {
      "map": """function(doc) {
          if (doc.id) {
              emit(doc.id, doc);
          }
      }"""
    },
  },
  "language": "javascript"
}



def make_design():
    couch = couchdb.Server(config.COUCH_SERVER)
    couch.resource.credentials = (config.COUCH_UN, config.COUCH_PW)
    db = couch[config.COUCH_DB]
    db.info()  # Will raise an error if it doesn't work
    print 'Db connection established.'
    # First get doc:
    existing=db.get('_design/by')
    pprint(existing)



    db.save(design_by)
    print 'Design document successfully created'
    return

if __name__=='__main__':
    print '''
    This does NOT work yet. I was starting to work on this, but then apparently its already set up on the new db. Eventually I should do database mgt through the script so I have source control. But not now.
    '''

    # make_design()