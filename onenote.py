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
# ONENOTE PROCESS
# #################################################################################################################################

def onenote_process( token, what='notebook', url='' ):
    run = True
    elements = []

    if url == '':
        if what == 'notebook': url='https://graph.microsoft.com/v1.0/me/onenote/notebooks/0-34CFFB16AE39C6B3!335920'
        elif what == 'section': url='https://graph.microsoft.com/v1.0/me/onenote/sections'
        elif what == 'group': url='https://graph.microsoft.com/v1.0/me/onenote/sectionGroups'
        elif what == 'page': url='https://graph.microsoft.com/v1.0/me/onenote/pages'
        else: run = False

    while run:
        onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} ).json()

        if 'error' in onenote_response:
            run = False
            print( '[{0:<8}] error: {1} {2}'.format(what, onenote_response['error']['code'], onenote_response['error']['message']) )
        else:
            if 'value' in onenote_response: onenote_objects = onenote_response['value']
            else: onenote_objects = [ onenote_response ]

            for onenote_object in onenote_objects:
                if 'contentUrl' in onenote_object:
                    onenote_object['content'] = requests.get( onenote_object["self"] + "/$value", headers={'Authorization': 'Bearer ' + token} )

                elements = elements + [ onenote_element(onenote_object, what) ]

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
        tree = content['id'].split('!')
        del tree[0]
        content['parent'] = '!'.join(tree)

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

    if 'content' in element: 
        soup = BeautifulSoup(element['content'].text, features="html.parser")

        # remove absolute positionning

        for tag in soup():
            for attribute in ["data-absolute-enabled"]:
                del tag[attribute]
        tags = soup.find_all( style=re.compile("position:absolute"))
        for tag in tags:
            if (tag["style"].find("position:absolute")  != -1):
                del tag["style"]
        body = soup.find("body")
        content['content'] = str( body )

        # replace resources

        # resize images

    print( '[{0:<8}] {1}'.format(content['what'], content['title']) )
    print( '-'*250 )
    pprint.pprint( element )
    print( '-'*250 )
    pprint.pprint( content )
    print( '-'*250 )

    return content