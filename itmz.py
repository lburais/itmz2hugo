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

import sys
import os
import re
import shutil

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

# ###################################################################################################################################################
# READ
# ###################################################################################################################################################

def read( directory, source, elements=empty_elements() ):

    myprint( '', line=True, title='READ ITMZ ELEMENTS')

    _elements = elements[elements['source'].isin(['itmz'])].copy()
    _files_directory = os.path.join( directory, 'itmz' )

    try:

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # parse ITMZ files
        # -------------------------------------------------------------------------------------------------------------------------------------------

        files = []
        if os.path.isdir( source ):
            for top, dirs, filenames in os.walk( source, topdown=True ):
                for file in filenames:
                    if os.path.splitext(file)[1] == '.itmz': 
                        files.append(os.path.join(top, file))

        else:
            files.append( source )

        for file in files:

            myprint( '', line=True, title='PARSE {} FILE'.format(file.upper()))

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # read ITMZ file
            # ---------------------------------------------------------------------------------------------------------------------------------------
            ithoughts = zipfile.ZipFile( file, 'r')
            xmldata = ithoughts.read('mapdata.xml')
            elements = ET.fromstring(xmldata)

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # get elements
            # ---------------------------------------------------------------------------------------------------------------------------------------
            itmz = empty_elements()

            for element in elements.iter('topic'):

                # -----------------------------------------------------------------------------------------------------------------------------------
                # set parent
                # -----------------------------------------------------------------------------------------------------------------------------------
                parents = elements.findall('.//topic[@uuid="{}"]...'.format(element.attrib['uuid']))
                if (len(parents) > 0) and (parents[0].tag == 'topic'):
                    element.attrib['parent'] = parents[0].attrib['uuid']

                # -----------------------------------------------------------------------------------------------------------------------------------
                # set itmz specific
                # -----------------------------------------------------------------------------------------------------------------------------------
                element.attrib['file'] = file
                element.attrib['author'] = elements.attrib['author']
                
                # -----------------------------------------------------------------------------------------------------------------------------------
                # get attachments
                # -----------------------------------------------------------------------------------------------------------------------------------
                att_resource = empty_resource()
                if 'att-id' in element.attrib:

                    if 'modified' in element.attrib: att_resource['date']  = element.attrib['modified']
                    elif 'created' in element.attrib: att_resource['date']  = element.attrib['created']

                    att_resource['name'] = element.attrib['att-name'].split('.')[0]

                    IMAGES_EXT = ['jpg', 'jpeg', 'gif', 'png']
                    ext = element.attrib['att-name'].split('.')[1] if (len(element.attrib['att-name'].split('.')) > 1) else''
                    if ext.lower() in IMAGES_EXT:
                        att_resource['type'] = 'image'
                    else:
                        att_resource['type'] = 'object'

                    att_resource['url'] = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )

                    att_resource['filename'] = os.path.join( _files_directory, 
                                                            os.path.basename(file).split('.')[0],
                                                            element.attrib['att-id'],
                                                            element.attrib['att-name'] )
                                                        
                # -----------------------------------------------------------------------------------------------------------------------------------
                # move attachments
                # -----------------------------------------------------------------------------------------------------------------------------------
                if att_resource['filename']:
                    # test dates to check if load is mandatory
                    date_page = att_resource['date']
                    date_page = dt.strptime(date_page, '%Y-%m-%dT%H:%M:%S')

                    if os.path.isfile(att_resource['filename']):
                        date_file = dt.fromtimestamp(os.path.getmtime( att_resource['filename'] ))
                    else:
                        date_file = date_page

                    myprint( '{}...'.format(att_resource['url']), prefix='>')

                    # load file
                    if not os.path.isfile(att_resource['filename']) or (date_file < date_page):

                        if not os.path.isfile(att_resource['filename']): myprint( 'missing file', prefix='...' )
                        elif (date_file < date_page): myprint( 'outdated file', prefix='...' )

                        out_dir = os.path.dirname(att_resource['filename'])

                        if not os.path.isdir(out_dir):
                            os.makedirs(out_dir)

                        try:
                            ithoughts = zipfile.ZipFile( file, 'r')
                            data = ithoughts.read(att_resource['url'])

                            with open(att_resource['filename'], 'wb') as fs: 
                                fs.write(data) 

                            att_resource['processed'] = True
                        except:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            myprint("Something went wrong [{} - {}]".format(exc_type, exc_obj), prefix='...')

                    else:
                        att_resource['processed'] = True

                    if os.path.isfile(att_resource['filename']):
                        myprint( '{}: {} bytes'.format( att_resource['filename'], os.path.getsize(att_resource['filename']) ), prefix='...' )

                # -----------------------------------------------------------------------------------------------------------------------------------
                # set links
                # -----------------------------------------------------------------------------------------------------------------------------------
                link_resource = empty_resource()
                if 'itmz_link' in element.attrib:

                    target = re.split( r":", element.attrib['link'])
                    if target[0] == 'http' or  target[0] == 'https': 
                        link_resource['type'] = 'url'
                        link_resource['title'] = element.attrib['link']
                        link_resource['url'] = element.attrib['link']

                    elif target[0] == 'ithoughts':
                        target = re.split( r"[?=&]+", target[1])
                        if target[0] == '//open':
                            if 'topic' in target: 
                                ref = target[target.index('topic') + 1]
                                link_resource['type'] = 'topic'
                                link_resource['url'] = target[target.index('topic') + 1]

                            elif 'path' in target: 
                                link_resource['type'] = 'path'
                                link_resource['url'] = target[target.index('path') + 1]

                # -----------------------------------------------------------------------------------------------------------------------------------
                # add resources attachments
                # -----------------------------------------------------------------------------------------------------------------------------------
                resources = []
                if att_resource['type']: resources += [ att_resource ]
                if link_resource['type']: resources += [ link_resource ]

                if len(resources) > 0: element.attrib['attachments'] = json.dumps( resources )

                # -----------------------------------------------------------------------------------------------------------------------------------
                # convert to dataframe
                # -----------------------------------------------------------------------------------------------------------------------------------
                itmz_objects = pd.DataFrame( element.attrib, index=['i',] )
                col_list = {}
                for col in itmz_objects.columns.to_list():
                    col_list[col] = 'itmz_{}'.format(col)
                itmz_objects.rename( columns=col_list, inplace=True )

                itmz = pd.concat( [ itmz, itmz_objects ], ignore_index=True )

            myprint( '{} elements loaded'.format( len(itmz) ), prefix="#" )
            
            _elements = pd.concat( [ _elements, itmz ], ignore_index=True )

        myprint( 'Nb of ITMZ elements = {}'.format(len(_elements)) )

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
                if ('resources' in element) and (element['itmz_attachments'] == element['itmz_attachments']):
                    for resource in json.loads(element['itmz_attachments']):
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

            return element['body']

        myprint( '', line=True, title='SET ITMZ BODY')

        cond = (~_elements['itmz_text'].isna())
        cond |= (~_elements['itmz_attachments'].isna())
        cond |= (~_elements['itmz_link'].isna())
        _elements['body'] = nan
        _elements.loc[cond, 'body'] = _elements[cond].apply( _body, axis='columns' )        
        
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalize
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # normalized ['source','what','type','id','title','created','modified','author','parent','childs','body','path','slug','resources']

        myprint( '', line=True, title='NORMALIZE ITMZ')

        _elements['source'] = 'itmz'
        _elements['what'] = 'topic'
        _elements['type'] = 'post'

        # id
        def _set_id( element ):
            return os.path.basename(element['itmz_file']).split('.')[0].upper() + '_' + element['itmz_uuid']
        _elements['id'] = _elements.apply( _set_id, axis='columns' )

        # title
        def _set_title( element ):
            soup = BeautifulSoup( element['body'], features="html.parser" )
            if soup.h1:
                return str( soup.h1.contents[0] )
            else:
                return nan
        _elements.loc[~_elements['body'].isna(), 'title'] = _elements[~_elements['body'].isna()].apply( _set_title, axis='columns' )

        # dates
        _elements['created'] = _elements['itmz_created']
        _elements['modified'] = _elements['itmz_modified']

        # author
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

        # parent
        def _set_parent( element ):
            if element['itmz_parent'] == element['itmz_parent']:
                return os.path.basename(element['itmz_file']).split('.')[0].upper() + '_' + element['itmz_parent']
            else: return nan
        _elements['parent'] = _elements.apply( _set_parent, axis='columns' )

        # childs
        def _set_childs( element ):
            childs = _elements[_elements['parent'] == element['id'] ]['id']
            if len(childs) > 0: return childs.to_list()
            else: return nan
        _elements['childs'] = _elements.apply( _set_childs, axis='columns' )

        # body
        # _elements['body'] set above

        # path
        # _elements['path']

        # resources
        _elements['resources'] = _elements['itmz_attachments']

        # slug
        _elements['slug'] = _elements['id'].apply( lambda x: slugify(x) )

        # cleanup
        _elements.drop( columns=[ 'itmz_attachments', 'itmz_parent' ], inplace=True )

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # save excel
        # -------------------------------------------------------------------------------------------------------------------------------------------

        save_excel(directory, _elements, 'itmz')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # completed
        # -------------------------------------------------------------------------------------------------------------------------------------------

        return _elements

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

def clear( directory, elements=empty_elements() ): 

    pass