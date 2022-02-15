#!/usr/bin/env python

import argparse
import os
import re
# import subprocess
# import sys
# from collections import defaultdict
# from urllib.error import URLError
# from urllib.parse import quote, urlparse, urlsplit, urlunsplit
# from urllib.request import urlretrieve

import xml.etree.ElementTree as ET
import zipfile
import unicodedata

import m2r2
from markupsafe import Markup   
from docutils.utils import column_width
import unidecode

# #################################################################################################################################
# UNWORKED FUNCTIONS
# #################################################################################################################################

# def get_filename(post_name, post_id):
#     if post_name is None or post_name.isspace():
#         return post_id
#     else:
#         return post_name

def get_attachment(xml):
    """returns a dictionary of posts that have attachments with a list
    of the attachment_urls
    """
    soup = xml_to_soup(xml)
    items = soup.rss.channel.findAll('item')
    names = {}
    attachments = []

    for item in items:
        kind = item.find('post_type').string
        post_name = item.find('post_name').string
        post_id = item.find('post_id').string

        if kind == 'attachment':
            attachments.append((item.find('post_parent').string,
                                item.find('attachment_url').string))
        else:
            filename = get_filename(post_name, post_id)
            names[post_id] = filename
    attachedposts = defaultdict(set)
    for parent, url in attachments:
        try:
            parent_name = names[parent]
        except KeyError:
            # attachment's parent is not a valid post
            parent_name = None

        attachedposts[parent_name].add(url)
    return attachedposts


def download_attachments(output_path, attachments):
    """Downloads attachments and returns a list of paths to
    attachments that can be associated with a post (relative path to output
    directory). Files that fail to download, will not be added to posts"""
    locations = {}
    for attachment in attachments:
        file = attachment[0]
        uuid =  attachment[1]
        name =  attachment[2]

        src_path = os.path.join('assets', uuid, name)
        dst_path = os.path.join(output_path, 'attachments', slugify( os.path.basename(file).split(".")[0] + " " + uuid + " " + name))

        if not os.path.exists(os.path.join(output_path, 'attachments')):
            os.makedirs(os.path.join(output_path, 'attachments'))

        print('downloading {}'.format(src_path))
        try:
            ithoughts = zipfile.ZipFile( file, 'r')
            data = ithoughts.read(src_path)
            locations[uuid] = dst_path
        except (URLError, OSError) as e:
            # Python 2.7 throws an IOError rather Than URLError
            print("[WARN] No file could be downloaded from %s\n%s", url, e)
    return locations

# def is_pandoc_needed(in_markup):
#     return in_markup in ('html', 'wp-html')


# def get_pandoc_version():
#     cmd = ['pandoc', '--version']
#     try:
#         output = subprocess.check_output(cmd, universal_newlines=True)
#     except (subprocess.CalledProcessError, OSError) as e:
#         print("[WARN] Pandoc version unknown: %s", e)
#         return ()

#     return tuple(int(i) for i in output.split()[1].split('.'))


def update_links_to_attached_files(content, attachments):
    for old_url, new_path in attachments.items():
        # url may occur both with http:// and https://
        http_url = old_url.replace('https://', 'http://')
        https_url = old_url.replace('http://', 'https://')
        for url in [http_url, https_url]:
            content = content.replace(url, '{static}' + new_path)
    return content

# #################################################################################################################################
# INTERNAL FUNCTIONS
# #################################################################################################################################

def display_tree( element, level=0 ):
    if level == 0:       
        tags = set( [elem.tag for elem in element.iter()] )
        print( "TAGS: {}".format(tags) )

        keys = set()
        for topic in element.iter('topic'):
            for key in topic.attrib.keys():
                keys.add(key)
        print( "KEYS: {}".format(keys) )

    for topic in element:
        print( "{}==> {} {}".format( ' '*(level*4), topic.tag, topic.attrib['uuid'] if 'uuid' in topic.attrib else '' ) )
        for attrib in topic.attrib:
            if attrib not in ['uuid', 'position']:
                print( "{}{}: {}".format( ' '*((level*4)+6), attrib, topic.attrib[attrib] ) )
        display_tree( topic, level+1 ) 

def get_topic_filename( file, uuid ):
    return "{}-{}".format( os.path.basename(file).split(".")[0], uuid )

def get_title( topic ):
    # first line is title
    if 'text' in topic.attrib:
        return topic.attrib['text'].splitlines()[0][2:] if topic.attrib['text'].splitlines()[0].startswith("# ") else topic.attrib['text'].splitlines()[0]
    else:
        return ''

def get_content( topic ):
    # other lines are content
    if 'text' in topic.attrib:
        return m2r2.convert( ''.join(topic.attrib['text'].splitlines(keepends=True)[1:]) )
    else:
        return ''

