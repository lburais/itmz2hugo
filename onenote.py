# #####################################################################################################################################################################################################
# Filename:     onenote.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
# Graph Explorer:
#   https://developer.microsoft.com/fr-fr/graph/graph-explorer
#
# #####################################################################################################################################################################################################
# OneNote structure
# -------------------
#
# #####################################################################################################################################################################################################

import json
import requests
import re
import os
import sys
import shutil
import random
import string
import time
import pathlib

from datetime import datetime as dt
import pytz
from unidecode import unidecode

from xml.etree import ElementTree
from pathvalidate import sanitize_filename
from html.parser import HTMLParser
from fnmatch import fnmatch

from bs4 import BeautifulSoup   

from mytools import *

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session

import msal

import uuid

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

import microsoft_config

MICROSOFT_GRAPH_URL = 'https://graph.microsoft.com/v1.0'
ALL_NOTEBOOKS = 'All Notebooks'

#onenote = None

output_directory = os.path.join( os.path.dirname(__file__), 'output', 'onenote' )


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

        print( f'[onenote] [process_url] action: {action}, url: {request.url}' )

        catalog = []
        elements = []
        note = {}
        comments = ''

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # GETATOKEN
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if action in ['getAToken']:
            if request.args['state'] != session.get("state"):
                return redirect(url_for("login"))
            cache = _load_cache()
            result = _build_msal_app(cache).acquire_token_by_authorization_code( request.args['code'],
                                                                                 scopes=microsoft_config.SCOPE,
                                                                                 redirect_uri=url_for("microsoft_token", _external=True))
            if "error" in result:
                return "Login failure: %s, %s" % ( result["error"], result.get("error_description") )

            session["user"] = result.get("id_token_claims")
            _save_cache(cache)
            return "/"

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # LOGIN
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        elif action in ['login']:
            session["state"] = str(uuid.uuid4())
            auth_url = _build_msal_app().get_authorization_request_url( microsoft_config.SCOPE,
                                                                        state=session["state"],
                                                                        redirect_uri=url_for("microsoft_token", _external=True))
            return auth_url

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # LOGOUT
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        elif action in ['logout']:
            session.clear()  
            return "https://login.microsoftonline.com/common/oauth2/v2.0/logout?post_logout_redirect_uri=" + url_for("microsoft_login", _external=True)

        # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # CATALOG
        # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # requires to be online

        if action in ['parse', 'catalog']:

            notebooks = _get_json(f'{MICROSOFT_GRAPH_URL}/me/onenote/notebooks')

            print(f'Got {len(notebooks)} notebooks : {", ".join( [ nb["displayName"] for nb in notebooks ] )}.')

            # add command to parse all notebooks        
            if len(notebooks) > 0:
                catalog = [ { 'source': 'onenote', 'object': 'notebook', 'name': ALL_NOTEBOOKS, 'url': f'notebook={ALL_NOTEBOOKS}' } ]

            # add command to parse each notebook      
            for nb in notebooks:
                catalog += [ { 'source': 'onenote', 'object': 'notebook', 'name': nb['displayName'], 'url': f'notebook={nb["displayName"]}' } ]
                
        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # ONENOTE
        #   ?NOTEBOOK=
        # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # requires to be online

        if action in ['parse', 'onenote']:

            notebook = request.args.get('notebook')

            if notebook:

                if notebook in [ALL_NOTEBOOKS]: notebook = None
                _download_notebooks( output_directory, select= [notebook] if notebook else None )

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # ONENOTE
        #   ID= 
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if action in ['content', 'onenote']:

            identifier = request.args.get('id')

            elements = list_notes( output_directory, identifier )

            # all_attr = {}
            # for element in elements:
            #     if 'html' in element:
            #         print( f'..{element["file"]}' )
            #         for tag in BeautifulSoup(element['html'], 'html.parser').find_all():
            #             if tag.name in all_attr:
            #                 all_attr[tag.name] += tag.attrs.keys()
            #             else:
            #                 all_attr[tag.name] = tag.attrs.keys()
            #             all_attr[tag.name] = list(dict.fromkeys( all_attr[tag.name] ))
            # print( f'TAGS and ATTRIBUTES: {all_attr}')

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
                        'source': 'onenote',
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
# CACHE
# #####################################################################################################################################################################################################

