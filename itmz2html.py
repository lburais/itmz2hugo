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

    # #################################################################################################################################
    # ITMZ
    # #################################################################################################################################

    # mapdata:
    #   uuid                : part of filename and slug
    #   created             : date
    #   modified            : modified
    #   text                : _title and _content
    #   note                : _comment
    #   callout             : first is summary, others are ignored
    #   link                : for title
    #   attachments
    #       att-name        :
    #       att-id          :
    #   task
    #       task-start
    #       task-due
    #       cost
    #       cost-type
    #       task-effort
    #       task-priority
    #       task-progress
    #       resources       :  can be used to set authors
    #   unused
    #       icon1
    #       icon2
    #       position
    #       color
    #       summary1        : no idea what it is ...
    #       summary2        : no idea what it is ...

class ITMZ:

    _site = None
    _file = None
    _stack = None
    _elements = None
    _ithoughts = None
    _filename = None
    _path = None

    # #############################################################################################################################
    # __init__
    #
    #   file: iThoughts file
    #   site: output directory
    #   type: type of static blog generatot [hugo, pelican, ...]
    # #############################################################################################################################

    def __init__(self, file, site, stack):
        self._file = file
        self._site = site
        self._stack = stack

        # read ITMZ file
        self._ithoughts = zipfile.ZipFile( file, 'r')
        xmldata = self._ithoughts.read('mapdata.xml')
        self._elements = ET.fromstring(xmldata)

        self._filename = os.path.basename(self._file).split(".")[0]

        paths = self._filename.split(" - ")
        for idx, path in enumerate(paths):
            paths[idx] = self._normalize( path, slug= True )
            paths[idx] = re.sub( r'(?u)\A-*', '', paths[idx] )
            paths[idx] = re.sub( r'(?u)-*\Z', '', paths[idx] )
        self._path = os.path.sep.join( paths )

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
    # _normalize
    # #############################################################################################################################

    def _normalize(self, value, slug=False):

        # remove invalid chars (replaced by '-')
        value = re.sub( r'[<>:"/\\|?*^%]', '-', value, flags=re.IGNORECASE )

        if not slug: 
            # replace ", ',  chars
            value = re.sub( r'["”]', '\"', value, flags=re.IGNORECASE )
            value = re.sub( r"['’]", "\'", value, flags=re.IGNORECASE )
        else:
            # remove non-alphabetical/whitespace/'-' chars
            value = re.sub( r'[^\w\s-]', '', value, flags=re.IGNORECASE )

            # replace whitespace by '-'
            value = re.sub( r'[\s]+', '-', value, flags=re.IGNORECASE )

            # ignore case
            value = value.lower()

        # reduce multiple whitespace to single whitespace
        value = re.sub( r'[\s]+', ' ', value, flags=re.IGNORECASE)

        # reduce multiple '-' to single '-'
        value = re.sub( r'[-]+', '-', value, flags=re.IGNORECASE)

        # strip
        value = value.strip()


        return value

    # #############################################################################################################################
    # _print_elements
    # #############################################################################################################################

    def _print_elements( self ):
        IDENT = '    '

        print( "ELEMENTS\n========\n")
        for element in self._elements.iter():
            print( "{}> {}{}".format(
                                IDENT * element.attrib['_level'] if '_level' in element.attrib else '', 
                                element.tag, 
                                " - " + element.attrib['uuid'] if 'uuid' in element.attrib else '' ))
            if '_title' in element.attrib:
                print( "{}{}title: {}".format( IDENT, IDENT * element.attrib['_level'], element.attrib['_title'] ))
            if '_filename' in element.attrib:
                print( "{}{}file:  {}".format( IDENT, IDENT * element.attrib['_level'], element.attrib['_filename'] ))
        print( "\n\nPROCESSING\n==========\n")
    
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
    # _get_directory
    # #############################################################################################################################
    # Hugo structure
    #   content
    #
    # Pelican structure
    #   content
    #   ├── pages
    #   |   ├── [filename1].html
    #   |   ├── [filename2].html --> {filename}[filename2].html
    #   |   └── attachments
    #   |       ├── [filename1]
    #   |       |   └── [attachment1] --> {attach}attachments/[filename1]/[attachment1]
    #   |       └── [filename2]
    #   |           └── [attachment2] --> {attach}attachments/[filename2]/[attachment2]
    #   ├── attachments
    #   |   ├── [filename1]
    #   |   |   └── [attachment1] --> {static}/attachments/[filename1]/[attachment1]
    #   |   └── [filename2]
    #   |       └── [attachment2] --> {static}/attachments/[filename2]/[attachment2]
    #   ├── articles
    #   |   ├── [filename1]
    #   |   |   └── [uuid1].html
    #   |   └── [filename2]
    #   |       └── [uuid2].html
    #   └── pelican.conf.py
    #           PATH = 'content'
    #           PAGE_PATHS = ['pages']
    #           ARTICLE_PATHS = ['articles']

    def _get_directory( self, type='attachment', relative=False ):
        dir = None
        if self._stack == 'hugo':
            dir = ''
        elif self._stack == 'pelican':
            if type == 'attachments': dir = os.path.join( "attachments", self._filename )
            elif type == 'post': dir = os.path.join( "articles", self._filename )
            elif type == 'page': dir = os.path.join( "pages" )

        if dir: dir = os.path.join( self._path, dir )
        if not relative: dir = os.path.join( self._site, self._path )

        return dir

    # #############################################################################################################################
    # _get_file
    # #############################################################################################################################

    def _get_file( self, name, type='post', relative=False ):

        file = name
        if self._stack == 'hugo':
            if type == 'post': 
                file = '_index.html'
        elif self._stack == 'pelican':
            if type in ['page', 'post']: 
                file = os.path.basename(name).split(".")[0] + ".html"

        return os.path.join( self._get_directory(type, relative), file )

    # #############################################################################################################################
    # _get_link
    # #############################################################################################################################
    # type of link:
    #   external:external webpage 
    #       ref
    #   parent, child, peer: internal anchor refering to uuid
    #       hugo:
    #       pelican: {filename}[self._filename].html#[ref]
    #   link: external anchor refering to uuid
    #       hugo:
    #       pelican: {filename}[filename].html#[ref]
    #   attachment: link to a internal file
    #       hugo:
    #       pelican: {static}/attachments/[self._filename]/[ref]

    def _get_link( self, type, ref, filename=None ):

        link = None
        if self._stack == 'hugo':
            link = ref
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
    # _set_topics
    # #############################################################################################################################

    def _set_topics( self ):

        self._set_parent( elements=self._elements, parent=None )

        for element in self._elements.iter('topic'):

            # _summary
            if 'note' in element.attrib:
                element.attrib['_summary'] = element.attrib['note']

            # _links
            element.attrib['_links'] = []

            if '_parent' in element.attrib:
                parents = self._elements.findall( ".//*[@uuid='{}']".format(element.attrib['_parent']) )
                for parent in parents:
                    link = { 'ref': self._get_link( 'parent', parent.attrib['uuid'] ), 'type': 'parent' }
                    element.attrib['_links'].append( link )

            if 'uuid' in element.attrib:
                for child in self._elements.findall( ".//*[@_parent='{}']".format(element.attrib['uuid']) ) :
                    if child.tag == 'topic' and '_directory' in child.attrib: 
                        link = { 'ref': self._get_link( 'child', child.attrib['uuid'] ), 'type': 'child' }
                        element.attrib['_links'].append( link )

                for relation in self._elements.findall( ".//*[@end1-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = self._elements.find( ".//*[@uuid='{}']".format(relation.attrib['end2-uuid']) )
                    link = { 'ref': self._get_link( 'peer', rel.attrib['uuid'] ), 'type': 'peer' }
                    element.attrib['_links'].append( link )

                for relation in self._elements.findall( ".//*[@end2-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = self._elements.find( ".//*[@uuid='{}']".format(relation.attrib['end1-uuid']) )
                    link = { 'ref': self._get_link( 'peer', rel.attrib['uuid'] ), 'type': 'peer' }
                    element.attrib['_links'].append( link )

            # add the link
            # http://www.google.fr
            # ithoughts://open?topic=65F7D386-7686-470E-BABC-A3535A6B0798
            # ithoughts://open?path=Servers.itmz&topic=6D35D231-1C09-4B09-8FCD-E0799EA14096
            # ../../Pharaoh/Downloads/Ariba%20Guided%20Buying.pdf
            if 'link' in element.attrib:
                link = None
                target = re.split( r":", element.attrib['link'])
                if target[0] == 'http' or  target[0] == 'https': 
                    link = { 'ref': self._get_link( 'external', element.attrib['link'] ), 'type': 'external' }
                elif target[0] == 'ithoughts':
                    target = re.split( r"[///?=&]+", target[1])
                    if target[1] == 'open':
                        link = { 'ref': self._get_link( 'link', 
                                                        target[target.index('topic') + 1], 
                                                        os.path.basename(target[target.index('path') + 1]) if 'path' in target else None ), 
                                 'type': 'link' }

                if link:
                    element.attrib['_links'].append( link )

            # attachment
            if 'att-id' in element.attrib:
                try:
                    # read in itmz file
                    filename = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )
                    data = self._ithoughts.read(filename)

                    # write attachment
                    out_ext = os.path.splitext(element.attrib['att-name'])[1]
                    out_file = self._get_file( element.attrib['att-id'] + out_ext, type='attachment', relative=False)
                    out_dir = os.path.dirname(out_file)
                    if not os.path.isdir(out_dir): 
                        os.makedirs(out_dir)
                    with open(out_file, 'wb') as fs: 
                        fs.write(data) 

                    element.attrib['_links'].append( { 'title': element.attrib['att-name'], 
                                                       'ref': self._get_link( 'attachment', element.attrib['att-id'] + out_ext ),
                                                       'type': 'attachment' } )
                except:
                    pass

            if len(element.attrib['_links']) == 0: element.attrib.pop('_links')



            # cleanup
            to_remove = ['position', 'color']
            for key in to_remove: 
                if key in element.attrib: element.attrib.pop(key)

    # #############################################################################################################################
    # _get_html
    # #############################################################################################################################

    def _get_html( self ):

        output = ''
        output += self._get_frontmatter()
        output += '<html>\n'
        output += self._get_header()
        output += '<body>\n'
        for topic in self._elements.iter('topic'):
            if not '_parent' in topic.attrib: output += self._get_body( topic, 0 )
        output += '</body>\n'
        output += '</html>'

        return output

    # #############################################################################################################################
    # _get_frontmatter
    # #############################################################################################################################

    def _get_frontmatter( self ):

        output = "---\n"
        output += 'title: "{}"\n'.format(self._filename)
        output += "date: {}\n".format(self._elements.attrib['modified'])
        output += 'author: "{}"\n'.format( self._elements.attrib['author'] )
        output += '---\n'

        return output

    # #############################################################################################################################
    # _get_header
    # #############################################################################################################################

    def _get_header( self ):

        output = '<head>\n'
        output += '\t<title>{}</title>\n'.format(self._filename)
        output += '\t<meta name="date" content="{}" />\n'.format(self._elements.attrib['modified'])
        # output += '\t<meta name="modified" content="{}" />\n'.format('')
        # output += '\t<meta name="keywords" content="{}" />\n'.format('')
        # output += '\t<meta name="category" content="{}" />\n'.format('')
        output += '\t<meta name="author" content="{}" />\n'.format(self._elements.attrib['author'])
        # output += '\t<meta name="authors" content="{}" />\n'.format('')
        output += '\t<meta name="slug" content="{}" />\n'.format(self._normalize(self._filename, slug=True))
        # output += '\t<meta name="summary" content="{}" />\n'.format('')
        # output += '\t<meta name="lang" content="{}" />\n'.format('')
        # output += '\t<meta name="translation" content="{}" />\n'.format('')
        output += '\t<meta name="status" content="{}" />\n'.format('published')
        output += '</head>\n'

        return output

    # #############################################################################################################################
    # _get_metadata
    # #############################################################################################################################

    def _get_metadata( self ):

        output = "---\n"
        output += 'title: "{}"\n'.format(filename)
        output += "date: {}\n".format(self._elements.attrib['modified'])
        output += 'author: "{}"\n'.format( elements.attrib['author'] )
        output += '---\n'

        return output

    # #############################################################################################################################
    # _get_body
    # #############################################################################################################################

    def _get_body( self, topic, level=0 ):

        output = ''

        if topic.tag == 'topic':

            if '_links' in topic.attrib:
                hyperlink = ''
                for link in topic.attrib['_links']:
                    output += '<a href="{}"'.format( link['ref'].lower())
                    if link['type'] == 'external' or ( link['type'] == 'link' and link['ref'][0] != '#' ): 
                        output += ' target="_blank"'
                    icon = None
                    if link['type'] == 'external': icon = 'fa-solid fa-link'
                    elif link['type'] == 'parent': icon = 'fa-solid fa-circle-up'
                    elif link['type'] == 'child': icon = 'fa-solid fa-circle-down'
                    elif link['type'] == 'peer': icon = 'fa-solid fa-circle-right'
                    if icon:
                        output += ' class="btn btn-default {}"'.format(icon)
                    output += '>'
                    if 'title' in link: output += link['title']
                    output += '</a> '
                output += '\n'

            body = ''

            # add content
            #   force first row to be H2
            #   shift H by two levels
            if 'text' in topic.attrib: 
                body = topic.attrib['text']
                if body[0] not in '[#`~]': body = '# ' + body
                body += '\n'

            # add task
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

            # add attachment as image
            if '_attachment' in topic.attrib: 
                body += "![{}]({})\n".format( topic.attrib['_attachment']['title'], topic.attrib['_attachment']['ref'])

            # convert to html
            body = markdown.markdown(body, extensions=['tables'])

            # add anchors
            if 'uuid' in topic.attrib:
                body = re.sub( r'<h1>', '<h1><a id="{}"></a>'.format(topic.attrib['uuid']), body, flags = re.MULTILINE )

            # shift headers by level
            for h in range (6, 0, -1):
                body = re.sub( r'h' + str(h) + r'>', 'h{}>'.format(h+level+1), body, flags = re.MULTILINE )

            output += body

            # add childs
            if 'uuid' in topic.attrib:
                for child in self._elements.findall( ".//*[@_parent='{}']".format(topic.attrib['uuid']) ) :
                    if child.tag == 'topic':
                        output += self._get_body( child, level+1 )

        if output != '': output += '\n'
        return output

    # #############################################################################################################################
    # process_file
    # #############################################################################################################################

    def process_file( self, force=False ):

        # tag iThoughts
        mod_time = datetime.strptime(self._elements.attrib['modified'], "%Y-%m-%dT%H:%M:%S")

        # out_file
        out_file = self._get_file(self._filename, type='post' )
        out_time = datetime.fromtimestamp(os.path.getmtime(out_file)) if os.path.isfile(out_file) else None
        out_dir = os.path.dirname(out_file)

        # need to proceed?
        if force or not out_time or mod_time > out_time:

            # set the topic tree
            self._set_topics()

            self._print_elements()
        
            output = self._get_html()

            # write the output file
            print('  > ' + out_file)

            print("    - title:    {}".format( self._filename ))
            print("    - modified: {}".format( mod_time.strftime("%Y-%m-%dT%H:%M:%S") ))
            if out_time: 
                print("    - file:     {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(out_file, 'w', encoding='utf-8') as fs:
                fs.write(output) 

            out_time = datetime.fromtimestamp(os.path.getmtime(out_file))
            print("    - saved:    {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

# #################################################################################################################################
# process_files
# #################################################################################################################################

def process_files(source, site, stack, force):

    filenames = []
    if os.path.isdir(source):
        for top, dirs, files in os.walk(source):
            for name in files:
                if os.path.splitext(name)[1] == '.itmz': filenames.append(os.path.join(top, name))
    else:
        filenames.append(source)

    for file in filenames:
        if not os.path.exists(file):
            print( "{} does not exist".format(file))
            continue
        else:
            itmz = ITMZ( file=file, site=site, stack=stack )
            itmz.process_file( force )

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
           
    process_files( source=args.input, site=args.output, stack=stack, force=args.force or False )

    print( "http://docker.local:8888")

main()