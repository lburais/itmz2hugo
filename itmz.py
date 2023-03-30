# #####################################################################################################################################################################################################
# Filename:     itmz.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# Graph Explorer:
#   https://developer.microsoft.com/fr-fr/graph/graph-explorer
#
# #####################################################################################################################################################################################################
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
# #####################################################################################################################################################################################################

import json
import re
import os
import sys
import pathlib
import requests

from datetime import datetime as dt

from bs4 import BeautifulSoup   

from flask import request

from mytools import *

import xml.etree.ElementTree as ET
import zipfile
import markdown
from markdownify import markdownify
from tabulate import tabulate

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

ALL_MAPS = 'All Maps'

itmz = None

output_directory = os.path.join( os.path.dirname(__file__), 'output', 'itmz' )
itmz_source = os.path.join( os.sep, 'Users', 'lburais', 'Library', 'Mobile Documents', 'iCloud~com~toketaware~ios~ithoughts', 'Documents' )

# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# GET_OBJECT_DATE
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _get_object_date( obj ):
    try:
        obj_date = obj['lastModifiedDateTime'] if 'lastModifiedDateTime' in obj else obj['createdDateTime']
        try:
            obj_date = dt.strptime(obj_date, '%Y-%m-%dT%H:%M:%S.%fZ')
        except:
            obj_date = dt.strptime(obj_date, '%Y-%m-%dT%H:%M:%SZ')
    except:
        obj_date = dt.now(dt.timezone.utc)

    return obj_date

# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# GET_FILE_DATE
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _get_file_date( file ):
    if os.path.exists( file ):
        return dt.utcfromtimestamp(os.path.getmtime(file))
    else:
        return None

# #####################################################################################################################################################################################################
# PROCESS_URL
# #####################################################################################################################################################################################################

def process_url():

    try:
                    
        action = request.base_url.split('/')[-1]

        print( f'[itmz] [process_url] action: {action}, url: {request.url}' )

        catalog = []
        elements = []
        note = {}
        comments = ''

        # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # CATALOG
        # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if action in ['parse', 'catalog']:

            if os.path.isdir( itmz_source ):
                for root, dirs, filenames in os.walk( itmz_source, topdown=True ):
                    for file in filenames:
                        if os.path.splitext(file)[1] == '.itmz': 
                            catalog += [ { 'source': 'itmz', 'object': 'file', 'name': os.path.splitext(file)[0], 'file': os.path.join(root, file), 'url': f'file={os.path.join(root, file)}' } ]

            # add command to parse all notebooks        
            if len(catalog) > 0:
                catalog.insert( 0, [ { 'source': 'itmz', 'object': 'file', 'name': ALL_MAPS, 'url': 'notebook={}'.format(ALL_MAPS) } ] )

        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # ITMZ
        #   ?FILE=
        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if action in ['parse', 'itmz']:

            itmz_files = request.args.get('file')

            if itmz_files and itmz_files in [ALL_MAPS]: itmz_files = None

            if itmz_files:
                itmz_files = [ itmz_files ]
            else:
                itmz_files = [ cat.file for cat in catalog ]
            
            for itmz_file in itmz_files:
                _download_itmz( output_directory, itmz_file )

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # ITMZ
        #   ?ID= 
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if action in ['content', 'itmz']:

            identifier = request.args.get('id')

            elements = list_notes( output_directory, identifier )

            all_attr = {}

            for element in elements:
                if 'html' in element:
                    print( f'..{element["file"]}' )
                    for tag in BeautifulSoup(element['html'], 'html.parser').find_all():
                        if tag.name in all_attr:
                            all_attr[tag.name] += tag.attrs.keys()
                        else:
                            all_attr[tag.name] = tag.attrs.keys()
                        all_attr[tag.name] = list(dict.fromkeys( all_attr[tag.name] ))

            print( f'TAGS and ATTRIBUTES: {all_attr}')

            if identifier:
                if len(elements) == 1:

                    note = get_note( elements[0] )

                    print( f'NAME {note["name"]} FOLDER {note["folder"]} HIERARCHY {note["hierarchy"]} ATTACHMENTS {note["attachments"]}\n{note["html"]}')

                    comments = note['html']
                
                else:
                    comments = f'too many pages for id {identifier}'

        else:
            comments = f'Invalid action: {action}'

        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # RESULT
        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        result = {}
        if len(catalog) > 0: result['catalog'] = catalog
        if len(elements) > 0: result['elements'] = elements
        if len(note) > 0: result['note'] = note
        if len(comments) > 0: result['comment'] = comments

        return result

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error = "Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname)
        print ( f'ERROR: {error}')
        return { 'comments': error }

