import os
import shutil
import re
import pprint

from bs4 import BeautifulSoup

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
    tag = soup.new_tag('code')
    tmp = dict(element)
    if 'content' in tmp: del tmp['content']
    tag.string = pprint.pformat(tmp)
    del tmp
    soup.body.append(tag)
    output = str( soup )

    return output

# #############################################################################################################################
# jamstack_write
# #############################################################################################################################

# assuming html for nikola

def jamstack_write( output='site/nikola', elements=[], stack='nikola', generate='html' ):

    # merge elements

    for element in reversed(elements):
        # is there a child with same title
        for item in reversed(elements):
            if ( item['what'] in ['page'] ) and ('parent' in item) and (item['parent'] == element['id']) and (item['title'] == element['title']):
                print( '*'*250 )
                print('> ' + element['title'])

                element['content'] = item['content']
                elements.remove(item)
                break

    # add tags

    for element in elements:

        element['tags'] =  []
        for item in elements:
            if ('parent' in element) and (item['id'] == element['parent']):
                if 'tags' in item: element['tags'] += item['tags']
                if (item['what'] in ['notebook', 'group']):
                    element['tags'] += [ item['slug'] ]
                break

    # process resources

    for element in elements:

        if 'resources' in element:
            for resource in element['resources']:
                if resource['type'] in ['image', 'fullres']: folder = 'images'
                else: folder = os.path.join('files', 'objects')

                out_file = os.path.join( output, folder, resource['name'] )
                out_dir = os.path.dirname(out_file)

                print('  - ' + out_file)

                if not os.path.isdir(out_dir):
                    os.makedirs(out_dir)

                try:
                    shutil.move(resource['data'], out_file)
                except:
                    pass

                if 'content' in element: 
                    if resource['type'] in ['image', 'fullres']: folder = 'images'
                    else: folder = 'objects'

                    url = resource['url']
                    path = os.path.join( os.path.sep, folder, resource['name'] )
                    element['content'] = element['content'].replace(url, path)

    # process HTML

    for element in elements:

        text = _get_header( element )
        text += _get_body( element )

        if element['what'] in ['page']: folder = 'posts'
        elif element['what'] in ['notebook', 'section', 'group']: folder = 'pages'
        else: folder = 'usused'

        out_file = os.path.join( output, folder, element['slug'] + '.html' )
        out_dir = os.path.dirname(out_file)

        print( '='*250 )
        print('> ' + out_file)
        print( '='*250 )
        tmp = dict(element)
        #if 'content' in tmp: del tmp['content']
        pprint.pprint(tmp)
        del tmp

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        with open(out_file, 'w', encoding='utf-8') as fs:
            fs.write(text) 