#!/usr/bin/python3
import json
import datetime
import ipaddress
from netmiko import ConnectHandler
import re
import macaddress
from gotify_message.gotify import GotifyNotification
from mac_vendor_lookup import MacLookup

class MacAddressEntry:
    'class to build mac address entry'

    def __init__(
        self, 
        mac:str, 
        port:str=None, 
        date:str=None, 
        ip:list=None, 
        port_description:str=None,
        company:str=None, 
        last_seen:str=None
        ):
        self.mac = str(macaddress.MAC(mac))
        self.port = port if port else ''
        self.date = date if date else \
                                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.port_description = port_description if port_description else ''
        self.last_seen = last_seen if last_seen else ''
        if company:
            self.company = company
        else:
            try:
                self.company = MacLookup().lookup(self.mac)
            except KeyError:
                self.company = ''

        try: #try to read `ip` as a list 
            self.ip = [str(ipaddress.ip_address(e)) for e in ip]
        except ValueError: # if failed read as str
            try:
                self.ip = []
                self.ip = [str(ipaddress.ip_address(ip))]
            except ValueError:
                 self.ip = []

    def __repr__(self):
        return str(self.__dict__)

    def __str__(self):
        return (str(self.__dict__)  .replace('\'','\"'))

    def __iter__(self):
        return iter(self.__dict__)

    def __getitem__(cls, item):
        return getattr(cls, item)

    @property
    def json(self):
        return json.dumps(self, default=vars, indent=4)
    
class MacAddressList:
    #def __init__(self, mac_list: list[MacAddressEntry]=None): # works only in python3.9
    def __init__(self, mac_list: list=None):
        self.mac_list = mac_list if mac_list is not None else [] 
    
    def __repr__(self):
        return str(self.mac_list)
        
    def __str__(self):
        return str(self.mac_list)

    def __iter__(self):
        return iter(self.mac_list)

    def __getitem__(self, item):
         return self.mac_list[item]

    def update(self, mac_input: MacAddressEntry, notify_to=None):
        if mac_input['mac'] not in [entry['mac']for entry in self.mac_list]:
             if not mac_input.date: 
                 mac_input.date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
             mac_input.last_seen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
             self.mac_list.append(mac_input)
             if notify_to: 
                try:
                    NotifyNewMac(mac_input, notify_to['url'], notify_to['app_token']).send()
                except Exception as e:
                    print (f'notification send failed: {str(e)}')

        else:
            for entry in self.mac_list:
                if entry['mac'] == mac_input['mac']:
                    for ip in mac_input.ip:
                        if ip not in entry.ip: entry.ip.append(ip)
                    if mac_input.port: entry.port = mac_input.port
                    if mac_input.port_description: entry.port_description = mac_input.port_description
                    if entry.company: pass # do not overwrite existing company 
                    if entry.date: pass # do not overwrite exisiting creation date
                    else: entry.date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    entry.last_seen = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
               
    @classmethod
    def from_json_file(cls, json_file):
        file=open(json_file, "r")
        list = [MacAddressEntry(**line) for line in (json.load(file))]
        file.close()
        return cls(list)


    def to_json_file(self, json_file):
        file=open(json_file, "w")
        file.write(self.json)
        file.close()

    @property
    def json(self):
        return json.dumps(self.mac_list, default=vars, indent=4)


class IOSMacAddressList(MacAddressList):
    def __init__(self, device, vrfs):
        self.connect = ConnectHandler(**device)
        super().__init__()
        self.port_descriptions = self._get_port_descriptions() #use genie to get entire show interface
        self.mac_address_table = self._get_mac_address_table()
        self.arp_table = self._get_arp_table()
        self.arp_table_vrf_outside = self._get_arp_table(vrf='vrf OUTSIDE')


        for entry in self.mac_address_table: #Add port description to mac address table
            try:
                entry['port_description'] = self.port_descriptions[entry['port']]['description']
            except KeyError:
                entry["port_description"] = ''
                print (f'no description for port: {entry["port"]}')

        #update entries from mac_address_table
        for entry in self.mac_address_table: 
            if entry['type'] != 'Self': self.update(MacAddressEntry(
                                                    mac=entry['mac'],
                                                    port=entry['port'],
                                                    port_description=entry['port_description'],
                                                    ))
        #update entries from arp_table
        for entry in self.arp_table:
            try: 
                self.update(MacAddressEntry(
                            mac=entry['mac'],
                            ip=entry['ip']
                            ))
            except AttributeError as e:
                print (f"cannot update entry: {entry} {str(e)}")
            except ValueError as e:
                print (f"cannot parse entry: {entry} {str(e)}")

        #update entries from arp_table_vrf_outside
        for entry in self.arp_table_vrf_outside:
            try:
                self.update(MacAddressEntry(
                            mac=entry['mac'],
                            ip=entry['ip']
                            ))
            except AttributeError as e:
                print (f"cannot update entry: {entry} {str(e)}")
            except ValueError as e:
                print (f"cannot parse entry: {entry} {str(e)}")

        self.connect.disconnect()


    def _get_port_descriptions(self):
        cmd_output = self.connect.send_command('show interfaces', use_genie=True)
        return cmd_output
    
    def _get_mac_address_table(self):
        cmd_output = self.connect.send_command('show mac-address-table', use_genie=False)
        cmd_output = re.sub(r'\n\s*\n','\n',cmd_output,re.MULTILINE) #remove empty lines
        cmd_output = cmd_output.splitlines() #convert to list
        cmd_output = cmd_output[2:] #remove output header
        keys = ['mac', 'type', 'vlan', 'port']
        mac_address_table = []
        for e in cmd_output: 
            mac_address_table.append(dict(zip(keys,e.split() )))
        return mac_address_table

    def _get_arp_table(self, vrf=''):
        cmd_output = self.connect.send_command('show ip arp ' + vrf, use_genie=False)
        cmd_output = re.sub(r'\n\s*\n','\n',cmd_output,re.MULTILINE) #remove empty lines
        cmd_output = cmd_output.splitlines() #convert to list
        cmd_output = cmd_output[1:] #remove output header
        keys = ['protocol', 'ip', 'age', 'mac', 'type', 'interface']
        arp_table = []
        for e in cmd_output: 
            arp_table.append(dict(zip(keys,e.split() )))
        return arp_table

