import os

# #############################################################################################################################
# _get_header
# #############################################################################################################################

def _get_header( element ):

    output = '<head>\n'

    if 'title' in element: output += '\t<title>{}</title>\n'.format(element['title'])

    for key, value in element.items():
        if not key in ['content', 'title']:
            output += '\t<meta name="{}" content="{}" />\n'.format(key, value)

    output += '</head>\n'

    return output

# #############################################################################################################################
# _get_body
# #############################################################################################################################

def _get_body( element ):

    if 'content' in element: output = element['content']
    else: output = '<body></body>'

    return output

# #############################################################################################################################
# jamstack_write
# #############################################################################################################################

# assuming html for nikola

def jamstack_write( output='site/nikola', elements=[], stack='nikola', generate='html' ):

    for element in elements:
        text = _get_header( element )
        text += _get_body( element )

        if element['what'] in ['page']: folder = 'posts'
        elif element['what'] in ['notebook', 'section', 'group']: folder = 'pages'
        else: folder = 'usused'

        out_file = os.path.join( output, folder, element['slug'] + '.html' )
        out_dir = os.path.dirname(out_file)

        print('  > ' + out_file)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        with open(out_file, 'w', encoding='utf-8') as fs:
            fs.write(text) 