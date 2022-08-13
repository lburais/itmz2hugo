# ###################################################################################################################################################
# Filename:     onenote.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# Graph Explorer:
#   https://developer.microsoft.com/fr-fr/graph/graph-explorer
#
# ###################################################################################################################################################
# todo
#
#   1. clear: encoding for resource.filename vs. os.walk
#   2. recombine object+image+link (shared from iPad)
#   3. recombine image+object+link (shared from Mac)
#
# ###################################################################################################################################################

import json
import requests
import re
import os
import sys
import shutil

from datetime import datetime as dt
from bs4 import BeautifulSoup

# pip3 install pandas
import pandas as pd

from mytools import *

ME = 'https://graph.microsoft.com/v1.0/users/laurent@burais.fr/onenote'

EXCEPT_HANDLING = False

# ###################################################################################################################################################
# CATALOG
# ###################################################################################################################################################

def catalog( token ): 

    return pd.concat( [ pd.DataFrame( {'source': ['onenote'], 'title': ['All Notebooks'], 'onenote_self': [None] } ),
                        read( token=token, get='catalog' )
                      ], ignore_index = True )

# ###################################################################################################################################################
# READ
# ###################################################################################################################################################

def read( token, notebookUrl=None, directory=None, get='notebooks', elements=empty_elements() ): 

    read_elements = elements.copy()
    if directory: _files_directory = os.path.join( directory, 'onenote' )

    try:

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # process url
        # -------------------------------------------------------------------------------------------------------------------------------------------
        #                       https://graph.microsoft.com/v1.0/me/onenote/notebooks
        #                       https://graph.microsoft.com/v1.0/me/onenote/notebooks/{id}
        #                       https://graph.microsoft.com/v1.0/me/onenote/sectionGroups
        # sectionGroupsUrl :    https://graph.microsoft.com/v1.0/me/onenote/notebooks/{id}/sectionGroups
        # sectionGroupsUrl :    https://graph.microsoft.com/v1.0/me/onenote/sectionGroups/{id}/sectionGroups
        #                       https://graph.microsoft.com/v1.0/me/onenote/sections
        # sectionsUrl:          https://graph.microsoft.com/v1.0/me/onenote/notebooks/{id}/sections
        # sectionsUrl:          https://graph.microsoft.com/v1.0/me/onenote/sectionGroups/{id}/sections
        # pagesUrl:             https://graph.microsoft.com/v1.0/me/onenote/sections/{id}/pages
        # pagesUrl:             https://graph.microsoft.com/v1.0/me/onenote/pages
        # contentUrl:           https://graph.microsoft.com/v1.0/me/onenote/pages/{id}/content
        # resourceUrl:          https://graph.microsoft.com/v1.0/me/onenote/resources/{id}/content

        def process_url( url ):
            nonlocal read_elements

            try:

                get_elements = empty_elements()
                get_url = url

                page_count = 0
                page_nb = 100

                # what: 'notebooks', 'sectionGroups', 'sections', 'pages', 'content', 'resources
                what = re.search( r'^.*/onenote/(.*)$', url ).group(1).split("/")
                if what[-1] in ['notebooks', 'sectionGroups', 'sections', 'pages', 'content', 'resources']:
                    if what[0] in ['resources']: what = what[0]
                    else: what = what[-1]
                else: what = what[0]

                # id: a-bbb!c-ddd!eee or c-ddd!eee
                identifier = None            
                identifier = re.search( r'^.*/(\d-[\w]+!\d-[\w]+![\w]+).*', url )
                if not identifier: identifier = re.search( r'^.*/(\d-[\w]+![\w]+).*', url )
                if identifier: identifier = identifier.group(1)

                # to get page hierarchy
                if what in ['pages']: get_url += '?pagelevel=true'

                while get_url:
                    myprint( '[{} - {}] {}'.format(what, identifier, get_url), prefix='>' )

                    try:
                        onenote_response = requests.get( get_url, headers={'Authorization': 'Bearer ' + token} )

                        if onenote_response.status_code != requests.codes.ok:
                            # exit because of error
                            myprint( '[{}] {} - {}'.format( onenote_response.status_code, 
                                                            onenote_response.json()['error']['code'], 
                                                            onenote_response.json()['error']['message']) )
                            break
                        else:
                            # .......................................................................................................................
                            # ONENOTE JSON NOTEBOOK | SECTIONGROUP | SECTION | PAGE
                            # .......................................................................................................................

                            if onenote_response.headers['content-type'].split(';')[0] == 'application/json':
                                if 'value' not in onenote_response.json(): onenote_objects = { 'value': [ onenote_response.json() ] }
                                else: onenote_objects = onenote_response.json()

                                onenote_objects = pd.json_normalize(onenote_objects['value'])

                                onenote_objects['date'] = nan
                                if 'lastModifiedDateTime' in onenote_objects:
                                    onenote_objects['date'] = onenote_objects['lastModifiedDateTime']
                                if 'createdDateTime' in onenote_objects:
                                     onenote_objects.loc[onenote_objects['date'].isna(), 'date'] = onenote_objects['createdDateTime']

                                if 'parentNotebook.id' in onenote_objects: onenote_objects['notebook'] = onenote_objects['parentNotebook.id']
                                if what in ['notebooks']: onenote_objects['notebook'] = onenote_objects['id']

                                onenote_objects['parent'] = nan
                                for context in ['parentNotebook@odata.context', 'parentSectionGroup@odata.context', 'parentSection@odata.context']:
                                    if context in onenote_objects:
                                        cond = onenote_objects['parent'].isna()
                                        onenote_objects.loc[cond, 'parent'] = onenote_objects[cond][context]

                                # .../sectionGroups('0-34CFFB16AE39C6B3%21335814')/sections('0-34CFFB16AE39C6B3%21335818')/parentNotebook/$entity
                                cond = ~onenote_objects['parent'].isna()
                                pattern = r'^.*/onenote/.*\(\'(.*?)\'\)/.*\(\'(.*?)\'\)/.*'

                                onenote_objects.loc[cond, 'parent'] = \
                                    onenote_objects[cond]['parent'].apply( lambda x: re.search( pattern, x).group(1).replace('%21','!') )

                                if ('@odata.nextLink' in onenote_response.json() or page_count > 0) and (len(onenote_objects) > 0):
                                    # paginate
                                    get_url = url
                                    get_url += '?{}'.format('pagelevel=true&' if what in ['pages'] else '')
                                    get_url += '$top={}'.format(page_nb)
                                    get_url += '&$skip={}'.format(page_count)
                                else:
                                    get_url = None

                                col_list = {}
                                for col in onenote_objects.columns.to_list():
                                    col_list[col] = 'onenote_{}'.format(col)
                                onenote_objects.rename( columns=col_list, inplace=True )

                            # .......................................................................................................................
                            # ONENOTE TEXT CONTENT
                            # .......................................................................................................................

                            elif onenote_response.headers['content-type'].split(';')[0] == 'text/html':
                                # content
                                identifier = re.search( r'^.*pages/(.*?)/content.*', get_url).group(1) if what == 'content' else None
                                cond = read_elements['onenote_what'].isin(['pages'])
                                cond &= read_elements['onenote_contentUrl'] == url
                                tmp = read_elements[cond]  

                                try:
                                    tmp_date = dt.strptime(tmp.iloc[0]['onenote_date'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                except:
                                    try:
                                        tmp_date = dt.strptime(tmp.iloc[0]['onenote_date'], '%Y-%m-%dT%H:%M:%SZ')
                                    except:
                                        tmp_date = nan

                                tmp_parent = tmp.iloc[0]['onenote_id'] if len(tmp) > 0 else nan
                                tmp_notebook = tmp.iloc[0]['onenote_notebook'] if len(tmp) > 0 else nan
                                tmp_created = tmp.iloc[0]['onenote_createdDateTime'] if len(tmp) > 0 else nan
                                tmp_modified = tmp.iloc[0]['onenote_lastModifiedDateTime'] if len(tmp) > 0 else nan
                                del tmp

                                onenote_objects = pd.DataFrame( { 'onenote_id': ['content' + identifier], 
                                                                  'onenote_self': [url], 
                                                                  'onenote_parent': [tmp_parent], 
                                                                  'onenote_notebook': [tmp_notebook], 
                                                                  'onenote_createdDateTime': [tmp_created], 
                                                                  'onenote_lastModifiedDateTime': [tmp_modified], 
                                                                  'onenote_date': [tmp_date], 
                                                                  'onenote_content': [onenote_response.text]} )

                                # add resources objects
                                onenote_resources = process_resources( onenote_response.text )

                                if len(onenote_resources) > 0:
                                    myprint( 'adding {} resources'.format(len(onenote_resources)), prefix='...' )
                                    onenote_resources['onenote_what'] = 'resources'
                                    onenote_resources['onenote_parent'] = 'content' + identifier
                                    onenote_resources['onenote_createdDateTime'] = tmp_created
                                    onenote_resources['onenote_lastModifiedDateTime'] = tmp_modified
                                    onenote_resources['onenote_date'] = tmp_date
                                    onenote_resources['onenote_notebook'] = tmp_notebook
                                    onenote_resources['onenote_self'] = onenote_resources['onenote_resourceUrl']
                                    onenote_objects = pd.concat( [ onenote_objects, onenote_resources ], ignore_index = True ) 

                                get_url = None

                            # .......................................................................................................................
                            # ONENOTE BINARY RESOURCE ELEMENT
                            # .......................................................................................................................

                            elif onenote_response.headers['content-type'].split(';')[0] == 'application/octet-stream':
                                # resource
                                def _load_resource( row ):
                                    try:
                                        if not os.path.isdir(os.path.dirname(row['onenote_file_name'])): 
                                            os.makedirs(os.path.dirname(row['onenote_file_name']))

                                        with open(row['onenote_file_name'], 'wb') as fs:
                                            fs.write(onenote_response.content) 

                                        myprint( '{}: {} bytes'.format( row['onenote_file_name'], 
                                                                        os.path.getsize(row['onenote_file_name']) 
                                                                      ), prefix='...' )

                                        row['onenote_file_size'] = os.path.getsize(row['onenote_file_name'])
                                        row['onenote_file_date'] = dt.fromtimestamp(os.path.getmtime(row['onenote_file_name']))
                                    except:
                                        exc_type, exc_obj, exc_tb = sys.exc_info()
                                        myprint( 'error [{} - {}] at line {}'.format(exc_type, exc_obj, exc_tb.tb_lineno), prefix='###')
                                    return row

                                cond = read_elements['onenote_what'].isin(['resources'])
                                cond &= read_elements['onenote_resourceUrl'] == url
                                cond &= ~read_elements['onenote_file_name'].isna()
                                onenote_objects = read_elements[cond].copy()
                                #read_elements = read_elements[~cond]
                                read_elements.loc[~cond, 'onenote_what'] = 'delete'

                                myprint( 'loading {} resources'.format(len(onenote_objects)), prefix='...' )
                                onenote_objects = onenote_objects.apply( _load_resource, axis='columns' )

                                get_url = None

                            # .......................................................................................................................
                            # ELSE
                            # .......................................................................................................................

                            else:
                                # exit because unknown content-type 
                                myprint( onenote_response.headers )
                                break

                            # .......................................................................................................................
                            # ONENOTE ELEMENTS
                            # .......................................................................................................................

                            if 'onenote_what' in onenote_objects: onenote_objects.loc[onenote_objects['onenote_what'].isna(), 'onenote_what'] = what
                            else: onenote_objects['onenote_what'] = what

                            if len(get_elements) >0 : get_elements = pd.concat( [ get_elements, onenote_objects ], ignore_index=True )
                            else: get_elements = onenote_objects.copy()

                            page_count += len(onenote_objects)

                            del onenote_objects

                    except:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        myprint("Get error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='###')
                        break

                get_elements.drop_duplicates( inplace=True )

                myprint( '{} {} loaded'.format(len(get_elements), what), prefix='...' )

                if len(get_elements) > 0:

                    # recursive
                    if identifier:
                        for u in ['onenote_sectionGroupsUrl', 'onenote_sectionsUrl', 'onenote_pagesUrl']:
                            if u in get_elements:
                                get_elements[(~get_elements[u].isna())][u].apply( lambda x: process_url(x) )

                    # concat 
                    if len(read_elements) > 0: read_elements = pd.concat([read_elements, get_elements], ignore_index=True)
                    else: read_elements = get_elements.copy()

            except:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                myprint("Url error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='###')
                if not EXCEPT_HANDLING: raise

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # process resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def process_resources( content ):

            resources_elements = pd.DataFrame()

            soup = BeautifulSoup(content, features="html.parser")

            # objects
            # -------
            # <object 
            # data="".../resources/0-8a9f130df6d87945a8099be6b6d2be82!1-34CFFB16AE39C6B3!335924/$value"
            # data-attachment="SEJOUR BURAIS 007-IND-M-22.pdf" 
            # type="application/pdf">
            # </object>

            for tag in soup.select("object[data-attachment]"): 
                identifier = re.search( r'^.*resources/(.*?)/\$value', tag['data']).group(1)
                filename = identifier.split('!')
                filename.reverse()
                filename = os.path.join( _files_directory, os.path.sep.join(filename), tag['data-attachment'] )
                resources_elements = pd.concat( [ resources_elements,
                                                  pd.DataFrame( { 'onenote_resource_type': ['object'],
                                                                  'onenote_title': [tag['data-attachment']],
                                                                  'onenote_id': [identifier],
                                                                  'onenote_resourceUrl': [tag['data'].replace('$value', 'content')],
                                                                  'onenote_file_name': [filename],
                                                                } ),
                                                ], ignore_index = True ) 

            # filename:

            # images
            # ------
            # <img 
            # alt="bla bla bla"
            # data-fullres-src=".../resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value
            # data-fullres-src-type="image/png" 
            # data-id="2f8fe6dc-10b8-c046-ba5b-c6ccf2c8884a" 
            # data-index="2" 
            # data-options="printout" 
            # data-src-type="image/png" 
            # height="842" 
            # src=".../resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value 
            # width="595"
            # />
            # .../resources/0-49c6674e67cc1c063307788cddf638db!1-34CFFB16AE39C6B3!335729/$value

            for tag in soup.select('img[src]'):
                name = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                identifier = re.search( r'^.*resources/(.*?)/\$value', tag['src']).group(1)
                filename = identifier.split('!')
                filename.reverse()
                filename = os.path.join( _files_directory, os.path.sep.join(filename), name )
                resources_elements = pd.concat( [ resources_elements,
                                                  pd.DataFrame( { 'onenote_resource_type': ['image'],
                                                                  'onenote_title': [name],
                                                                  'onenote_id': [identifier],
                                                                  'onenote_resourceUrl': [tag['src'].replace('$value', 'content')],
                                                                  'onenote_file_name': [filename],
                                                                } ),
                                                ], ignore_index = True ) 

            for tag in soup.select('img[data-fullres-src]'):
                name = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
                identifier = re.search( r'^.*resources/(.*?)/\$value', tag['data-fullres-src']).group(1)
                filename = identifier.split('!')
                filename.reverse()
                filename = os.path.join( _files_directory, os.path.sep.join(filename), name )
                resources_elements = pd.concat( [ resources_elements,
                                                  pd.DataFrame( { 'onenote_resource_type': ['fullres'],
                                                                  'onenote_title': [name],
                                                                  'onenote_id': [identifier],
                                                                  'onenote_resourceUrl': [tag['data-fullres-src'].replace('$value', 'content')],
                                                                  'onenote_file_name': [filename],
                                                                } ),
                                                ], ignore_index = True ) 

            return resources_elements

        # -------------------------------------------------------------------------------------------------------------------------------------------

        myprint( '', line=True, title='GET ONENOTE {}'.format(get.upper()))

        if get in ['catalog']:
            # catalog
            process_url(ME + '/notebooks')

        else:
            if notebookUrl and (notebookUrl not in ['nan', 'None']):
                # one notebook
                process_url(notebookUrl)

            else:
                # all notebook
                process_url(ME + '/notebooks')

                # sectionGroups
                process_url(ME + '/sectionGroups')

                # sections
                process_url(ME + '/sections')

                # pages
                process_url(ME + '/pages')


            if get in ['notebooks', 'content']:
                # content
                if 'onenote_contentUrl' in read_elements:
                    read_elements[(~read_elements['onenote_contentUrl'].isna())]['onenote_contentUrl'].apply( lambda x: process_url(x) )

            if get in ['notebooks', 'resources']:
                # resources
                if 'onenote_resourceUrl' in read_elements:
                    # check file_name
                    read_elements['onenote_file_ok'] = True
                    read_elements['onenote_file_date'] = nan

                    cond = (~read_elements['onenote_file_name'].isna())

                    # file does not exist
                    cond = ~read_elements['onenote_file_name'].isna()
                    read_elements.loc[cond, 'onenote_file_ok'] = read_elements[cond]['onenote_file_name'].apply( lambda x: os.path.isfile(x) )

                    # get file mtime
                    cond = ~read_elements['onenote_file_name'].isna() & read_elements['onenote_file_ok']
                    read_elements.loc[cond, 'onenote_file_date'] = \
                        read_elements[cond]['onenote_file_name'].apply( lambda x: dt.fromtimestamp(os.path.getmtime(x)) )

                    # no page date to compare to
                    cond = ~read_elements['onenote_file_name'].isna() & read_elements['onenote_file_ok'] & read_elements['onenote_date'].isna()
                    read_elements.loc[cond, 'onenote_file_ok'] = False

                    # file older than page date
                    cond = ~read_elements['onenote_file_name'].isna() & read_elements['onenote_file_ok']
                    read_elements.loc[cond, 'onenote_file_ok'] = \
                        read_elements[cond].apply( lambda x: (x['onenote_file_date'] > x['onenote_date']), axis = 'columns' )

                    cond = ~read_elements['onenote_file_ok']
                    myprint( read_elements[cond][['onenote_file_name', 'onenote_file_ok', 'onenote_date', 'onenote_file_date' ]])

                    cond = (~read_elements['onenote_resourceUrl'].isna())
                    cond &= (~read_elements['onenote_file_ok'])
                    
                    myprint( 'loading {} resources'.format(len(read_elements[cond])), prefix='...' )

                    read_elements[cond]['onenote_resourceUrl'].apply( lambda x: process_url(x) )

        # -------------------------------------------------------------------------------------------------------------------------------------------

        try:
            # normalized 'source','what','type','id','level','title','created','modified','authors','slug','top','parent','childs','body'

            myprint( '', line=True, title='NORMALIZE ONENOTE')

            # source
            read_elements['source'] = 'onenote'

            # what
            read_elements['what'] = read_elements['onenote_what'] if 'onenote_what' in read_elements else nan

            # type
            read_elements['type'] = 'post' 
            read_elements.loc[read_elements['what'].isin(['pages']), 'type'] = 'page' 

            # id
            read_elements['id'] = read_elements['onenote_id'] if 'onenote_id' in read_elements else nan

            # title
            read_elements['title'] = nan
            if 'onenote_title' in read_elements: 
                read_elements['title'] = read_elements['onenote_title']
            if 'onenote_displayName' in read_elements: 
                cond = read_elements['title'].isna()
                read_elements.loc[cond, 'title'] = read_elements[cond]['onenote_displayName']

            # dates
            read_elements['created'] = read_elements['onenote_createdDateTime'] if 'onenote_createdDateTime' in read_elements else nan
            read_elements['modified'] = read_elements['onenote_lastModifiedDateTime'] if 'onenote_lastModifiedDateTime' in read_elements else nan

            # authors
            read_elements['authors'] = nan
            for col in ['onenote_createdBy.user.displayName', 'onenote_lastModifiedBy.user.displayName']:
                if col in read_elements:
                    cond = ~read_elements[col].isna()
                    read_elements.loc[cond, 'authors'] = read_elements[cond][col]

            # slug
            read_elements['slug'] = read_elements['onenote_id'].apply( lambda x: slugify(x) )

            # top
            if 'onenote_notebook' in read_elements: read_elements['top'] = read_elements['onenote_notebook']

            # parent
            read_elements['parent'] = read_elements['onenote_parent'] if 'onenote_parent' in read_elements else nan

            # childs
            def _set_childs( element ):
                cond = (read_elements['parent'] == element['id'] )
                cond &= (~read_elements['what'].isin(['content', 'resources']) )
                childs = read_elements[cond]['id']
                if len(childs) > 0: return childs.to_list()
                else: return []
            read_elements['childs'] = read_elements.apply( _set_childs, axis='columns' )

            # number
            def _set_number( row ):
                cond = read_elements['parent'] == row['id']
                if len(read_elements[cond]) > 0:
                    read_elements.loc[cond, 'number'] = [(row['number'] + '.' + str(x)) for x in list(range( 1, len(read_elements[cond]) +1 ))]
                    read_elements[cond].apply(_set_number, axis='columns')

            read_elements['number'] = nan
            if get not in ['catalog']:
                cond = read_elements['what'].isin(['notebooks'])
                read_elements.loc[cond, 'number'] = [str(x) for x in list(range( 1, len(read_elements[cond]) +1 ))] # .astype(int).astype(str)
                cond = ~read_elements['number'].isna()
                read_elements[cond].apply(_set_number, axis='columns')

            read_elements.sort_values(by=['number'], inplace=True)

            # body
            read_elements = body(read_elements)

            # drop columns

            to_drop = [
                r'isDefault',
                r'userRole',
                r'isShared',
                r'By.user.id',
                r'Url.href',
                r'odata.context',
                #r'parent*.id',
                r'parent*.displayName',
                r'parent*.self',
                #r'parentSectionGroup',
                r'createdByAppId',
                r'onenote_file_ok',
                r'indent',
            ]
            drop_list = []

            for key in read_elements:
                for val in to_drop:
                    if re.search( val, key): 
                        drop_list += [ key ]
                        break

            # if 'contentUrl' in drop_list: drop_list.remove('contentUrl')

            myprint( 'Drop list: {}'.format(drop_list))

            # read_elements.drop( columns=drop_list, inplace=True )

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            myprint("Normalize erreor [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...')
            raise

        # -------------------------------------------------------------------------------------------------------------------------------------------

        myprint( 'Nb elements = {}'.format(len(read_elements)) )

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Read error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='###')
        if not EXCEPT_HANDLING: raise

    return read_elements

# ###################################################################################################################################################
# BODY
# ###################################################################################################################################################

def body( elements ): 

    try:
        myprint( '', line=True, title='GET ONENOTE CONTENTS')

        # readdress resources

        # rebuild macOS / iPadOS / iOS share

        # reorganize content

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Boddy error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...')

    return elements

# ###################################################################################################################################################
# NEXT
# ###################################################################################################################################################

def next():

    try:
    
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # reorganize elements
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # merge elements

        myprint( '', line=True, title='REORGANIZE ONENOTE ELEMENTS' )

        def _find_page( row ):
            cond = (_elements['onenote_self'].str.contains("/pages/"))
            cond &= (_elements['tmp_name'].isin([row['tmp_name']]))
            cond &= (_elements['onenote_parent'].isin([row['onenote_id']]))
            found_pages = _elements[cond]
            if len(found_pages) > 0:
                # it is a match
                for index, found_page in found_pages.iterrows():
                    if found_page['onenote_content'] == found_page['onenote_content']: 
                        if row['onenote_content'] != row['onenote_content']: row['onenote_content'] = found_page['onenote_content']
                        else: row['onenote_content'] += found_page['onenote_content']
                    if found_page['onenote_attachments'] == found_page['onenote_attachments']: 
                        if row['onenote_attachments'] != row['onenote_attachments']: row['onenote_attachments'] = found_page['onenote_attachments']
                        else: row['onenote_attachments'] = json.dumps( json.loads(row['onenote_attachments']) + json.loads(found_page['onenote_attachments']) )
                row['tmp_found'] = found_pages['onenote_id'].to_list()
            return row

        _elements['tmp_name'] = nan
        if 'onenote_displayName' in _elements.columns.to_list():
            _elements['tmp_name'] = _elements['onenote_displayName']
        if 'onenote_title' in _elements.columns.to_list():
            cond = ~_elements['onenote_title'].isna()
            cond &= _elements['tmp_name'].isna()
            _elements.loc[cond, 'tmp_name'] = _elements['onenote_title']

        cond = (~_elements['onenote_self'].str.contains("/pages/"))
        _elements['tmp_found'] = nan
        _elements[cond] = _elements[cond].apply(_find_page, axis='columns')

        cond = (~_elements['tmp_found'].isna())
        myprint( 'merged {} contents'. format(len(_elements[cond])), prefix="...")

        _elements['onenote_merged'] = False
        pages = list(dict.fromkeys([x for xs in _elements[cond]['tmp_found'].drop_duplicates().to_list() for x in xs]))
        cond = (_elements['onenote_id'].isin(pages))
        _elements.loc[cond, 'onenote_merged'] = True

        _elements.drop( columns=['tmp_found', 'tmp_name'], inplace=True)

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set body
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _body( element ):
            if element['onenote_content'] and (element['onenote_content'] == element['onenote_content']):

                soup = BeautifulSoup( '<body>' + element['onenote_content'] + '</body>', features="html.parser" )

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

                # resize images

                tags = soup.find_all( 'img' )
                for tag in tags:
                    del tag['width']
                    del tag['height']

                    tag['width'] = 1000

                # resize objects

                tags = soup.find_all( 'object' )
                for tag in tags:
                    del tag['width']
                    del tag['height']

                    tag['width'] = 1000

                # stripped

                if len(soup.body.contents) > 0:
                    element['body'] = str( soup.body.contents[0] )
                
                # resources

                # replace url by file
                if element['onenote_attachments'] == element['onenote_attachments']:
                    for resource in json.loads(element['onenote_attachments']):
                        if resource['filename']:
                            element['body'] = element['body'].replace( resource['url'], 
                                                                    resource['filename'].replace( directory, 'static' )
                                                                    )

            return element

        if 'onenote_content' in _elements.columns.to_list():
            myprint( '', line=True, title='SET ONENOTE BODY')

            cond = (~_elements['onenote_content'].isna())
            _elements['body'] = nan
            _elements.loc[cond, 'body'] = _elements[cond].apply( _body, axis='columns' )
        
    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...')

        return empty_elements()

# ###################################################################################################################################################
# WRITE
# ###################################################################################################################################################

def write( directory, token, elements=empty_elements() ): 

    pass

# ###################################################################################################################################################
# CLEAR
# ###################################################################################################################################################

def clear( directory, elements=empty_elements(), all=False ): 

    myprint( '', line=True, title='CLEAR ONENOTE FILES')

    _directory = os.path.join( directory, 'onenote' )

    if all:
        if os.path.isdir(_directory):
            myprint( 'Removing {}...'.format(_directory), prefix='>' )
            shutil.rmtree(_directory)
            os.makedirs(_directory)
    else:
        cond = (~elements['resources'].isna())
        cond &= elements['source'].isin(['onenote'])
        resources = elements[cond]['resources'].apply( lambda x: json.loads(x) )

        if len(resources) > 0: 
            resources = resources.apply(pd.Series).stack().reset_index(drop=True).apply(pd.Series)
            resources = resources['filename'].drop_duplicates()

            myprint( 'Processing {} resources'. format(len(resources)))

            onenote_files = list(dict.fromkeys(resources.to_list()))

            count = 0
            removed = 0
            for root, dirs, files in os.walk(_directory):
                for name in files:
                    if not (os.path.join(root, name) in onenote_files):
                        removed += 1
                        myprint('[{}] removing {} file'.format(removed, os.path.join(root, name)), prefix='>')
                        #os.remove( os.path.join(root, name) )
                    count += 1

            for root, dirs, files in os.walk(_directory, topdown=False):
                for name in dirs:
                    walk = sum([len(files) for r, d, files in os.walk(os.path.join(root, name))])
                    if walk == 0:
                        myprint('removing {} directory'.format(os.path.join(root, name)), prefix='>')
                        #shutil.rmtree(os.path.join(root, name))

            myprint('removed {} out of {} files'.format(removed, count), prefix='...')