def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

def _build_msal_app(cache=None, authority=None):
    return msal.ConfidentialClientApplication(
        microsoft_config.CLIENT_ID, authority=authority or microsoft_config.AUTHORITY,
        client_credential=microsoft_config.SECRET_VALUE, token_cache=cache)

def _get_token_from_cache(scope=None):
    cache = _load_cache()  # This web app maintains one cache per session
    cca = _build_msal_app(cache)
    accounts = cca.get_accounts()
    if accounts:  # So all accounts belong to the current signed-in user
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(cache)
        return result

# #####################################################################################################################################################################################################
# GET_JSON
# #####################################################################################################################################################################################################

def _get_json(url, force=False):
    values = []
    next_page = url
    while next_page:
        resp = _get(next_page)
        if resp:
            if resp.headers['content-type'].split(';')[0] == 'application/json':
                resp = resp.json()
                if 'value' not in resp:
                    raise RuntimeError(f'Invalid server response: {resp}')
                values += resp['value']
                next_page = resp.get('@odata.nextLink')
            else:
                print( f'not a json: {resp.headers["content-type"].split(";")[0]}' )

    return values

# #####################################################################################################################################################################################################
# GET
# #####################################################################################################################################################################################################

def _get(url):
    try:
        sec = 0

        token = _get_token_from_cache(microsoft_config.SCOPE)
        if not token:
            return redirect(url_for("login"))

        while True:
            resp = requests.get( url, headers={'Authorization': 'Bearer ' + token['access_token']} )

            if resp.status_code == 429:
                # We are being throttled due to too many requests.
                # See https://docs.microsoft.com/en-us/graph/throttling
                sec = min( [ sec + 20, 60 ] )
                
                print(f'Too many requests, waiting {sec}s and trying again.')
                time.sleep(sec)
            
            elif resp.status_code == 500:
                # In my case, one specific note page consistently gave this status
                # code when trying to get the content. The error was "19999:
                # Something failed, the API cannot share any more information
                # at the time of the request."
                print('Error 500, skipping this page.')
                return None
            
            elif resp.status_code == 504:
                print('Request timed out, probably due to a large attachment. Skipping.')
                return None
            
            else:
                resp.raise_for_status()
                return resp
    except:
        return None

# #####################################################################################################################################################################################################
# DOWNLOAD_ATTACHMENTS
# #####################################################################################################################################################################################################

