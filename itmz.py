# ###################################################################################################################################################
# Filename:     itmz.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# ###################################################################################################################################################
# iThoughts structure
# -------------------
#   [src]
#   └── [file1].itmz
#       ├── mapdata.xml
#       |   ├── tag
#       |   ├── iIhoughts attribs
#       |   |   ├── modified
#       |   |   └── author
#       |   ├── topic attribs
#       |   |   ├── uuid
#       |   |   ├── text
#       |   |   ├── link
#       |   |   ├── created
#       |   |   ├── modified
#       |   |   ├── note
#       |   |   ├── callout
#       |   |   ├── floating
#       |   |   ├── att-name
#       |   |   ├── att-id
#       |   |   ├── task-start
#       |   |   ├── task-due
#       |   |   ├── cost
#       |   |   ├── cost-type
#       |   |   ├── task-effort
#       |   |   ├── task-priority
#       |   |   ├── task-progress
#       |   |   ├── resources
#       |   |   ├── icon1
#       |   |   ├── icon2
#       |   |   ├── position
#       |   |   ├── color
#       |   |   ├── summary1
#       |   |   └── summary2
#       |   ├── relationship
#       |   |   ├── end1-uui
#       |   |   └── end2-uui
#       |   └── group
#       |       ├── member1
#       |       └── member2
#       └── assets
#           ├── [uuid1]
#           |   ├── [attachment1]
#           |   └── [attachment1]
#           └── [uuid2]
#               └── [attachment3]
#
# ###################################################################################################################################################

import xml.etree.ElementTree as ET
import zipfile
import markdown
import json

from datetime import datetime as dt

from tabulate import tabulate
from bs4 import BeautifulSoup

# pip3 install pandas
import pandas as pd

from mytools import *

# #################################################################################################################################
# ITMZ
# #################################################################################################################################

