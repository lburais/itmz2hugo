# ###################################################################################################################################################
# Filename:     nikola.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# ###################################################################################################################################################
# Nikola structure
# -----------------
#   content
#   ├── pages
#   |   ├── [filename1].html
#   |   |       external --> url
#   |   |       internal in --> {filename}#[uuid]
#   |   |       internal out --> {filename}[filename].html#[ref]
#   |   └── [filename2].html --> {filename}[filename2].html
#   ├── posts
#   |   ├── [filename3].html
#   |   |       external --> url
#   |   |       internal in --> {filename}#[uuid]
#   |   |       internal out --> {filename}[filenamex].html#[ref]
#   |   └── [filename4].html --> {filename}[filename2].html
#   ├── files
#   |   └── objects
#   |       └── [tag 1]
#   |           ├── [object1] --> /objects/[tag1]/[object1]
#   |           └── [tag 2]
#   |               └── [object2] --> /objects/[tag1]/[tag2]/[object2]
#   └── conf.py
#           PATH = 'content'
#           PAGE_PATHS = ['pages']
#           ARTICLE_PATHS = ['articles']
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
# WRITE
# ###################################################################################################################################################

def write( directory, elements=empty_elements() ):

    elements['nikola'] = nan

    folder_site = os.path.join(directory, 'nikola')

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

            soup = BeautifulSoup(element['body'] if element['body'] else '<body></body>', features="html.parser")

            text += str( soup )

            # -------------------------------------------------------------------------------------------------------------------------------------------
            # write html
            # -------------------------------------------------------------------------------------------------------------------------------------------

            element['nikola'] = os.path.join( folder_site, element['type']+'s', element['slug'] + '.html' )
            out_dir = os.path.dirname(element['nikola'])

            myprint('> ' + element['nikola'])

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(element['nikola'], 'w', encoding='utf-8') as fs:
                fs.write(text) 

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            myprint("write error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...') 

        return element

    myprint( '', line=True, title='NIKOLA')

    try:

        cond = elements['publish']
        cond &= ~elements['body'].isna()
        myprint( 'Processing {} elements to Nikola'.format(len(elements[cond])))
        elements[cond] = elements[cond].apply(_write_element, axis='columns')

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Nikola went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...') 

    return elements   

# ###################################################################################################################################################
# CLEAR
# ###################################################################################################################################################

def clear( directory ): 

    myprint( '', line=True, title='CLEAR NIKOLA FILES')

    _directory = os.path.join( directory, 'nikola' )

    if os.path.isdir(_directory):
        myprint( 'Removing {}...'.format(_directory), prefix='>' )
        shutil.rmtree(_directory)
        os.makedirs(_directory)