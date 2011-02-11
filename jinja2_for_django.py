"""

    A Jinja2 template loader for Django 1.2+
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    
    Add the following to your settings.py file.  (The comma is important!) 

        TEMPLATE_LOADERS = ('jinja2_for_django.Loader',)

    Now use your templates as usual (with render_to_response, generic views or
    anything else that uses Django templates), and they will actually be
    rendered by Jinja2.
    
    See http://exyr.org/2010/Jinja-in-Django/
    
    Author: Simon Sapin
    License: BSD

"""

from django.template.loader import BaseLoader
from django.template.loaders.app_directories import app_template_dirs
from django.template import TemplateDoesNotExist
from django.core import urlresolvers
from django.conf import settings
import jinja2

class Template(jinja2.Template):
    def render(self, context):
        # flatten the Django Context into a single dictionary.
        context_dict = {}
        for d in context.dicts:
            context_dict.update(d)
        return super(Template, self).render(context_dict)

class Loader(BaseLoader):
    is_usable = True

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(app_template_dirs))
    env.template_class = Template

    # These are available to all templates.
    env.globals['url_for'] = urlresolvers.reverse
    env.globals['MEDIA_URL'] = settings.MEDIA_URL
    #env.globals['STATIC_URL'] = settings.STATIC_URL

    def load_template(self, template_name, template_dirs=None):
        try:
            template = self.env.get_template(template_name)
        except jinja2.TemplateNotFound:
            raise TemplateDoesNotExist(template_name)
        return template, template.filename

