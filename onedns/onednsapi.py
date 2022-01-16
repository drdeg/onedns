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

class ResolveException(Exception):
    def __init__(self, reason : str):
        super().__init__(reason)


class OneComException(Exception):
    def __init__(self, reason : str):
        super().__init__(reason)

class OneDnsAPI:
    """ Simple interface to updating DNS records on one.com

    Inspired by https://lugico.de/one_com_ddns.py
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

        Arguments
        ---------
        
        records: Structure from getCustomRecords
        subdomain: The hostname of the subdomain (only the hostname, not FQDN!!)

        """
        for item in records:
            if item['attributes']['prefix'] == subdomain:
                return item['id']
        return None

    def updateRecord(self, id, domain, subdomain, value, type = 'A', ttl = 3600):

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


""" Documentation goes here """

def initParser():
    """ One DNS A record updater """
    pre_parser = argparse.ArgumentParser(
        description=__doc__,
        prog='onedns',
        # Don't mess with format of description
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # Turn off help, so we print all options in response to -h
        add_help=False
        )

    pre_parser.add_argument('--config', '-c', type=Path, help='Full path to configuration file', metavar="FILE" )

    # Set defaults
    defaults = {
        'domain': 'varukulla.se',
        'timeout': 3600
    }

    # Start with parsing only the known arguments, i.e the config file
    args, remaining_argv = pre_parser.parse_known_args()

    if args.config:
        config = ConfigParser()
        config.read([args.config])
        defaults.update(dict(config.items('OneDns')))

    description = """ How to determine A-Record ID
    - In Firefox/Chrome, press F12 to open the Developer Console
    - Select the Network tab
    - Log in and go to the DNS page of one.com
    - Change anything to one of the domains
    - In the dev console, you can find the requests of the query, 
      You can identify the ID by the "PATCH" in the second column

Config File

    [OneDNS]
    domain = domain.com
    subdomain = dyn
    id = 12345678
    timeout = 3600
    username = your-username@one.com
    password = ****
    """
    # Create the new argparser
    parser = argparse.ArgumentParser(
        parents=[pre_parser],
        description=description,
        prog='onedns',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True
    )
    parser.set_defaults(**defaults)
    parser.add_argument('fqdn', type=str, help='FQDN of host to update, e.g. hostname.domain.org')
    #parser.add_argument('--domain', '-d', type=str, help='Base domain name, e.g. domain.org')
    #parser.add_argument('--subdomain', '-s', type=str, help='Subdomain to update, e.g. hostname')
    parser.add_argument('--username', type=str, help='Username at one.com')
    parser.add_argument('--password', type=str, help='Password at one.com')
    parser.add_argument('--id', '-i', type=str, help='ID of corresponding A-record at one.com')
    parser.add_argument('--timeout', '-t', type=int, help='Timeout in seconds')
    parser.add_argument('--force', action='store_true', help='Force update of A-record')
    args = parser.parse_args(remaining_argv)

    return args


def updateARecord(args, ip):

    # Up until now, this script only handles type A records.
    # More may come on request
    # See https://stackoverflow.com/questions/3898363/set-specific-dns-server-using-dns-resolver-pythondns

    #DOMAIN="varukulla.se"
    # looks like: domain.com
    # no www

    #SUBDOMAIN="dyn"
    # looks like "play"
    # NOT play.example.com

    #TIMEOUT=3600
    #TTL

    #ID="16684569"
    #  ID="16684569" for dyn.varukulla.se
    # You can find the DNS ID like this:
    # In Firefox, Press F12 to open the Developer Console
    # Select the Network tab
    # Go to the dns page of one.com
    # Change anything to one of the domains
    # Click on the second element in the list in the console (counted from the button)
    # You can identify it by the "PATCH" in the second column
    # A window should pop up on the left
    # At the very top it says "Request URL:"
    # At the end of that domain, there should be a 8 Digit long number
    # That is your ID
    # Copy it into the variable above
    # KEEP THE QUOTATION MARKS!!!

    # CREDENTIALS
    #USERNAME="username@host.com"
    #PASSWORD="*****"


    # Split fqdn into host.domain.org
    parts = args.fqdn.split('.')
    assert len(parts) == 3, 'Can only handle domain names with three components'

    hostname = parts[0]
    domain = '.'.join(parts[1:])

    # INITIATE SESSION
    session=requests.Session()

    loginurl = "https://www.one.com/admin/login.do"

    # CREATE DATA FOR LOGIN
    logindata = {
        'loginDomain': True,
        'displayUsername': args.username, 
        'password1': args.password, 
        'username': args.username, 
        'targetDomain': '', 
        'loginTarget': ''}
    response = session.post(loginurl, data=logindata)
    assert response.status_code == 200
    # The request silently fails if login is bad



    # Create data for DNS A-record update
    tosend = {
        "type":"dns_service_records",
        "id":args.id,
        "attributes": {
            "type":"A",
            "prefix":hostname,
            "content":ip,
            "ttl":args.timeout}}

    dnsurl="https://www.one.com/admin/api/domains/" + domain + "/dns/custom_records/" + args.id
    print(f"dnsurl: {dnsurl}")
    sendheaders={'Content-Type': 'application/json'}

    # Make PATCH request to update the record
    r2 = session.patch(dnsurl, data=json.dumps(tosend), headers=sendheaders)

    # print the response
    if r2.status_code != 200:
        raise OneComException('Failed to update A-record! Check that your ID, username and passwords are correct')


def getPublicIp():
    GET_IP = requests.get("https://api.ipify.org/")
    if (GET_IP.status_code != 200):
        raise ResolveException(f'Could not get IP address from api.ipify.org. Status code {GET_IP.status_code}')
        #sys.exit("Could not get IP address from api.ipify.org - Check your internet connection, or check that https://api.ipify.org is up.")
    return GET_IP.text

def resolve(fqdn):
    res = dns.resolver.Resolver(configure=False)
    res.nameservers = ['8.8.8.8', '8.8.4.4']
    r = res.resolve(fqdn)
    return r

