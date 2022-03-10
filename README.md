# MacAddressDB
get your network devices mac address tables into json text files

## creating MacAddressEntry object

```python
mac1 = MacAddressEntry(mac="28-52-61-aa-bb-cc", \
                        port="gi1/1", \
                        date="2022-02-05 14:58:48", \
                        ip=["172.16.0.2", \
                            "10.0.0.2", \
                            "192.168.0.2"], \
                        port_description = "home router", \
                        company = "Cisco Systems, Inc", \
                        last_seen = "2022-02-20 10:10:22",
                        )
#or
mac1 = MacAddressEntry(**{"mac":"28-52-61-aa-bb-cc", \
                        "port":"gi1/1", \
                        "date":"2022-02-05 14:58:48", \
                        "ip":["172.16.0.2", \
                            "10.0.0.2", \
                            "192.168.0.2"], \
                        "port_description" : "home router", \
                        "company" : "Cisco Systems, Inc", \
                        "last_seen" : "2022-02-20 10:10:22",}
                        )

                        
```

## adding MacAddressEntry object to MacAddressList

```python
mac_list = MacAddressList()
mac_list.update(mac1)

```

## updating port number for MacAddressEntry in MacAddressList

```python
mac_list.update(MacAddressEntry(**{"mac":"28-52-61-aa-bb-cc", "port":"gi1/2"}))

```