# #####################################################################################################################################################################################################
# LIST_NOTES
# #####################################################################################################################################################################################################

def list_notes( dir, identifier ):
    try:

        elements = []

        base = len(os.path.normpath(dir).split(os.sep))

        for root, subdirs, files in os.walk(dir):
            for file in files:
                root_ext = os.path.splitext(file)

                if file == 'main.html':
                    element = { 
                        'object': 'page',
                        'source': 'itmz',
                        'folder': root,
                        'file': os.path.join(root, 'main.html'),
                        'indent': len(os.path.normpath(root).split(os.sep)) - base,
                        'hierarchy': os.path.relpath(root, start=output_directory).split(os.sep),
                    }
                    element['hierarchy'].pop()
                    element['hierarchy'].insert(0, 'onenote')

                    element['url'] = pathlib.Path(element['file']).as_uri()

                    with open(element['file'], 'rb') as f:
                        f_content = f.read()

                    element['html'] = f_content

                    # <meta mind="" content="">
                    # mind = ['id', 'self', 'title', 'contentUrl', 'level', 'order', 'createdDateTime', 'lastModifiedDateTime']
                    
                    soup = BeautifulSoup( f_content, features="html.parser" )

                    tag = soup.find("meta", {"mind":"title"})
                    element['name'] = tag["content"] if tag else None

                    tag = soup.find("meta", {"mind":"lastModifiedDateTime"})
                    element['date'] = tag["content"] if tag else None

                    tag = soup.find("meta", {"mind":"id"})
                    element['id'] = tag["content"] if tag else None

                    element['body'] = soup.body.prettify()

                    if element['id'] and (not identifier or element['id'] == identifier) and ('main.html' in files):

                        elements += [ element ]

        return elements  

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print ( "Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname) )
        return []

# #####################################################################################################################################################################################################
# GET_NOTE
# #####################################################################################################################################################################################################
# name          = note's title
# hierarchy     = list of folders
# folder        = location for main.html, images/ and attachments/
# url           =
# html          = content of the note (main.html)
# attchments    = list of attachments' file name

def get_note( element ):
    try:
        note = {
            'name': element['name'],
            'hierarchy': element['hierarchy'],
            'folder': element['folder'],
            'url': element['url'],
            'html': element['html'],
            'attachments': [],
        }

        # add attachments

        attachments = os.path.join( note['folder'], 'attachments')
        if os.path.exists( attachments ): 
            for root, subdirs, files in os.walk(attachments):
                for file in files:
                    note['attachments'] += [ os.path.join( root, file )]

        return note

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print ( "Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname) )
        return {}

# #####################################################################################################################################################################################################
# DOWNLOAD_ITMZ
# #####################################################################################################################################################################################################

def _download_itmz(output_directory, itmz_file=None):

    try:
        print( f'PARSE {itmz_file.upper()} FILE' )

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # read ITMZ file
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        ithoughts = zipfile.ZipFile( itmz_file, 'r')
        xmldata = ithoughts.read('mapdata.xml')
        elements = ET.fromstring(xmldata)

        # ---------------------------------------------------------------------------------------------------------------------------------------
        # get elements
        # ---------------------------------------------------------------------------------------------------------------------------------------

        itmz = []

        for element in elements.iter('topic'):

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # set mind specific
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            element.attrib['source'] = 'itmz'
            element.attrib['object'] = 'topic'
            element.attrib['file'] = itmz_file

            element.attrib['author'] = elements.attrib['author']
            
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # set hierarchy
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            def get_parents( uuid ):
                parents = elements.findall(f'.//topic[@uuid="{uuid}"]...')
                if (len(parents) > 0) and (parents[0].tag == 'topic'):
                    return get_parents( parents[0].attrib['uuid'] ) + [ parents[0].attrib['uuid'] ]
                else:
                    return []

            element.attrib['hierarchy'] = get_parents( element.attrib['uuid'] )

            element.attrib['folder'] = os.path.join( output_directory, os.sep.join( element.attrib['hierarchy'] ), element.attrib['uuid'] )

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # attachment
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            if 'att-id' in element.attrib:

                element.attrib['attachment'] = {}
            
                if 'modified' in element.attrib: element.attrib['attachment']['date']  = element.attrib['modified']
                elif 'created' in element.attrib: element.attrib['attachment']['date']  = element.attrib['created']

                element.attrib['attachment']['name'] = element.attrib['att-name'].split('.')[0]

                IMAGES_EXT = ['jpg', 'jpeg', 'gif', 'png']
                ext = element.attrib['att-name'].split('.')[1] if (len(element.attrib['att-name'].split('.')) > 1) else''
                if ext.lower() in IMAGES_EXT:
                    element.attrib['attachment']['type'] = 'image'
                else:
                    element.attrib['attachment']['type'] = 'object'

                element.attrib['attachment']['url'] = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )

                element.attrib['attachment']['filename'] = os.path.join( element.attrib['folder'], 
                                                                         'images' if element.attrib['attachment']['type'] == 'image' else 'attachments',
                                                                         element.attrib['att-name'] )
                                                    
                # move attachments

                out_dir = os.path.dirname(element.attrib['attachment']['filename'])

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                try:
                    ithoughts = zipfile.ZipFile( itmz_file, 'r')
                    data = ithoughts.read(element.attrib['attachment']['url'])

                    with open(element.attrib['attachment']['filename'], 'wb') as fs: 
                        fs.write(data) 

                    element.attrib['attachment']['processed'] = True
                except:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print("Something went wrong [{} - {}]".format(exc_type, exc_obj))

                if os.path.isfile(element.attrib['attachment']['filename']):
                    print( '{}: {} bytes'.format( element.attrib['attachment']['filename'], os.path.getsize(element.attrib['attachment']['filename']) ) )
                else:
                    print( f'missing {element.attrib["attachment"]["filename"]} file ...')

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # link
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            if 'link' in element.attrib:
                element.attrib['reference'] = {}
                element.attrib['reference']['name'] = ''

                target = re.split( r":", element.attrib['link'])
                if target[0] == 'http' or  target[0] == 'https': 
                    element.attrib['reference']['type'] = 'url'
                    element.attrib['reference']['title'] = element.attrib['link']
                    element.attrib['reference']['url'] = element.attrib['link']

                elif target[0] == 'ithoughts':
                    target = re.split( r"[?=&]+", target[1])
                    if target[0] == '//open':
                        if 'topic' in target: 
                            ref = target[target.index('topic') + 1]
                            element.attrib['reference']['type'] = 'topic'
                            element.attrib['reference']['url'] = target[target.index('topic') + 1]

                        elif 'path' in target: 
                            element.attrib['reference']['type'] = 'path'
                            element.attrib['reference']['url'] = target[target.index('path') + 1]

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # set main.html
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            if 'text' in element.attrib: 
                element.attrib['html'] = '<head></head><body>'

                # first row is H1 / title
                if element.attrib['text'][0] not in '[#`~]': element.attrib['html'] += '# '
                element.attrib['html'] += element.attrib['text']

                # convert code
                element.attrib['html'] = re.sub( r'```', '~~~', element.attrib['html'], flags = re.MULTILINE )
                #element.attrib['html'] = re.sub( r'~~~', '```', element.attrib['html'], flags = re.MULTILINE )

                # add anchors to body
                element.attrib['html'] = re.sub( r'^(?P<line>.*)', '\g<line> {#' + element.attrib['uuid'] + '}', element.attrib['html'], count = 1 )

                # convert body to html
                element.attrib['html'] = markdown.markdown( element.attrib['html'], extensions=['extra', 'nl2br'] )

                # shift headers by level in body
                #for h in range (6, 0, -1):
                #    element.attrib['body'] = re.sub( r'h' + str(h) + r'>', 'h{}>'.format(h+level+1), element.attrib['body'], flags = re.MULTILINE )

                # add attachment to body
                if 'attachment' in element.attrib:
                    if element.attrib['attachment']['type'] in ['image']:
                        tag = '\n<img src="{}" title="{}" width="1000" />'
                        element.attrib['html'] += tag.format( element.attrib['attachment']['url'], element.attrib['attachment']['name'] )

                    elif element.attrib['attachment']['type'] in ['object']:
                        tag= '\n<object data="{}" data-attachment="{}" type="application/{}" target="_blank" width="1000"></object>'
                        ext = os.path.basename(element.attrib['attachment']['filename']).split('.')
                        element.attrib['html'] += tag.format( element.attrib['attachment']['url'],  
                                                       os.path.basename(element.attrib['attachment']['filename']),
                                                       ext[1].lower() if len(ext) > 1 else 'pdf' )
                    if element.attrib['attachment']['filename']:
                        element.attrib['html'] = element.attrib['html'].replace( element.attrib['attachment']['url'], 
                                                                   element.attrib['attachment']['filename']
                                                                 )
                # add reference to body
                if 'reference' in element.attrib:
                    if element.attrib['reference']['type'] in ['url', 'topic', 'path']:
                        tag= '\n<a href="{}" {} target="_blank" width="1000">{}</a>'
                        element.attrib['html'] += tag.format( element.attrib['reference']['url'], 
                                                              'class="btn btn-default fa-solid fa-link"', 
                                                              element.attrib['reference']['name'] )


                # add task information to body
                # tabulate
                # table by row
                # header
                task_table = {}
                task = { 'task-start': 'Start', 'task-due': 'Due', 'cost': 'Cost', 'task-effort': 'Effort', 
                        'task-priority': 'Priority', 'task-progress': 'Progress', 'resources': 'Resource(s)' }
                for key, value in task.items():
                    if key in element and element.attrib[key] and (element.attrib[key] == element.attrib[key]):
                        if key == 'task-progress':
                            if element.attrib[key][-1] != "%": 
                                if int(element.attrib[key]) > 100: continue
                                element.attrib[key] += '%'
                        if key == 'task-effort' and element.attrib[key][0] == '-': continue
                        task_table[value] = [ element.attrib[key] ]

                if len(task_table) > 0: 
                    element.attrib['html'] += "\n\n"
                    element.attrib['html'] += tabulate( task_table, headers="keys", tablefmt="html" )

                element.attrib['html'] += '</body>'

                # retrieve title
                soup = BeautifulSoup( element.attrib['html'], features="html.parser" )
                if soup.h1:
                    element.attrib['title'] = soup.h1.text

                # add meta tag related to mind: 
                # <meta mind="[source, object, id, folder, createdDateTime, lastModifiedDateTime, url]" content="">

                meta_list = [{ 'tag': 'source', 'content': 'itmz'}]
                for tag in ['uuid', 'title', 'author', 'created', 'modified']:
                    if tag in element.attrib: meta_list += [{ 'tag': tag, 'content':element.attrib[tag]}]
                meta_list += [{ 'tag': 'folder', 'content': element.attrib['folder']}]

                for meta in meta_list:
                    metatag = soup.new_tag('meta')
                    metatag.attrs['content'] = meta['content']
                    metatag.attrs['mind'] = meta['tag']
                    soup.head.append(metatag)

                # clean tags

                blacklist=['style', 'lang', 'data-absolute-enabled', 'span', 'p',  'data-src-type', 'data-render-original-src', 'data-index', 'data-options', 'data-attachment', 'data-id', 'height', 'width']
                whitelist=['href', 'alt']

                for tag in soup.findAll(True):
                    for attr in [attr for attr in tag.attrs if( attr in blacklist and attr not in whitelist)]:
                        del tag[attr]
                    if tag.name in blacklist and tag.name not in whitelist:
                        tag.unwrap()

                content = str(soup)
                element.attrib['body'] = str(soup.body)

                out_html = os.path.join( element.attrib['folder'], 'main.html')
                os.makedirs( element.attrib['folder'], exist_ok=True )

                with open(out_html, "w", encoding='utf-8') as f:
                    f.write(content)

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # done
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            print( f'\nELEMENT: {element.attrib}')

            itmz += [ element.attrib ]

        print( f'Nb of ITMZ elements = {len(itmz)}' )

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))
