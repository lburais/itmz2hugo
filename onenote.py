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

    cat = read( token=token, what='catalog' )
    cat = cat[cat['what'].isin(['notebooks'])]
    cat['what'] = 'content'

    return pd.concat( [ pd.DataFrame( {'source': ['onenote'], 'title': ['All Notebooks'], 'what': ['notebooks'], 'onenote_self': [None] } ),
                        cat,
                        pd.DataFrame( {'source': ['onenote'], 'title': ['All Contents'], 'what': ['content'], 'onenote_self': [None] } ),
                        pd.DataFrame( {'source': ['onenote'], 'title': ['All Resources'], 'what': ['resources'], 'onenote_self': [None] } ),
                        pd.DataFrame( {'source': ['onenote'], 'title': ['Clear Resources'], 'what': ['clear'], 'onenote_self': [None] } ),
                        pd.DataFrame( {'source': ['onenote'], 'title': ['Delete Resources'], 'what': ['delete'], 'onenote_self': [None] } ),
                        pd.DataFrame( {'source': ['onenote'], 'title': ['Refresh'], 'what': ['refresh'], 'onenote_self': [None] } ),
                      ], ignore_index = True )

# ###################################################################################################################################################
# READ
# ###################################################################################################################################################
# catalog: just get list of notebooks if True
# url:
#   notebooks:
#       https://graph.microsoft.com/v1.0/me/onenote/notebooks/0-34CFFB16AE39C6B3!335975
#       https://graph.microsoft.com/v1.0/me/onenote/notebooks
#   sections:
#       https://graph.microsoft.com/v1.0/me/onenote/sections?$expand=parentNotebook&$filter=(parentNotebook/id eq '0-34CFFB16AE39C6B3!335975')
#       https://graph.microsoft.com/v1.0/me/onenote/sections
#   sectionGroups:
#       https://graph.microsoft.com/v1.0/me/onenote/sectionGroups?$expand=parentNotebook&$filter=(parentNotebook/id eq '0-34CFFB16AE39C6B3!335975')
#       https://graph.microsoft.com/v1.0/me/onenote/sectionGroups
#   pages:
#       https://graph.microsoft.com/v1.0/me/onenote/pages?$expand=parentNotebook&$filter=(parentNotebook/id eq '0-34CFFB16AE39C6B3!335975')
#       https://graph.microsoft.com/v1.0/me/onenote/pages
#   content:
#       https://graph.microsoft.com/v1.0/me/onenote/pages/0-6e7049480c3b7746b57125df2fa5c443!1-34CFFB16AE39C6B3!336108/content
#   resources:
#       https://graph.microsoft.com/v1.0/me/onenote/resources/0-baeb483a8d536e428d9ea60b08665ca2!1-34CFFB16AE39C6B3!335977/content
# directory: get resources if directory is provided
# elements: get content and resources if some elements are passed, otherwise get notebooks, sectionGroups, sections and pages

