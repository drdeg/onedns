#! /usr/bin/env python3

import argparse
from pathlib import Path
from configparser import ConfigParser, SafeConfigParser
import requests
import json
import sys

import dns.resolver

class ResolveException(Exception):
    def __init__(self, reason : str):
        super().__init__(reason)


class OneComException(Exception):
    def __init__(self, reason : str):
        super().__init__(reason)

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
    parser.add_argument('--domain', '-d', type=str, help='Base domain name, e.g. varukulla.se')
    parser.add_argument('--subdomain', '-s', type=str, help='Subdomain to update, e.g. hostname')
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
    #USERNAME="david.degerfeldt@outlook.com"
    #PASSWORD="*****"

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
    session.post(loginurl, data=logindata)
    # The request silently fails if login is bad

    # Create data for DNS A-record update
    tosend = {
        "type":"dns_service_records",
        "id":args.id,
        "attributes": {
            "type":"A",
            "prefix":args.subdomain,
            "content":ip,
            "ttl":args.timeout}}

    dnsurl="https://www.one.com/admin/api/domains/" + args.domain + "/dns/custom_records/" + args.id
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

def app():

    args = initParser()

    # Resolve the host name
    resIp = resolve(args.subdomain + "." + args.domain)

    # Take the first value
    resolvedIp = resIp[0].to_text()

    # Get my public IP address
    publicIp = getPublicIp()

    if publicIp == resolvedIp:
        print("Public IP and resolved IP matches, no need to update DNS record.")
        if not args.force:
            return
    else:
        print(f'Detected change of public IP address from {resolvedIp} to {publicIp}. Need to update DNS record.')

    # Update A-record
    print(f'Updating A-record: {args.subdomain}.{args.domain}({args.id})  IN  A   {publicIp}')
    updateARecord(args, publicIp)

if __name__ == '__main__':
    app()