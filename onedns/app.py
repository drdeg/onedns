from pathlib import Path
import argparse
from configparser import ConfigParser, SafeConfigParser
import re
import requests
import logging

import dns.resolver

from .exceptions import ResolveException
from .logger import logger
from .onednsapi import OneDnsAPI

class OneDns:
    """ Command line interface to update DNS records at OneDns """

    # Set defaults
    _defaults = {
        'timeout': 3600
    }

    _nameservers = ['8.8.8.8', '8.8.4.4']

    def __init__(self):

        # Create self._parser and self._preParser
        self.createParsers()

        # Parse the configuration
        self._args = self.parseConfig()

        self.checkConfig()

    def createParsers(self):
        """ Argument 
        
            Configuration is a three-stage rocket:
            1. Check if a configuration file is specified on the command line
            2. Parse configuration file
            3. Parse command line arguments (overrides configuration file)
        
        """
        self._preParser = argparse.ArgumentParser(
            description=__doc__,
            prog='onedns',
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
            # Turn off help, so we print all options in response to -h
            add_help=False
            )

        self._preParser.add_argument('--config', '-c', type=Path, help='Full path to configuration file', metavar="FILE" )

        description = """ 
        Config File

            [OneDNS]
            domain = domain.com
            subdomain = dyn
            timeout = 3600
            username = your-username@one.com
            password = ****
        """
        # Create the new argparser
        self._parser = argparse.ArgumentParser(
            parents=[self._preParser],
            description=description,
            prog='onedns',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=True
        )
        #parser.add_argument('--domain', '-d', type=str, help='Base domain name, e.g. domain.org')
        #parser.add_argument('--subdomain', '-s', type=str, help='Subdomain to update, e.g. hostname')
        self._parser.add_argument('--username', type=str, help='Username at one.com')
        self._parser.add_argument('--password', type=str, help='Password at one.com')
        #self._parser.add_argument('--id', '-i', type=str, help='ID of corresponding A-record at one.com')
        self._parser.add_argument('--fqdn', type=str, help='FQDN of host to update, e.g. hostname.domain.org')
        self._parser.add_argument('--timeout', '-t', type=int, help='Timeout in seconds (TTL)')
        self._parser.add_argument('--force', action='store_true', help='Force update of A-record')
        self._parser.add_argument('--log', help='Set log level', choices=['CRITICAL','ERROR','WARNING','INFO','DEBUG'], default='INFO')

    def parseConfig(self):
        """ Parses argument list and configuration file """

        # Start with parsing only the known arguments, i.e the config file
        args, remaining_argv = self._preParser.parse_known_args()

        if args.config:
            config = ConfigParser()
            config.read([args.config])
            self._defaults.update( dict(config.items('OneDns')))

        # Update the defaults 
        self._parser.set_defaults(**self._defaults)

        # Parse the remaining arguments
        return self._parser.parse_args(remaining_argv)


    def checkConfig(self):
        assert self._args.username
        assert self._args.password

        # Check the domain name
        parts = self._args.fqdn.split('.')
        assert len(parts) == 3
        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        assert all(allowed.match(part) for part in parts)
            

    def getPublicIp(self):
        """ Uses ipyfy.org to determine the public IP of the computer running this tool """

        GET_IP = requests.get("https://api.ipify.org/")
        if (GET_IP.status_code != 200):
            raise ResolveException(f'Could not get IP address from api.ipify.org. Status code {GET_IP.status_code}')
            #sys.exit("Could not get IP address from api.ipify.org - Check your internet connection, or check that https://api.ipify.org is up.")
        return GET_IP.text

    def resolve(self, fqdn):
        res = dns.resolver.Resolver(configure=False)
        res.nameservers = self._nameservers
        r = res.resolve(fqdn)
        return r

    def getDomain(self) -> str:

        return '.'.join( self._args.fqdn.split('.')[1:])

    def getSubdomain(self) -> str:

        return '.'.join( self._args.fqdn.split('.')[:-2])


    def run(self):

        # Set log level
        numLogLevel = getattr(logging, self._args.log.upper(), None)
        #logger.setLevel(self._args.log)
        logging.basicConfig(level=numLogLevel)

        # Resolve the host name
        resIp = self.resolve(self._args.fqdn)

        # Take the first value
        resolvedIp = resIp[0].to_text()

        # Get my public IP address
        publicIp = self.getPublicIp()

        if publicIp == resolvedIp:
            logger.info(f"Public IP and resolved IP matches ({resolvedIp}), no need to update DNS record.")
            if not self._args.force:
                return
        else:
            logger.info(f'Detected change of public IP address from {resolvedIp} to {publicIp}. Need to update DNS record.')

        domain = self.getDomain()
        subdomain = self.getSubdomain()
        assert domain == 'varukulla.se'
        assert subdomain == 'lovlund'

        od = OneDnsAPI()
        od.loginSession(self._args.username, self._args.password)
        records = od.getCustomRecords(domain)
        id = od.findIdBySubdomain(records, subdomain)
        if id:
            #od.updateRecord(id, domain, subdomain, value = '95.155.200.227')
            od.updateRecord(id, domain, subdomain, value = publicIp)
        else:
            logger.error("Couldn't determine the ID for the record")


if __name__ == '__main__':
    theApp = OneDns()
    theApp.run()