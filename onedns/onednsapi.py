#! /usr/bin/env python3

import argparse
from pathlib import Path
from configparser import ConfigParser, SafeConfigParser
import requests
import json
import sys

import dns.resolver

import re
from .logger import logger


class OneDnsAPI:
    """ Simple interface to updating DNS records on one.com

    Inspired by https://lugico.de/one_com_ddns.py

    Currently, the interface can do the following
     - Log in
     - Get DNS records
     - Update DNS records
     - Log out

    """

    def __init__(self):
        self.session = None
        pass

    def __del__(self):
        """ Ensure that a graceful logout is done when object is destroyed """
        self.logoutSession()

    def loginSession(self, username, password):

        # Create a new session
        logger.debug('Creating session')
        session = requests.session()

        # Navigate to admin panel. This will generate a redirect to the login page
        # This gives the necessary session identifications for login
        redirectionUrl = 'https://www.one.com/admin/'
        r = session.get(redirectionUrl)

        # <form id="kc-form-login" class="Login-form login autofill" onsubmit="login.disabled = true; return true;" action="https://account.one.com/auth/realms/customer/login-actions/authenticate?session_code=Oj9Cmq-x-rhEWNN-lsUM_0L_bj5n3jEme18djQil8ro&amp;execution=18715cea-ac50-4a71-beba-dd532060ca05&amp;client_id=crm-appsrv&amp;tab_id=r2bdsc5Ok6M" method="post">
        match = re.search('<form id=\"kc-form-login\"[^>]*action=\"([^\"]+)\"[^>]*>', r.text)

        assert match, "Failed to determine the login URL for one.com"

        actionUrl = match.group(1).replace('&amp;','&')

        logindata = {
            #'loginDomain': True,
            #'displayUsername': args.username, 
            'password': password, 
            'username': username, 
            'credentialId': ''}
        response = session.post(actionUrl, data=logindata)
        logger.debug("Login response status code is %d", response.status_code)

        assert response.status_code == 200

        # Check for login error message:
        match = re.search('<div class=\"alert alert-error\">', response.text)
        if match:

            match = re.search("<span class=\"kc-feedback-text\">([^<]*)</span>", response.text)
            if match:
                logger.error("Login failed: %s",  match.group(1))
            else:
                logger.error("Login failed. Couldn't determine why.")

        else:
            logger.debug("Login was successfull!")
            self.session = session


    def logoutSession(self):
        """ Closes the session and removes the session object from self """
        if self.session:
            logger.debug("Logging out")
            self.session.get('https://one.com/admin/logout.do')
            logger.debug("Closing session")
            self.session.close()
            self.session = None


    def getCustomRecords(self, domain) -> list:
        """ Retreives a list of the registered cutom records
        Depends on an active authenticated session, see loginSession

        returns the list or None if the request failed

        """
        r = self.session.get("https://www.one.com/admin/api/domains/" + domain + "/dns/custom_records")
        if r:
            logger.debug("Got the custom records")
            records = json.loads(r.text)["result"]["data"]

            for item in records:
                if item['type'] == 'dns_custom_records':
                    logger.debug(f"{item['id']}: {item['attributes']['prefix']} ({item['attributes']['type']}) - {item['attributes']['content']}")

            return records
        else:
            logger.error("Failed to get records")

    def findIdBySubdomain(self, records, subdomain) -> str:
        """ Searches for the ID of a record identified by a subdomain 

        Parameters
        ---------
        
        records: Structure from getCustomRecords
        subdomain: The hostname of the subdomain (only the hostname, not FQDN!!)

        """
        for item in records:
            if item['attributes']['prefix'] == subdomain:
                return item['id']
        return None

    def updateRecord(self, id, domain, subdomain, value, type = 'A', ttl = 3600) -> bool:
        """ Update a DNS record
        
        Parameters
        ----------

        id (number) : The record ID of the entry
        domain (str) : The domain to which the prefix (subdomain) belongs
        subdomain (str) : The prefix, or the subdomain, that should be updated
        value (str) : The content of the record, i.e. an IP number for A records and a FQDN for CNAME records
        type ('A' or 'CNAME') : The type of record, defaults to 'A'
        ttl (number > 0) : Time To Live parameter

        """

        assert type in ('A', 'CNAME'), "Type must be either 'A' or 'CNAME'"
        assert ttl > 0

        data = {
            'type': 'dns_service_records',
            'id': id,
            'attributes': {
                'type': type,
                'prefix': subdomain,
                'content': value,
                'ttl': ttl
            }
        }
        url="https://www.one.com/admin/api/domains/" + domain + "/dns/custom_records/" + id
        headers={'Content-Type': 'application/json'}
        logger.debug("Updating record: %s", json.dumps(data))
        r = self.session.patch(url, data=json.dumps(data), headers=headers)
        logger.debug("Update staus code is %d", r.status_code)

        return r.status_code == 200


