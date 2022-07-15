"""
Filename:    onenote.py

- Author:      [Laurent Burais](mailto:lburais@cisco.com)
- Release:
- Date:

Dependencies:

* TBC

Run:
mkdir /Volumes/library
mount_afp -i afp://Pharaoh.local/library /Volumes/library

cd /Volumes/library/Development/jamstack
python3 -m venv venv
source venv/bin/activate

python3 -m pip install --upgrade pip
pip3 install requests,flask,flask_session,msal,markdownify

python3 jamstack.py --input onenote --output site/nikola --nikola --html

Graph Explorer:
https://developer.microsoft.com/fr-fr/graph/graph-explorer
"""

import json
import requests
import re
import os
import time
import shutil

from datetime import datetime as dt
from bs4 import BeautifulSoup
from tabulate import tabulate

# pip3 install pandas
import pandas as pd

from mytools import *

# ###################################################################################################################################################
# ONENOTE
# ###################################################################################################################################################

class ONENOTE:

    onenote_elements = pd.DataFrame()

    token = None

    directory = None
    files_directory = None
    timestamp = None

    # ===============================================================================================================================================
    # __init__
    # ===============================================================================================================================================

    def __init__( self, directory ): 
        self.directory = directory
        self.files_directory = os.path.join( self.directory, 'onenote' )

    # ===============================================================================================================================================
    # clear
    # ===============================================================================================================================================

    def clear(self):

        if os.path.isdir(self.files_directory):
            shutil.rmtree(self.files_directory)
        os.makedirs(self.files_directory)

    # ===============================================================================================================================================
    # clean
    # ===============================================================================================================================================

    def clean(self):

        pass

    # ===============================================================================================================================================
    # get_all
    # ===============================================================================================================================================

    def get_all( self, token, elements=pd.DataFrame() ):

        myprint( elements, 'ELEMENTS')
        x = 1/0

        self.token = token
        self.onenote_elements = elements[elements['source'].isin(['onenote'])]

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get elements
        # -------------------------------------------------------------------------------------------------------------------------------------------

        if len(self.onenote_elements) == 0:
            myprint( '', line=True, title='GET ELEMENTS')

            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('notebook') ], ignore_index=True )
            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('group') ], ignore_index=True )
            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('section') ], ignore_index=True )
            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('page') ], ignore_index=True )

            myprint( 'Nb elements = {}'.format(len(self.onenote_elements)) )

            save_excel(self.directory, self.onenote_elements, 'elements')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get content
        # -------------------------------------------------------------------------------------------------------------------------------------------

        status = self._get_contents()

        save_excel(self.directory, self.onenote_elements, 'content')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        status = self._get_resources()

        save_excel(self.directory, self.onenote_elements, 'resources')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # expand data
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self._set_parents()

        self._merge_elements()

        self._set_path()
        
        self._set_tags()
        
        self._set_childs()
        
        save_excel(self.directory, self.onenote_elements, 'data')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # load resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self._load_resources()

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalize
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self._normalize()

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # save excel
        # -------------------------------------------------------------------------------------------------------------------------------------------

        save_excel(self.directory, self.onenote_elements)

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # completed
        # -------------------------------------------------------------------------------------------------------------------------------------------

        return self.onenote_elements

    # ===============================================================================================================================================
    # _get
    # ===============================================================================================================================================

    def _get( self, what ):
        elements = pd.DataFrame()
        run = True
        page_count = 0
        page_nb = 100

        if (what == 'notebook'): url='https://graph.microsoft.com/v1.0/me/onenote/notebooks'
        elif (what == 'group'): url='https://graph.microsoft.com/v1.0/me/onenote/sectionGroups'
        elif (what == 'section'): url='https://graph.microsoft.com/v1.0/me/onenote/sections'
        elif (what == 'page'): url='https://graph.microsoft.com/v1.0/me/onenote/pages'
        else: run = False

        while run:
            if (what == 'page'): 
                url += '?$top={}'.format(page_nb)
                if page_count > 0: url += '&$skip={}'.format(page_count)

            myprint( '> {}'.format( url) )

            onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + self.token} ).json()

            if 'error' in onenote_response:
                myprint( '[{0:<8}] error: {1} - {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
                run = False
            else:
                if 'value' not in onenote_response: onenote_objects = { 'value': [ onenote_response ] }
                else: onenote_objects = onenote_response

                onenote_elements = pd.json_normalize(onenote_objects['value'])
                onenote_elements['what'] = what
                onenote_elements['source'] = 'onenote'

                if len(elements) >0 : elements = pd.concat( [ elements, onenote_elements ], ignore_index=True )
                else: elements = onenote_elements.copy()

                if '@odata.nextLink' in onenote_response:
                    url = onenote_response['@odata.nextLink']
                else:
                    if (what == 'page'): 
                        if len(onenote_elements) == 0:
                            run = False
                        else:
                            page_count += len(onenote_elements)
                            url='https://graph.microsoft.com/v1.0/me/onenote/pages'
                    else:
                        run = False

                del onenote_elements

        elements.drop_duplicates( inplace=True )

        myprint( '{}: {} elements loaded'.format( what, len(elements) ) )

        return elements

    # ===============================================================================================================================================
    # _get_contents
    # ===============================================================================================================================================

    def _get_contents( self ):

        def _get_content( row ):
            myprint( '> [{}] {}'.format( int(row['index']), row['contentUrl'] ))
            
            response = requests.get( row['contentUrl'].replace( "content", "$value"), headers={'Authorization': 'Bearer ' + self.token} )
            try:
                iserror = ('error' in response.json())
            except:
                iserror = False

            if iserror:
                myprint( 'error: {} - {}'.format(response.json()['error']['code'], response.json()['error']['message']) )
                return nan
            else:
                soup = BeautifulSoup(response.text, features="html.parser")

                # absolute
                # --------
                # <body data-absolute-enabled="true" style="font-family:Calibri;font-size:11pt">
                # <div style="position:absolute;left:48px;top:115px;width:576px">

                for tag in soup.select("body[data-absolute-enabled]"):
                    del tag["data-absolute-enabled"]

                tags = soup.find_all( 'div', style=re.compile("position:absolute") )
                for tag in tags:
                    if (tag["style"].find("position:absolute") != -1):
                        del tag["style"]

                return str( soup.find("body").contents )

        if 'contentUrl' in self.onenote_elements.columns.to_list():
            myprint( '', line=True, title='GET CONTENTS')

            if 'content' not in self.onenote_elements.columns.to_list():
                self.onenote_elements['content'] = nan

            # process elements with contentUrl and no content
            cond = (~self.onenote_elements['contentUrl'].isna())
            cond &= (self.onenote_elements['content'].isna())
            nb = len(self.onenote_elements[cond])

            myprint( 'Recovering {} contents'. format(nb))

            self.onenote_elements['index'] = nan
            self.onenote_elements.loc[cond, 'index'] = range(nb, 0, -1)
            self.onenote_elements.loc[cond, 'content'] = self.onenote_elements[cond].apply(_get_content, axis='columns')
            self.onenote_elements.drop( columns=['index'], inplace=True)

            cond = (~self.onenote_elements['contentUrl'].isna())
            cond &= (self.onenote_elements['content'].isna())

            if len(self.onenote_elements[cond]) > 0: myprint( '.. missing {} contents out of {}'. format(len(self.onenote_elements[cond]), nb))

    # ===============================================================================================================================================
    # _get_resources
    # ===============================================================================================================================================

    def _get_resources( self ):

        def _get_resource( row ):

            soup = BeautifulSoup(row['content'], features="html.parser")

            resources = []

            empty = { 'type': None, 'name': None, 'url': None, 'filename': None, 'uptodate': False, 'path': None, 'date': None }
            empty['path'] = row['id'].split('!')
            empty['path'].reverse()
            if ('createdDateTime' in row) and (row['createdDateTime'] == row['createdDateTime']): 
                empty['date']  = row['createdDateTime']
            if ('lastModifiedDateTime' in row) and (row['lastModifiedDateTime'] == row['lastModifiedDateTime']): 
                empty['date']  = row['lastModifiedDateTime']
            
            # objects
            # -------
            # <object 
            # data="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-8a9f130df6d87945a8099be6b6d2be82!1-34CFFB16AE39C6B3!335924/$value" 
            # data-attachment="SEJOUR BURAIS 007-IND-M-22.pdf" 
            # type="application/pdf">
            # </object>

            for tag in soup.select("object[data-attachment]"): 
                resource = dict(empty)
                resource['name'] = re.search( r'^.*resources/(.*?)!', tag['data']).group(1) + '_' + tag['data-attachment']
                resource['name'] = tag['data-attachment']
                resource['url'] = tag['data']
                resource['type'] = 'object'

                resources += [ resource ]

            # images
            # ------
            # <img 
            # alt="bla bla bla"
            # data-fullres-src="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value" 
            # data-fullres-src-type="image/png" 
            # data-id="2f8fe6dc-10b8-c046-ba5b-c6ccf2c8884a" 
            # data-index="2" 
            # data-options="printout" 
            # data-src-type="image/png" 
            # height="842" 
            # src="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value" 
            # width="595"
            # />

            for tag in soup.select('img[src]'):
                del tag['alt']

                resource = dict(empty)
                resource['name'] = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                resource['url'] = tag['src']
                resource['type'] = 'image'

                resources += [ resource ]

                resource = dict(empty)
                resource['name'] = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                resource['url'] = tag['data-fullres-src']
                resource['type'] = 'fullres'

                resources += [ resource ]

                del tag['height']

                tag['width'] = 600

            if len(resources) > 0: return json.dumps( resources )
            else: return nan

        if 'content' in self.onenote_elements.columns.to_list():
            myprint( '', line=True, title='GET RESOURCES')

            if 'resources' not in self.onenote_elements.columns.to_list():
                self.onenote_elements['resources'] = nan

            cond = (~self.onenote_elements['content'].isna())
            cond &= (self.onenote_elements['resources'].isna())

            myprint( 'Parsing {} contents'. format(len(self.onenote_elements[cond])))

            self.onenote_elements.loc[cond, 'resources'] = self.onenote_elements[cond].apply(_get_resource, axis='columns')

            cond = (~self.onenote_elements['content'].isna())
            cond &= (self.onenote_elements['resources'].isna())

            if len(self.onenote_elements[cond]) > 0: myprint( '.. missing {} contents'. format(len(self.onenote_elements[cond])))

    # ===============================================================================================================================================
    # _load_resources
    # ===============================================================================================================================================

    def _load_resources( self ):

        myprint( '', line=True, title='LOAD RESOURCES')

        def _load_resource( resource ):

            if not resource['path']:
                myprint("[{}] no path for {}".format(resource['index'], resource['url']), prefix='  ...')
                return resource

            #out_file = os.path.join( os.path.dirname(__file__), 
            out_file = os.path.join( self.files_directory, 
                                     os.path.sep.join(resource['path']),
                                     resource['name'] )

            # test dates to check if load is mandatory
            date_page = resource['date']
            try:
                date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%SZ')

            try:
                date_file = dt.fromtimestamp(os.path.getmtime( out_file ))
            except:
                date_file = date_page

            if not os.path.isfile(out_file) or (date_file < date_page):

                myprint( '[{}] {}...'.format(resource['index'], resource['url'].replace('$value', 'content')), prefix='>')

                if not os.path.isfile(out_file): myprint( 'missing file', prefix='  ...' )
                elif (date_file < date_page): myprint( 'outdated file', prefix='  ...' )

                out_dir = os.path.dirname(out_file)

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                data =  requests.get( resource['url'].replace('$value', 'content'), headers={'Authorization': 'Bearer ' + self.token} )

                with open(out_file, 'wb') as fs:
                    fs.write(data.content) 

                myprint( '[{}] {}: {} bytes'.format( resource['index'], out_file, os.path.getsize(out_file) ), prefix='  ...' )
                
            resource['processed'] = True

            return resource

        cond = (~self.onenote_elements['resources'].isna())
        resources = self.onenote_elements[cond]['resources'].apply( lambda x: json.loads(x) )
        if len(resources) > 0: resources = resources.apply(pd.Series).stack().reset_index(drop=True).apply(pd.Series)

        nb = len(resources)
        myprint( 'Processing {} resources'. format(nb))
        resources['index'] = range(nb, 0, -1)        
        resources['processed'] = False       
            
        resources = resources.apply(_load_resource, axis='columns')

        myprint( '.. missing {} resources out of {}'. format(len(resources[resources['processed']==False]), nb))

    # ===============================================================================================================================================
    # _set_parents
    # ===============================================================================================================================================

    def _set_parents( self ):

        myprint( '', line=True, title='SET PARENT' )

        self.onenote_elements['parentId'] = nan
        self.onenote_elements.loc[~self.onenote_elements['parentNotebook.id'].isna(), 'parentId'] = self.onenote_elements['parentNotebook.id']
        self.onenote_elements.loc[~self.onenote_elements['parentSectionGroup.id'].isna(), 'parentId'] = self.onenote_elements['parentSectionGroup.id']
        self.onenote_elements.loc[~self.onenote_elements['parentSection.id'].isna(), 'parentId'] = self.onenote_elements['parentSection.id']

        self.onenote_elements['parentName'] = nan
        self.onenote_elements.loc[~self.onenote_elements['parentNotebook.displayName'].isna(), 'parentName'] = self.onenote_elements['parentNotebook.displayName']
        self.onenote_elements.loc[~self.onenote_elements['parentSectionGroup.displayName'].isna(), 'parentName'] = self.onenote_elements['parentSectionGroup.displayName']
        self.onenote_elements.loc[~self.onenote_elements['parentSection.displayName'].isna(), 'parentName'] = self.onenote_elements['parentSection.displayName']

    # ===============================================================================================================================================
    # _merge_elements
    # ===============================================================================================================================================

    def _merge_elements( self ):

        myprint( '', line=True, title='MERGE ELEMENTS' )

        def _find_page( row ):
            cond = (self.onenote_elements['what'].isin(['page']))
            cond &= (self.onenote_elements['Name'].isin([row['Name']]))
            cond &= (self.onenote_elements['parentId'].isin([row['id']]))
            found_pages = self.onenote_elements[cond]
            if len(found_pages) > 0:
                # it is a match
                for index, found_page in found_pages.iterrows():
                    if found_page['content'] == found_page['content']: 
                        if row['content'] != row['content']: row['content'] = found_page['content']
                        else: row['content'] += found_page['content']
                    if found_page['resources'] == found_page['resources']: 
                        if row['resources'] != row['resources']: row['resources'] = found_page['resources']
                        else: row['resources'] = json.dumps( json.loads(row['resources']) + json.loads(found_page['resources']) )
                row['found pages'] = found_pages['id'].to_list()
            return row

        self.onenote_elements['Name'] = self.onenote_elements['displayName']
        if 'title' in self.onenote_elements.columns.to_list():
            cond = self.onenote_elements['title'].isna()
            cond &= ~self.onenote_elements['Name'].isna()
            self.onenote_elements.loc[cond, 'Name'] = self.onenote_elements['title']

        cond = (~self.onenote_elements['what'].isin(['page']))
        self.onenote_elements['found pages'] = nan
        self.onenote_elements[cond] = self.onenote_elements[cond].apply(_find_page, axis='columns')

        cond = (~self.onenote_elements['found pages'].isna())
        myprint( '.. merged {} contents'. format(len(self.onenote_elements[cond])))

        pages = list(dict.fromkeys([x for xs in self.onenote_elements[cond]['found pages'].drop_duplicates().to_list() for x in xs]))

        cond = (~self.onenote_elements['id'].isin(pages))
        # self.onenote_elements = self.onenote_elements[cond]

        self.onenote_elements.drop( columns=['found pages', 'Name'], inplace=True)

    # ===============================================================================================================================================
    # _set_path
    # ===============================================================================================================================================

    def _set_path( self ):

        myprint( '', line=True, title='SET PATH' )

        def _path( row ):
            row['path'] = row['id'].split('!')
            row['path'].reverse()
            return row['path']

        self.onenote_elements['path'] = nan
        self.onenote_elements['path'] = self.onenote_elements.apply(_path, axis='columns')

    # ===============================================================================================================================================
    # _set_tags
    # ===============================================================================================================================================

    def _set_tags( self ):

        myprint( '', line=True, title='SET TAGS' )

        def _tags( row ):
            tags = []
            for id in row['path']:
                tmp = self.onenote_elements[self.onenote_elements['id'] == id]
                if len(tmp) > 0:
                    tags += [ tmp.iloc[0]['slug'] ]
            if len(tags) > 0: row['tags'] = tags
            else: row['tags'] = nan

            return row['tags']

        self.onenote_elements['tags'] = nan
        self.onenote_elements['tags'] = self.onenote_elements.apply(_tags, axis='columns')

    # ===============================================================================================================================================
    # _set_childs
    # ===============================================================================================================================================

    def _set_childs( self ):

        myprint( '', line=True, title='SET CHILDS' )

        self.onenote_elements['childs'] = nan

    # ===============================================================================================================================================
    # _normalize
    # ===============================================================================================================================================

    def _normalize( self ):
        myprint( '', line=True, title='NORMALIZE CONTENT' )

        # title

        if 'title' in self.onenote_elements.columns.to_list() and 'displayName' in self.onenote_elements.columns.to_list():
            cond = self.onenote_elements['title'].isna()
            cond &= ~self.onenote_elements['displayName'].isna()
            self.onenote_elements.loc[cond, 'title'] = self.onenote_elements['displayName']

        # drop columns

        to_drop = [
            r'Url',
            r'parent*.id',
            r'odata.context',
            r'parent*.self',
            r'displayName',
            r'createdByAppId',
            r'isShared',
            r'isDefault',
            r'userRole',
        ]
        drop_list = []

        for key in self.onenote_elements.columns.to_list():
            for val in to_drop:
                if re.search( val, key): 
                    drop_list += [ key ]
                    break

        # if 'contentUrl' in drop_list: drop_list.remove('contentUrl')

        myprint( 'Drop list: {}'.format(drop_list))

        # self.onenote_elements.drop( columns=drop_list, inplace=True )

