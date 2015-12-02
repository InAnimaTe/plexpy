#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of PlexPy.
#
#  PlexPy is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  PlexPy is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with PlexPy.  If not, see <http://www.gnu.org/licenses/>.

from plexpy import logger, helpers
from httplib import HTTPSConnection
from httplib import HTTPConnection
import ssl
import plexpy


class HTTPHandler(object):
    def __init__(self, host, port, token=None, ssl_verify=True):
        self.host = host
        self.port = str(port)
        self.token = token

        if not plexpy.CONFIG.VERIFY_SSL_CERT:
            self.ssl_verify = False
        else:
            self.ssl_verify = ssl_verify

    """
    Handle the HTTP requests.

    Output: object
    """
    def make_request(self,
                     uri=None, proto='HTTP',
                     request_type='GET',
                     headers=None,
                     output_format='raw',
                     return_type=False,
                     no_token=False,
                     body=None):

        valid_request_types = ['GET', 'POST', 'PUT', 'DELETE']

        if not headers:
            headers = {}

        if request_type.upper() not in valid_request_types:
            logger.debug(u"HTTP request made but unsupported request type given.")
            return None

        if uri:
            request_url = '%s://%s:%s%s' % (proto.lower(), self.host, self.port, uri)

            # Enable for debugging
            logger.debug(u"PlexPy HTTP Handler :: [%s] %s" %
                         (request_type.upper(), request_url))

            if proto.upper() == 'HTTPS':
                if not self.ssl_verify and hasattr(ssl, '_create_unverified_context'):
                    context = ssl._create_unverified_context()
                    handler = HTTPSConnection(host=self.host, port=self.port, timeout=10, context=context)
                    logger.warn(u"PlexPy HTTP Handler :: Unverified HTTPS request made. This connection is not secure.")
                else:
                    handler = HTTPSConnection(host=self.host, port=self.port, timeout=10)
            else:
                handler = HTTPConnection(host=self.host, port=self.port, timeout=10)

            if not no_token:
                headers['X-Plex-Token'] = self.token

            try:
                handler.request(method=request_type, url=uri, body=body, headers=headers)
                response = handler.getresponse()
                request_status = response.status
                request_content = response.read()
                content_type = response.getheader('content-type')
            except IOError, e:
                logger.warn(u"PlexPy HTTP Handler :: Failed to access %s with error %s" % (request_url, e))
                return None
            except Exception, e:
                logger.warn(u"PlexPy HTTP Handler :: Failed to access %s. "
                            u"Is the remote host accepting SSL connections only? %s" % (request_url, e))
                return None
            except:
                logger.warn(u"PlexPy HTTP Handler :: Failed to access %s with Uncaught exception." % request_url)
                return None

            if request_status == 200:
                try:
                    if output_format == 'dict':
                        output = helpers.convert_xml_to_dict(request_content)
                    elif output_format == 'json':
                        output = helpers.convert_xml_to_json(request_content)
                    elif output_format == 'xml':
                        output = helpers.parse_xml(request_content)
                    else:
                        output = request_content

                    if return_type:
                        return output, content_type

                    return output

                except Exception as e:
                    logger.warn(u"PlexPy HTTP Handler :: Failed format response from %s to %s error %s"
                                % (request_url, output_format, e))
                    return None

            else:
                logger.warn(u"PlexPy HTTP Handler :: Failed to access %s. Status code %r: %r"
                            % (request_url, request_status, request_content))
                return None
        else:
            logger.debug(u"PlexPy HTTP Handler :: HTTP request made but no endpoint given.")
            return None
