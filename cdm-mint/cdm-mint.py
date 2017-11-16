#!/usr/bin/python

import ConfigParser
import json
import logging
import urllib, urllib2

# Based on https://gist.github.com/saverkamp/9198310

# cdm-mint.py
# Mints ARKS and updates CONTENTdm records with the Catcher protocol.
# CDM Catcher documentation at: http://contentdm.org/help6/addons/catcher.asp
# ***requires SUDS, a third-party SOAP python client: https://fedorahosted.org/suds/***

class Catcher(object):
    """A CONTENTdm Catcher session."""
    # Taken from saverkamp (https://gist.github.com/saverkamp/9197945)
    def __init__(self, url, user, password, license):
        self.transactions = []
        self.client = Client('https://worldcat.org/webservices/contentdm/catcher/6.0/CatcherService.wsdl')
        self.url = url
        self.user = user
        self.password = password
        self.license = license

    def processCONTENTdm(self, action, user, password, license, alias, metadata):
    # function to connect to CatcherServices and process metadata updates
        transaction = self.client.service.processCONTENTdm(action, url, user, password, license, alias, metadata)
        self.transactions.append(transaction)

    def edit(self, alias, recordid, field, value):
    #function to edit metadata--call packageMetadata and processCONTENTdm
        metadata = self.packageMetadata('edit', recordid, field, value)
        self.processCONTENTdm('edit', self.user, self.password, self.license, alias, metadata)

    def packageMetadata(self, action, recordid, field, value):
    #function to package metadata in metadata wrapper
        action = action
        if action == 'edit':
            metadata = self.client.factory.create('metadataWrapper')
            metadata.metadataList = self.client.factory.create('metadataWrapper.metadataList')
            metadata1 = self.client.factory.create('metadata')
            metadata1.field = 'dmrecord'
            metadata1.value = recordid
            metadata2 = self.client.factory.create('metadata')
            metadata2.field = field
            metadata2.value = value
            metadata.metadataList.metadata = [metadata1, metadata2]
        return metadata

class Query(object):
    """A CONTENTdm Query session."""
    def __init__(self, url):
        self.url = url + '/dmwebservices/index.php?q='


    # dmQuery/oclcsample/0/title!ark/pointer/5/0/1/0/0/1/json
    def query(self, alias, search='0', fields='0', sortby='0', maxrec=1024, start=1, suppress='1', docptr='0', suggest='0', facets='0', unpub='1', denormalize='1' ):
        """ Returns an array of search results as dicts. """
        alias = alias.lstrip('/')
        query= 'dmQuery/'+'/'.join((alias,search,fields,sortby,str(maxrec),str(start),suppress,docptr,suggest,facets,unpub,denormalize)) + '/json'
        print 'Running %s' % (self.url + query)
        request = urllib2.Request(self.url + query)

        try:
            response = json.load(urllib2.urlopen(request))
        except urllib2.HTTPError as h:
            logging.error("Unable to process CONTENTdm wsAPI call (%s): %s - %s - %s" % (query, h.code, h.reason, h.read()))
            return {}
        # PAGING
        if response['pager']['start']:
            start = int(response['pager']['start'])
        if (maxrec+start) < response['pager']['total']:
            start += maxrec
            response['records'].extend(self.query(alias, search, fields, sortby, maxrec, start, suppress, docptr, suggest, facets, unpub, denormalize))

        return response['records']; #object


# who_what_when is a dict with the keys who, what, and when. All other keys are ignored.
def mint_ark(identifier, dublin_core={}):
    request = urllib2.Request("%s/%s" % (config.get('ezid','minter-url'),
                              config.get('ezid','ark-shoulder')))
    request.add_header("Content-Type", "text/plain; charset=UTF-8")

    #Authentication
    encoded_auth = base64.encodestring('%s:%s' % (config.get('ezid','username'),
                                                  config.get('ezid','password')
                                                  )).replace('\n', '')
    request.add_header("Authorization","Basic %s" % encoded_auth)

    #Add target URL
    # target = "%s/%s.pdf" % (config.get('archivesspace','pdf-url-prefix'),
    #                         identifier )
    data = "_target: %s\n" % (target)
    for descriptive_item_term, descriptive_item_value in dublin_core.iteritems():
        data += '%s: %s\n' % (descriptive_item_term, descriptive_item_value)

    request.add_data(data.encode("UTF-8"))

    try:
        response = urllib2.urlopen(request)
        answer = response.read()
        if answer.startswith('success'):
            code,ark = answer.split(": ")
            logging.info('Minted ARK for %s: %s => %s' % (identifier,
                                                          ark, target))
            return ark
        else:
            logging.error("Can't mint ark: %s", answer)
            return ''
    except urllib2.HTTPError, e:
        logging.error("%d %s\n" % (e.code, e.msg))
        if e.fp != None:
          response = e.fp.read()
          if not response.endswith("\n"): response += "\n"
          logging.error("Can't mint ark. Response: %s", response)


if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    global config
    config = ConfigParser.ConfigParser()
    configFilePath = r'config.ini'
    config.read(configFilePath)

    test_query = Query(config.get('cdm','wsAPI-url'))
    results = test_query.query('/oclcsample','0','ark','0',3)
    print json.dumps(results, indent=4)
    print "Count of results " + str(len(results))