def read( token, url=None, what='catalog', directory=None, elements=empty_elements() ): 

    try:

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # process url
        # -------------------------------------------------------------------------------------------------------------------------------------------
        def process_url( url ):
            nonlocal read_elements

            try:

                get_url = url

                page_count = 0
                page_nb = 100

                # what: 'notebooks', 'sectionGroups', 'sections', 'pages', 'content', 'resources
                what = re.search( r'^.*/onenote/(.*)\?.*$', url )
                if what:
                    what = what.group(1).split("/")
                else:
                    what = re.search( r'^.*/onenote/(.*).*$', url ).group(1).split("/")
                if what[-1] in ['notebooks', 'sectionGroups', 'sections', 'pages', 'content', 'resources']:
                    if what[0] in ['resources']: what = what[0]
                    else: what = what[-1]
                else: 
                    # notebooks/{id} case
                    what = what[0]

                # remove elements of notebook
                get_elements = empty_elements()

                while get_url:
                    myprint( '[{}] {}'.format(what, get_url), prefix='>' )

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

                                # paginate
                                if ('@odata.nextLink' in onenote_response.json() or page_count > 0) and (len(onenote_objects) > 0):
                                    get_url = url + '&' if what in ['pages'] else '?'
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

                                tmp_parent = tmp.iloc[0]['onenote_id'] if len(tmp) > 0 else nan
                                tmp_created = tmp.iloc[0]['onenote_createdDateTime'] if len(tmp) > 0 else nan
                                tmp_modified = tmp.iloc[0]['onenote_lastModifiedDateTime'] if len(tmp) > 0 else nan
                                del tmp

                                onenote_objects = pd.DataFrame( { 'onenote_id': ['content' + identifier], 
                                                                  'onenote_self': [url], 
                                                                  'onenote_parentPage.id': [tmp_parent], 
                                                                  'onenote_createdDateTime': [tmp_created], 
                                                                  'onenote_lastModifiedDateTime': [tmp_modified], 
                                                                  'onenote_content': [onenote_response.text],
                                                                  'onenote_resources': [''],
                                                                } )

                                # add resources objects
                                onenote_resources = process_resources( onenote_response.text )

                                if len(onenote_resources) > 0:
                                    myprint( 'adding {} resources'.format(len(onenote_resources)) )
                                    onenote_resources['onenote_what'] = 'resources'
                                    onenote_resources['onenote_parentContent.id'] = 'content' + identifier
                                    onenote_resources['onenote_createdDateTime'] = tmp_created
                                    onenote_resources['onenote_lastModifiedDateTime'] = tmp_modified
                                    onenote_resources['onenote_self'] = onenote_resources['onenote_resourceUrl']
                                    onenote_objects['onenote_resources'] = \
                                        onenote_objects['onenote_id'].apply(lambda x: ','.join(onenote_resources['onenote_id'].to_list()))
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
                                                                      ) )

                                        row['onenote_file_size'] = os.path.getsize(row['onenote_file_name'])
                                        row['onenote_file_date'] = dt.fromtimestamp(os.path.getmtime(row['onenote_file_name']))
                                    except:
                                        exc_type, exc_obj, exc_tb = sys.exc_info()
                                        myprint( 'error [{} - {}] at line {}'.format(exc_type, exc_obj, exc_tb.tb_lineno))
                                    return row

                                # retrieve element by url and save file
                                cond = read_elements['onenote_what'].isin(['resources'])
                                cond &= read_elements['onenote_resourceUrl'] == url

                                myprint( 'writing {} files'.format(len(read_elements[cond])) )
                                if len(read_elements[cond]) > 0:
                                    read_elements[cond] = read_elements[cond].apply( _load_resource, axis='columns' )

                                onenote_objects = empty_elements()
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
                        myprint("Get error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))
                        break

                get_elements.drop_duplicates( subset=['onenote_id'], inplace=True )

                myprint( '{} {} loaded'.format(len(get_elements), what) )

                if len(get_elements) > 0:
                    # concat 
                    if len(read_elements) > 0: read_elements = pd.concat([read_elements, get_elements], ignore_index=True)
                    else: read_elements = get_elements.copy()

            except:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                myprint("Url error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))
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

            # images
            # ------
            # <img 
            # src=".../resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value 
            # data-src-type="image/png" 
            # data-fullres-src=".../resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value
            # data-fullres-src-type="image/png" 
            # height="842" 
            # width="595"
            # />

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
                name = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-fullres-src-type'].replace('image/', '')
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

        if what in ['catalog']:
            # catalog
            myprint( '', line=True, title='READ ONENOTE CATALOG' )

            read_elements = empty_elements()
            process_url(ME + '/notebooks')
            read_elements['what'] = 'catalog'

        else:
            myprint( '{} - {} - {} - {}'.format(url, what, directory, len(elements) ))
    
            _files_directory = os.path.join( directory, 'onenote' )

            if what in ['notebooks']:
                myprint( '', line=True, title='READ ONENOTE NOTEBOOKS' )

                read_elements = empty_elements()

                # notebooks
                process_url(ME + "/notebooks")

                # sectionGroups
                process_url(ME + "/sectionGroups")

                # sections
                process_url(ME + "/sections")

                # pages
                process_url(ME + "/pages?$pagelevel=true")

                # force content update
                what = 'content'

            else:
                read_elements = elements.copy()

            if what in ['content'] and (len(read_elements) > 0) and 'onenote_contentUrl' in read_elements:

                # content : use the page's contentUrl to retrieve content and create content and resources records

                myprint( '', line=True, title='READ ONENOTE CONTENT' )

                # remove content and resources (that will be re-added)
                cond = read_elements['onenote_what'].isin(['content', 'resources'])
                if url: cond &= read_elements['top'] == url
                read_elements = read_elements[~cond]

                # process contentUrl
                cond = ~read_elements['onenote_what'].isin(['content', 'resources'])
                if url: cond &= read_elements['top'] == url
                cond &= ~read_elements['onenote_contentUrl'].isna()

                myprint( 'Processing {} elements...'.format(len(read_elements[cond])))
                read_elements[cond]['onenote_contentUrl'].apply( lambda x: process_url(x) )

                # for resources update
                what = 'resources'

                # NEED REORG TO SET TOP
                read_elements = normalize( read_elements )

            if what in ['resources']  and (len(read_elements) > 0) and 'onenote_resourceUrl' in read_elements and 'onenote_file_name' in read_elements:
                myprint( '', line=True, title='READ ONENOTE RESOURCES' )

                read_elements['onenote_file_ok'] = True
                read_elements['onenote_file_date'] = nan

                # file does not exist
                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                cond = ~read_elements['onenote_file_name'].isna()
                read_elements.loc[cond, 'onenote_file_ok'] = read_elements[cond]['onenote_file_name'].apply( lambda x: os.path.isfile(x) )

                # get file mtime
                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                cond = ~read_elements['onenote_file_name'].isna() & read_elements['onenote_file_ok']
                read_elements.loc[cond, 'onenote_file_date'] = \
                    read_elements[cond]['onenote_file_name'].apply( lambda x: dt.fromtimestamp(os.path.getmtime(x)) )

                # set page date
                def _set_date(row):
                    if 'onenote_lastModifiedDateTime' in row:
                        tmp_date = row['onenote_lastModifiedDateTime']
                    elif 'onenote_createdDateTime' in row:
                        tmp_date = row['onenote_createdDateTime']
                    else: tmp_date = nan

                    try:
                        tmp_date = dt.strptime(tmp_date, '%Y-%m-%dT%H:%M:%S.%fZ')
                    except:
                        try:
                            tmp_date = dt.strptime(tmp_date, '%Y-%m-%dT%H:%M:%SZ')
                        except:
                            tmp_date = nan

                    return tmp_date

                read_elements['onenote_date'] = nan
                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                read_elements.loc[cond, 'onenote_date'] = read_elements.apply( _set_date, axis = 'columns' )

                # no page date to compare to
                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                cond = ~read_elements['onenote_file_name'].isna() & read_elements['onenote_file_ok'] & read_elements['onenote_date'].isna()
                read_elements.loc[cond, 'onenote_file_ok'] = False

                # file older than page date
                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                cond &= ~read_elements['onenote_file_name'].isna() & read_elements['onenote_file_ok']
                read_elements.loc[cond, 'onenote_file_ok'] = \
                    read_elements[cond].apply( lambda x: (x['onenote_file_date'] > x['onenote_date']), axis = 'columns' )

                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                cond &= (read_elements['onenote_file_ok'] == False)
                file_list = ['onenote_file_name', 'onenote_file_ok', 'onenote_date', 'onenote_file_date', 'onenote_resourceUrl' ]
                if len(read_elements[cond]) > 0:
                    myprint( read_elements[cond][:20][file_list].replace(to_replace=r"^.*/onenote/", value=".../", regex=True) )

                del read_elements['onenote_date']

                # all set 

                cond = read_elements['what'].isin(['resources'])
                if url: cond &= read_elements['top'] == url
                cond &= (~read_elements['onenote_resourceUrl'].isna())
                cond &= (~read_elements['onenote_file_name'].isna())
                cond &= (~read_elements['onenote_file_ok'])
                
                if len(read_elements[cond]) > 0:
                    myprint( 'Loading {} resources...'.format(len(read_elements[cond])) )
                    read_elements[cond]['onenote_resourceUrl'].apply( lambda x: process_url(x) )
                else:
                    cond = read_elements['what'].isin(['resources'])
                    if url: cond &= read_elements['top'] == url
                    cond &= (~read_elements['onenote_file_name'].isna())
                    myprint( 'All {} files ok, no resource to be loaded'.format(len(read_elements[cond])) )

        # -------------------------------------------------------------------------------------------------------------------------------------------

        read_elements = normalize( read_elements )

        # display first elements if not just notebooks (catalog)
        if len(read_elements[~read_elements['what'].isin(['notebooks'])]) > 0: 
            if len(read_elements) > 20: myprint( '', line=True, title='FIRST 20 OF {} ONENOTE ELEMENTS'.format(len(read_elements)))
            else: myprint( '', line=True, title='ONENOTE ELEMENTS')
            read_elements['short'] = read_elements['title'].str[:30]
            display_list =['number', 'id', 'what', 'short', 'parent', 'path']
            for val in reversed(display_list):
                if val not in read_elements:
                    display_list.remove(val)
            cond = ~read_elements['id'].isna()
            myprint(read_elements.iloc[:30][display_list].replace(r'.*/onenote','...'))
            del read_elements['short']

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Read error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))
        if not EXCEPT_HANDLING: raise

    return read_elements