def get_summary( root, uuid ):
    # first callout is summary
    callout = root.findall( ".//*[@parent='{}'][@callout='1']".format(uuid) )
    if callout: 
        # need to remove invalid characters such as \n
        if 'text' in callout[0].attrib:
            return callout[0].attrib['text'].replace("\n", " ")
        else:
            return ''
    else:
        return ""

# #################################################################################################################################
# PREPARE_TOPICS
# #################################################################################################################################
# KEYS:
#   parent              : create links
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

def prepare_topics( site, filename, topics, parent=None ):

    for topic in topics: 
        # add new attributes
        topic.attrib['_parent'] = parent

        if topic.tag == 'topic':
            # _slug = uuid
            topic.attrib['_slug'] = slugify(topic.attrib['uuid'])

            # _title = text first row without trailing #
            if 'text' in topic.attrib:
                if topic.attrib['text'].splitlines()[0].startswith("# "):
                    topic.attrib['_title'] = topic.attrib['text'].splitlines()[0][2:]
                else:
                    topic.attrib['_title'] = topic.attrib['text'].splitlines()[0]
            else:
                topic.attrib['_title'] ="{}".format(topic.attrib['uuid'])

            # _content
            if 'text' in topic.attrib:
                topic.attrib['_content'] = m2r2.convert( ''.join(topic.attrib['text'].splitlines(keepends=True)[1:]) )

            # _comment
            if 'note' in topic.attrib:
                topic.attrib['_comment'] = m2r2.convert( topic.attrib['note'] )

            # add reference
            if 'link' in topic.attrib:
                pass

            # _type and _filename
            if parent: 
                topic.attrib['_type'] = 'post'
                topic.attrib['_filename'] = topic.attrib['_slug'] + '.rst'
            else: 
                topic.attrib['_type'] = 'page'
                topic.attrib['_filename'] = os.path.join( 'pages', topic.attrib['_slug'] + '.rst' )
        else: 
            topic.attrib['_type'] = 'ignore'

        # recurse
        prepare_topics( site, filename, topic, topic.attrib['uuid'] if 'uuid' in topic.attrib else None )

# #################################################################################################################################
# PROCESS_CALLOUT
# #################################################################################################################################

def process_callout( site, topics ):
    for topic in topics:
        if 'callout' in topic.attrib:
            pass

# #################################################################################################################################
# PROCESS_ATTACHMENTS
# #################################################################################################################################

def process_attachments( site, topics ):
    for topic in topics:
        if 'att-id' in topic.attrib:
            topic.attrib['_attachments'] = {}
            pass

# #################################################################################################################################
# PROCESS_LINKS
# #################################################################################################################################

def process_links( site, topics ):
    for topic in topics:
        topic.attrib['_links'] = {}
        # relationships
        if 'end1-uuid' in topic.attrib:
            pass

        # add parents as links at the top of the content
        if '_parent' in topic.attrib and topic.attrib['_parent']:
            parents = topics.findall( ".//*[@uuid='{}']".format(topic.attrib['_parent']) )
            for parent in parents:
                reST += "`{} <{".format(parent.attrib['_title']) + "filename} {}>`_ ".format( parent.attrib['_filename'] )

        # add childs as links at the top of the content
        if 'uuid' in topic.attrib:
            for child in topics.findall( ".//*[@_parent='{}']".format(topic.attrib['uuid']) ) :
                if child.tag == 'topic': 
                    reST += "`{} <{".format(child.attrib['_title']) + "filename} {}>`_ ".format( child.attrib['_filename'] )

        # ==> relationships 
        #     ==> relationship 663C36F2-78B7-4B5E-B88B-F7D2BD9C65B5
        #         end1-uuid: 549F30CE-AE4C-4A69-AF3E-65B86EB313BB
        #         end2-uuid: 7C32D088-9538-4D69-BC68-85564ADBD492
        # for relation in root.findall( ".//*[@end1-uuid='{}']".format(topic.attrib['uuid']) ):
        #     reST += "`{} <{}>`_ ".format( get_title(relation), 
        #                                 get_out_filename( topic.attrib['type'], 
        #                                                     relation.attrib['end2-uuid'], 
        #                                                     '.html', 
        #                                                     'post', 
        #                                                     type
        #                                                     )
        #                                 )
        # for relation in root.findall( ".//*[@end2-uuid='{}']".format(topic.attrib['uuid']) ):
        #     reST += "`{} <{}>`_ ".format( get_title(relation), 
        #                                 get_out_filename( baseline = topic.attrib['type'], 
        #                                                     name     = relation.attrib['end1-uuid'], 
        #                                                     ext      = '.html', 
        #                                                     kind     = 'post', 
        #                                                     type     = type
        #                                                     )
        #                                 )

# #################################################################################################################################
# SLUGIFY
# #################################################################################################################################