class ITMZ:

    _timestamp = None

    # #############################################################################################################################
    # __init__
    # #############################################################################################################################

    def __init__( self ):

        pass

    # #############################################################################################################################
    # read
    # #############################################################################################################################

    def read( self, directory, source, elements=empty_elements() ):

        _elements = elements[elements['source'].isin(['itmz'])].copy()
        _files_directory = os.path.join( directory, 'itmz' )

        myprint( elements, 'ITMZ ELEMENTS')
        
        def _set_uuid( file, id ):
            pass

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get topics
        # -------------------------------------------------------------------------------------------------------------------------------------------

        myprint( '', line=True, title='GET ITMZ ELEMENTS')

        files = []
        if os.path.isdir( source ):
            for top, dirs, filenames in os.walk( source, topdown=True ):
                for file in filenames:
                    if os.path.splitext(file)[1] == '.itmz': 
                        files.append(os.path.join(top, file))

        else:
            files.append( source )

        for file in files:

            myprint( file, prefix='>')

            # read ITMZ file
            ithoughts = zipfile.ZipFile( file, 'r')
            xmldata = ithoughts.read('mapdata.xml')
            elements = ET.fromstring(xmldata)

            itmz = empty_elements()

            # get elements
            for element in elements.iter('topic'):
                parents = elements.findall('.//topic[@uuid="{}"]...'.format(element.attrib['uuid']))

                itmz_objects = pd.DataFrame( element.attrib, index=['i',] )
                col_list = {}
                for col in itmz_objects.columns.to_list():
                    col_list[col] = 'itmz_{}'.format(col)
                itmz_objects.rename( columns=col_list, inplace=True )
                itmz_objects['itmz_file'] = file
                itmz_objects['itmz_author'] = elements.attrib['author']
                
                if (len(parents) > 0) and (parents[0].tag == 'topic'):
                    itmz_objects['itmz_parent'] = parents[0].attrib['uuid']

                itmz = pd.concat( [ itmz, itmz_objects ], ignore_index=True )

            myprint( '{} elements loaded'.format( len(itmz) ), prefix="..." )

            _elements = pd.concat( [ _elements, itmz ], ignore_index=True )

        myprint( 'Nb of ITMZ elements = {}'.format(len(_elements)) )

        save_excel(directory, _elements, 'itmz elements')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _get_resource( element ):
            resources = []
            if element['itmz_att-id'] and (element['itmz_att-id'] == element['itmz_att-id']):

                resource = { 'type': None, 'name': None, 'url': None, 'parent': None, 'filename': None, 'date': None }

                if ('itmz_created' in element) and (element['itmz_created'] == element['itmz_created']): 
                    resource['date']  = element['itmz_created']
                if ('itmz_modified' in element) and (element['itmz_modified'] == element['itmz_modified']): 
                    resource['date']  = element['itmz_modified']

                resource['name'] = element['itmz_att-name'].split('.')[0]

                if (len(element['itmz_att-name'].split('.')) > 1) \
                and element['itmz_att-name'].split('.')[1].lower() in ['jpg', 'jpeg', 'gif', 'png']:
                    resource['type'] = 'image'
                else:
                    resource['type'] = 'object'

                resource['url'] = os.path.join( "assets", element['itmz_att-id'], element['itmz_att-name'] )

                resource['filename'] = os.path.join( _files_directory, 
                                                     os.path.basename(element['itmz_file']).split('.')[0],
                                                     element['itmz_att-id'],
                                                     element['itmz_att-name'] )
                                                    
                resources += [ resource ]

            if element['itmz_link'] and (element['itmz_link'] == element['itmz_link']):

                resource = { 'type': None, 'name': None, 'url': None, 'parent': None, 'filename': None, 'date': None }

                target = re.split( r":", element['itmz_link'])
                if target[0] == 'http' or  target[0] == 'https': 
                    resource['type'] = 'url'
                    resource['title'] = element['itmz_link']
                    resource['url'] = element['itmz_link']

                elif target[0] == 'ithoughts':
                    target = re.split( r"[?=&]+", target[1])
                    if target[0] == '//open':
                        if 'topic' in target: 
                            ref = target[target.index('topic') + 1]
                            resource['type'] = 'topic'
                            resource['url'] = target[target.index('topic') + 1]

                        elif 'path' in target: 
                            resource['type'] = 'path'
                            resource['url'] = target[target.index('path') + 1]

                if resource['type']: resources += [ resource ]

            if len(resources) > 0:
                return json.dumps( resources )
            else:
                return nan

        if ('itmz_att-id' in _elements) or ('itmz_link' in _elements):
            myprint( '', line=True, title='GET ITMZ RESOURCES')

            _elements['resources'] = nan

            cond = ((~_elements['itmz_att-id'].isna()) & (~_elements['itmz_att-name'].isna()))
            cond |= (~_elements['itmz_link'].isna())

            myprint( 'Parsing {} contents'. format(len(_elements[cond])))

            _elements.loc[cond, 'resources'] = _elements[cond].apply(_get_resource, axis='columns')

            save_excel(directory, _elements, 'itmz resources')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set body
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _body( element ):
            if ('itmz_text' in element) and (element['itmz_text'] == element['itmz_text']): 
                element['body'] = ''

                # first row is H1 / title
                if element['itmz_text'][0] not in '[#`~]': element['body'] += '# '
                element['body'] += element['itmz_text']

                # convert code
                element['body'] = re.sub( r'```', '~~~', element['body'], flags = re.MULTILINE )
                #element['body'] = re.sub( r'~~~', '```', element['body'], flags = re.MULTILINE )

                # add anchors to body
                element['body'] = re.sub( r'^(?P<line>.*)', '\g<line> {#' + element['itmz_uuid'] + '}', element['body'], count = 1 )

                # convert body to html
                element['body'] = markdown.markdown( element['body'], extensions=['extra', 'nl2br'] )

                # shift headers by level in body
                #for h in range (6, 0, -1):
                #    element['body'] = re.sub( r'h' + str(h) + r'>', 'h{}>'.format(h+level+1), element['body'], flags = re.MULTILINE )

                # add anchors to body
                if ('itmz_uuid' in element) and (element['itmz_uuid'] == element['itmz_uuid']):
                    element['body'] = '<a id="{}">'.format(element['itmz_uuid']) + element['body']

                # add resources to body
                if ('resources' in element) and (element['resources'] == element['resources']):
                    for resource in json.loads(element['resources']):
                        # image
                        if resource['type'] in ['image']:
                            tag = '\n<img src="{}" title="{}" width="1000" />'
                            element['body'] += tag.format( resource['url'],
                                                           resource['name'] )
                        # object
                        elif resource['type'] in ['object']:
                            tag= '\n<object data="{}" data-attachment="{}" type="application/{}" target="_blank" width="1000"></object>'
                            ext = os.path.basename(resource['filename']).split('.')
                            element['body'] += tag.format( resource['url'], 
                                                           os.path.basename(resource['filename']),
                                                           ext[1].lower() if len(ext) > 1 else 'pdf' )
                        # link
                        elif resource['type'] in ['url', 'topic', 'path']:
                            tag= '\n<a href="{}" {} target="_blank" width="1000">{}</a>'
                            element['body'] += tag.format( resource['url'], 
                                                           'class="btn btn-default fa-solid fa-link"', 
                                                           resource['name'] )

                        if resource['filename']:
                            element['body'] = element['body'].replace( resource['url'], 
                                                                       resource['filename'].replace( directory, 'static' )
                                                                     )

                # add task information to body
                # tabulate
                # table by row
                # header
                task_table = {}
                task = { 'itmz_task-start': 'Start', 'itmz_task-due': 'Due', 'itmz_cost': 'Cost', 'itmz_task-effort': 'Effort', 
                        'itmz_task-priority': 'Priority', 'itmz_task-progress': 'Progress', 'itmz_resources': 'Resource(s)' }
                for key, value in task.items():
                    if key in element and element[key] and (element[key] == element[key]):
                        if key == 'task-progress':
                            if element[key][-1] != "%": 
                                if int(element[key]) > 100: continue
                                element[key] += '%'
                        if key == 'task-effort' and element[key][0] == '-': continue
                        task_table[value] = [ element[key] ]

                if len(task_table) > 0: 
                    element['body'] += "\n\n"
                    element['body'] += tabulate( task_table, headers="keys", tablefmt="html" )

            return element

        myprint( '', line=True, title='SET ITMZ BODY')

        cond = (~_elements['itmz_text'].isna())
        cond |= (~_elements['resources'].isna())
        cond |= (~_elements['itmz_link'].isna())
        _elements['body'] = nan
        _elements.loc[cond, 'body'] = _elements[cond].apply( _body, axis='columns' )        
        
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalize
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalized ['source','what','id','title','created','modified','author','parent','body','path','resources']

        myprint( '', line=True, title='NORMALIZE ITMZ')

        _elements['source'] = 'itmz'
        _elements['what'] = 'topic'

        def _set_id( element ):
            return os.path.basename(element['itmz_file']).split('.')[0].upper() + '_' + element['itmz_uuid']
        _elements['id'] = _elements.apply( _set_id, axis='columns' )

        def _set_title( element ):
            soup = BeautifulSoup( element['body'], features="html.parser" )
            if soup.h1:
                return str( soup.h1.contents[0] )
            else:
                return nan
        _elements.loc[~_elements['body'].isna(), 'title'] = _elements[~_elements['body'].isna()].apply( _set_title, axis='columns' )

        _elements['created'] = _elements['itmz_created']
        _elements['modified'] = _elements['itmz_modified']

        def _set_author( element ):
            if element['itmz_author'] and (element['itmz_author'] == element['itmz_author']):
                authors = re.split( r"[\[\]]+", element['itmz_author'])
                if len(authors) > 2:
                    return authors[1]
                else:
                    return nan
            else:
                return nan
        _elements['authors'] = _elements.apply( _set_author, axis='columns' )

        # _elements['parent'] set above
        # _elements['body'] set above
        # _elements['resources'] set above

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # load resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _load_resource( resource ):

            if not resource['filename']:
                myprint("[{}] no filename for {}".format(resource['index'], resource['url']), prefix='>')
                return resource

            # test dates to check if load is mandatory
            date_page = resource['date']
            date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%S')

            if os.path.isfile(resource['filename']):
                date_file = dt.fromtimestamp(os.path.getmtime( resource['filename'] ))
            else:
                date_file = date_page

            myprint( '[{}] {}...'.format(resource['index'], resource['url'], prefix='>'))

            # load file
            if not os.path.isfile(resource['filename']) or (date_file < date_page):

                if not os.path.isfile(resource['filename']): myprint( 'missing file', prefix='...' )
                elif (date_file < date_page): myprint( 'outdated file', prefix='...' )

                out_dir = os.path.dirname(resource['filename'])

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                try:
                    data = ithoughts.read(resource['url'])

                    with open(resource['filename'], 'wb') as fs: 
                        fs.write(data) 

                    resource['processed'] = True
                except:
                    myprint("something wrong from {} to {}".format(resource['url'], resource['filename']), prefix='...')

            else:
                    resource['processed'] = True

            if os.path.isfile(resource['filename']):
                myprint( '{}: {} bytes'.format( resource['filename'], os.path.getsize(resource['filename']) ), prefix='...' )

            return resource

        cond = (~_elements['resources'].isna())
        resources = _elements[cond]['resources'].apply( lambda x: json.loads(x) )
        if len(resources) > 0: 
            myprint( '', line=True, title='LOAD ITMZ RESOURCES')

            resources = resources.apply(pd.Series).stack().reset_index(drop=True).apply(pd.Series)
            resources = resources[resources['type'].isin(['image','object'])]

            nb = len(resources)
            myprint( 'Processing {} resources'. format(nb))
            resources['index'] = range(nb, 0, -1)        
            resources['processed'] = False       
            
            if len(resources) > 0: 
                resources = resources.apply(_load_resource, axis='columns')

            myprint( '.. missing {} resources out of {}'. format(len(resources[resources['processed']==False]), nb))

            save_excel(directory, _elements, 'itmz loaded')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # save excel
        # -------------------------------------------------------------------------------------------------------------------------------------------

        save_excel(directory, _elements, 'itmz')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # completed
        # -------------------------------------------------------------------------------------------------------------------------------------------

        return _elements