# ###################################################################################################################################################
# NORMALIZE
# ###################################################################################################################################################

def normalize( elements ): 
    try:
        myprint( 'Normalizing {} elements'.format(len(elements)) )

        if len(elements) > 0:

            # source
            elements['source'] = 'onenote'

            # what
            elements['what'] = elements['onenote_what'] if 'onenote_what' in elements else nan

            # type
            elements['type'] = 'unknown' 
            elements.loc[elements['what'].isin(['notebooks','sections','sectionGroups']), 'type'] = 'page' 
            elements.loc[elements['what'].isin(['pages']), 'type'] = 'post' 

            # id
            elements['id'] = elements['onenote_id'] if 'onenote_id' in elements else nan

            # title
            elements['title'] = nan
            if 'onenote_title' in elements: 
                elements['title'] = elements['onenote_title']
            if 'onenote_displayName' in elements: 
                cond = elements['title'].isna()
                elements.loc[cond, 'title'] = elements[cond]['onenote_displayName']

            # dates
            elements['created'] = elements['onenote_createdDateTime'] if 'onenote_createdDateTime' in elements else nan
            elements['modified'] = elements['onenote_lastModifiedDateTime'] if 'onenote_lastModifiedDateTime' in elements else nan

            # authors
            elements['authors'] = nan
            for col in ['onenote_createdBy.user.displayName', 'onenote_lastModifiedBy.user.displayName']:
                if col in elements:
                    cond = ~elements[col].isna()
                    elements.loc[cond, 'authors'] = elements[cond][col]

            # slug
            elements['slug'] = elements['id'].apply( lambda x: slugify(x) )

            # osname
            elements['osname'] = elements['title'].apply( lambda x: slugify(x, True) if x == x else nan )

            # body
            if 'onenote_contents' in elements:
                cond = ~elements['onenote_content'].isna()
                elements.loc[cond, 'onenote_content'] = elements[cond]['onenote_content'].str.replace('_x000D_','')


            # parent
            elements['onenote_parent_context'] = nan
            elements['onenote_parent'] = nan
            ids =  ['onenote_parentContent.id', 'onenote_parentPage.id']
            ids += ['onenote_parentSection.id', 'onenote_parentSectionGroup.id', 'onenote_parentNotebook.id']
            for context in ids:
                if context in elements:
                    cond = elements['onenote_parent_context'].isna()
                    cond &= ~elements[context].isna()
                    elements.loc[cond, 'onenote_parent'] = elements[cond][context]
                    elements.loc[cond, 'onenote_parent_context'] = context.replace('onenote_parent','').replace('.id','')
            elements['parent'] = elements['onenote_parent'] if 'onenote_parent' in elements else nan

            # sub pages
            def _set_subpages( row ):
                cond = elements['onenote_parent'] == row['onenote_parent']
                cond &= elements['onenote_order'] == (row['onenote_order'] - 1)
                row['onenote_parent'] = elements[cond]['onenote_parent']

            if (len(elements[~elements['what'].isin(['notebooks'])]) > 0) and  'onenote_level' in elements:
                for level in range( 1, int(elements['onenote_level'].max(skipna=True)) + 1 ):
                    elements[(elements['onenote_level'] == (level+1))].apply(_set_subpages, axis='columns')

            # childs
            def _set_childs( element ):
                cond = (elements['parent'] == element['id'] )
                cond &= (~elements['what'].isin(['content', 'resources']) )
                childs = elements[cond]['id']
                if len(childs) > 0: return childs.to_list()
                else: return []
            elements['childs'] = elements.apply( _set_childs, axis='columns' ) if len(elements) > 0 else nan

            # number and path
            def _set_number_path( row ):
                cond = elements['parent'] == row['id']
                if len(elements[cond]) > 0:
                    elements.loc[cond, 'number'] = [(row['number'] + '.' + str(x).zfill(3)) for x in list(range( 1, len(elements[cond]) +1 ))]
                    myprint('[{}] - [{}]'.format(elements[cond].iloc[0]['osname'], row['path']))
                    elements.loc[cond, 'path'] = elements[cond].iloc[0]['osname'] + '!' + row['path']
                    elements[cond].apply(_set_number_path, axis='columns')

            elements['number'] = nan
            elements['path'] = ''
            if len(elements[~elements['what'].isin(['notebooks'])]) > 0: 
                if 'onenote_order' in elements:
                    elements.sort_values(by=['onenote_order'], inplace=True)

                cond = elements['what'].isin(['notebooks'])
                elements.loc[cond, 'number'] = elements[cond]['id'].str.split(pat='!', expand=True)[1]
                elements.loc[cond, 'path'] = elements[cond]['osname']
                cond = ~elements['number'].isna()
                elements[cond].apply(_set_number_path, axis='columns')

            elements.sort_values(by=['number'], inplace=True)

            # top
            def _set_top( row ):
                cond = elements['number'].str.startswith(row['number'], na=False)
                elements.loc[cond, 'top'] = row['onenote_self']

            # publish
            elements['publish'] = True
            elements.loc[elements['what'].isin(['content','resources']), 'publish'] = False
            elements.loc[elements['childs'].isin(['[]]'] & elements['childs'].isna()), 'publish'] = False

            # reorganize
            if len(elements[~elements['what'].isin(['notebooks'])]) > 0: 
                elements = reorganize(elements)

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Normalize error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))
        raise

    return elements

