#!/usr/bin/env python

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from urllib.error import URLError
from urllib.parse import quote, urlparse, urlsplit, urlunsplit
from urllib.request import urlretrieve

import xml.etree.ElementTree as ET
import zipfile
import unicodedata

import m2r2
from markupsafe import Markup   
import unidecode

# #################################################################################################################################
# UNWORKED FUNCTIONS
# #################################################################################################################################

def get_filename(post_name, post_id):
    if post_name is None or post_name.isspace():
        return post_id
    else:
        return post_name

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

def is_pandoc_needed(in_markup):
    return in_markup in ('html', 'wp-html')


def get_pandoc_version():
    cmd = ['pandoc', '--version']
    try:
        output = subprocess.check_output(cmd, universal_newlines=True)
    except (subprocess.CalledProcessError, OSError) as e:
        print("[WARN] Pandoc version unknown: %s", e)
        return ()

    return tuple(int(i) for i in output.split()[1].split('.'))


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

def set_parent( element, parent=None ):
    for topic in element: 
        topic.attrib['parent'] = parent
        topic.attrib['kind'] = 'article' if parent else 'page'
        set_parent( topic, topic.attrib['uuid'] if 'uuid' in topic.attrib else None )

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
# SLUGIFY
# #################################################################################################################################

def slugify(value, regex_subs=(), preserve_case=False, use_unicode=False):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.

    Took from Django sources.
    """

    SLUG_SUBS = [
        (r'[^\w\s-]', ''),  # remove non-alphabetical/whitespace/'-' chars
        (r'(?u)\A\s*', ''),  # strip leading whitespace
        (r'(?u)\s*\Z', ''),  # strip trailing whitespace
        (r'[-\s]+', '-'),  # reduce multiple whitespace or '-' to single '-'
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
# ITMZ2FIELDS
# #################################################################################################################################

def itmz2fields(input):
    """Opens an iThoughts file, and yield Pelican fields"""

    # KEYS:
    #   parent              : create links
    #   uuid                : part of filename and slug
    #   created             : unused
    #   modified            : date
    #   text                : title and content
    #   note                :
    #   callout             : first is summary, others are ignored
    #   link                : 
    #   attachmentd
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

    filenames = []
    if os.path.isdir(input):
        pass
        for top, dirs, files in os.walk(input):
            for name in files:
                if os.path.splitext(name)[1] == '.itmz': filenames.append(os.path.join(top, name))
    else:
        filenames.append(input)

    for file in filenames:
        if not os.path.exists(file):
            print( "{} does not exist".format(file))
            continue
        else:
            print( "Processing {} ...".format(file))

        ithoughts = zipfile.ZipFile( file, 'r')
        xmldata = ithoughts.read('mapdata.xml')
        root = ET.fromstring(xmldata)

        # add name to uuid
        for topic in root.iter('topic'):
            topic.attrib['uuid'] = slugify( os.path.basename(file).split(".")[0] + " " + topic.attrib['uuid'] )

        # identify parent
        set_parent(root)

        # display_tree(root)

        # change tag for first callout
        for child in root.findall(".//*[@callout='1']"): 
            child.tag = "callout"

        for topic in root.iter('topic'):

            title = get_title(topic)

            content = ''
            # add parents as links at the top of the content
            if topic.attrib['parent']:
                parents = root.findall( ".//*[@uuid='{}']".format(topic.attrib['parent']) )
                content += "`{} <{}{}.html>`_ ".format( get_title(parents[0]), 
                                                        'pages/' if parents[0].attrib['kind'] == 'page' else '',
                                                        parents[0].attrib['uuid'])

            # add childs as links at the top of the content
            for child in root.findall( ".//*[@parent='{}']".format(topic.attrib['uuid']) ):
                if child.tag == 'topic': 
                    content += "`{} <{}{}.html>`_ ".format( get_title(child), 
                                                            '../' if topic.attrib['kind'] == 'page' else '', 
                                                            child.attrib['uuid'])

            content += "\n\n"

            # add attrib for debug purpose
            content += "{}".format(topic.attrib) + "\n\n"
            
            # need to address notes 
            # ==> topic 4331F10E-231F-4E64-9F06-F072AF473411
            #     text: # Notes
            #     note: # Level 1
            #     created: 2022-02-09T17:14:33
            #     modified: 2022-02-09T17:15:46
            #     parent: 0C3E0D7C-04B8-438E-8E5B-E9265FA1070E

            # need to address relationships 
            # ==> relationships 
            #     parent: None
            #     ==> relationship 663C36F2-78B7-4B5E-B88B-F7D2BD9C65B5
            #         type: 0
            #         end1-uuid: 549F30CE-AE4C-4A69-AF3E-65B86EB313BB
            #         end1-style: 0
            #         end2-uuid: 7C32D088-9538-4D69-BC68-85564ADBD492
            #         end2-style: 1
            #         b-offset: {107.47821523117955, -62.806713420782103}
            #         parent: None

            content += get_content(topic)

            summary = get_summary( root, topic.attrib['uuid'] )

            filename = topic.attrib['uuid']

            date = topic.attrib['modified']
            
            author = []
            
            categories = []
            tags = []
            
            status = 'published'

            kind = topic.attrib['kind']
            
            attachments = []
            if 'att-id' in topic.attrib:
                attachments.append( [file, topic.attrib['att-id'], topic.attrib['att-name']]  )
            
            slug = slugify(filename)

            yield (title, content, filename, date, author, categories, tags, status, kind, summary, attachments, slug)

# #################################################################################################################################
# BUILD_HEADER
# #################################################################################################################################

def build_header(title, date, author, categories, tags, slug, summary, status=None, attachments=None):
    """Build a header from a list of fields"""

    from docutils.utils import column_width

    header = '{}\n{}\n'.format(title, '#' * column_width(title))
    if date:
        header += ':date: %s\n' % date
    if author:
        header += ':author: %s\n' % author
    if categories:
        header += ':category: %s\n' % ', '.join(categories)
    if tags:
        header += ':tags: %s\n' % ', '.join(tags)
    if slug:
        header += ':slug: %s\n' % slug
    if summary:
        header += ':summary: %s\n' % summary
    if status:
        header += ':status: %s\n' % status
    if attachments:
        header += ':attachments: %s\n' % ', '.join(attachments)
    header += '\n'
    return header

# #################################################################################################################################
# GET_OUT_FILENAME
# #################################################################################################################################

def get_out_filename(output_path, filename, ext, kind):
    filename = os.path.basename(filename)

    # Enforce filename restrictions for various filesystems at once; see
    # https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
    # we do not need to filter words because an extension will be appended
    filename = re.sub(r'[<>:"/\\|?*^% ]', '-', filename)  # invalid chars
    filename = filename.lstrip('.')  # should not start with a dot
    if not filename:
        filename = '_'
    filename = filename[:249]  # allow for 5 extra characters

    out_filename = os.path.join(output_path, filename + ext)

    # option to put page posts in pages/ subdirectory
    if kind == 'page':
        pages_dir = os.path.join(output_path, 'pages')
        if not os.path.isdir(pages_dir):
            os.mkdir(pages_dir)
        out_filename = os.path.join(pages_dir, filename + ext)

    return out_filename

# #################################################################################################################################
# FIELDS2RST
# #################################################################################################################################

def fields2rst(
        fields, output_path,
        out_markup="rst", dircat=False, strip_raw=False, disable_slugs=False,
        dirpage=False, filename_template=None, filter_author=None,
        wp_custpost=False, wp_attach=False, attachments=None):

    pandoc_version = get_pandoc_version()
    posts_require_pandoc = []

    for (title, content, filename, date, author, categories, tags, status, kind, summary, attachments, slug) in fields:

        in_markup = 'rst'

        if is_pandoc_needed(in_markup) and not pandoc_version:
            posts_require_pandoc.append(filename)

        if attachments:
            try:
                links = download_attachments(output_path, attachments)
            except KeyError:
                links = None
        else:
            links = None

        ext = ".rst"
        header = build_header(title, date, author, categories,
                                tags, slug, summary, status, links.values()
                                if links else None)

        out_filename = get_out_filename(output_path, filename, ext, kind)
        print(out_filename)

        # if in_markup in ('html', 'wp-html'):
        #     html_filename = os.path.join(output_path, filename + '.html')

        #     with open(html_filename, 'w', encoding='utf-8') as fp:
        #         # Replace newlines with paragraphs wrapped with <p> so
        #         # HTML is valid before conversion
        #         if in_markup == 'wp-html':
        #             new_content = decode_wp_content(content)
        #         else:
        #             paragraphs = content.splitlines()
        #             paragraphs = ['<p>{}</p>'.format(p) for p in paragraphs]
        #             new_content = ''.join(paragraphs)

        #         fp.write(new_content)

        #     if pandoc_version < (2,):
        #         parse_raw = '--parse-raw' if not strip_raw else ''
        #         wrap_none = '--wrap=none' \
        #             if pandoc_version >= (1, 16) else '--no-wrap'
        #         cmd = ('pandoc --normalize {0} --from=html'
        #                ' --to={1} {2} -o "{3}" "{4}"')
        #         cmd = cmd.format(parse_raw, out_markup, wrap_none,
        #                          out_filename, html_filename)
        #     else:
        #         from_arg = '-f html+raw_html' if not strip_raw else '-f html'
        #         cmd = ('pandoc {0} --to={1}-smart --wrap=none -o "{2}" "{3}"')
        #         cmd = cmd.format(from_arg, out_markup,
        #                          out_filename, html_filename)

        #     try:
        #         rc = subprocess.call(cmd, shell=True)
        #         if rc < 0:
        #             error = 'Child was terminated by signal %d' % -rc
        #             exit(error)

        #         elif rc > 0:
        #             error = 'Please, check your Pandoc installation.'
        #             exit(error)
        #     except OSError as e:
        #         error = 'Pandoc execution failed: %s' % e
        #         exit(error)

        #     os.remove(html_filename)

        #     with open(out_filename, encoding='utf-8') as fs:
        #         content = fs.read()
        #         if out_markup == 'markdown':
        #             # In markdown, to insert a <br />, end a line with two
        #             # or more spaces & then a end-of-line
        #             content = content.replace('\\\n ', '  \n')
        #             content = content.replace('\\\n', '  \n')

        #     if wp_attach and links:
        #         content = update_links_to_attached_files(content, links)

        with open(out_filename, 'w', encoding='utf-8') as fs:
            fs.write(header + content)

    if posts_require_pandoc:
        print("[ERR] Pandoc must be installed to import the following posts:"
                     "\n  {}".format("\n  ".join(posts_require_pandoc)))

    #if wp_attach and attachments and None in attachments:
    if attachments and None in attachments:
        print("downloading attachments that don't have a parent post")
        urls = attachments[None]
        download_attachments(output_path, urls)


def main():
    parser = argparse.ArgumentParser(
        description="Transform iThoughts "
                    "files into reST (rst) or Markdown (md) files. "
                    "Be sure to have pandoc installed.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

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

    fields = itmz2fields(args.input)

    attachments = None
    # if args.wp_attach:
    #     attachments = get_attachment(args.input)

    # init logging
    # init()
    fields2rst( fields, args.output )

main()