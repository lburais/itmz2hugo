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

from datetime import datetime as dt

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

        myprint( files )

        for file in files:

            myprint( file, prefix='>')

            # read ITMZ file
            ithoughts = zipfile.ZipFile( file, 'r')
            xmldata = ithoughts.read('mapdata.xml')
            elements = ET.fromstring(xmldata)

            itmz = empty_elements()

            # get elements
            for element in elements.iter('topic'):
                itmz_objects = pd.DataFrame( element.attrib, index=['i',] )
                col_list = {}
                for col in itmz_objects.columns.to_list():
                    col_list[col] = 'itmz_{}'.format(col)
                itmz_objects.rename( columns=col_list, inplace=True )
                itmz_objects['itmz_file'] = file

                itmz = pd.concat( [ itmz, itmz_objects ], ignore_index=True )

            myprint( '{} elements loaded'.format( len(itmz) ) )

            _elements = pd.concat( [ _elements, itmz ], ignore_index=True )

        _elements['source'] = 'itmz'
        _elements['what'] = 'topic'

        myprint( 'Nb elements = {}'.format(len(_elements)) )

        save_excel(directory, _elements, 'itmz elements')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get content
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # link
        # myprint( '', line=True, title='GET ITMZ CONTENTS')

        # save_excel(directory, _elements, 'itmz contents')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _get_resource( element ):
            resources = []
            if element['itmz_att-id']:

                resource = { 'type': None, 'name': None, 'url': None, 'parent': None, 'filename': None, 'date': None }

                if ('itmz_created' in element) and (element['itmz_created'] == element['itmz_created']): 
                    resource['date']  = element['itmz_created']
                if ('itmz_modified' in element) and (element['itmz_modified'] == element['itmz_modified']): 
                    resource['date']  = element['itmz_modified']

                resource['name'] = os.path.splitext(element['itmz_att-name'])[0]

                resource['type'] = os.path.splitext(element['itmz_att-name'])[1]

                resource['url'] = os.path.join( "assets", element['itmz_att-id'], element['itmz_att-name'] )

                resource['filename'] = os.path.join( _files_directory, 
                                                     element['itmz_file'],
                                                     element['itmz_att-id'],
                                                     element['itmz_att-name'] )

                return resource
            else:
                return nan

        if 'itmz_att-id' in _elements:
            myprint( '', line=True, title='GET ITMZ RESOURCES')

            if 'resources' not in _elements.columns.to_list():
                _elements['resources'] = nan

            cond = (~_elements['itmz_att-id'].isna())
            cond = (~_elements['itmz_att-name'].isna())
            cond &= (_elements['resources'].isna())

            myprint( 'Parsing {} contents'. format(len(_elements[cond])))

            _elements.loc[cond, 'resources'] = _elements[cond].apply(_get_resource, axis='columns')

            cond = (~_elements['itmz_att-id'].isna())
            cond = (~_elements['itmz_att-name'].isna())
            cond &= (_elements['resources'].isna())

            if len(_elements[cond]) > 0: myprint( '.. missing {} contents'. format(len(_elements[cond])))       
                
            save_excel(directory, _elements, 'itmz resources')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # get links
        # -------------------------------------------------------------------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set parent
        # -------------------------------------------------------------------------------------------------------------------------------------------
        
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set childs
        # -------------------------------------------------------------------------------------------------------------------------------------------
        
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set path and tags
        # -------------------------------------------------------------------------------------------------------------------------------------------
        
        # -------------------------------------------------------------------------------------------------------------------------------------------
        # expand data
        # -------------------------------------------------------------------------------------------------------------------------------------------
        
        # self._merge_elements()

        # save_excel(directory, self.onenote_elements, 'data')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # set body
        # -------------------------------------------------------------------------------------------------------------------------------------------

        def _body( element ):
            # convert markdown to html
            if (element['itmz_text'] == element['itmz_text']):

                element['body'] = markdown.markdown( element['itmz_text'] )
                
            if (element['resources'] == element['resources']):
            #     # resources
            #     # ---------
            #     # replace url by file
            #     if element['resources'] == element['resources']:
            #         for resource in json.loads(element['resources']):
            #             if resource['filename']:
            #                 element['body'] = element['body'].replace(resource['url'], resource['filename'])
                pass

            if element['itmz_link']:
                pass

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

        # _elements['what'] set above from _get function
        _elements['id'] = _elements['itmz_uuid']

        #_elements['title'] = _elements['onenote_title']
        #_elements.loc[_elements['title'].isna(), 'title'] = _elements['onenote_displayName']

        _elements['created'] = _elements['itmz_created']
        _elements['modified'] = _elements['itmz_modified']

        #_elements['authors'] = _elements['lastModifiedDateTime']

        # _elements['parent'] set above
        # _elements['body'] set above
        # _elements['resources'] set above

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # load resources
        # -------------------------------------------------------------------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # save excel
        # -------------------------------------------------------------------------------------------------------------------------------------------

        save_excel(directory, _elements, 'itmz')

        # -------------------------------------------------------------------------------------------------------------------------------------------
        # completed
        # -------------------------------------------------------------------------------------------------------------------------------------------

        return _elements

