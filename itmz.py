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

import re
import os
import sys
import pathlib
import shutil

from datetime import datetime as dt

from bs4 import BeautifulSoup   

from flask import request

#from mytools import *

import xml.etree.ElementTree as ET
import zipfile
import markdown
from tabulate import tabulate
from urllib.parse import urlparse

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

        if action in ['parse', 'catalog', 'itmz']:

            if os.path.isdir( itmz_source ):
                for root, dirs, filenames in os.walk( itmz_source, topdown=True ):
                    for file in filenames:
                        if os.path.splitext(file)[1] == '.itmz': 
                            catalog += [ { 'source': 'itmz', 'object': 'file', 'name': os.path.splitext(file)[0], 'file': os.path.join(root, file), 'url': f'file={os.path.join(root, file)}' } ]

            # add command to parse all notebooks        
            if len(catalog) > 0:
                catalog.insert( 0, { 'source': 'itmz', 'object': 'file', 'name': ALL_MAPS, 'url': 'file={}'.format( ALL_MAPS ) } )

        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # ITMZ
        #   ?FILE=
        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # parse file aka. create local structure

        if action in ['parse', 'itmz']:

            itmz_files = request.args.get('file')

            if itmz_files and itmz_files in [ALL_MAPS]: itmz_files = None

            if itmz_files:
                itmz_files = [ itmz_files ]
            else:
                itmz_files = []
                for cat in catalog:
                    if 'file' in cat: itmz_files += [ cat['file'] ]
            
            for itmz_file in itmz_files:
                _download_itmz( itmz_file )

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # ITMZ
        #   ?ID= 
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # list local content

        if action in ['content', 'itmz']:

            identifier = request.args.get('id')

            elements = list_notes( output_directory, identifier )

            if identifier:
                if len(elements) == 1:

                    note = get_note( elements[0] )

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
                        'object': 'topic',
                        'source': 'itmz',
                        'folder': root,
                        'file': os.path.join(root, 'main.html'),
                        'indent': len(os.path.normpath(root).split(os.sep)) - base,
                        'hierarchy': os.path.relpath(root, start=output_directory).split(os.sep),
                    }
                    element['hierarchy'].pop()
                    element['hierarchy'].insert(0, 'itmz')

                    element['url'] = pathlib.Path(element['file']).as_uri()

                    with open(element['file'], 'rb') as f:
                        f_content = f.read()

                    element['html'] = f_content

                    # <meta mind="" content="">
                    # mind = ['id': 'uuid', 'name': 'title', 'date': 'modified']
                    
                    soup = BeautifulSoup( f_content, features="html.parser" )

                    tag = soup.find("meta", {"mind":"title"})
                    element['name'] = tag["content"] if tag else None

                    tag = soup.find("meta", {"mind":"modified"})
                    element['date'] = tag["content"] if tag else None

                    tag = soup.find("meta", {"mind":"uuid"})
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

