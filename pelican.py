# ###################################################################################################################################################
# Filename:     pelican.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# ###################################################################################################################################################
# Pelican structure
# -----------------
#   content
#   ├── [top 1]
#   |   ├── pages
#   |   |   ├── [top 1] 
#   |   |   |   ├── [top 1].html
#   |   |   |   └── [top 1 attachment 1].[ext]
#   |   |   ├── [page 1] 
#   |   |   |   ├── [page 1].html
#   |   |   |   ├── [page 1 attachment 1].[ext]
#   |   |   |   └── [page 1.1] 
#   |   |   |       ├── [page 1.1].html
#   |   |   |       ├── [page 1.1 attachment 1].[ext] 
#   |   |   |       └── [page 1.1.1] 
#   |   |   |               ├── [page 1.1.1].html
#   |   |   |               └── [page 1.1.1 attachment 1].[ext]
#   |   |   └── [page2] 
#   |   |       └── [page 2].html
#   |   |       └── [page 2 attachment 1].[ext]
#   |   ├── posts
#   |   |   └── [top 1]
#   |   |   |   ├── [top 1 post 1].html
#   |   |   |   └── [top 1 post 1 attachment 1].[ext]
#   |   |   ├── [page 1] 
#   |   |   |   ├── [page 1 post 1].html
#   |   |       └── [page 1 post 1 attachment 1].[ext]
#   ├── attachments
#   |   ├── [attachment 1] --> {static}/attachments/[attachment 1]
#   |   └── [attachment 2] --> {static}/attachments/[attachment 2]
#   └── pelican.conf.py
#           PATH = 'content'
#           PAGE_PATHS = ['[top 1]/pages']
#           ARTICLE_PATHS = ['[top 1]/posts']
#           STATIC_PATHS = ['attachments']
# ###################################################################################################################################################

import os
import sys
import shutil

from bs4 import BeautifulSoup

# pip3 install pandas
import pandas as pd

from mytools import *

MAPPING = {
    'title': None,
    'slug': 'slug',
    'date': 'created',
    'tags': None,
    'status': 'published',
    'has_math': None,
    'category': None,
    'guid': None,
    'link': None,
    'description': None,
    'type': None,
    'author': 'authors',
    'enclosure': None,
    'data': None,
    'filters': None,
    'hidetitle': None,
    'hyphenate': None,
    'nocomments': None,
    'pretty_url': None,
    'previewimage': None,
    'template': None,
    'updated': 'modified',
    'url_type': None,
}

# ###################################################################################################################################################
# GET FILENAME
# ###################################################################################################################################################

def get_filename( directory, type, path, file ):
    # directory: /Volumes/library/Development/jamstack/site
    # path: [notebook, group, group, section, page, page]
    # type: PAGE | POST | ATTACHMENT | STATIC
    # file: filename
    # return tupple:
    #   computer filename
    #   pelican link
    filename = directory
    root = path[0]
    if type.lower() in ['PAGE']:
        filename = os.join( filename, 'content', root, 'pages')
    elif type.lower() in ['POST']:
        filename = os.join( filename, 'content', 'pages')
    elif type.lower() in ['PAGE']:
        filename = os.join( filename, 'content', 'pages')
    elif type.lower() in ['PAGE']:
        filename = os.join( filename, 'content', 'pages')
    else:
        pass

# ###################################################################################################################################################
# GET FILE
# ###################################################################################################################################################

def get_file( element ):
    # get the header + body
    pass

# ###################################################################################################################################################
# WRITE
# ###################################################################################################################################################

def write( directory, elements=empty_elements() ):

    elements['pelican'] = nan

    folder_site = os.path.join(directory, 'pelican')

    def _write_element( element ):
        nonlocal folder_site

        try:

            # -------------------------------------------------------------------------------------------------------------------------------------------
            # header
            # -------------------------------------------------------------------------------------------------------------------------------------------

            text = '<head>\n'

            if 'title' in element: text += '\t<title>{}</title>\n'.format(element['title'])

            # metadata
            for key, val in MAPPING.items():
                if val:
                    if val in elements: text += '\t<meta name="{}" content="{}" />\n'.format(key, element[val])
                    else: text += '\t<meta name="{}" content="{}" />\n'.format(key, val)

            text += '</head>\n'

            # -------------------------------------------------------------------------------------------------------------------------------------------
            # body
            # -------------------------------------------------------------------------------------------------------------------------------------------

            soup = BeautifulSoup(element['body'] if element['body'] == element['body'] else '<body></body>', features="html.parser")

            text += str( soup )

            # -------------------------------------------------------------------------------------------------------------------------------------------
            # resources
            # -------------------------------------------------------------------------------------------------------------------------------------------

            # if 'onenote_id' in elements and 'onenote_resources' in elements and 'onenote_self' in elements and 'onenote_file_name' in elements:
            #     resources = elements[ elements['onenote_id'].isin(row['onenote_resources'].split(',')) ]
            #     resources = dict(zip(resources['onenote_self'].str.replace('/content','/$value'), resources['onenote_file_name']))
            #     for url, name in resources.items():
            #         body = body.replace( url, name )

            # -------------------------------------------------------------------------------------------------------------------------------------------
            # write html
            # -------------------------------------------------------------------------------------------------------------------------------------------

            element['pelican'] = element['id'].split('!')
            element['pelican'].reverse()
            element['pelican'] = os.path.join( folder_site, 'content', element['type']+'s', os.path.sep.join(element['pelican']), element['slug'] + '.html' )
            out_dir = os.path.dirname(element['pelican'])

            myprint('> ' + element['pelican'])

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(element['pelican'], 'w', encoding='utf-8') as fs:
                fs.write(text) 

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            myprint("write error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...') 

        return element

    myprint( '', line=True, title='PELICAN')

    try:

        cond = elements['publish']
        cond &= elements['type'].isin(['post', 'page'])
        # cond &= ~elements['body'].isna()
        myprint( 'Processing {} elements to Pelican'.format(len(elements[cond])))
        elements[cond] = elements[cond].apply(_write_element, axis='columns')

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Pelican went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...') 

    return elements   

# ###################################################################################################################################################
# CLEAR
# ###################################################################################################################################################

def clear( directory ): 

    myprint( '', line=True, title='CLEAR PELICAN FILES')

    _directory = os.path.join( directory, 'pelican' )

    if os.path.isdir(_directory):
        myprint( 'Removing {}...'.format(_directory), prefix='>' )
        shutil.rmtree(_directory)
        os.makedirs(_directory)