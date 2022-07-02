"""
Filename:    onenote.py

- Author:      [Laurent Burais](mailto:lburais@cisco.com)
- Release:
- Date:

Dependencies:

* TBC

Run:

python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
pip3 install requests,flask,flask_session,msal,markdownify
python3 onenote.py
"""

import json
import requests
import re
import os
import time

from bs4 import BeautifulSoup

import pprint

# #################################################################################################################################
# GLOBAL VARIABLES
# #################################################################################################################################

# #################################################################################################################################
# INTERNAL FUNCTIONS
# #################################################################################################################################

def slugify( value ):

    # remove invalid chars (replaced by '-')
    value = re.sub( r'[<>:"/\\|?*^%]', '-', value, flags=re.IGNORECASE )

    # remove non-alphabetical/whitespace/'-' chars
    value = re.sub( r'[^\w\s-]', '', value, flags=re.IGNORECASE )

    # replace whitespace by '-'
    value = re.sub( r'[\s]+', '-', value, flags=re.IGNORECASE )

    # lower case
    value = value.lower()

    # reduce multiple whitespace to single whitespace
    value = re.sub( r'[\s]+', ' ', value, flags=re.IGNORECASE)

    # reduce multiple '-' to single '-'
    value = re.sub( r'[-]+', '-', value, flags=re.IGNORECASE)

    # strip
    value = value.strip()

    return value  

# #################################################################################################################################
# ONENOTE ALL
# #################################################################################################################################

def onenote_all( token, force=False ):

    elements = []

    out_file = os.path.join( os.path.dirname(__file__), 'onenote', 'onenote.json' )
    
    # load from json

    if not force and os.path.isfile(out_file):
        try:
            print("LOAD")
            out_fp = open(out_file, "r")
            elements = json.load( out_fp )
            out_fp.close()
        except:
            raise        
    
    if len(elements) == 0:
        print("GET")
        elements = onenote_process( token=token, what='notebook', url='' )

    # dump as json

    out_file = os.path.join( os.path.dirname(__file__), 'onenote', 'onenote.json' )
    out_dir = os.path.dirname(out_file)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    try:
        out_fp = open(out_file, "w")
        json.dump( elements, out_fp, indent=2 )
        out_fp.close()
    except:
        pass

    return elements

# #################################################################################################################################
# ONENOTE PROCESS
# #################################################################################################################################

