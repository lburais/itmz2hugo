#!/usr/bin/env python

import argparse
import os
import re
import shutil
import time
from datetime import datetime
import markdown

import xml.etree.ElementTree as ET
import zipfile

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

# #################################################################################################################################
# ITMZ
# #################################################################################################################################

class ITMZ:

    _site = None
    _source = None
    _stack = None
    # _elements = None
    # _ithoughts = None
    # _filename = None
    # _path = None

    # #############################################################################################################################
    # __init__
    # #############################################################################################################################

    def __init__(self, source, site, stack):
        self._source = source
        self._site = site
        self._stack = stack

        self._set_site()

    # #############################################################################################################################
    # _set_site
    # #############################################################################################################################

    def _set_site(self):
        if self._stack == 'hugo': self._set_hugo_site()
        elif self._stack == 'pelican': self._set_pelican_site()

    # #############################################################################################################################
    # _set_pelican_site
    # #############################################################################################################################

    def _set_pelican_site(self):
        pass

    # #############################################################################################################################
    # _set_hugo_site
    # #############################################################################################################################

    def _set_hugo_site(self):
        shortcodes = {}
        shortcodes['mybutton'] = '''
            {{- $_hugo_config := `{ "version": 1 }` }}
            {{- $icon := .Get "icon" }}
            {{- $iconposition := .Get "icon-position" }}
            {{- $target := .Get "target" }}
            <a{{ with .Get "href"}} href="{{ . }}"{{ end }}
            {{- if ($target) }}
             target="{{$target}}"
            {{- end }}
             class="btn btn-default">
            {{- if ($icon) }}
                {{- if or (not ($iconposition)) (eq $iconposition "left") }}
            <i class="{{ $icon }}"></i>
                {{- end }}
            {{- end }}
            {{ .Inner }}
            {{- if and ($icon) (eq $iconposition "right")}}
            <i class="{{$icon}}"></i>
            {{- end }}
            </a>
        '''

        shortcodes['mytoc'] = '''
            {{ .Page.TableOfContents }}
        '''

        for key, shortcode in shortcodes.items():
            out_file = os.path.join( self._site, "..", "layouts", "shortcodes", key + ".html")
            out_dir = os.path.dirname(out_file)
            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(out_file, 'w', encoding='utf-8') as fs:
                fs.write(shortcode) 
                fs.close() 

        config = '''
baseURL = 'http://pharaoh.local'
languageCode = 'en-us'
title = 'MindMap'
theme = "relearn"
themesDir = "../themes"

[params]
    themeVariant = "relearn-dark"
    disableToc = false
    disableSearch = false
        '''
        out_file = os.path.join( self._site, "..", "config.toml")
        out_dir = os.path.dirname(out_file)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        with open(out_file, 'w', encoding='utf-8') as fs:
            fs.write(config) 
            fs.close() 

    # #############################################################################################################################
    # _parse_source
    # #############################################################################################################################

    def _parse_source( self, force=False ):

        files = []
        if os.path.isdir( self._source ):
            for top, dirs, filenames in os.walk( self._source, topdown=True ):
                for file in filenames:
                    if os.path.splitext(file)[1] == '.itmz': 
                        files.append(os.path.join(top, file))

        else:
            files.append( self._source )

        print( files )

        for file in files:
            self.process_file( file, force )

    # #############################################################################################################################
    # process_file
    # #############################################################################################################################

    def process_file( self, file, force=False ):

        structure = self._get_structure( file )

        print( 'structure: {}'.format(structure))

        # read ITMZ file
        ithoughts = zipfile.ZipFile( file, 'r')
        xmldata = ithoughts.read('mapdata.xml')
        elements = ET.fromstring(xmldata)

        # tag iThoughts
        mod_time = datetime.strptime(elements.attrib['modified'], "%Y-%m-%dT%H:%M:%S")

        # out_file
        out_file = os.path.join( self._site, os.path.sep.join(structure['content']), structure['filename'] )
        out_time = datetime.fromtimestamp(os.path.getmtime(out_file)) if os.path.isfile(out_file) else None
        out_dir = os.path.dirname(out_file)

        print( 'file: {}'.format(file))
        print( '  out_dir: {}'.format(out_dir))
        print( '  out_file: {}'.format(out_file))
        print( '  out_time: {}'.format(out_time))
        print( '  mod_time: {}'.format(mod_time))

        # need to proceed?
        if force or not out_time or mod_time > out_time:

            # set the topic tree
            self._set_topics( structure, ithoughts, elements )

            self._print_elements( elements )
        
            output = self._get_html( structure, elements )

            # write the output file
            print('  > ' + out_file)

            print("    - file:       {}".format( structure['file'] ))
            print("    - title:      {}".format( structure['title'] ))
            print("    - name:       {}".format( structure['name'] ))
            print("    - content:    {}".format( structure['content'] ))
            print("    - filename:   {}".format( structure['filename'] ))
            print("    - attachment: {}".format( structure['attachment'] ))
            print("    - modified:   {}".format( mod_time.strftime("%Y-%m-%dT%H:%M:%S") ))
            if out_time: 
                print("    - file:       {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(out_file, 'w', encoding='utf-8') as fs:
                fs.write(output) 

            out_time = datetime.fromtimestamp(os.path.getmtime(out_file))
            print("    - saved:      {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

    # #############################################################################################################################
    # _get_structure
    # #############################################################################################################################

    def _get_structure(self, file ):
        structure = {}

        structure['file'] = file
        structure['title'] = os.path.basename(file).split(".")[0]
        structure['name'] = self._slugify(structure['title'])

        if self._stack == 'hugo':
            structure['content'] = os.path.split(os.path.relpath(structure['file'], self._source))[0].split(os.path.sep)
            if len(structure['content']) == 1 and structure['content'][0] == '':
                structure['content'][0] = structure['name']
            else: 
                structure['content'].append( structure['name'] )
            structure['filename'] = "_index.html"
            structure['attachment'] = [ structure['name'], "attachments" ]

        elif self._stack == 'pelican':
            structure['content'] = [ "pages" ]
            structure['filename'] = structure['name'] + ".html"
            structure['attachment'] = [ "attachments", structure['name'] ]

        return structure

    # #############################################################################################################################
    # _slugify
    # #############################################################################################################################

    def _slugify(self, value):

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

    # #############################################################################################################################
    # _set_topics
    # #############################################################################################################################

    def _set_topics( self, structure, ithoughts, elements ):

        self._set_parent( elements=elements, parent=None )

        for element in elements.iter('topic'):

            # _summary
            if 'note' in element.attrib:
                element.attrib['_summary'] = element.attrib['note']

            # _links
            element.attrib['_links'] = []

            if '_parent' in element.attrib:
                parents = elements.findall( ".//*[@uuid='{}']".format(element.attrib['_parent']) )
                for parent in parents:
                    element.attrib['_links'].append( self._get_link( 'parent', parent.attrib['uuid'], structure ) )

            if 'uuid' in element.attrib:
                for child in elements.findall( ".//*[@_parent='{}']".format(element.attrib['uuid']) ) :
                    if child.tag == 'topic' and '_directory' in child.attrib: 
                        element.attrib['_links'].append( self._get_link( 'child', child.attrib['uuid'], structure ) )

                for relation in elements.findall( ".//*[@end1-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = elements.find( ".//*[@uuid='{}']".format(relation.attrib['end2-uuid']) )
                    element.attrib['_links'].append( self._get_link( 'peer', rel.attrib['uuid'], structure ) )

                for relation in elements.findall( ".//*[@end2-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = elements.find( ".//*[@uuid='{}']".format(relation.attrib['end1-uuid']) )
                    element.attrib['_links'].append( self._get_link( 'peer', rel.attrib['uuid'], structure ) )

            # add the link
            # http://www.google.fr
            # ithoughts://open?topic=65F7D386-7686-470E-BABC-A3535A6B0798
            # ithoughts://open?path=Servers.itmz&topic=6D35D231-1C09-4B09-8FCD-E0799EA14096
            # ../../Pharaoh/Downloads/Ariba%20Guided%20Buying.pdf
            if 'link' in element.attrib:
                link = None
                target = re.split( r":", element.attrib['link'])
                if target[0] == 'http' or  target[0] == 'https': 
                    element.attrib['_links'].append( self._get_link( 'external', element.attrib['link'], structure ) )
                elif target[0] == 'ithoughts':
                    target = re.split( r"[///?=&]+", target[1])
                    if target[1] == 'open':
                        ref = ''
                        if 'path' in target: ref += os.path.basename(target[target.index('path') + 1])
                        if 'topic' in target: ref += target[target.index('topic') + 1]
                        element.attrib['_links'].append( self._get_link( 'link', ref, structure ) )

            # attachment
            if 'att-id' in element.attrib:
                try:
                    # read in itmz file
                    filename = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )
                    data = ithoughts.read(filename)

                    # write attachment
                    out_ext = os.path.splitext(element.attrib['att-name'])[1]
                    out_file = os.path.join( os.path.sep.join(structure['attachment']), element.attrib['att-id'] + out_ext )
                    out_dir = os.path.dirname(out_file)
                    if not os.path.isdir(out_dir): 
                        os.makedirs(out_dir)
                    with open(out_file, 'wb') as fs: 
                        fs.write(data) 

                    element.attrib['_links'].append( self._get_link( 'attachment', 
                                                                     element.attrib['att-id'] + out_ext, 
                                                                     structure, 
                                                                     title=element.attrib['att-name'] ) )

                except:
                    pass

            if len(element.attrib['_links']) == 0: element.attrib.pop('_links')

            # cleanup
            to_remove = ['position', 'color']
            for key in to_remove: 
                if key in element.attrib: element.attrib.pop(key)

    # #############################################################################################################################
    # _set_parent
    # #############################################################################################################################

    def _set_parent( self, elements, parent=None ):
        for element in elements:

            if 'floating' in element.attrib and element.attrib['floating'] == '1':
                parent = None

            if parent: 
                if '_level' in parent.attrib: element.attrib['_level'] = parent.attrib['_level'] + 1
                if 'uuid' in parent.attrib: 
                    element.attrib['_parent'] = parent.attrib['uuid']

            if not '_level' in element.attrib: element.attrib['_level'] = 0

            self._set_parent( element, element )

    # #############################################################################################################################
    # _get_link
    # #############################################################################################################################

    def _get_link( self, type, ref, structure, title=None ):

        link = {}
        link['type'] = type
        if title: link['title'] = title
        link['ref'] = ref

        if self._stack == 'hugo':
            if type in ['parent', 'child', 'peer']: 
                link['type'] = 'unknown'
            elif type in ['link']: 
                if ref[0] == '#': # iThoughts in
                    src = ''
                    uuid = ref
                else: # iThoughts out
                    src = ''
                    uuid = ''
                link['ref'] = '{{< ref "' + src + '#' + uuid + '" >}}'
            elif type in ['attachment']: 
                link['ref'] = '{{< ref "attachments/' + ref + '" >}}'

        elif self._stack == 'pelican':
            if not filename: filename = self._filename
            if type in ['parent', 'child', 'peer', 'link']: 
                link = "{filename}" + filename + ".html#{}".format(ref)
            elif type in ['attachment']:
                link = "{static}/attachments/" + filename + "/{}".format(ref)
            elif type in ['external']:
                link = ref

        return link

    # #############################################################################################################################
    # _print_elements
    # #############################################################################################################################

    def _print_elements( self, elements ):
        IDENT = '    '

        print( "ELEMENTS\n========\n")
        for element in elements.iter():
            print( "{}> {}{}".format(
                                IDENT * element.attrib['_level'] if '_level' in element.attrib else '', 
                                element.tag, 
                                " - " + element.attrib['uuid'] if 'uuid' in element.attrib else '' ))
            if '_title' in element.attrib:
                print( "{}{}title: {}".format( IDENT, IDENT * element.attrib['_level'], element.attrib['_title'] ))
            if '_filename' in element.attrib:
                print( "{}{}file:  {}".format( IDENT, IDENT * element.attrib['_level'], element.attrib['_filename'] ))
            if '_links' in element.attrib:
                print( "{}{}links:  {}".format( IDENT, IDENT * element.attrib['_level'], element.attrib['_links'] ))
        print( "\n\nPROCESSING\n==========\n")
    
    # #############################################################################################################################
    # _get_html
    # #############################################################################################################################

    def _get_html( self, structure, elements ):

        output = ''
        output += self._get_frontmatter(structure, elements)
        output += '<html>\n'
        output += self._get_header( structure, elements )
        output += '<body>\n'
        for topic in elements.iter('topic'):
            if not '_parent' in topic.attrib: output += self._get_body( elements, topic, 0 )
        output += '</body>\n'
        output += '</html>'

        return output

    # #############################################################################################################################
    # _get_frontmatter
    # #############################################################################################################################

    def _get_frontmatter( self, structure, elements ):

        output = "---\n"
        output += 'title: "{}"\n'.format(structure['title'])
        output += "date: {}\n".format(elements.attrib['modified'])
        output += 'author: "{}"\n'.format(elements.attrib['author'])
        output += '---\n'

        return output

    # #############################################################################################################################
    # _get_header
    # #############################################################################################################################

    def _get_header( self, structure, elements ):

        output = '<head>\n'
        output += '\t<title>{}</title>\n'.format(structure['title'])
        output += '\t<meta name="date" content="{}" />\n'.format(elements.attrib['modified'])
        # output += '\t<meta name="modified" content="{}" />\n'.format('')
        # output += '\t<meta name="keywords" content="{}" />\n'.format('')
        # output += '\t<meta name="category" content="{}" />\n'.format('')
        output += '\t<meta name="author" content="{}" />\n'.format(elements.attrib['author'])
        # output += '\t<meta name="authors" content="{}" />\n'.format('')
        output += '\t<meta name="slug" content="{}" />\n'.format(structure['name'])
        # output += '\t<meta name="summary" content="{}" />\n'.format('')
        # output += '\t<meta name="lang" content="{}" />\n'.format('')
        # output += '\t<meta name="translation" content="{}" />\n'.format('')
        output += '\t<meta name="status" content="{}" />\n'.format('published')
        output += '</head>\n'

        return output

    # #############################################################################################################################
    # _get_body
    # #############################################################################################################################

    def _get_body( self, elements, topic, level=0 ):

        output = ''

        if topic.tag == 'topic':

            hyperlinks = ''
            body = ''
            attachment = ''

            # compile links
            if '_links' in topic.attrib:
                for link in topic.attrib['_links']:
                    if link['type'] in ['attachment']:
                        attachment += "![{}]({})\n".format( link['title'] if 'title' in link else 'attachment', link['ref'])
                    else:
                        hyperlinks += '<a href="{}"'.format( link['ref'])
                        if link['type'] == 'external' or ( link['type'] == 'link' and link['ref'][0] != '#' ): 
                            hyperlinks += ' target="_blank"'
                        icon = None
                        if link['type'] == 'external': icon = 'fa-solid fa-link'
                        elif link['type'] == 'parent': icon = 'fa-solid fa-circle-up'
                        elif link['type'] == 'child': icon = 'fa-solid fa-circle-down'
                        elif link['type'] == 'peer': icon = 'fa-solid fa-circle-right'
                        if icon:
                            #hyperlinks += ' class="btn btn-default {}"'.format(icon)
                            pass
                        hyperlinks += '>'
                        if 'title' in link: hyperlinks += link['title']
                        hyperlinks += '</a> '

            # add hyperlinks
            if hyperlinks != '': 
                output += hyperlinks + '\n'

            # add body
            if 'text' in topic.attrib: 
                body = topic.attrib['text']
                if body[0] not in '[#`~]': body = '# ' + body
                body += '\n'

            # add task information to body
            task_header = []
            task_sep = []
            task_values = []
            task = { 'task-start': 'Start', 'task-due': 'Due', 'cost': 'Cost', 'task-effort': 'Effort', 
                    'task-priority': 'Priority', 'task-progress': 'Progress', 'resources': 'Resource(s)' }
            for key in task:
                if key in topic.attrib:
                    if key == 'task-progress':
                        if topic.attrib[key][-1] != "%": 
                            if int(topic.attrib[key]) > 100: continue
                            topic.attrib[key] += '%'
                    if key == 'task-effort' and topic.attrib[key][0] == '-': continue
                    task_header.append( " {} ".format( task[key] ))
                    task_sep.append( " --- " )
                    task_values.append( " {} ".format( topic.attrib[key] ))

            if task_header != '':
                body += "" + "|".join(task_header) + "\n"
                body += "" + "|".join(task_sep) + "\n"
                body += "" + "|".join(task_values) + "\n"
                body += "\n"

            # add attachment to body as image
            if attachment != '': body += attachment + '\n'

            # convert body to html
            body = markdown.markdown(body, extensions=['tables'])

            # add anchors to body
            if 'uuid' in topic.attrib:
                body = re.sub( r'<h1>', '<h1><a id="{}"></a>'.format(topic.attrib['uuid']), body, flags = re.MULTILINE )

            # shift headers by level in body
            for h in range (6, 0, -1):
                body = re.sub( r'h' + str(h) + r'>', 'h{}>'.format(h+level+1), body, flags = re.MULTILINE )

            output += body

            # add childs
            if 'uuid' in topic.attrib:
                for child in elements.findall( ".//*[@_parent='{}']".format(topic.attrib['uuid']) ) :
                    if child.tag == 'topic':
                        output += self._get_body( elements, child, level+1 )

        if output != '': output += '\n'
        return output

# #################################################################################################################################
# main
# #################################################################################################################################

def main():
    parser = argparse.ArgumentParser(
        description="Transform iThoughts files into reST files for static site generators.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        dest='input', help='The input file to read or directory to parse')
    parser.add_argument(
        '-o', '--output', dest='output', default='content',
        help='Output path')
    parser.add_argument(
        '--force', action='store_true', dest='force',
        help='Force refresh of all iThoughtsX files')
    parser.add_argument(
        '--hugo', action='store_true', dest='hugo',
        help='Create Hugo structure')
    parser.add_argument(
        '--pelican', action='store_true', dest='pelican',
        help='Create Pelican structure')

    args = parser.parse_args()

    stack = None
    if args.hugo: stack='hugo'
    if args.pelican: stack='pelican'

    if os.path.exists(args.output):
        try:
            # shutil.rmtree(args.output)
            pass
        except OSError:
            error = 'Unable to remove the output folder: ' + args.output
            exit(error)

    if not os.path.exists(args.output):
        try:
            os.makedirs(args.output)
        except OSError:
            error = 'Unable to create the output folder: ' + args.output
            exit(error)
           
    itmz = ITMZ( source=args.input, site=args.output, stack=stack )
    itmz._parse_source( args.force or False )


    print( "hugo server --bind 0.0.0.0 --port 8888 --baseURL http://pharaoh.local --destination /web --cleanDestinationDir --renderToDisk --watch")

main()