"""
Middleware for KEEP Auto SSO
"""
from django.conf import settings
from django.shortcuts import redirect
from django.utils.http import urlencode
import logging
log = logging.getLogger(__name__)

class KEEPMiddleware(object):
    """
    Checks a user's COOKIE KEEPSAMLAuthToken
    """
    def process_request(self, request):
        user = request.user
        http_referer = ''

        try: 
            http_referer = request.META['HTTP_REFERER']
        except:
            http_referer = ''

        if '/register' in request.path and 'account.keep.edu.hk' in http_referer:
            log.info("Test RLNF")
            log.info(request.path)
            log.info(http_referer)

        try:
            if not user.is_authenticated() and (request.COOKIES.get('KEEPSAMLAuthToken') or '/login' in request.path or '/register' in request.path) and not '/sso_login' in request.path and not '/shib-login' in request.path and not '/sso_logout' in request.path and not '/tpa-saml' in request.path and not ('/register' in request.path and 'account.keep.edu.hk' in http_referer) and not '/registration' in request.path:
                redirect_url = '/sso_login'
                if request.get_full_path():
                    next = urlencode({'next':request.get_full_path()})
                    redirect_url += '?' + next
                response = redirect(redirect_url)
                return response
            if user.is_authenticated() and not request.COOKIES.get('KEEPSAMLAuthToken') and not '/logout' in request.path:
                response = redirect('/logout')
                return response
        except:
            pass
            
class KEEPMiddlewareStudio(object):
    """
    Checks a user's COOKIE KEEPSAMLAuthToken
    """
    def process_request(self, request):
        user = request.user
        try:
            if not user.is_authenticated() and (request.COOKIES.get('KEEPSAMLAuthToken') or '/signin' in request.path) and not '/sso_login' in request.path:
                redirect_url = '/sso_login'
                if request.get_full_path():
                    next = urlencode({'next':request.get_full_path()})
                    redirect_url += '?' + next
                response = redirect(redirect_url)
                return response
            if user.is_authenticated() and not request.COOKIES.get('KEEPSAMLAuthToken') and not '/logout' in request.path:
                response = redirect('/logout')
                return response
        except:
            pass