# ###################################################################################################################################################
# REORGANIZE
# ###################################################################################################################################################

def reorganize( elements ): 
    try:
        def _readdress( row ):
            nonlocal elements

            body = row['onenote_content']

            try:

                # readdress resources
                if 'onenote_id' in elements and 'onenote_resources' in elements and 'onenote_self' in elements and 'onenote_file_name' in elements:
                    resources = elements[ elements['onenote_id'].isin(row['onenote_resources'].split(',')) ]
                    resources = dict(zip(resources['onenote_self'].str.replace('/content','/$value'), resources['onenote_file_name']))
                    for url, name in resources.items():
                        body = body.replace( url, name )

                soup = BeautifulSoup( body, features="html.parser" )

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
                    body = ''.join([str(i) for i in soup.body.contents]).strip()
                else:
                    body = '<br>' # to avoid consider empty

            except:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                myprint("readdress error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))


            return body

        if 'onenote_resources' in elements and 'onenote_content' in elements:
            cond = ~elements['onenote_content'].isna()
            cond &= len(elements['onenote_resources']) > 0
            
            myprint( 'Readdressing {} content and resources'.format(len(elements[cond])) )

            elements.loc[cond, 'body'] = elements[cond].apply( _readdress, axis='columns' )

        # set page body
        def _set_body( row ):
            nonlocal elements

            if 'onenote_parent' in elements and 'onenote_id' in row:
                cond = elements['onenote_parent'] == row['onenote_id']
                return elements[cond].iloc[0]['body'] if len(elements[cond]) == 1 else ''
            else: return ''

        if 'onenote_what' in elements and 'body' in elements :
            cond = elements['onenote_what'].isin( ['pages'] )
            
            myprint( 'Setting body for {} pages'.format(len(elements[cond])) )

            elements.loc[cond, 'body'] = elements[cond].apply( _set_body, axis='columns' )

        return elements

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
        myprint( 'merged {} contents'. format(len(_elements[cond])))

        _elements['onenote_merged'] = False
        pages = list(dict.fromkeys([x for xs in _elements[cond]['tmp_found'].drop_duplicates().to_list() for x in xs]))
        cond = (_elements['onenote_id'].isin(pages))
        _elements.loc[cond, 'onenote_merged'] = True

        _elements.drop( columns=['tmp_found', 'tmp_name'], inplace=True)

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Reorganize error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))

    return elements

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

            myprint('removed {} out of {} files'.format(removed, count))

