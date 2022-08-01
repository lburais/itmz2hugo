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

# ###################################################################################################################################################
# WRITE
# ###################################################################################################################################################

def write( directory, elements=empty_elements() ):

    _elements = element.copy()
    _elements['nikola'] = nan

    _folder_site = os.path.join(directory, 'nikola')

    _folder_images = os.path.join(_folder_site, 'images')
    _folder_objects = os.path.join(_folder_site, 'objects')

    def _write_element( element ):

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # header
        # -------------------------------------------------------------------------------------------------------------------------------------------

        text = '<head>\n'

        if 'title' in element: text += '\t<title>{}</title>\n'.format(element['title'])

        for key in element:
            if key in ['id']:
                text += '\t<meta name="{}" content="{}" />\n'.format(key, 'value')

        if 'tags' in element: text += '\t<meta name="{}" content="{}" />\n'.format(key, ', '.join(value))

        text += '</head>\n'

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # body
        # -------------------------------------------------------------------------------------------------------------------------------------------

        soup = BeautifulSoup(element['body'] if element['body'] else '<body></body>', features="html.parser")

        # add child posts
        # if element['what'] in ['notebook', 'section', 'group']: 
        #     if 'slug' in element:
        #         tag = soup.new_tag('div')
        #         tag.string = "{{% post-list tags=" + "{}".format(element['slug']) + " %}}{{% /post-list %}}"
        #         soup.body.append(tag)

        # add struture
        # tag = soup.new_tag('code')
        # tmp = dict(element[ELEMENT_COLUMNS])
        # if 'body' in tmp: del tmp['body']
        # tag.string = pprint.pformat(tmp)
        # del tmp
        # soup.body.append(tag)

        # done
        text += str( soup )

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # write html
        # -------------------------------------------------------------------------------------------------------------------------------------------

        elements['nikola'] = os.path.join( folder_site, 'posts', element['slug'] + '.html' )
        out_dir = os.path.dirname(elements['nikola'])

        print('> ' + elements['nikola'])

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        with open(elements['nikola'], 'w', encoding='utf-8') as fs:
            fs.write(text) 

    myprint( '', line=True, title='NIKOLA')

    try:

        _elements = _elements.apply(_write_element, axis='columns')

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        myprint("Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname), prefix='...') 

    return _elements   

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