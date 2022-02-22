#!/usr/bin/env python

import argparse
import os
import re
import shutil
import time
from datetime import datetime

import xml.etree.ElementTree as ET
import zipfile
import unicodedata
from docutils.utils import column_width

from markupsafe import Markup, escape   
import unidecode

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

    _file = None
    _filename = None
    _elements = None

    # #############################################################################################################################
    # __init__
    # #############################################################################################################################

    def __init__(self, site, file):
        self._site = site
        self._file = file
        self._filename = os.path.basename(file).split(".")[0]

        ithoughts = zipfile.ZipFile( file, 'r')
        xmldata = ithoughts.read('mapdata.xml')
        self._elements = ET.fromstring(xmldata)

        self._set_parent( self._elements )
        self._set_topics()
        self._set_relationships()

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
    # _get_content
    # #############################################################################################################################

    def _get_content( self, element ):
        if 'text' in element.attrib:
            if element.attrib['text'].splitlines()[0].startswith("# "): title = element.attrib['text'].splitlines()[0][2:]
            else: title = element.attrib['text'].splitlines()[0]
            content = ''.join(element.attrib['text'].splitlines(keepends=True)[1:])
        else:
            title ="{}".format(element.attrib['uuid'])
            content = None
        link = None

        # fields are s0 [s1][s2] s3
        # ref is [s2]: s4
        fields = re.match( r'(.*)\[(.+)\]\[([0-9]+)\](.*)', title )
        if fields and fields.groups()[2] != '': 
            lines = content.splitlines(keepends=True)
            for line in lines:
                ref = re.match( r'(.*)\[' + re.escape(fields.groups()[2]) + r'\]:(.*)', line )
                if ref:
                    link = { 'title': fields.groups()[1], 'ref': ref.groups()[1].strip() }
                    lines.remove(line)
                    break
            content = ''.join(lines)

        if link:
            title = fields.groups()[0] + fields.groups()[1] + fields.groups()[3]
            return { 'title': title, 'link': link, 'content': content}
        else:
            return { 'title': title, 'content': content}
        
    # #############################################################################################################################
    # _set_parent
    # #############################################################################################################################

    def _set_parent( self, elements, parent=None, level=0 ):
        for element in elements: 
            if parent: 
                if 'uuid' in parent.attrib: 
                    element.attrib['_parent'] = parent.attrib['uuid']
                if '_directory' in parent.attrib and 'uuid' in element.attrib: 
                    element.attrib['_directory'] = os.path.join( parent.attrib['_directory'], element.attrib['uuid'] )
                else:
                    element.attrib['_directory'] = self._normalize( self._get_content(element)['title'], slug= True )

            # print( "{}{}: {} [{}] [{}]".format( '  ' * level, element.tag, element.attrib['uuid'] if 'uuid' in element.attrib else '', element.attrib['_parent'] if '_parent' in element.attrib else '', element.attrib['_directory'] if '_directory' in element.attrib else '' ))

            self._set_parent( element, element, level+1 )

    # #############################################################################################################################
    # _get_parent
    # #############################################################################################################################

    def _get_parent( self, topic ):
        parent = None
        if _parent in topic.attrib: parent = self._elements.find( ".//*[@uuid='{}']".format(topic.attrib['_parent']) )
        return parent

    # #############################################################################################################################
    # _set_topics
    # #############################################################################################################################

    def _set_topics( self ):
        for element in self._elements.iter(): 

            if element.tag == 'topic': 

                content = self._get_content( element )

                # _title = text first row without trailing #
                element.attrib['_title'] = content['title']

                # _titleLink 
                if 'link' in content: element.attrib['_titlelink'] = content['link']

                # _content
                if content['content']: element.attrib['_content'] = content['content']

                # _summary
                # if 'note' in element.attrib:
                #     element.attrib['_summary'] = element.attrib['note']

                # _filename
                if '_directory' in element.attrib:
                    element.attrib['_filename'] = os.path.join( element.attrib['_directory'], '_index.md' )

                # _comment
                # if 'callout' in element.attrib:
                #     element.tag = 'comment'

                # _attachment
                self._set_attachment( element )

                # cleanup
                to_remove = ['position', 'color']
                for key in to_remove: 
                    if key in element.attrib: element.attrib.pop(key)

    # #################################################################################################################################
    # _set_relationships
    # #################################################################################################################################

    def _set_relationships( self ):
        for element in self._elements.iter('topic'):

            element.attrib['_relationships'] = []

            if '_parent' in element.attrib:
                parents = self._elements.findall( ".//*[@uuid='{}']".format(element.attrib['_parent']) )
                for parent in parents:
                    link = { 'title': parent.attrib['_title'], 'ref': os.path.join( "..", "_index.md") }
                    element.attrib['_relationships'].append( link )

            if 'uuid' in element.attrib:
                for child in self._elements.findall( ".//*[@_parent='{}']".format(element.attrib['uuid']) ) :
                    if child.tag == 'topic' and '_directory' in child.attrib: 
                        link = { 'title': child.attrib['_title'], 'ref': os.path.join( os.path.sep, child.attrib['_directory'] ) }
                        element.attrib['_relationships'].append( link )

                for relation in self._elements.findall( ".//*[@end1-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = self._elements.find( ".//*[@uuid='{}']".format(relation.attrib['end2-uuid']) )
                    link = { 'title': rel.attrib['_title'], 'ref': os.path.join( os.path.sep, rel.attrib['_directory'], "_index.md") }
                    element.attrib['_relationships'].append( link )

                for relation in self._elements.findall( ".//*[@end2-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = self._elements.find( ".//*[@uuid='{}']".format(relation.attrib['end1-uuid']) )
                    link = { 'title': rel.attrib['_title'], 'ref': os.path.join( os.path.sep, rel.attrib['_directory'], "_index.md") }
                    element.attrib['_relationships'].append( link )

            if len(element.attrib['_relationships']) == 0: element.attrib.pop('_relationships')

    # #############################################################################################################################
    # _set_attachment
    # #############################################################################################################################

    def _set_attachment( self, topic ):
        if 'att-id' in topic.attrib:
            try:
                ithoughts = zipfile.ZipFile( self._file, 'r')
                filename = os.path.join( "assets", topic.attrib['att-id'], topic.attrib['att-name'] )
                data = ithoughts.read(filename)

                out_ext = os.path.splitext(topic.attrib['att-name'])[1]
                out_filename = os.path.join( topic.attrib['_directory'], topic.attrib['att-id'] + out_ext ) 
                
                out_file = os.path.join( self._site, out_filename)
                out_dir = os.path.dirname(out_file)
                if not os.path.isdir(out_dir): os.makedirs(out_dir)
                with open(out_file, 'wb') as fs: fs.write(data) 

                topic.attrib['_attachment'] = '![' + topic.attrib['att-id'] + ']'
                topic.attrib['_attachment'] += '(' + topic.attrib['att-id'] + out_ext + ' "' 
                topic.attrib['_attachment'] += topic.attrib['att-name'] +'")'
            except:
                pass

    # #############################################################################################################################
    # _get_header
    # #############################################################################################################################

    def _get_header( self, topic ):
        output = "---\n"

        output += 'title: "{}"\n'.format(topic.attrib['_title'])
        output += "date: {}\n".format(topic.attrib['created'])
        if 'modified' in topic.attrib: output += 'lastmod: {}\n'.format(topic.attrib['modified'])
        if '_images' in topic.attrib: output += 'images: "{}"\n'.format(topic.attrib['_images'])
        if '_keywords' in topic.attrib: output += 'keywords: "{}"\n'.format(topic.attrib['_summary'])
        if 'uuid' in topic.attrib: output += 'slug: %s\n' % topic.attrib['uuid']
        if '_summary' in topic.attrib: output += 'summary: "{}"\n'.format(topic.attrib['_summary'])

        output += '---\n'

        return output

    # #############################################################################################################################
    # _get_body
    # #############################################################################################################################

    def _get_body( self, topic ):

        output = ''

        if '_titlelink' in topic.attrib:
            hyperlink = '{{% button href="' + topic.attrib['_titlelink']['ref'] + '" icon="fa-brands fa-wordpress" %}}'
            hyperlink += topic.attrib['_titlelink']['title'] + '{{% /button %}}'
            output += hyperlink + ' '

        if '_relationships' in topic.attrib:
            for relation in topic.attrib['_relationships']:
                # hyperlink = '[' + relation['title'] + ']'
                # hyperlink += '({{< ref "' + relation['ref'] + '" >}})'
                hyperlink = '{{% button href="' + relation['ref'].lower() + '" %}}'
                hyperlink += relation['title'] + '{{% /button %}}'
                output += hyperlink + ' '
            output += '\n\n'

        # add attrib for debug purpose
        # output += "attrib: {}".format(topic.attrib) + "\n\n"

        if '_content' in topic.attrib: 
            output += topic.attrib['_content']
            output += "\n"

        # task
        # task_header = ''
        # task_values = ''
        # task = { 'task-start': 'Start', 'task-due': 'Due', 'cost': 'Cost', 'task-effort': 'Effort', 
        #         'task-priority': 'Priority', 'task-progress': 'Progress', 'resources': 'Resource(s)' }
        # for key in task:
        #     if key in topic.attrib:
        #         if key == 'task-progress' and int(topic.attrib[key]) > 100: continue
        #         if key == 'task-progress': topic.attrib[key] += '%'
        #         if key == 'task-effort' and topic.attrib[key][0] == '-': continue
        #         task_header += "   {} - {}\n".format( '*' if task_header == '' else ' ', task[key] )
        #         task_values += "   {} - {}\n".format( '*' if task_values == '' else ' ', topic.attrib[key] )

        # if task_header != '':
        #     output += ".. list-table:: Task\n"
        #     output += "   :widths: auto\n"
        #     output += "   :header-rows: 1\n"
        #     output += "\n"
        #     output += task_header
        #     output += task_values
        #     output += "\n"

        # attachments
        if '_attachment' in topic.attrib: 
            output += topic.attrib['_attachment'] + '\n'

        return output

    # #############################################################################################################################
    # process_file
    # #############################################################################################################################

    def process_file( self, force=False ):
        for topic in self._elements.iter('topic'):
            # let's go !
            # print('  creating {}...'.format(topic.attrib['uuid']))

            topic.attrib['_header'] = self._get_header( topic )

            topic.attrib['_body'] = self._get_body( topic )

            # write the output file
            if '_header' in topic.attrib:
                out_file = os.path.join( self._site, topic.attrib['_filename'] )
                print('  > ' + out_file)
                print("    - title:   {}".format( topic.attrib['_title'] ))
                if 'created' in topic.attrib: print("    - created: {}".format( topic.attrib['created'] ))
                if 'modified' in topic.attrib: 
                    topic_time = datetime.strptime(topic.attrib['modified'], "%Y-%m-%dT%H:%M:%S")
                    print("    - updated: {}".format( topic_time.strftime("%Y-%m-%dT%H:%M:%S") ))
                else:
                    topic_time = datetime.strptime(topic.attrib['created'], "%Y-%m-%dT%H:%M:%S")
                    print("    - created: {}".format( topic_time.strftime("%Y-%m-%dT%H:%M:%S") ))

                if os.path.isfile(out_file):
                    out_time = datetime.fromtimestamp(os.path.getmtime(out_file))
                    print("    - file:    {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))
                    if not force or topic_time > out_time:
                        print("    - skipped" )
                        continue

                out_dir = os.path.dirname(out_file)
                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                with open(out_file, 'w', encoding='utf-8') as fs:
                    fs.write(topic.attrib['_header']) 
                    fs.write(topic.attrib['_body']) 

                out_time = datetime.fromtimestamp(os.path.getmtime(out_file))
                print("    - saved:   {}".format( out_time.strftime("%Y-%m-%dT%H:%M:%S") ))

        return True

# #################################################################################################################################
# process_files
# #################################################################################################################################

def process_files(directory, site):

    filenames = []
    if os.path.isdir(directory):
        for top, dirs, files in os.walk(directory):
            for name in files:
                if os.path.splitext(name)[1] == '.itmz': filenames.append(os.path.join(top, name))
    else:
        filenames.append(directory)

    cnt = 0
    for file in filenames:
        if not os.path.exists(file):
            print( "{} does not exist".format(file))
            continue
        else:
            itmz = ITMZ(site, file)

            ret = itmz.process_file( force=False )

            time.sleep(20)
            # if ret: cnt +=1
            # if cnt >= 1: return

# #################################################################################################################################
# main
# #################################################################################################################################

def main():
    parser = argparse.ArgumentParser(
        description="Transform iThoughts files into reST (rst) files for Pelican static site generator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        dest='input', help='The input file or directory to read')
    parser.add_argument(
        '-o', '--output', dest='output', default='content',
        help='Output path')

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

    process_files( args.input, args.output )

    print( "http://docker.local:8888")

main()