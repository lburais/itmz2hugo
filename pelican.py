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
#   ├── pages
#   |   ├── [page1].html
#   |   |       external --> url
#   |   |       internal in --> {filename}#[uuid]
#   |   |       internal out --> {filename}[filenamex].html#[ref]
#   |   └── [page2].html --> {filename}[filename2].html
#   ├── [top]
#   |   ├── [page1]
#   |   |   └── [post1.1] --> {static}/attachments/[filename1]/[attachment1]
#   |   └── [page2]
#   |       └── [post2.1] --> {static}/attachments/[filename2]/[attachment2]

#   ├── attachments
#   |   ├── [filename1]
#   |   |   └── [attachment1] --> {static}/attachments/[filename1]/[attachment1]
#   |   └── [filename2]
#   |       └── [attachment2] --> {static}/attachments/[filename2]/[attachment2]
#   └── pelican.conf.py
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

            soup = BeautifulSoup(element['body'] if element['body'] else '<body></body>', features="html.parser")

            text += str( soup )

            # -------------------------------------------------------------------------------------------------------------------------------------------
            # write html
            # -------------------------------------------------------------------------------------------------------------------------------------------

            element['pelican'] = os.path.join( folder_site, element['type']+'s', element['slug'] + '.html' )
            out_dir = os.path.dirname(element['pelican'])

            myprint('> ' + element['pelican'])

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(element['nikola'], 'w', encoding='utf-8') as fs:
                fs.write(text) 

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            myprint("write error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...') 

        return element

    myprint( '', line=True, title='PELICAN')

    try:

        cond = elements['publish']
        cond &= ~elements['body'].isna()
        myprint( 'Processing {} elements to Pelican'.format(len(elements[cond])))
        #elements[cond] = elements[cond].apply(_write_element, axis='columns')

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