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
    _source = None
    _page_only = False

    # #############################################################################################################################
    # __init__
    # #############################################################################################################################

    def __init__(self, source, site, page_only):
        self._site = site
        self._source = source
        self._page_only = page_only

        self._set_site()

    # #############################################################################################################################
    # _set_site
    # #############################################################################################################################

    def _set_site(self):
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

    def _get_directory( self, file, relative=False ):
        paths = file.split(" - ")
        for idx, path in enumerate(paths):
            paths[idx] = self._normalize( path, slug= True )
            paths[idx] = re.sub( r'(?u)\A-*', '', paths[idx] )
            paths[idx] = re.sub( r'(?u)-*\Z', '', paths[idx] )
        if relative: return os.path.sep.join( paths )
        else: return os.path.join( self._site, os.path.sep.join( paths ) )

    # #############################################################################################################################
    # _set_topics
    # #############################################################################################################################

    def _set_topics( self, elements ):
        for element in elements.iter('topic'):

            content = self._get_content( element )

            # _title = text first row without trailing #
            element.attrib['_title'] = content['title']

            # _titleLink 
            if 'link' in content: element.attrib['_titlelink'] = content['link']

            # _content
            if content['content']: element.attrib['_content'] = content['content']

            # _summary
            if 'note' in element.attrib:
                element.attrib['_summary'] = element.attrib['note']

            # _description
            # if 'note' in element.attrib:
            #     element.attrib['_description'] = element.attrib['note']

            # _comment
            # if 'callout' in element.attrib:
            #     element.tag = 'comment'

            # cleanup
            to_remove = ['position', 'color']
            for key in to_remove: 
                if key in element.attrib: element.attrib.pop(key)

    # #################################################################################################################################
    # _set_links
    # #################################################################################################################################

    def _set_links( self, directory, ithoughts, elements ):
        for element in elements.iter('topic'):

            element.attrib['_relationships'] = []

            if '_titlelink' in element.attrib:
                link = { 'title': element.attrib['_titlelink']['title'], 'ref': element.attrib['_titlelink']['ref'], 'type': 'external' }
                element.attrib['_relationships'].append( link )

            # if '_parent' in element.attrib:
            #     parents = elements.findall( ".//*[@uuid='{}']".format(element.attrib['_parent']) )
            #     for parent in parents:
            #         link = { 'title': parent.attrib['_title'], 'ref': os.path.join( "..", ""), 'type': 'parent' }
            #         element.attrib['_relationships'].append( link )

            # if 'uuid' in element.attrib:
            #     for child in elements.findall( ".//*[@_parent='{}']".format(element.attrib['uuid']) ) :
            #         if child.tag == 'topic' and '_directory' in child.attrib: 
            #             link = { 'title': child.attrib['_title'], 'ref': os.path.join( os.path.sep, child.attrib['_directory'] ), 'type': 'child' }
            #             element.attrib['_relationships'].append( link )

            #     for relation in elements.findall( ".//*[@end1-uuid='{}']".format(element.attrib['uuid']) ) :
            #         rel = elements.find( ".//*[@uuid='{}']".format(relation.attrib['end2-uuid']) )
            #         link = { 'title': rel.attrib['_title'], 'ref': os.path.join( os.path.sep, rel.attrib['_directory'], ""), 'type': 'peer' }
            #         element.attrib['_relationships'].append( link )

            #     for relation in elements.findall( ".//*[@end2-uuid='{}']".format(element.attrib['uuid']) ) :
            #         rel = elements.find( ".//*[@uuid='{}']".format(relation.attrib['end1-uuid']) )
            #         link = { 'title': rel.attrib['_title'], 'ref': os.path.join( os.path.sep, rel.attrib['_directory'], ""), 'type': 'peer' }
            #         element.attrib['_relationships'].append( link )

            if len(element.attrib['_relationships']) == 0: element.attrib.pop('_relationships')

            if 'att-id' in element.attrib:
                try:
                    filename = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )
                    data = ithoughts.read(filename)

                    out_ext = os.path.splitext(element.attrib['att-name'])[1]
                    out_filename = os.path.join( directory, element.attrib['att-id'] + out_ext ) 
                    
                    out_file = os.path.join( self._site, out_filename)
                    out_dir = os.path.dirname(out_file)
                    if not os.path.isdir(out_dir): os.makedirs(out_dir)
                    with open(out_file, 'wb') as fs: fs.write(data) 

                    src = os.path.join( os.path.sep, directory, element.attrib['att-id'] + out_ext)
                    attachment = { 'alt': element.attrib['att-id'], 'title': element.attrib['att-name'],'src': src}

                    element.attrib['_attachment'] = attachment
                except:
                    pass

    # #############################################################################################################################
    # _get_body
    # #############################################################################################################################

    def _get_body( self, elements, topic, level=0 ):

        output = ''

        print( "{}* {} - {}".format( "  "*level, topic.tag, topic.attrib['uuid'] if 'uuid' in topic.attrib else ''))

        if topic.tag == 'topic':

            if level == 0:
                output += '{{% mytoc %}}\n'

            # set buttons
            if '_links' in topic.attrib:
                hyperlink = ''
                for link in topic.attrib['_links']:
                    icon = ''
                    if link['type'] == 'external': icon = ' icon="fa-solid fa-link"'
                    elif link['type'] == 'link': icon = ' icon="fa-solid fa-circle-right"'
                    else: continue
                    hyperlink += '{{% mybutton href="' + link['ref'].lower() + '"'
                    hyperlink += icon
                    hyperlink += ' target="_blank"' if link['type'] == 'external' else ''
                    hyperlink += ' %}}'
                    hyperlink += link['title']
                    hyperlink += '{{% /mybutton %}} '
                    output = hyperlink + ' '
                output += hyperlink + '\n'

            body = ''

            # add content
            #   force first row to be H2
            #   shift H by two levels
            if 'text' in topic.attrib: 
                body = re.sub( r'^#', '#' * (level+2), topic.attrib['text'], flags = re.MULTILINE )
                if body[0] not in '[#`~]': body = '## ' + body
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
                body += "|".join(task_header) + "\n"
                body += "|".join(task_sep) + "\n"
                body += "|".join(task_values) + "\n"
                body += "\n"

            # add attachment as image
            if '_attachment' in topic.attrib: 
                body += "![{}]({})\n".format( topic.attrib['_attachment']['title'], topic.attrib['_attachment']['src'])

            output += markdown.markdown(body, extensions=['tables'])

            # add childs
            if 'uuid' in topic.attrib:
                for child in elements.findall( ".//*[@_parent='{}']".format(topic.attrib['uuid']) ) :
                    if child.tag == 'topic':
                        output += self._get_body( elements, child, level+1 )

        return output

    # #############################################################################################################################
    # _process_file
    # #############################################################################################################################

    def _process_file( self, file, force=False ):

        filename = os.path.basename(file).split(".")[0]

        # read ITMZ file
        ithoughts = zipfile.ZipFile( file, 'r')
        xmldata = ithoughts.read('mapdata.xml')
        elements = ET.fromstring(xmldata)

        # tag iThoughts
        mod_time = datetime.strptime(elements.attrib['modified'], "%Y-%m-%dT%H:%M:%S")

        # out_file
        out_file = os.path.join( self._get_directory(filename), self._normalize(filename) + ".html" )
        out_time = datetime.fromtimestamp(os.path.getmtime(out_file)) if os.path.isfile(out_file) else None
        out_dir = os.path.dirname(out_file)

        # need to proceed?
        if force or not out_time or mod_time > out_time:

            # set the topic tree
            self._set_parent( elements )
            self._set_links( self._get_directory(filename, True), ithoughts, elements )

            self._print_elements(elements)
        
            # header
            header = "---\n"
            header += 'title: "{}"\n'.format(filename)
            header += "date: {}\n".format(mod_time.strftime("%Y-%m-%dT%H:%M:%S"))
            header += 'author: "{}"\n'.format( elements.attrib['author'] )
            header += 'menu: "{}"\n'.format(filename)
            header += '---\n'

            # body
            body = ''
            for topic in elements.iter('topic'):
                if not '_parent' in topic.attrib: body += self._get_body( elements, topic, 0 )

            # write the output file
            print('  > ' + out_file)

            print("    - title:    {}".format( filename ))
            print("    - modified: {}".format( mod_time.strftime("%Y-%m-%dT%H:%M:%S") ))
            if out_time: 
                print("    - file:     {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)

            with open(out_file, 'w', encoding='utf-8') as fs:
                fs.write(header) 
                fs.write(body) 

            out_time = datetime.fromtimestamp(os.path.getmtime(out_file))
            print("    - saved:    {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

    # #################################################################################################################################
    # process_files
    # #################################################################################################################################

    def process_files(self, force=False):

        filenames = []
        if os.path.isdir(self._source):
            for top, dirs, files in os.walk(self._source):
                for name in files:
                    if os.path.splitext(name)[1] == '.itmz': filenames.append(os.path.join(top, name))
        else:
            filenames.append(self._source)

        for file in filenames:
            if not os.path.exists(file):
                print( "{} does not exist".format(file))
                continue
            else:
                self._process_file( file, force=True )

# #################################################################################################################################
# main
# #################################################################################################################################

def main():
    parser = argparse.ArgumentParser(
        description="Transform iThoughts files into reST (rst) files for Pelican static site generator.",
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
        '--page-only', action='store_true', dest='page_only',
        help='Export pages only')

    args = parser.parse_args()

    if os.path.exists(args.output):
        try:
            # shutil.rmtree(args.output)
            pass
        except OSError:
            error = 'Unable to remove the output folder: ' + args.output
            exit(error)

    if not os.path.exists(args.output):
        try:
            os.mkdir(args.output)
        except OSError:
            error = 'Unable to create the output folder: ' + args.output
            exit(error)
           
    itmz = ITMZ( source=args.input, site=args.output, page_only=args.page_only or False )

    itmz.process_files( force=args.force or False )

    print( "http://docker.local:8888")

main()