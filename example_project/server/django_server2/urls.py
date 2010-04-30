from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to, direct_to_template

urlpatterns = patterns('',
    url(r'^$','direct_to_template', {'template': 'test.html'}),
	(r'^api/', include('api.urls')),
)
