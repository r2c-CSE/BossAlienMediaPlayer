from __future__ import absolute_import, unicode_literals

import json
import tornado.web
import logging
import ldap

from .dtos import TrackDTO, DTOEncoder

from .base_request_handler import BaseRequestHandler
from .database_connection import DBConnection

logger = logging.getLogger(__package__)


class LoginRequestHandler(BaseRequestHandler):
    def post(self):
        data = json.loads(self.request.body.decode('utf-8'))

        # exposes passwords!
        #logger.debug('Got JSON data: {0}'.format(data))

        user_full_name = data['user_id']
        password = data['password']

        ldap_dn = self.config['mopidy_bamp']['ldap_schema'].replace('#USER_NAME#', user_full_name)

        logger.debug('ldap dn:' + ldap_dn)

        try:
            # talk to ldap server, see if user is authed
            ldap_connection = ldap.initialize(self.config['mopidy_bamp']['ldap_uri'])
            ldap_connection.simple_bind_s(who=ldap_dn, cred=password)
            user_id = ldap_connection.whoami_s().replace('u:CORP\\', '')
            logger.debug('User validated! ' + user_id)
        except ldap.LDAPError, e:
            logger.debug('ldap error: ' + str(e))
            raise tornado.web.HTTPError(status_code=403, log_message='invalid creds')

        # set our cookie to show that we've logged in
        self.set_secure_cookie(self.SECURE_COOKIE_USER_FIELD, user_id)

        # does this user have a record in the db?
        new_user = False
        user_dto = None
        with DBConnection() as db_connection:
            new_user = db_connection.user_table.exists(user_id) == False

            if new_user:
                # add row to db if they are new - make their alias their user id
                db_connection.user_table.add(user_id, user_id)

            user_dto = db_connection.user_table.get(user_id)

        response = {'status': 'ok', 'new_user': new_user, 'user': user_dto}

        self.write(json.dumps(response, cls=DTOEncoder))


class LogoutRequestHandler(BaseRequestHandler):
    def get(self):

        # clear our cookie to log us out
        self.clear_cookie(self.SECURE_COOKIE_USER_FIELD)

        response = {'status': 'ok'}

        self.write(response)