def onenote_process( token, what='notebook', url='', force=False ):
    run = True
    elements = []

    if url == '':
        #if what == 'notebook': url='https://graph.microsoft.com/v1.0/me/onenote/notebooks/0-34CFFB16AE39C6B3!335975'
        if what == 'notebook': url='https://graph.microsoft.com/v1.0/me/onenote/notebooks'
        elif what == 'section': url='https://graph.microsoft.com/v1.0/me/onenote/sections'
        elif what == 'group': url='https://graph.microsoft.com/v1.0/me/onenote/sectionGroups'
        elif what == 'page': url='https://graph.microsoft.com/v1.0/me/onenote/pages'
        elif what == 'resource': url='https://graph.microsoft.com/v1.0/me/onenote/resources'
        else: run = False

    while run:
        retry = 2

        while retry > 0:
            onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} ).json()

            if 'error' in onenote_response:
                print( '[{0:<8}] error: {1} - {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
                if onenote_response['error']['code'] == "20166":
                    print( "... sleep ...") 
                    time.sleep( 60.0 )
                    retry -= 1
                else:
                    retry = 0
                    break
            else:
                retry = 0
                break

        if 'error' in onenote_response:
            run = False
        else:
            if 'value' in onenote_response: onenote_objects = onenote_response['value']
            else: onenote_objects = [ onenote_response ]

            for onenote_object in onenote_objects:
                if 'contentUrl' in onenote_object:
                    onenote_object['content'] = requests.get( onenote_object["self"] + "/$value", headers={'Authorization': 'Bearer ' + token} )

                element = onenote_element(onenote_object, what)

                # process resources
                if 'resources' in element:
                    for resource in element['resources']:
                        print( 'retrieving {}...'.format(resource['url']))
                        out_file = os.path.join( os.path.dirname(__file__), 'onenote', resource['name'] )
                        out_dir = os.path.dirname(out_file)

                        if not os.path.isdir(out_dir):
                            os.makedirs(out_dir)

                        if force or not os.path.isfile(out_file):
                            print( '  > loading {}...'.format(resource['url']))
                            data =  requests.get( resource['url'].replace('$value', 'content'), headers={'Authorization': 'Bearer ' + token} )

                            with open(out_file, 'wb') as fs:
                                fs.write(data.content) 

                            resource['data'] = out_file

                        print( '  > {}: {} bytes'.format( out_file, os.path.getsize(out_file) ) )

                elements = elements + [ element ]

                if 'sectionsUrl' in onenote_object:
                    elements = elements + onenote_process( token, 'section', onenote_object["sectionsUrl"] )

                if 'sectionGroupsUrl' in onenote_object:
                    elements = elements + onenote_process( token, 'group', onenote_object["sectionGroupsUrl"] )

                if 'pagesUrl' in onenote_object:
                    elements = elements + onenote_process( token, 'page', onenote_object["pagesUrl"] + '?pagelevel=true&orderby=order' )

            if '@odata.nextLink' in onenote_response:
                url = onenote_response['@odata.nextLink']
            else:
                run = False

    return elements

# #################################################################################################################################
# ONENOTE ELEMENT
# #################################################################################################################################

def onenote_element( element, what ):
    content = {}

    content['what'] = what

    if 'id' in element: 
        content['id'] = element['id']

    if 'parentNotebook' in element: 
        if element['parentNotebook'] and 'id' in element['parentNotebook']: 
            content['parent'] = element['parentNotebook']['id']

    if 'parentSectionGroup' in element: 
        if element['parentSectionGroup'] and 'id' in element['parentSectionGroup']: 
            content['parent'] = element['parentSectionGroup']['id']

    if 'parentSection' in element: 
        if element['parentSection'] and 'id' in element['parentSection']: 
            content['parent'] = element['parentSection']['id']

    if 'order' in element: 
        content['order'] = element['order']

    if 'displayName' in element: content['title'] = element["displayName"]
    elif 'title' in element: content['title'] = element["title"]
    else: content['hidetitle'] = True

    if 'title' in content: content['slug'] = slugify( content['title'] )
    else: content['slug'] = slugify( content['id'] )

    if 'createdDateTime' in element: content['date'] = element["createdDateTime"]
    if 'lastModifiedDateTime' in element: content['updated'] = element["lastModifiedDateTime"]

    # content['tags']
    # content['status']
    # content['has_math']
    # content['category']
    # content['guid']
    # content['link']
    # content['description']
    # content['type']
    # content['author']
    # content['enclosure']
    # content['data']
    # content['filters']
    # content['hyphenate']
    # content['nocomments'] = False
    # content['pretty_url']
    # content['previewimage']
    # content['template']
    # content['url_type']

    resources = []

    if 'content' in element: 

        # pprint.pprint( element['content'].text )

        soup = BeautifulSoup(element['content'].text, features="html.parser")

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

        content['resources'] = []

        # objects
        # -------
        # <object 
        # data="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-8a9f130df6d87945a8099be6b6d2be82!1-34CFFB16AE39C6B3!335924/$value" 
        # data-attachment="SEJOUR BURAIS 007-IND-M-22.pdf" 
        # type="application/pdf">
        # </object>

        for tag in soup.select("object[data-attachment]"): 
            name = re.search( r'^.*resources/(.*?)!', tag['data']).group(1) + '_' + tag['data-attachment']
            content['resources'] += [ { 'name': name, 'url': tag['data'], 'data': None, 'type': 'object' } ]

        # images
        # ------
        # <img 
        # alt="bla bla bla"
        # data-fullres-src="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value" 
        # data-fullres-src-type="image/png" 
        # data-id="2f8fe6dc-10b8-c046-ba5b-c6ccf2c8884a" 
        # data-index="2" 
        # data-options="printout" 
        # data-src-type="image/png" 
        # height="842" 
        # src="https://graph.microsoft.com/v1.0/users('laurent@burais.fr')/onenote/resources/0-158d4dc3eb09c647b6cb9c4759dc3f69!1-34CFFB16AE39C6B3!335924/$value" 
        # width="595"
        # />

        for tag in soup.select('img[src]'):
            del tag['alt']

            name = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
            content['resources'] += [ { 'name': name, 'url': tag['src'], 'data': None, 'type': 'image' } ]

            if tag['data-fullres-src'] == tag['src']:
                name = re.search( r'^.*resources/(.*?)!', tag['src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
            else:
                name = re.search( r'^.*resources/(.*?)!', tag['data-fullres-src']).group(1) + '.' + tag['data-src-type'].replace('image/', '')
            content['resources'] += [ { 'name': name, 'url': tag['data-fullres-src'], 'data': None, 'type': 'fullres' } ]


            del tag['height']

            tag['width'] = 600

        content['content'] = str( soup.find("body") )

        if len( content['resources'] ) > 0: 
            # remove duplicates
            pass
        else:
            del content['resources']

    print( '[{0:<8}] {1}'.format(content['what'], content['title']) )
    print( '-'*250 )
    pprint.pprint( element )
    print( '-'*250 )
    tmp = dict(content)
    if 'content' in tmp: tmp['content'] = "scrubbed content"
    pprint.pprint( tmp )
    del tmp
    print( '-'*250 )

    return content