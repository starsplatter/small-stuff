#!/usr/bin/python

import base64
import ConfigParser
import json
import logging
import argparse, sys
import urllib, urllib2

"""
Migrate CONTENTdm digital objects to ArchivesSpace: PHOTOGRAPHS SPECIAL EDITION

Assuming the CONTENTdm digital object's title is the same as an Archival Object
in ArchivesSpace, we can create a Digital Object in ArchivesSpace with either
the CONTENTdm URI or an ARK and link it to the Archival Object.

Some photographs have a special compontent ID field we can use to match items,
but it breaks other stuff, so it gets it's own script.

@author Seth Shaw
@date 2018-03-??

"""

class CDMQueryClient(object):
    """A CONTENTdm Query session."""
    def __init__(self, url):
        self.url = url + '/dmwebservices/index.php?q='

    # dmQuery/oclcsample/0/title!ark/pointer/5/0/1/0/0/1/json
    def query(self, alias, search='0', fields='0', sortby='0', maxrec=1024, start=1, suppress='1', docptr='0', suggest='0', facets='0', unpub='1', denormalize='1' ):
        """ Generator of search results. """
        alias = alias.lstrip('/')

        more = True
        while more == True:
            query= 'dmQuery/'+'/'.join((alias,search,fields,sortby,str(maxrec),str(start),suppress,docptr,suggest,facets,unpub,denormalize)) + '/json'
            logging.debug('Running %s' % (self.url + query))
            request = urllib2.Request(self.url + query)

            try:
                response = json.load(urllib2.urlopen(request))
            except urllib2.HTTPError as h:
                logging.error("Unable to process CONTENTdm wsAPI call (%s): %s - %s - %s" % (query, h.code, h.reason, h.read()))
                raise StopIteration
            except ValueError as v:
                logging.error("Invalid Response to CONTENTdm wsAPI call (%s): %s" % (query, v))
                raise StopIteration

            for record in response['records']:
                yield record

            # Paging
            if (maxrec+start) < response['pager']['total']:
                start += maxrec
            else:
                more = False

