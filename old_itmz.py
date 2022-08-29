#!/usr/bin/env python

import re
import shutil
import time
import pprint
from datetime import datetime
import markdown
from markdownify import markdownify
from tabulate import tabulate
import urllib.parse
# from selenium import webdriver


import xml.etree.ElementTree as ET
import zipfile

# #################################################################################################################################
# ITMZ
# #################################################################################################################################

class ITMZ2STACK:

    _site = None
    _source = None
    _stack = None
    _output = None

    # #############################################################################################################################
    # __init__
    # #############################################################################################################################

    def __init__(self, source, site, stack, output):
        self._source = source
        self._site = site
        self._stack = stack
        self._output = output

        self._set_site()

    # #############################################################################################################################
    # _set_site
    # #############################################################################################################################

    def _set_site(self):
        if self._stack == 'hugo': self._set_hugo_site()
        elif self._stack == 'pelican': self._set_pelican_site()
        elif self._stack == 'nikola': self._set_nikola_site()

    # #############################################################################################################################
    # _set_pelican_site
    # #############################################################################################################################

    def _set_pelican_site(self):
        pass

    # #############################################################################################################################
    # _set_nikola_site
    # #############################################################################################################################

    def _set_nikola_site(self):
        pass

    # #############################################################################################################################
    # _set_hugo_site
    # #############################################################################################################################

    def _set_hugo_site(self):
        shortcodes = {}
        shortcodes['mybutton'] = '''
<a {{ with .Get "href" }} href="{{ . }}" {{ end }}  {{ with .Get "target" }} target="{{ . }}" {{ end }} {{ with .Get "icon" }} class="{{ . }} btn btn-default" {{ end }}>
{{ .Inner }}
</a>
        '''

        shortcodes['myanchor'] = '''
<a {{ with .Get "id" }} id="{{ . }}" {{ end }}></a>
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
theme = "shadocs"
themesDir = "../themes"

[markup]
  defaultMarkdownHandler = 'goldmark'

  [markup.tableOfContents]
    endLevel = 7
    ordered = false
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

        # read ITMZ file
        ithoughts = zipfile.ZipFile( file, 'r')
        xmldata = ithoughts.read('mapdata.xml')
        elements = ET.fromstring(xmldata)

        # tag iThoughts
        mod_time = datetime.strptime(elements.attrib['modified'], "%Y-%m-%dT%H:%M:%S")

        # out_file
        out_file = structure['source']
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

            # self._print_elements( elements )
        
            output = ''
            if self._output == "html": output = self._get_html( structure, elements )
            elif self._output == "md": output = self._get_markdown( structure, elements )

            # write the output file
            print('  > ' + out_file)

            print("    - structure")
            pprint.pprint( structure, indent=18, sort_dicts=False )

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

    def _get_structure(self, file, base=None ):
        structure = {}

        structure['file'] = urllib.parse.unquote(file)
        structure['itmz'] = urllib.parse.unquote(base['itmz']) if base else structure['file']
        structure['title'] = os.path.basename(structure['file']).split(".")[0]
        structure['ext'] = os.path.splitext(structure['file'])[1]
        structure['slug'] = self._slugify(structure['title'])
        if not os.path.isabs(structure['file']):
            structure['file'] = os.path.join(os.path.split(structure['itmz'])[0], structure['file'])

        structure['abs path'] = os.path.split( os.path.join(self._site, os.path.relpath(structure['file'], self._source)))[0].split(os.path.sep)
        for idx, val in enumerate(structure['abs path']): structure['abs path'][idx] = self._slugify(val)

        if self._stack == 'hugo':
            if structure['ext'].lower() != '.itmz':
                structure['abs path'].append( base['slug'] )
                structure['abs path'].append( 'attachments' )
                structure['filename'] = structure['title'] + structure['ext']
            else:
                structure['abs path'].append( structure['slug'] )
                structure['filename'] = "_index." + self._output

        elif self._stack == 'pelican':
            pass

        structure['rel path'] = structure['abs path']
        for val in self._site.split(os.path.sep):
            if val in structure['rel path']: structure['rel path'].remove(val) 

        structure['source'] = os.path.join( os.getcwd(), self._site, os.path.sep.join(structure['abs path']), structure['filename'])
        structure['reference'] = os.path.sep + os.path.sep.join(structure['rel path']) + os.path.sep
        if structure['ext'].lower() != '.itmz':
            structure['reference'] += structure['filename']

        print( "----- {} - {} - {} ----".format(file, base['itmz'] if base else None, self._source ) )
        pprint.pprint( structure, sort_dicts=False )

        # cleanup
        to_remove = ['abs path', 'rel path', 'filename', 'ext']
        for key in to_remove: 
            if key in structure: structure.pop(key)

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

            # _relationships
            element.attrib['_relationships'] = []

            if '_parent' in element.attrib:
                parents = elements.findall( ".//*[@uuid='{}']".format(element.attrib['_parent']) )
                for parent in parents:
                    element.attrib['_relationships'].append({ 'type': 'parent', 'ref': '#' + parent.attrib['uuid'] })

            if 'uuid' in element.attrib:
                for child in elements.findall( ".//*[@_parent='{}']".format(element.attrib['uuid']) ) :
                    if child.tag == 'topic' and '_directory' in child.attrib: 
                        element.attrib['_relationships'].append({ 'type': 'child', 'ref': '#' + child.attrib['uuid'] })

                for relation in elements.findall( ".//*[@end1-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = elements.find( ".//*[@uuid='{}']".format(relation.attrib['end2-uuid']) )
                    element.attrib['_relationships'].append({ 'type': 'peer', 'ref': '#' + rel.attrib['uuid'] })

                for relation in elements.findall( ".//*[@end2-uuid='{}']".format(element.attrib['uuid']) ) :
                    rel = elements.find( ".//*[@uuid='{}']".format(relation.attrib['end1-uuid']) )
                    element.attrib['_relationships'].append({ 'type': 'peer', 'ref': '#' + rel.attrib['uuid'] })

            if len(element.attrib['_relationships']) == 0: element.attrib.pop('_relationships')

            # add the _link
            # http://www.google.fr
            # ithoughts://open?topic=65F7D386-7686-470E-BABC-A3535A6B0798
            # ithoughts://open?path=Servers.itmz&topic=6D35D231-1C09-4B09-8FCD-E0799EA14096
            # ../../Pharaoh/Downloads/Ariba%20Guided%20Buying.pdf

            # if not ithoughts:
            #   driver = webdriver.Firefox()
            #   driver.get('https://www.python.org')
            #   sleep(1)
            #   driver.get_screenshot_as_file("screenshot.png")
            #   driver.quit()

            if 'link' in element.attrib:
                target = re.split( r":", element.attrib['link'])
                if target[0] == 'http' or  target[0] == 'https': 
                    element.attrib['_link'] = { 'type': 'external', 'title': element.attrib['link'], 'ref': element.attrib['link'], 'target': '_blank'}

                elif target[0] == 'ithoughts':
                    target = re.split( r"[?=&]+", target[1])
                    if target[0] == '//open':
                        ref = ''
                        title = ''
                        if 'path' in target: 
                            struct = self._get_structure( target[target.index('path') + 1], structure )
                            ref += struct['reference']
                            title = struct['title']
                        if 'topic' in target: 
                            ref += '#' + target[target.index('topic') + 1]
                        element.attrib['_link'] = { 'type': 'link', 'title': title, 'ref': ref}

            # attachment
            if 'att-id' in element.attrib:
                try:
                    # read in itmz file
                    filename = os.path.join( "assets", element.attrib['att-id'], element.attrib['att-name'] )
                    data = ithoughts.read(filename)

                    # write attachment
                    out_ext = os.path.splitext(element.attrib['att-name'])[1]
                    link = self._get_structure( element.attrib['att-id'] + out_ext, structure)
                    out_file = link['source']
                    out_dir = os.path.dirname(out_file)
                    if not os.path.isdir(out_dir): 
                        os.makedirs(out_dir)
                    with open(out_file, 'wb') as fs: 
                        fs.write(data) 

                    element.attrib['_attachment'] = { 'type': 'image', 'title': element.attrib['att-name'], 'ref': link['reference']}

                    if '_link' in element.attrib:
                        if element.attrib['_link']['type'] == 'external':
                            element.attrib['_attachment']['link'] = element.attrib['_link']['ref']
                            element.attrib.pop( '_link' )

                except:
                    pass

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
    # _get_markdown
    # #############################################################################################################################

    def _get_markdown( self, structure, elements ):

        output = ''
        output += self._get_frontmatter(structure, elements)
        for topic in elements.iter('topic'):
            if not '_parent' in topic.attrib: output += self._get_body( elements, topic, 0 )

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

            # add relationships
            buttons = ''
            if '_relationships' in topic.attrib:
                for link in topic.attrib['_relationships']:
                    icon = None
                    if link['type'] == 'parent': icon = 'fa-solid fa-circle-up'
                    elif link['type'] == 'child': icon = 'fa-solid fa-circle-down'
                    elif link['type'] == 'peer': icon = 'fa-solid fa-circle-right'
                    elif link['type'] == 'unknown': continue
                    
                    if self._output == "html":
                        buttons += '<a href="{}"'.format( link['ref'])
                        if 'target' in link: buttons += ' target="{}"'.format(link['target'])
                        if icon: buttons += ' class="btn btn-default {}"'.format(icon)
                        buttons += '>'
                        if 'title' in link: buttons += link['title']
                        buttons += '</a> '
                    elif self._output == "md":
                        buttons += '{{< mybutton href="' + link['ref'] + '"'
                        if 'target' in link: buttons += ' target="{}"'.format(link['target'])
                        if icon: buttons += ' icon="{}"'.format( icon )
                        buttons += ' />}}'

            # add body
            if 'text' in topic.attrib: 
                body = ''
                if topic.attrib['text'][0] not in '[#`~]': body += '# '
                body += topic.attrib['text']
                # convert code
                body = re.sub( r'```', '~~~', body, flags = re.MULTILINE )
                #body = re.sub( r'~~~', '```', body, flags = re.MULTILINE )
                # add anchors to body
                body = re.sub( r'^(?P<line>.*)', '\g<line> {#' + topic.attrib['uuid'] + '}', body, count = 1 )

                # convert body to html
                #   shift headers
                #   reorder links
                body = markdown.markdown(body)
                # shift headers by level in body
                for h in range (6, 0, -1):
                    body = re.sub( r'h' + str(h) + r'>', 'h{}>'.format(h+level+1), body, flags = re.MULTILINE )
                # convert back to markdown
                if self._output == "md":
                    body = markdownify( body )

                # add anchors to body
                # if 'uuid' in topic.attrib:
                #     if self._output == "html":
                #         body = '<a id="{}">'.format(topic.attrib['uuid']) + body
                #     elif self._output == "md":
                #         body = '{{< myanchor id="' + topic.attrib['uuid'] + '" >}}\n' + body

                # process H7+
                if self._output == "md":
                    body = re.sub( r'^(?P<h>[#]{10}) (?P<title>.*)', '<h10>\g<title></h10>', body, flags = re.MULTILINE )
                    body = re.sub( r'^(?P<h>[#]{9}) (?P<title>.*)', '<h9>\g<title></h9>', body, flags = re.MULTILINE )
                    body = re.sub( r'^(?P<h>[#]{8}) (?P<title>.*)', '<h8>\g<title></h8>', body, flags = re.MULTILINE )
                    body = re.sub( r'^(?P<h>[#]{7}) (?P<title>.*)', '<h7>\g<title></h7>', body, flags = re.MULTILINE )

                # add buttons
                if buttons != '':
                    if self._output == "html":
                        body = re.sub( r'<h1>', '<h1> {}'.format(buttons), body, count = 1, flags = re.MULTILINE )
                    elif self._output == "md":
                        pass
                        # body = buttons + '\n' + body
                        # body = re.sub( r'^(?P<h>#+) ', '\g<h> {}'.format(buttons), body, count = 1, flags = re.MULTILINE )

                body += '\n'
                output += body
            else:
                output += buttons + '\n\n'

            # add task information to body
            # tabulate
            # table by row
            # header
            task_table = {}
            task = { 'task-start': 'Start', 'task-due': 'Due', 'cost': 'Cost', 'task-effort': 'Effort', 
                    'task-priority': 'Priority', 'task-progress': 'Progress', 'resources': 'Resource(s)' }
            for key in task:
                if key in topic.attrib:
                    if key == 'task-progress':
                        if topic.attrib[key][-1] != "%": 
                            if int(topic.attrib[key]) > 100: continue
                            topic.attrib[key] += '%'
                    if key == 'task-effort' and topic.attrib[key][0] == '-': continue
                    task_table[key] = [ topic.attrib[key] ]

            if len(task_table) > 0: 
                output += tabulate( task_table, headers="keys", tablefmt="html" if self._output == "html" else "github" )
                output += "\n\n"

            # add attachment to body as image
            if '_attachment' in topic.attrib:
                if self._output == "html":
                    output += '<img src="{}"'.format(topic.attrib['_attachment']['ref'])
                    if 'title' in topic.attrib['_attachment']: output += 'title="{}"'.format( topic.attrib['_attachment']['title'] )
                    output += ' />'
                elif self._output == "md":
                    output += '{{< figure src="' + topic.attrib['_attachment']['ref'] + '"'
                    output += ' alt="' + topic.attrib['_attachment']['ref'] + '"'
                    output += ' caption="' + os.path.basename(topic.attrib['_attachment']['title'] ).split(".")[0]+ '"'
                    #if 'title' in topic.attrib['_attachment']:
                    #    output += ' title="' + topic.attrib['_attachment']['title'] + '"'
                    output += ' >}}'
                output += "\n\n"

            # add link to body 
            if '_link' in topic.attrib:
                icon = 'fa-solid fa-link' if topic.attrib['_link']['type'] == 'external' else 'fa-solid fa-link'                    
                if self._output == "html":
                    output += '<a href="{}"'.format( topic.attrib['_link']['ref'])
                    if 'target' in topic.attrib['_link']: output += ' target="{}"'.format(topic.attrib['_link']['target'])
                    if icon: output += ' class="btn btn-default {}"'.format(icon)
                    output += '>'
                    if 'title' in topic.attrib['_link']: output += topic.attrib['_link']['title']
                    output += '</a> '
                elif self._output == "md":
                    output += '{{< mybutton href="' + topic.attrib['_link']['ref'] + '"'
                    if 'target' in topic.attrib['_link']: output += ' target="{}"'.format(topic.attrib['_link']['target'])
                    #if icon: output += ' icon="{}"'.format( icon )
                    output += ' >}}'
                    output += topic.attrib['_link']['title'] if 'title' in topic.attrib['_link'] else topic.attrib['_link']['ref']
                    output += '{{< /mybutton >}}'
                output += '\n\n'

            # add childs
            if 'uuid' in topic.attrib:
                for child in elements.findall( ".//*[@_parent='{}']".format(topic.attrib['uuid']) ) :
                    if child.tag == 'topic':
                        output += self._get_body( elements, child, level+1 ) + '\n\n'

        return output

