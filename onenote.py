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
import pprint

from datetime import datetime as dt
from bs4 import BeautifulSoup
from tabulate import tabulate

# pip3 install pandas
import pandas as pd

# pip3 install XlsxWriter
# pip3 install openpyxl
import xlsxwriter

# #################################################################################################################################
# GLOBAL VARIABLES
# #################################################################################################################################

DEBUG = True

nan = float('NaN')

def _print( text, line=False, prefix='', title='' ):
    if DEBUG:
        if line:
            if title == '':
                print( "-"*250 )
            else:
                print( "= {} {}".format(title, "="*(250-len(title)-3)) )
        if text != '':
            print('{}{}{}'.format(prefix, '' if prefix == '' else ' ', text))

class ONENOTE_ELEMENT:
    def __init__(self):
        self.id = None
        self.self = None
        self.parent = None
        self.order = None
        self.title = None
        self.created = None
        self.modified = None
        self.content = None
        self.tags = None
        self.path = None
        self.what = None
        self.slug = None
        self.author = None
        self.resources = None

    def dict(self):
        return vars()

# #################################################################################################################################
# INTERNAL FUNCTIONS
# #################################################################################################################################

def slugify( value ):

    # remove invalid chars (replaced by '-')
    value = re.sub( r'[<>:"/\\|?*^%]', '-', value, flags=re.IGNORECASE )

    # remove non-alphabetical/whitespace/'-' chars
    value = re.sub( r'[^\w\s-]', '', value, flags=re.IGNORECASE )

    # replace whitespace by '-'
    value = re.sub( r'[\s]+', '-', value, flags=re.IGNORECASE )

    # lower case
    value = value.lower()

    # reduce multiple whitespace to single whitespace
    value = re.sub( r'[\s]+', ' ', value, flags=re.IGNORECASE)

    # reduce multiple '-' to single '-'
    value = re.sub( r'[-]+', '-', value, flags=re.IGNORECASE)

    # strip
    value = value.strip()

    return value  

# ###################################################################################################################################################
# ONENOTE
# ###################################################################################################################################################