def slugify(value, regex_subs=(), preserve_case=False, use_unicode=False):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """

    SLUG_SUBS = [
        (r'[^\w\s-]', ''),  # remove non-alphabetical/whitespace/'-' chars
        (r'(?u)\A\s*', ''),  # strip leading whitespace
        (r'(?u)\s*\Z', ''),  # strip trailing whitespace
        (r'[-\s]+', '-'),  # reduce multiple whitespace or '-' to single '-'
        (r'[<>:"/\\|?*^% ]', '-'), # invalid chars
    ]

    # strip tags from value
    value = Markup(value).striptags()

    # normalization
    value = unicodedata.normalize('NFKC', value)

    if not use_unicode:
        # ASCII-fy
        value = unidecode.unidecode(value)

    # perform regex substitutions
    for src, dst in SLUG_SUBS:
        value = re.sub(
            unicodedata.normalize('NFKC', src),
            unicodedata.normalize('NFKC', dst),
            value,
            flags=re.IGNORECASE)

    if not preserve_case:
        value = value.lower()

    return value.strip()
    
# #################################################################################################################################
# process_files
# #################################################################################################################################

def process_files(directory, site):
    """Opens directory and process iThoughts files into site"""

    filenames = []
    if os.path.isdir(directory):
        for top, dirs, files in os.walk(directory):
            for name in files:
                if os.path.splitext(name)[1] == '.itmz': filenames.append(os.path.join(top, name))
    else:
        filenames.append(directory)

    for file in filenames:
        if not os.path.exists(file):
            print( "{} does not exist".format(file))
            continue
        else:
            print( "Processing {} ...".format(file))

            ithoughts = zipfile.ZipFile( file, 'r')
            xmldata = ithoughts.read('mapdata.xml')
            root = ET.fromstring(xmldata)

            prepare_topics(site, file, root)

            process_callout(site, root)

            process_links(site, root)

            process_attachments(site, root)

            for topic in root.iter('topic'):

                # let's go !
                print('  ' + topic.attrib['uuid'])
                reST = ''

                reST += '{}\n{}\n'.format(topic.attrib['_title'], '#' * column_width(topic.attrib['_title']))

                reST += ':title: %s\n' % topic.attrib['_title']
                reST += ':slug: %s\n' % topic.attrib['_slug']

                if 'created' in topic.attrib: reST += ':date: %s\n' % topic.attrib['created']
                if 'modified' in topic.attrib: reST += ':modified: %s\n' % topic.attrib['modified']

                reST += ':status: %s\n' % 'published'

                # :category:
                # :tags:
                # :author:
                # :authors:
                # :summary:

                reST += '\n'

                if '_links' in topic.attrib:
                    for key, link in topic.attrib['_links']:
                        reST += "`{} <{}>`_ ".format( key, link)

                reST += "\n\n"

                # add attrib for debug purpose
                reST += "attrib: {}".format(topic.attrib) + "\n\n"

                if '_content' in topic.attrib:
                    reST += topic.attrib['_content']

                if '_comment' in topic.attrib:
                    reST += topic.attrib['_comment']

                out_file = os.path.join( site, topic.attrib['_filename'] )
                print('  > ' + out_file)

                out_dir = os.path.dirname(out_file)
                if not os.path.isdir(out_dir):
                    os.mkdir(out_dir)

                with open(out_file, 'w', encoding='utf-8') as fs:
                    fs.write(reST) 

# #################################################################################################################################
# GET_OUT_FILENAME
# #################################################################################################################################

def get_out_filename(baseline, name, ext, kind, type):
    name = os.path.basename(name)

    # Enforce filename restrictions for various filesystems at once; see
    # https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
    # we do not need to filter words because an extension will be appended
    name = re.sub(r'[<>:"/\\|?*^% ]', '-', name)  # invalid chars
    name = name.lstrip('.')  # should not start with a dot
    if not name:
        name = '_'

    if baseline == 'page':
        if kind == 'page': out_dir = '.'
        elif kind == 'post': 
            if type == 'nikola': out_dir = '../posts'
            else: out_dir = '..'
    elif baseline == 'post':
        if kind == 'post': out_dir = '.'
        elif kind == 'page': 
            if type == 'nikola': out_dir = '../pages'
            else: out_dir = 'pages'
    else:
        if kind == 'page': out_dir = os.path.join(baseline, 'pages')
        elif kind == 'post':
            if type == 'nikola': out_dir = os.path.join(baseline, 'posts')
            else: out_dir = baseline
        elif kind == 'image': out_dir = os.path.join(baseline, 'images')
        elif kind == 'attachment': out_dir = os.path.join(baseline, 'attachments')

    out_filename = os.path.join(out_dir, name + ext)

    if out_dir != '' and not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    return out_filename

# #################################################################################################################################
# MAIN
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

    if not os.path.exists(args.output):
        try:
            os.mkdir(args.output)
        except OSError:
            error = 'Unable to create the output folder: ' + args.output
            exit(error)

    process_files( args.input, args.output )

main()