def _download_attachments(content, out_dir):
    image_dir = os.path.join( out_dir, 'images' )
    attachment_dir = os.path.join( out_dir, 'attachments' )

    class MyHTMLParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            self.attrs = {k: v for k, v in attrs}

    def generate_html(tag, props):
        element = ElementTree.Element(tag, attrib=props)
        return ElementTree.tostring(element, encoding='unicode')

    def download_image(tag_match):
        try:
            # <img width="843" height="218.5" src="..." data-src-type="image/png" data-fullres-src="..."
            # data-fullres-src-type="image/png" />
            parser = MyHTMLParser()
            parser.feed(tag_match[0])
            props = parser.attrs
            image_url = props.get('data-fullres-src', props['src'])
            image_type = props.get('data-fullres-src-type', props['data-src-type']).split("/")[-1]
            file_name = ''.join(random.choice(string.ascii_lowercase) for _ in range(10)) + '.' + image_type

            out_image = os.path.join( image_dir, file_name )

            if os.path.exists( out_image ): 
                print(f'Image {out_image} already downloaded; skipping.')
            else:
                req = _get(image_url)
            
                if req is None:
                    return tag_match[0]
                img = req.content
                print(f'Downloaded image of {len(img)} bytes.')

                os.makedirs( image_dir, exist_ok=True )
                with open(out_image, "wb") as f:
                    f.write(img)

            props['src'] = os.path.join( "images", file_name )
            props = {k: v for k, v in props.items() if 'data-fullres-src' not in k}

            return generate_html('img', props)

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print( "Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname) )
            return tag_match[0]

    def download_attachment(tag_match):
        try:
            # <object data-attachment="Trig_Cheat_Sheet.pdf" type="application/pdf" data="..."
            # style="position:absolute;left:528px;top:139px" />
            parser = MyHTMLParser()
            parser.feed(tag_match[0])
            props = parser.attrs
            data_url = props['data']
            file_name = props['data-attachment']

            out_attachment = os.path.join( attachment_dir, file_name )
        
            if os.path.exists( out_attachment ): 
                print(f'Attachment {out_attachment} already downloaded; skipping.')
            else:
                req = _get(data_url)

                if req is None:
                    return tag_match[0]
                data = req.content
                print(f'Downloaded attachment {file_name} of {len(data)} bytes.')

                os.makedirs( attachment_dir, exist_ok=True )
                with open(out_attachment, "wb") as f:
                    f.write(data)

            props['data'] = os.path.join( "attachments", file_name )

            return generate_html('object', props)

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print( "Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname) )
            return tag_match[0]

    content = re.sub(r"<img .*?\/>", download_image, content, flags=re.DOTALL)
    content = re.sub(r"<object .*?\/>", download_attachment, content, flags=re.DOTALL)

    return content

# #####################################################################################################################################################################################################
# FILTER_ITEMS
# #####################################################################################################################################################################################################

def _filter_items(items, select, name='items'):
    if not select:
        return items, select

    items = [item for item in items if fnmatch(item.get('displayName', item.get('title')).lower(), select[0].lower())]

    return items, select[1:]

# #####################################################################################################################################################################################################
# DOWNLOAD_NOTEBOOKS
# #####################################################################################################################################################################################################

def _download_notebooks(path, select=None):

    notebooks = _get_json(f'{MICROSOFT_GRAPH_URL}/me/onenote/notebooks')

    force = True if select else False

    print(f'Got {len(notebooks)} notebooks : {", ".join( [ nb["displayName"] for nb in notebooks ] )}.')

    notebooks, select = _filter_items(notebooks, select, 'notebooks')

    for obj in notebooks:

        obj_name = obj["displayName"]
        print('- NOTEBOOK: {} {}'.format( obj_name, '-'*(80-5-len('NOTEBOOK')-len(obj_name)) ) )

        obj_dir = os.path.join( path, unidecode(obj_name.lower()) )
        if force: shutil.rmtree( obj_dir, ignore_errors=True )

        obj_time = _get_file_date( obj_dir )
        if not force and obj_time and obj_time > _get_object_date( obj ):
            print('Skipping notebook {} [{} > {}]'.format( obj_name, obj_time.strftime("%Y-%m-%d %H:%M:%S"), _get_object_date( obj ).strftime("%Y-%m-%d %H:%M:%S")))
            continue

        sections = _get_json(obj['sectionsUrl'])
        section_groups = _get_json(obj['sectionGroupsUrl'])

        print(f'Got {len(sections)} sections and {len(section_groups)} section groups.')

        os.makedirs( obj_dir, exist_ok=True )

        _download_sections(sections, obj_dir, select, force=force)
        _download_section_groups(section_groups, obj_dir, select, force=force)

# #####################################################################################################################################################################################################
# DOWNLOAD_SECTION_GROUPS
# #####################################################################################################################################################################################################

def _download_section_groups(section_groups, path, select=None, force=False):

    section_groups, select = _filter_items(section_groups, select, 'section groups')

    for obj in section_groups:

        obj_name = obj["displayName"]
        print('- SECTION GROUP: {} {}'.format( obj_name, '-'*(80-5-len('SECTION GROUP')-len(obj_name)) ) )

        obj_dir = os.path.join( path, unidecode(obj_name.lower()) )
        if force: shutil.rmtree( obj_dir, ignore_errors=True )

        obj_time = _get_file_date( obj_dir )
        if not force and obj_time and obj_time > _get_object_date( obj ):
            print( 'Skipping group {} [{} > {}]'.format( obj_name, obj_time.strftime("%Y-%m-%d %H:%M:%S"), _get_object_date( obj ).strftime("%Y-%m-%d %H:%M:%S")))
            continue

        sections = _get_json(obj['sectionsUrl'])

        print(f'Got {len(sections)} sections.')

        os.makedirs( obj_dir, exist_ok=True )

        _download_sections(sections, obj_dir, select, force=force)

# #####################################################################################################################################################################################################
# DOWNLOAD_SECTIONS
# #####################################################################################################################################################################################################

def _download_sections(sections, path, select=None, force=False):

    sections, select = _filter_items(sections, select, 'sections')

    for obj in sections:

        obj_name = obj["displayName"]
        print('- SECTION: {} {}'.format( obj_name, '-'*(80-5-len('SECTION')-len(obj_name)) ) )

        obj_dir = os.path.join( path, unidecode(obj_name.lower()) )
        if force: shutil.rmtree( obj_dir, ignore_errors=True )

        obj_time = _get_file_date( obj_dir )
        if not force and obj_time and obj_time > _get_object_date( obj ):
            print( 'Skipping section {} [{} > {}]'.format( obj_name,obj_time.strftime("%Y-%m-%d %H:%M:%S"), _get_object_date( obj ).strftime("%Y-%m-%d %H:%M:%S")))
            continue

        pages = _get_json( obj['pagesUrl'] + '?pagelevel=true')

        print(f'Got {len(pages)} pages.')

        os.makedirs( obj_dir, exist_ok=True )

        _download_pages( pages, obj_dir, select, force=force )

# #####################################################################################################################################################################################################
# DOWNLOAD_PAGES
# #####################################################################################################################################################################################################

def _download_pages(pages, path, select=None, force=False):

    pages, select = _filter_items(pages, select, 'pages')

    pages = sorted([(page['order'], page) for page in pages])
    level_dirs = [None] * 4

    for order, page in pages:
        level = page['level']
        page_title = sanitize_filename(f'{order} {page["title"]}', platform='auto')

        print('- PAGE: {} {}'.format( page_title, '-'*(80-5-len('PAGE')-len(page_title)) ) )

        if level == 0:
            page_dir = os.path.join( path, unidecode(page_title.lower()) )
        else:
            try:
                level_dir = next((dop for dop in reversed(level_dirs[:level-1]) if dop is not None), level_dirs[level - 1])
                page_dir = os.path.join( level_dir, unidecode(page_title.lower()) )
            except:
                print(f'level: {level}, dir: {level_dir}, join: {level_dirs[level - 1]}, level_dirs: {level_dirs}')
                raise
        level_dirs[level] = page_dir

        _download_page( page, page_dir, force=force )

# #####################################################################################################################################################################################################
# DOWNLOAD_PAGE
# #####################################################################################################################################################################################################

def _download_page(page, path, force=False):

    obj_name = page["title"]

    if force: shutil.rmtree( path, ignore_errors=True )

    out_html = os.path.join( path, 'main.html')

    obj_time = _get_file_date( out_html )
    if not force and obj_time and obj_time > _get_object_date( obj ):
        print('Skipping page {} [{} > {}]'.format( obj_name, obj_time.strftime("%Y-%m-%d %H:%M:%S"), _get_object_date( page ).strftime("%Y-%m-%d %H:%M:%S")))
        return

    response = _get(page['contentUrl'])

    if response is not None:
        content = response.text
        print(f'Got content of length {len(content)}')

        os.makedirs( path, exist_ok=True )

        content = _download_attachments( content, path )

        soup = BeautifulSoup( content, features="html.parser" )
        
        # add meta tag related to mind: 
        # <meta mind="[source, object, id, folder, createdDateTime, lastModifiedDateTime, url]" content="">

        meta_list = [{ 'tag': 'source', 'content': 'onenote'}]
        page_tag = ['id', 'self', 'title', 'contentUrl', 'level', 'order', 'createdDateTime', 'lastModifiedDateTime']
        for tag in page_tag:
            if tag in page: meta_list += [{ 'tag': tag, 'content':page[tag]}]
        meta_list += [{ 'tag': 'folder', 'content': path}]

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

        with open(out_html, "w", encoding='utf-8') as f:
            f.write(content)