class ONENOTE:

    onenote_elements = pd.DataFrame()
    token = None
    directory = None
    files_directory = None

    # ===============================================================================================================================================
    # __init__
    # ===============================================================================================================================================

    def __init__( self, directory ): 
        self.directory = directory
        self.files_directory = os.path.join( self.directory, 'files' )

    # ===============================================================================================================================================
    # clear
    # ===============================================================================================================================================

    def clear(self):

        if os.path.isdir(self.files_directory):
            shutil.rmtree(self.files_directory)
        os.makedirs(self.files_directory)

    # ===============================================================================================================================================
    # get_all
    # ===============================================================================================================================================

    def get_all( self, token, filename=None ):

        self.token = token

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # load xls file
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self.onenote_elements = pd.DataFrame()
        if filename:
            if os.path.isfile( filename ):
                _print( '', line=True, title='LOAD EXCEL FILE')
                _print( 'Loading {} file'.format(filename))

                self.onenote_elements = pd.read_excel( filename, sheet_name='OneNote', engine='openpyxl')
            
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get elements
        # -------------------------------------------------------------------------------------------------------------------------------------------

        if len(self.onenote_elements) == 0:
            _print( '', line=True, title='GET ELEMENTS')

            self.onenote_elements = self._get('notebook')
            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('group') ], ignore_index=True )
            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('section') ], ignore_index=True )
            self.onenote_elements = pd.concat( [ self.onenote_elements, self._get('page') ], ignore_index=True )

            _print( 'Nb elements = {}'.format(len(self.onenote_elements)) )

            self._save_excel('elements')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get content
        # -------------------------------------------------------------------------------------------------------------------------------------------

        status = self._get_contents()

        self._save_excel('content')

        #if not status: return False

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        status = self._get_resources()

        self._save_excel('resources')

        #if not status: return False

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # expand data
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self._process_elements()
        
        self._save_excel('data')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # load resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self._load_resources()

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # drop columns
        # -------------------------------------------------------------------------------------------------------------------------------------------

        _print( '', line=True, title='DROP COLUMNS')

        to_drop = [
            r'Url',
            r'user.id',
            r'odata.context',
            r'parent*.self',
            r'title',
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

        if 'contentUrl' in drop_list: drop_list.remove('contentUrl')

        _print( 'Drop list: {}'.format(drop_list))

        self.onenote_elements.drop( columns=drop_list, inplace=True )

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # save excel
        # -------------------------------------------------------------------------------------------------------------------------------------------

        self._save_excel()

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # completed
        # -------------------------------------------------------------------------------------------------------------------------------------------

        return True

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

            _print( '> {}'.format( url) )

            onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + self.token} ).json()

            if 'error' in onenote_response:
                _print( '[{0:<8}] error: {1} - {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
                run = False
            else:
                if 'value' not in onenote_response: onenote_objects = { 'value': [ onenote_response ] }
                else: onenote_objects = onenote_response

                onenote_elements = pd.json_normalize(onenote_objects['value'])
                onenote_elements['what'] = what

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

        _print( '{}: {} elements loaded'.format( what, len(elements) ) )

        return elements

    # ===============================================================================================================================================
    # _get_contents
    # ===============================================================================================================================================

    def _get_contents( self ):

        def _get_content( row ):
            _print( '> [{}] {}'.format( int(row['index']), row['contentUrl'] ))
            
            response = requests.get( row['contentUrl'].replace( "content", "$value"), headers={'Authorization': 'Bearer ' + self.token} )
            try:
                iserror = ('error' in response.json())
            except:
                iserror = False

            if iserror:
                _print( 'error: {} - {}'.format(response.json()['error']['code'], response.json()['error']['message']) )
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

                return str( soup.find("body") )

        if 'contentUrl' in self.onenote_elements.columns.to_list():
            _print( '', line=True, title='GET CONTENTS')

            if 'content' not in self.onenote_elements.columns.to_list():
                self.onenote_elements['content'] = nan

            # process elements with contentUrl and no content
            cond = (~self.onenote_elements['contentUrl'].isna())
            cond &= (self.onenote_elements['content'].isna())
            nb = len(self.onenote_elements[cond])

            _print( 'Recovering {} contents'. format(nb))

            self.onenote_elements['index'] = nan
            self.onenote_elements.loc[cond, 'index'] = range(1, nb+1)
            self.onenote_elements.loc[cond, 'content'] = self.onenote_elements[cond].apply(_get_content, axis='columns')
            self.onenote_elements.drop( columns=['index'], inplace=True)

            cond = (~self.onenote_elements['contentUrl'].isna())
            cond &= (self.onenote_elements['content'].isna())

            if len(self.onenote_elements[cond]) > 0: _print( '.. missing {} contents'. format(len(self.onenote_elements[cond])))

            return (len(self.onenote_elements[cond]) == 0)

    # ===============================================================================================================================================
    # _get_resources
    # ===============================================================================================================================================

    def _get_resources( self ):

        def _get_resource( row ):

            soup = BeautifulSoup(row['content'], features="html.parser")

            resources = []
            empty = [{ 'type': [None], 'name': [None], 'url': [None], 'filename': [None], 'uptodate': [False], 'path': [None], 'date': [None] }]
            if 'path' in row: empty[-1]['path']  = row['path']
            if 'created' in row: empty[-1]['date']  = row['created']
            if 'modified' in row: empty[-1]['date']  = row['modified']

            # objects
            # -------
            # <object 
            # data="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-8a9f130df6d87945a8099be6b6d2be82!1-34CFFB16AE39C6B3!335924/$value" 
            # data-attachment="SEJOUR BURAIS 007-IND-M-22.pdf" 
            # type="application/pdf">
            # </object>

            for tag in soup.select("object[data-attachment]"): 
                resources += empty
                resources[-1]['name'] = re.search( r'^.*resources/(.*?)!', tag['data']).group(1) + '_' + tag['data-attachment']
                resources[-1]['name'] = tag['data-attachment']
                resources[-1]['url'] = tag['data']
                resources[-1]['type'] = 'object'

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

                resources += empty
                resources[-1]['name'] = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                resources[-1]['url'] = tag['src']
                resources[-1]['type'] = 'image'

                resources += empty
                resources[-1]['name'] = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                resources[-1]['url'] = tag['data-fullres-src']
                resources[-1]['type'] = 'fullres'

                del tag['height']

                tag['width'] = 600

            return resources

        if 'content' in self.onenote_elements.columns.to_list():
            _print( '', line=True, title='GET RESOURCES')

            if 'resources' not in self.onenote_elements.columns.to_list():
                self.onenote_elements['resources'] = nan

            cond = (~self.onenote_elements['content'].isna())
            cond &= (self.onenote_elements['resources'].isna())
            nb = len(self.onenote_elements[cond])

            _print( 'Parsing {} contents'. format(nb))

            self.onenote_elements.loc[cond, 'resources'] = self.onenote_elements[cond].apply(_get_resource, axis='columns')

            cond = (~self.onenote_elements['content'].isna())
            cond &= (self.onenote_elements['resources'].isna())

            if len(self.onenote_elements[cond]) > 0: _print( '.. missing {} contents'. format(len(self.onenote_elements[cond])))

            return (len(self.onenote_elements[cond]) == 0)

    # ===============================================================================================================================================
    # _load_resources
    # ===============================================================================================================================================

    def _load_resources( self ):

        def _load_resource( row ):
            _print( '{}...'.format(row['url']), prefix='>>')

            out_file = os.path.join( os.path.dirname(__file__), 'onenote', os.path.sep.join(element['path']), row['name'] )

            # test dates to check if load is mandatory
            date_page = element['modified'] if 'modified' in element else element['created']
            date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%SZ')
            try:
                date_file = dt.fromtimestamp(os.path.getmtime( out_file ))
            except:
                date_file = date_page

            if not os.path.isfile(out_file) or (date_file < date_page):

                if not os.path.isfile(out_file): _print( 'missing file', prefix='  ...' )
                elif (date_file < date_page): _print( 'outdated file', prefix='  ...' )

                out_dir = os.path.dirname(out_file)

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                data =  requests.get( resource['url'].replace('$value', 'content'), headers={'Authorization': 'Bearer ' + self.token} )

                with open(out_file, 'wb') as fs:
                    fs.write(data.content) 

            _print( '{}: {} bytes'.format( out_file, os.path.getsize(out_file) ), prefix='  ...' )

        if 'contentUrl' in self.onenote_elements.columns.to_list():
            _print( '', line=True, title='LOAD RESOURCES')
            
    # ===============================================================================================================================================
    # _process_elements
    # ===============================================================================================================================================

    def _process_elements( self ):
        _print( '', line=True, title='TWEAK CONTENT' )

        if 'title' in self.onenote_elements.columns.to_list() and 'displayName' in self.onenote_elements.columns.to_list():
            cond = ~self.onenote_elements['title'].isna()
            cond &= self.onenote_elements['displayName'].isna()
            self.onenote_elements.loc[cond, 'displayName'] = self.onenote_elements['title']

        _print( '', line=True, title='SET PARENT' )

        self.onenote_elements['parent'] = nan
        self.onenote_elements.loc[~self.onenote_elements['parentNotebook.id'].isna(), 'parent'] = self.onenote_elements['parentNotebook.id']
        self.onenote_elements.loc[~self.onenote_elements['parentSectionGroup.id'].isna(), 'parent'] = self.onenote_elements['parentSectionGroup.id']
        self.onenote_elements.loc[~self.onenote_elements['parentSection.id'].isna(), 'parent'] = self.onenote_elements['parentSection.id']
        
        _print( '', line=True, title='MERGE ELEMENTS' )

        self.onenote_elements['delete'] = False
        cond = (~self.onenote_elements['what'].isin(['page']))
        for i, row in self.onenote_elements[cond].iterrows():
            # find a page with same title
            pass

        self.onenote_elements.drop( columns=['delete'], inplace=True)

        _print( '', line=True, title='SET TAGS' )

        _print( '', line=True, title='SET PATH' )

        _print( '', line=True, title='SET CHILDS' )

    # ===============================================================================================================================================
    # _save_excel
    # ===============================================================================================================================================

    def _save_excel( self, type='' ):

        _print( '', line=True, title='SAVE EXCEL')

        try:
            name = 'onenote_{}{}{}.xlsx'.format( '' if type=='' else type, '' if type=='' else '_', dt.now().strftime("%d_%b_%Y_%H_%M_%S").lower())
            out_file = os.path.join( os.path.dirname(__file__), 'onenote', name )
            out_dir = os.path.dirname(out_file)
            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            writer = pd.ExcelWriter(out_file, engine='xlsxwriter')
            workbook  = writer.book
            self.onenote_elements.to_excel( writer, sheet_name='OneNote', index=False, na_rep='')
            writer.close()

            _print( "{} rows saved in file {}.".format(len(self.onenote_elements), out_file) )        

        except:
            _print( "Something went wrong with file {}.".format(out_file) )        

def onenote( token, url ):

    # get from OneNote

    _print( '', line=True, title='ONENOTE{}'.format(': ' if url != '' else '', url.upper() if url != '' else ''))
    elements = onenote_process( token=token, what='notebook', url=url )

    print( tabulate( elements, headers='keys', tablefmt='fancy_grid', showindex=False, floatfmt=".1f" ))

    return elements

    # reorder elements

    _print( '', line=True, title='REORDER ELEMENTS')

    # merge elements

    _print( '', line=True, title='MERGE ELEMENTS')
    for element in reversed(elements):
        # is there a child with same title
        for item in reversed(elements):
            if ('parent' in item) and (item['parent'] == element['id']) and (item['title'] == element['title']):
                _print('merge {} {} in {}'.format(item['title'], item['what'], element['what']), prefix='>')
                if 'content' in item:
                    if 'content' in element: element['content'] += item['content']
                    else: element['content'] = item['content']
                if 'resources' in item:
                    if 'resources' in element: element['resources'] += item['resources']
                    else: element['resources'] = item['resources']
                if item['what'] in ['page']: elements.remove(item)
                break

    # tags and path

    _print( '', line=True, title='TAGS AND PATHS')
    for element in elements:

        element['tags'] =  []
        element['path'] =  []
        for item in elements:
            if ('parent' in element) and (item['id'] == element['parent']):
                if 'tags' in item: element['tags'] += item['tags']
                if 'path' in item: element['path'] += item['path']
                if (item['what'] in ['notebook', 'group']):
                    element['tags'] += [ item['slug'] ]
                element['path'] += [ item['slug'] ]
                element['path'] += [ element['slug'] ]
                break

    # resources

    _print( '', line=True, title='RESOURCES')
    for element in elements:
        onenote_resources( token, element )

    # dump as json

    out_file = os.path.join( os.path.dirname(__file__), 'onenote', 'onenote.json' )
    out_dir = os.path.dirname(out_file)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    try:
        out_fp = open(out_file, "w")
        json.dump( elements, out_fp, indent=2 )
        out_fp.close()
    except:
        pass

    _print( '', line=True, title='ELEMENTS')
    for element in elements:
        tmp = dict(element)
        if 'content' in tmp: tmp['content'] = "scrubbed content"
        _print( '{}'.format(pprint.pformat( tmp )))
        del tmp    

    _print( '', line=True, title='STRUCTURE')
    for element in elements:
        level = len(element['path']) if 'path' in element else 0
        _print( '{}{} [{}]{}{} [{}] [{}]'.format( "    "*level, element['title'], 
                                        element['what'], 
                                        ' by ' if 'author' in element else '', 
                                        element['author'] if 'author' in element else '',
                                        element['order'] if 'order' in element else '-',
                                        element['modified'] if 'modified' in element else element['created'],
                                      ))

    return elements

# #################################################################################################################################
# ONENOTE CLEAR
# #################################################################################################################################

def onenote_clear():

    out_dir = os.path.join( os.path.dirname(__file__), 'onenote', 'files' )
    shutil.rmtree(out_dir)
    os.makedirs(out_dir)

# #################################################################################################################################
# ONENOTE CATALOG
# #################################################################################################################################

def onenote_catalog( token ):

    onenote_response = requests.get( 'https://graph.microsoft.com/v1.0/me/onenote/notebooks', 
                                     headers={'Authorization': 'Bearer ' + token} ).json()

    if 'value' in onenote_response: onenote_objects = onenote_response['value']
    else: onenote_objects = [ onenote_response ]

    catalog=[]
    for onenote_object in onenote_objects:
        catalog += [ {'title': onenote_object['displayName'], 'self': onenote_object['self']}]        

    return catalog

# #################################################################################################################################
# ONENOTE RESOURCES
# #################################################################################################################################

def onenote_resources( token, element ):

    if 'resources' in element:
        for resource in element['resources']:
            _print( '{}...'.format(resource['url']), prefix='>>')

            out_file = os.path.join( os.path.dirname(__file__), 'onenote', os.path.sep.join(element['path']), resource['name'] )

            # test dates to check if load is mandatory
            date_page = element['modified'] if 'modified' in element else element['created']
            date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%SZ')
            try:
                date_file = dt.fromtimestamp(os.path.getmtime( out_file ))
            except:
                date_file = date_page

            if not os.path.isfile(out_file) or (date_file < date_page):

                if not os.path.isfile(out_file): _print( 'missing file', prefix='  ...' )
                elif (date_file < date_page): _print( 'outdated file', prefix='  ...' )

                out_dir = os.path.dirname(out_file)

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                data =  requests.get( resource['url'].replace('$value', 'content'), headers={'Authorization': 'Bearer ' + token} )

                with open(out_file, 'wb') as fs:
                    fs.write(data.content) 

                resource['data'] = out_file

            _print( '{}: {} bytes'.format( out_file, os.path.getsize(out_file) ), prefix='  ...' )
    
#################################################################################################################################
# ONENOTE PROCESS
# #################################################################################################################################

def onenote_process( token, what, url ):
    run = True
    elements = pd.DataFrame()

    if (url == '') and (what == 'notebook'): 
        url='https://graph.microsoft.com/v1.0/me/onenote/notebooks'

    while run:
        onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} ).json()

        if 'error' in onenote_response:
            print( '[{0:<8}] error: {1} - {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
            run = False
        else:
            if 'value' in onenote_response: onenote_objects = onenote_response['value']
            else: onenote_objects = [ onenote_response ]

            for onenote_object in onenote_objects:
                if 'contentUrl' in onenote_object:
                    # onenote_object['content'] = onenote_process( token, 'content', onenote_object["self"] + "/$value" )
                    onenote_object['content'] = requests.get( onenote_object["self"] + "/$value", headers={'Authorization': 'Bearer ' + token} )

                element = onenote_element(onenote_object, what)

                elements = elements.append( vars(element), ignore_index=True )

                if 'sectionGroupsUrl' in onenote_object:
                    elements = elements.append( onenote_process( token, 'group', onenote_object["sectionGroupsUrl"] + '?$orderby=lastModifiedDateTime desc' ), ignore_index=True )

                if 'sectionsUrl' in onenote_object:
                    elements = elements.append( onenote_process( token, 'section', onenote_object["sectionsUrl"] + '?$orderby=lastModifiedDateTime desc' ), ignore_index=True )

                if 'pagesUrl' in onenote_object:
                    elements = elements.append( onenote_process( token, 'page', onenote_object["pagesUrl"] + '?pagelevel=true&orderby=order' ), ignore_index=True )

            if '@odata.nextLink' in onenote_response:
                url = onenote_response['@odata.nextLink']
            else:
                run = False

    return elements

# #################################################################################################################################
# ONENOTE ELEMENT
# #################################################################################################################################

def onenote_element( element, what ):
    content = ONENOTE_ELEMENT()

    content.what = what

    if 'id' in element: 
        content.id = element['id']

    if 'self' in element: 
        content.self = element['self']

    if 'order' in element: 
        content.order = element['order']

    if 'parentNotebook' in element: 
        if element['parentNotebook'] and 'id' in element['parentNotebook']: 
            content.parent = element['parentNotebook']['id']

    if 'parentSectionGroup' in element: 
        if element['parentSectionGroup'] and 'id' in element['parentSectionGroup']: 
            content.parent = element['parentSectionGroup']['id']

    if 'parentSection' in element: 
        if element['parentSection'] and 'id' in element['parentSection']: 
            content.parent = element['parentSection']['id']

    if 'displayName' in element: content.title = element["displayName"]
    elif 'title' in element: content.title = element["title"]

    if content.title: content.slug = slugify( content.title )
    else: content.slug = slugify( content.id )

    if 'createdDateTime' in element: content.created = element["createdDateTime"]
    if 'lastModifiedDateTime' in element: content.modified = element["lastModifiedDateTime"]

    if 'createdBy' in element and 'user' in element['createdBy'] and 'displayName' in element['createdBy']['user']: 
        content.author = element['createdBy']['user']['displayName']

    if 'lastModifiedBy' in element and 'user' in element['lastModifiedBy'] and 'displayName' in element['lastModifiedBy']['user']: 
        content.author = element['lastModifiedBy']['user']['displayName']

    resources = []

    if 'content' in element: 

        soup = BeautifulSoup(element['content'].text, features="html.parser")

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

        content.resources = []

        # objects
        # -------
        # <object 
        # data="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-8a9f130df6d87945a8099be6b6d2be82!1-34CFFB16AE39C6B3!335924/$value" 
        # data-attachment="SEJOUR BURAIS 007-IND-M-22.pdf" 
        # type="application/pdf">
        # </object>

        for tag in soup.select("object[data-attachment]"): 
            name = re.search( r'^.*resources/(.*?)!', tag['data']).group(1) + '_' + tag['data-attachment']
            name = tag['data-attachment']
            content.resources += [ { 'name': name, 'url': tag['data'], 'data': None, 'type': 'object' } ]

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

            name = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
            content.resources += [ { 'name': name, 'url': tag['src'], 'data': None, 'type': 'image' } ]

            name = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
            content.resources += [ { 'name': name, 'url': tag['data-fullres-src'], 'data': None, 'type': 'fullres' } ]

            del tag['height']

            tag['width'] = 600

        content.content = str( soup.find("body") )

        if len( content.resources ) > 0: 
            # remove duplicates
            pass
        else:
            content.resources = None

    _print( '[{0:<8}] {1}'.format(content['what'], content['title']), line=True )
    _print( '{}'.format(pprint.pformat( element )), line=True )
    _print( '{}'.format(pprint.pformat( vars(content)) ), line=True )

    return content