class ASClient(object):
    """An ArchivesSpace Client"""

    SESSION = ''

    def __init__(self, api_root, username, password):
        self.api_root = api_root
        self.login(username, password)

    def api_call(self, path, method = 'GET', data = {}, as_obj = True):

        path = self.api_root + path

        # urllib2 will force a call to POST if the data element is provided.
        # So, a query string must be appended to path if you want a GET
        if method == 'GET':
            if data:
                request = urllib2.Request(path + '?' + urllib.urlencode(data))
            else:
                request = urllib2.Request(path)
        elif method == 'POST':
            if isinstance(data, dict):
                data = json.dumps(data)
            request = urllib2.Request(path, data)
        else:
            logging.error("Unknown or unused HTTP method: %s" % method)
            return

        if self.SESSION: #only absent during login.
            request.add_header("X-ArchivesSpace-Session",self.SESSION)

        logging.debug("ArchivesSpace API call (%s;%s): %s %s %s %s" % (path, json.dumps(data), json.dumps(request.header_items()), request.get_method(), request.get_full_url(), request.get_data()) )
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError as h:
            logging.error("Unable to process ArchivesSpace API call (%s): %s - %s - %s" % (path, h.code, h.reason, h.read()))
            return {}
        if as_obj:
            return json.load(response); #object
        else:
            return response #readable stream

    def api_call_paginated(self, path, method = 'GET', data = {}):
        objects = [] #The stuff we are giving back
        data['page'] = 1
        last_page = 1 #assume one page until told otherwise
        data['page_size'] = 200

        while data['page'] <= last_page:

            #The call
            archival_objs = self.api_call(path, method, data)

            #Debuggging and Pagination
            logging.debug("Page %s of %s" % (data['page'], last_page))
            # logging.debug(json.dumps(archival_objs))
            if archival_objs['last_page'] != last_page:
                logging.debug('Updating last page from %s to %s' % (last_page, archival_objs['last_page']))
                last_page = archival_objs['last_page']

            objects += archival_objs['results']

            #Next, please....
            data['page'] += 1

        return objects

    def login(self, username, password):
        path = '/users/%s/login' % (username)
        obj = self.api_call(path,'POST', urllib.urlencode({'password': password }))
        self.SESSION = obj["session"]

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("alias", help="a CONTENTdm collection alias", nargs='+')
    # parser.add_argument("-c","--collection-id", help='an ArchivesSpace resource identifier. E. g., "MS-00425".')
    parser.add_argument("-i","--image-id-field", help='the CONTENTdm field storing the source image\'s identifier')
    # parser.add_argument("-k","--ark-field", help='the CONTENTdm field to use for the object ARKs (overrides config.ini)')
    parser.add_argument("-o","--digital-object-field", help='the CONTENTdm field to use for the digital object\'s identifier (overrides config.ini)')
    parser.add_argument("-v","--verbosity", help="change output verbosity: DEBUG, INFO (default), ERROR")
    parser.add_argument("-d","--dry", help="doesn't update ArchivesSpace, used for testing", action="store_true")
    args = parser.parse_args()

    dry = False
    if args.dry:
        dry = True

    # Configuration
    verbosity = logging.INFO
    if args.verbosity:
        if args.verbosity == 'DEBUG':
            verbosity = logging.DEBUG
        if args.verbosity == 'INFO': # Redundant, I know, but it keeps the list clean
            verbosity = logging.INFO
        if args.verbosity == 'ERROR':
            verbosity = logging.ERROR
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=verbosity)

    global config
    config = ConfigParser.ConfigParser()
    configFilePath = r'config.ini'
    config.read(configFilePath)

    # Fields for CDM to return.
    # Will add the ark field, if used, and the collection id field later
    cdm_fields = ['title']

    # # Which field holds the ARK?
    # ark_field = None
    # if config.get('cdm','ark-field'):
    #     ark_field = config.get('cdm','ark-field')
    # if args.ark_field:
    #     ark_field = args.ark_field
    # if ark_field:
    #     cdm_fields.append(ark_field)

    # Which field holds the Image Identifier?
    iid_field = 'sourca'
    if args.image_id_field:
        iid_field = args.image_id_field
    cdm_fields.append(iid_field)

    # Which field holds the Digital Object Identifier?
    do_field = config.get('cdm','doid-field')
    if args.digital_object_field:
        do_field = args.digital_object_field
    cdm_fields.append(do_field)

    public_url = config.get('cdm','public-url')

    # # Limit by AS collection id?
    query = '%s^Image+ID^exact' % (iid_field)

    # Initialize the query client
    dmQuery = CDMQueryClient(config.get('cdm','wsAPI-url'))

    # Initialize AS client
    aspace_client = ASClient(config.get('archivesspace','api-prefix'),
                             config.get('archivesspace','username'),
                             config.get('archivesspace','password'))
    repository = config.get('archivesspace','repository')

    for alias in args.alias:

        alias = alias.lstrip('/') # The preceding / on an alias is annoying to work with. Chop it off if present.
        for result in dmQuery.query(alias,query,'!'.join(cdm_fields), sortby=iid_field):

    #         # REPORT and SKIP if the do has no ARK
    #         if ark_field and not result[ark_field]:
    #             logging.info('SKIPPING: no ARK for %s/id/%d (%s:%s)' % (result['collection'],result['pointer'],current_cid,current_as_rid))
    #             continue
    #         #  REPORT and SKIP if the do has no title

            # USING CDM URI FOR NOW AS A DEMONSTRATOR. USE ARK FOR PRODUCTION.
            cdm_uri = public_url % (alias,result['pointer'])

            if not 'title' in result:
                # print('\t'.join((cdm_uri,'NO TITLE FOUND',archival_object['uri'],archival_object['display_string'])))
                result['title'] = 'NO TITLE EXISTS IN CDM'
                # continue

            # Clean up the Image ID field to match AS
            iid = result[iid_field].rstrip().replace('Image ID: ','').replace('  ',' ').replace(' ', '_')
            # Query ArchivesSpace for archival objects (ao) with component idenfifier
            ao_query = '{"query":{"op":"AND","subqueries":[{"field":"component_id","value":"%s","jsonmodel_type":"field_query","negated":false,"literal":true},{"field":"primary_type","value":"archival_object","jsonmodel_type":"boolean_field_query"}],"jsonmodel_type":"boolean_query"},"jsonmodel_type":"advanced_query"}' % (iid)
            archival_objects = aspace_client.api_call('/repositories/%s/search?page=1&aq=%s' % (repository,ao_query))

            if not archival_objects['results']:
                # logging.info('SKIPPING: Could not find Component ID "%s" in ArchivesSpace for %s/id/%s' % (iid,alias,result['pointer']))
                print('\t'.join((cdm_uri,result['title'],iid,'NO AO FOUND','NO AO FOUND')))
                continue
            # Check to see if we have different URIs, or multiple of the same
            ao_uris = list()
            for ao in archival_objects['results']:
                ao_uris.append(ao['uri'])
            ao_uris = set(ao_uris)
            if len(ao_uris) > 1:
                print('\t'.join((cdm_uri,result['title'].rstrip(),iid,'MULTIPLE AOs: '+','.join(ao_uris),'MULTIPLE TITLES')))
                # logging.info('SKIPPING: multiple Archival Objects with Component ID "%s" for %s/id/%s: %s'% (iid,alias,result['pointer'],','.join(ao_uris)))
                continue
            # Build a clean copy from search results json field
            archival_object = json.loads(archival_objects['results'][0]['json'])
            # - IF a single result: update ao in AS with instance link using the CDM URI. **USE ARK for production, this is a DEMONSTRATION!**
            # based on https://github.com/djpillen/bentley_scripts/blob/master/update_archival_object.py

            ado = {'title':result['title'],'digital_object_id':result[do_field],'publish':True,'file_versions':[{'file_uri':cdm_uri,'publish':True,'is_representative':True}]}
            ado_uri = 'FAKE/URI' # Incase the DRY option is enabled
            print('\t'.join((cdm_uri,result['title'].rstrip(),iid,archival_object['uri'],archival_object['display_string'].rstrip())))
            # if dry:
                # logging.debug('DRY: Would create AS digital object: %s' % (json.dumps(ado)))
            # else:
            #     ado_response = aspace_client.api_call('/repositories/%s/digital_objects' % (repository),'POST', ado)
            #     if not 'uri' in ado_response:
            #         logging.warn('FAILED to create AS digital object %s %s: %s' % ('/repositories/%s/digital_objects' % (repository), ado, json.dumps(ado_response)))
            #         continue
            #     ado_uri = ado_response['uri']
    #
    #         # Update the Archival Object
    #         # TODO: (Assuming we ignore that the AS digital object already existed.) Add checking to make sure we don't already have a matching instance
    #         ado_instance = {'instance_type':'digital_object','digital_object':{'ref':ado_uri}}
    #         archival_object['instances'].append(ado_instance)
    #         if dry:
    #             logging.info('DRY: Would update AS Archival Object %s with new instance %s' % (archival_object['uri'], ado_instance))
    #         else:
    #             ao_update_response = aspace_client.api_call(archival_object['uri'],'POST', archival_object)
    #             logging.info('%s: AS Archival Object %s with AS Digital Object %s for CDM object %s : %s' % (ao_update_response['status'],ao_update_response['id'],ado_uri,result[do_field],result['title']))