class SG500MacAddressList(MacAddressList):
    def __init__(self, device):
        self.connect = ConnectHandler(**device)
        super().__init__()
        self.port_descriptions = self._get_port_descriptions()
        self.mac_address_table = self._get_mac_address_table()
        self.arp_table = self._get_arp_table()

        for entry in self.mac_address_table: #Add port description to mac address table
            try:
                entry["port_description"] = next(port_desc['description'] \
                                            for port_desc in self.port_descriptions \
                                            if entry['port'] == port_desc['port'])
            except StopIteration:
                print(f"Port {entry['port']} not found")
            except KeyError:
                entry["port_description"] = ''
                print(f"No description for port: {entry['port']}")

        #update entries from mac_address_table
        for entry in self.mac_address_table:
            if entry['type'] != 'self': self.update(MacAddressEntry(
                                                    mac=entry['mac'],
                                                    port=entry['port'],
                                                    port_description=entry['port_description'],
                                                    ))
        #update entries from arp_table
        for entry in self.arp_table:
            try:
                self.update(MacAddressEntry(
                            mac=entry['mac'],
                            ip=entry['ip']
                            ))
            except AttributeError as e:
                print (f"cannot update entry: {entry} {str(e)}")
            except ValueError as e:
                print (f"cannot parse entry: {entry} {str(e)}")

        self.connect.disconnect()

    def _get_port_descriptions(self):
        cmd_output = self.connect.send_command('show interface description', use_genie=False)
        cmd_output = re.sub(r'\n\s*\n','\n',cmd_output,re.MULTILINE) #remove empty lines
        cmd_output = cmd_output.splitlines() #convert to list
        cmd_output = cmd_output[2:] #remove output header
        keys = ['port', 'description']
        port_descriptions = []
        for e in cmd_output: 
            port_descriptions.append(dict(zip(keys,e.split() )))
        return port_descriptions
    
    def _get_mac_address_table(self):
        cmd_output = self.connect.send_command('show mac address-table', use_genie=False)
        cmd_output = re.sub(r'\n\s*\n','\n',cmd_output,re.MULTILINE) #remove empty lines
        cmd_output = cmd_output.splitlines() #convert to list
        cmd_output = cmd_output[5:] #remove output header
        keys = ['vlan', 'mac', 'port', 'type']
        mac_address_table = []
        for e in cmd_output: 
            mac_address_table.append(dict(zip(keys,e.split() )))
        return mac_address_table

    def _get_arp_table(self):
        cmd_output = self.connect.send_command('show arp', use_genie=False)
        cmd_output = re.sub(r'\s{12}',' unknown', cmd_output, re.MULTILINE) #replace sequence of 12 spaces to ' unknown' string
        cmd_output = re.sub(r'\n\s*\n','\n',cmd_output,re.MULTILINE) #remove empty lines
        cmd_output = cmd_output.splitlines() #convert to list
        cmd_output = cmd_output[5:] #remove output header
        keys = ['vlan', 'vlan_number', 'interface', 'ip', 'mac', 'status']
        arp_table = []
        for e in cmd_output: 
            arp_table.append(dict(zip(keys,e.split() )))
        return arp_table

class NotifyNewMac(GotifyNotification):
        '''example
        mac1=MacAddressEntry(mac='aaaa.bbbb.cccc')
        NotifyNewMac(url='http://192.168.3.7:8090' ,mac=mac1, app_token='rtadf4Vq8Ovc8bY').send()
        '''
        CONTENT_TYPE='markdown'

        def __init__(self, mac:MacAddressEntry, url,  app_token, priority:int=5):
                title='Wykryto nowy MAC address w sieci'
                message= '''| MAC | ''' + mac.mac + ''' |
| ----------- | ----------- |
| Description | ''' + mac.port_description + ''' |
| Port | ''' + mac.port + ''' |
| Manufacturer | ''' + mac.company  +''' |
| IP | ''' + str(mac.ip) + ''' |
| Date | ''' + mac.date
                super().__init__(url, app_token, title, message, priority)


