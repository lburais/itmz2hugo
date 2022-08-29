import os
import shutil
import re
import pprint

from bs4 import BeautifulSoup

# #############################################################################################################################
# Structure
# #############################################################################################################################
# iThoughts structure
# -------------------
#   [src]
#   ├── [file1].itmz
#   |   ├── mapdata.xml
#   |   |   ├── tag
#   |   |   ├── iIhoughts attribs
#   |   |   |   ├── modified
#   |   |   |   └── author
#   |   |   ├── topic attribs
#   |   |   |   ├── uuid
#   |   |   |   ├── text
#   |   |   |   ├── link
#   |   |   |   ├── created
#   |   |   |   ├── modified
#   |   |   |   ├── note
#   |   |   |   ├── callout
#   |   |   |   ├── floating
#   |   |   |   ├── att-name
#   |   |   |   ├── att-id
#   |   |   |   ├── task-start
#   |   |   |   ├── task-due
#   |   |   |   ├── cost
#   |   |   |   ├── cost-type
#   |   |   |   ├── task-effort
#   |   |   |   ├── task-priority
#   |   |   |   ├── task-progress
#   |   |   |   ├── resources
#   |   |   |   ├── icon1
#   |   |   |   ├── icon2
#   |   |   |   ├── position
#   |   |   |   ├── color
#   |   |   |   ├── summary1
#   |   |   |   └── summary2
#   |   |   ├── relationship
#   |   |   |   ├── end1-uui
#   |   |   |   └── end2-uui
#   |   |   └── group
#   |   |       ├── member1
#   |   |       └── member2
#   |   └── assets
#   |       ├── [uuid1]
#   |       |   ├── [attachment1]
#   |       |   └── [attachment1]
#   |       └── [uuid2]
#   |           └── [attachment3]
#   ├── [file2].itmz
#   |   ├── mapdata.xml
#   |   └── assets
#   |       └── [uuid3]
#   |           └── [attachment4]
#   └── [folder]
#       ├── [file3].itmz
#       |   ├── mapdata.xml
#       |   └── assets
#       |       └── [uuid4]
#       |           └── [attachment5]
#       └── [folder]
#           └── [file4].itmz
#
# Hugo structure
# --------------
#   content
#   ├── _index.html
#   ├── [filename1] == page1 bundle for itmz1
#   |   ├── _index.html == filename1 page
#   |   |       external --> url
#   |   |       internal in --> {{< ref "#[uuid]" >}}
#   |   |       internal out --> {{< ref "/[filename2]/_index#[uuid]" >}}
#   |   ├── attachments
#   |   |   └── [attachment1] 
#   |   |           --> {{< ref "/[filename1]/attachments/[attachment1]" >}}
#   |   |           --> {{< ref "attachments/[attachment1]" >}}
#   |   └── [filename2] --> page2 bundle for itmz2
#   |       ├── _index.html == filename2 page
#   |       └── attachments
#   |           └── [attachment2] 
#   |                   --> {{< ref "/[filename1]/[filename2]/attachments/[attachment2]" >}}
#   |                   --> {{< ref "attachments/[attachment2]" >}}
#   ├── layouts
#   |   └── shortcodes
#   |       └── [shortcodes].html
#   └── config.toml
#
# Pelican structure
# -----------------
#   content
#   ├── pages
#   |   ├── [filename1].html
#   |   |       external --> url
#   |   |       internal in --> {filename}#[uuid]
#   |   |       internal out --> {filename}[filenamex].html#[ref]
#   |   └── [filename2].html --> {filename}[filename2].html
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
#
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


# #############################################################################################################################
# _get_header
# #############################################################################################################################

def _get_header( element ):

    output = '<head>\n'

    if 'title' in element: output += '\t<title>{}</title>\n'.format(element['title'])

    for key, value in element.items():
        if not key in ['content', 'title', 'resources', 'tags']:
            output += '\t<meta name="{}" content="{}" />\n'.format(key, value)

    if 'tags' in element: output += '\t<meta name="{}" content="{}" />\n'.format(key, ', '.join(value))

    output += '</head>\n'

    return output

# #############################################################################################################################
# _get_body
# #############################################################################################################################

def _get_body( element ):

    if ('content' in element) and element['content']: output = element['content']
    else: output = '<body></body>'

    soup = BeautifulSoup(output, features="html.parser")

    # add child posts
    if element['what'] in ['notebook', 'section', 'group']: 
        if 'slug' in element:
            tag = soup.new_tag('div')
            tag.string = "{{% post-list tags=" + "{}".format(element['slug']) + " %}}{{% /post-list %}}"
            soup.body.append(tag)

    # add struture
    tag = soup.new_tag('code')
    tmp = dict(element)
    if 'content' in tmp: del tmp['content']
    tag.string = pprint.pformat(tmp)
    del tmp
    soup.body.append(tag)

    # done
    output = str( soup )

    return output

# #############################################################################################################################
# jamstack_clear
# #############################################################################################################################

def jamstack_clear( output='site/nikola', stack='nikola' ):
    try:
        if stack in ['nikola']:
            shutil.rmtree(os.path.join( 'site/nikola', 'images'))
            shutil.rmtree(os.path.join( 'site/nikola', 'onenote', 'objects'))
            shutil.rmtree(os.path.join( 'site/nikola', 'posts'))
            shutil.rmtree(os.path.join( 'site/nikola', 'pages'))
        else:
            return

    except:
        pass

# #############################################################################################################################
# jamstack_write
# #############################################################################################################################

# assuming html for nikola

def jamstack_write( output='site/nikola', elements=[], stack='nikola', generate='html' ):

    print( '-'*250 )
    print( 'JAMSTACK WRITE' )
    print( '-'*250 )
    pprint.pprint( elements )
    print( '-'*250 )

    # manage stacks

    if stack in ['nikola']:
        output = 'site/nikola'
        folder_images = 'images'
        folder_objects = 'objects'
        folder_resources = os.path.join('files', folder_objects)
    elif stack in ['pelican']:
        output = 'site/pelican'
        folder_images = 'images'
        folder_objects = 'objects'
        folder_resources = os.path.join('files', folder_objects)
    else:
        return

    # process HTML

    for element in elements:

        # place for html

        if element['what'] in ['page']: folder_html = 'posts'
        elif element['what'] in ['notebook', 'section', 'group']: 
            folder_html = 'pages'
        else: folder_html = 'usused'
        folder_path = os.path.sep.join(element['path']) if 'path' in element else ''

        # get html
        text = _get_header( element )
        text += _get_body( element )

        # write html 
        out_file = os.path.join( output, folder_html, folder_path, element['slug'] + '.html' )
        out_dir = os.path.dirname(out_file)

        print('> ' + out_file)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        with open(out_file, 'w', encoding='utf-8') as fs:
            fs.write(text) 