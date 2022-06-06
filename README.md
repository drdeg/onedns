# OneDNS

Simple DNS record updater for domains hosted at one.com

As my ISP does not give me a static IP number, I need some sort of dynamic DNS service to access my
home computer(s). One common solution is to rely on the router to update a DDNS service, like no-IPO
and ASUS.

## Description

This program checks the current public IP of the host running the script, and compares the result
to the DNS resolved IP number of the specified fully qualified domain name (FQDN). If they differ,
it can update the corresponding DNS record on one.com DNS server.

## Installation

As always, it is recommended to install in a virtual python environment.
After you've created your virtual environment, install the package
directly from github using pip

```bash
python -m pip install git+https://github.com/drdeg/onedns.git
```

## Command line arguments

To run the tool, simply

```bash
python -m onedns --config path/to/config
```

|  Argument                | Description                                                                     |
| :---                     | :---                                                                            |
| --help, -h               | Show help screen                                                                |
| --config, -c *filepath*  | Pathname to a configuration file for the following parameters. See below!       | 
| --username *user*        | Username to login to one.com admin panel                                        |
| --password *pass*        | Password used to login to one.com admin panel                                   |
| --fqdn *host.domain.top* | Specifies the FQDN of the record to modify                                      |
| --log *level*            | Set log level [critical, error, warning, info, debug]                           |
| --timeout *TTL*          | Specify the TTL (defulas to 3600)                                               |
| --simulate               | If specified, the record is not changed                                         |
| --force                  | The record is updated, even if it is the same as the current public IP address  |

## Configuration file

As you don't want parameters like username and password visible on the command line, you can place them in
an ini/toml like configuration file. The parameters are the same as the long commad line arguments and must
be placed in a [OneDNS] configuration section. Like this:

```ini
[OneDNS]
username = your@email.com
password = really?!?
fqdn = www.yordomain.com
timeout = 3600
```

Observer that any command line argument overrides the corresponding value
in the configuration file.

### Systemd service

The script is well used when invoked from a systemd service. In this case, you should create one service
uinit and one timer unit. In this way, you can trigger the script periodically. 15-30 minutes interval is
a reasonable choise for interval. There should be an example of these files in the repository (but there
isn't as of now. My bad.).