def _download_itmz(itmz_file, force=True):
    global output_directory

    try:
        print( f'PARSE {itmz_file.upper()} FILE' )

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # read ITMZ file
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if os.path.exists( itmz_file ):
            ithoughts = zipfile.ZipFile( itmz_file, 'r')
            xmldata = ithoughts.read('mapdata.xml')
            elements = ET.fromstring(xmldata)
        else:
            print( f'INVALID FILE {itmz_file.upper()}')
            return

        # ---------------------------------------------------------------------------------------------------------------------------------------
        # set structure
        # ---------------------------------------------------------------------------------------------------------------------------------------

        out_dir = os.path.join(output_directory, '[itmz] ' + os.path.splitext(os.path.basename(itmz_file))[0])
        if force: shutil.rmtree( out_dir, ignore_errors=True )
        os.makedirs( out_dir, exist_ok=True )

        # ---------------------------------------------------------------------------------------------------------------------------------------
        # parse elements
        # ---------------------------------------------------------------------------------------------------------------------------------------

        itmz = []

        for element in elements.iter('topic'):
            if 'text' in element.attrib: 

                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # set mind specific
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                element.attrib['source'] = 'itmz'
                element.attrib['object'] = 'topic'
                element.attrib['file'] = itmz_file

                element.attrib['title'] = element.attrib['uuid']
                
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # set main.html
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                element.attrib['html'] = '<head></head><body>'

                md = ''
                
                # first row is H1 / title
                if element.attrib['text'][0] not in '[#`~]': md += '# '
                md += element.attrib['text']

                # convert code
                md = re.sub( r'```', '~~~', md, flags = re.MULTILINE )
                #md = re.sub( r'~~~', '```', md, flags = re.MULTILINE )

                # add anchors
                md = re.sub( r'^(?P<line>.*)', '\g<line> {#' + element.attrib['uuid'] + '}', md, count = 1 )

                # convert body to html
                element.attrib['html'] += markdown.markdown( md, extensions=['extra', 'nl2br'] )

                print( element.attrib['html'][:132] )

                # shift headers by level in body
                #for h in range (6, 0, -1):
                #    element.attrib['body'] = re.sub( r'h' + str(h) + r'>', 'h{}>'.format(h+level+1), element.attrib['body'], flags = re.MULTILINE )

                # retrieve title
                soup = BeautifulSoup( element.attrib['html'], features="html.parser" )
                if soup.h1:
                    element.attrib['title'] = soup.h1.text

                element.attrib['html'] += '</body>'

                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # attachment
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                if 'att-id' in element.attrib:

                    soup = BeautifulSoup( element.attrib['html'], features="html.parser" )

                    att_split = os.path.splitext( os.path.basename( element.attrib['att-name'] ))

                    element.attrib['att-asset'] = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )

                    if len(att_split) > 1 and att_split[1].lower() in ['.jpg', '.jpeg', '.gif', '.png']:
                        tag = soup.new_tag('img')
                        element.attrib['att-relative'] = os.path.join( 'images', element.attrib['att-name'] )
                        tag.attrs['src'] = element.attrib['att-relative']
                        tag.attrs['title'] = att_split[0]
                    else:
                        tag = soup.new_tag('object')
                        element.attrib['att-relative'] = os.path.join( 'attachments', element.attrib['att-name'] )
                        tag.attrs['data'] = element.attrib['att-relative']
                        #tag.attrs['data'] = element.attrib['att-asset']
                        #tag.attrs['data-attachment'] = element.attrib['att-relative']
                        tag.attrs['type'] = "application/{}".format( att_split[1].lower()[1:] if len(att_split) > 1 else 'pdf' )
                        #tag.attrs['target'] = "_blank"

                    soup.body.append(soup.new_tag('br'))
                    soup.body.append(tag)

                    element.attrib['html'] = str(soup)

                    element.attrib['html'] = element.attrib['html'].replace( element.attrib['att-asset'], element.attrib['att-relative'] )

                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # link
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                if 'link' in element.attrib:

                    soup = BeautifulSoup( element.attrib['html'], features="html.parser" )

                    tag = soup.new_tag('a')
                    tag.attrs['target'] = "_blank"

                    target = urlparse( element.attrib['link'] )
                    # scheme://netloc/path;parameters?query#fragment
                    if target.scheme in ['ithoughts']:
                        # MAY NEED TO REWORK WHEN SCHEME IS ITHOUGHTS 
                        pass
                    
                    tag.attrs['href'] = element.attrib['link']

                    soup.body.append(soup.new_tag('br'))
                    soup.body.append(tag)

                    element.attrib['html'] = str(soup)

                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # task information
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                # tabulate
                # table by row
                # header

                soup = BeautifulSoup( element.attrib['html'], features="html.parser" )

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
                    soup.body.append(soup.new_tag('br'))
                    soup.body.append(soup.new_tag('br'))
                    soup.body.append( BeautifulSoup( tabulate( task_table, headers="keys", tablefmt="html" ), features="html.parser" ))

                    print( soup.prettify() )
                    element.attrib['html'] = str(soup)

                # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # clean tags
                # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                soup = BeautifulSoup( element.attrib['html'], features="html.parser" )

                blacklist = ['span', 'p', 'link', 'style', 'script', 'meta', 'svg', 'nav', 'header', 'footer']
                blacklist += ['style', 'lang', 'class', 'height', 'width']
                blacklist += ['data-absolute-enabled', 'data-src-type', 'data-render-original-src', 'data-index', 'data-options', 'data-attachment', 'data-id']
                whitelist=['href', 'alt', 'src', 'title', 'data', 'target', 'type', 'content', 'mind']

                for tag in soup.findAll(True):
                    for attr in [attr for attr in tag.attrs if( attr in blacklist and attr not in whitelist)]:
                        del tag[attr]
                    if tag.name in blacklist and tag.name not in whitelist:
                        tag.unwrap()

                element.attrib['html'] = str(soup)
                element.attrib['body'] = str(soup.body)

                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # mind meta tags
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # <meta mind="[source, object, id, folder, createdDateTime, lastModifiedDateTime, url]" content="">

                soup = BeautifulSoup( element.attrib['html'], features="html.parser" )

                metatag = soup.new_tag('meta')
                metatag.attrs['content'] = "text/html; charset=utf-8"
                metatag.attrs['http-equiv'] = "Content-Type"
                soup.head.insert( 0, metatag )

                meta_list = [{ 'tag': 'source', 'content': 'itmz'}]
                for tag in ['uuid', 'title', 'author', 'created', 'modified']:
                    if tag in element.attrib: meta_list += [{ 'tag': tag, 'content':element.attrib[tag]}]
                #meta_list += [{ 'tag': 'folder', 'content': element.attrib['folder']}]

                for meta in meta_list:
                    metatag = soup.new_tag('meta')
                    metatag.attrs['content'] = meta['content']
                    metatag.attrs['mind'] = meta['tag']
                    soup.head.append(metatag)

                element.attrib['html'] = str(soup)

                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # done
                # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                itmz += [ element.attrib ]

        # print( 'ELEMENTS: {}'.format("\n".join( [ d["folder"] for d in itmz ] )))

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # set hierarchy and folder
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # need to have title set first

        for element in itmz:

            element['folder'] = ''

            def get_parents_title( uuid ):
                parents = elements.findall(f'.//topic[@uuid="{uuid}"]...')
                if (len(parents) > 0) and (parents[0].tag == 'topic'):
                    return get_parents_title( parents[0].attrib['uuid'] ) + [ parents[0].attrib['title' if 'title' in parents[0].attrib else 'uuid'] ]
                else:
                    return []

            element['hierarchy'] = get_parents_title( element['uuid'] )

            element['folder'] = os.path.join( out_dir, os.sep.join( element['hierarchy'] ), element['title'] )

            while os.path.exists( element['folder'] ):
                element['hierarchy'] += [ 'sub' ] 
                element['folder'] = os.path.join( out_dir, os.sep.join( element['hierarchy'] ), element['title'] )

            # print( f'HIERARCHY\n\t{element["hierarchy"]}\n\t{element["title"]}\n\t{element["folder"]}')

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # write attachment
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            if 'att-id' in element:

                try:
                    out_file = os.path.join(element['folder'], element['att-relative'])

                    os.makedirs( os.path.dirname(out_file), exist_ok=True )

                    ithoughts = zipfile.ZipFile( itmz_file, 'r')
                    data = ithoughts.read(element['att-asset'])

                    with open(out_file, 'wb') as fs: 
                        fs.write(data) 
                except:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print("Something went wrong [{} - {}]".format(exc_type, exc_obj))
                    print( f'ERROR\n\t{element["hierarchy"]}\n\t{element["folder"]}\n\t{element["att-relative"]}\n\t{element["att-asset"]}' )

                if not os.path.isfile(out_file): print( f'missing {out_file} file ...')
                # else: print( '{}: {} bytes'.format( out_file, os.path.getsize(out_file) ) )

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # write html
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            if 'html' in element:

                try:
                    out_html = os.path.join( element['folder'], 'main.html')
                    os.makedirs( element['folder'], exist_ok=True )

                    with open(out_html, "w", encoding='utf-8') as f:
                        f.write(element['html'])
                except:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    print("Something went wrong [{} - {}]".format(exc_type, exc_obj))
                    print( f'ERROR\n\t{element["hierarchy"]}\n\t{element["folder"]}' )

                if not os.path.isfile(out_html): print( f'missing {out_html} file ...')
                # else: print( '{}: {} bytes'.format( out_html, os.path.getsize(out_html) ) )

            # print( f'\nELEMENT: {element}')

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # check duplicates
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        itmz = sorted(itmz, key=lambda d: d['folder']) 

        # print( 'FOLDERS: {}\n'.format("\n".join( [ d["folder"] for d in itmz ] )))

        folders = []
        for element in itmz:
            folders += [ element['folder'] ]
            if folders.count( element['folder'] ) > 1:
                print( f'DUPLICATED : {element["folder"]}')

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))
