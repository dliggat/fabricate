#!/usr/bin/env python

import boto3

def foo():
    client = boto3.client('ec2')
    sg = event['ResourceProperties']['GroupId']
    to_delete = []
    for interface in client.describe_network_interfaces()['NetworkInterfaces']:
        if [i for i in interface['Groups'] if i['GroupId'] == sg ]:
            to_delete.append(interface['NetworkInterfaceId'])

    for interface in to_delete:
        client.delete_network_interface(NetworkInterfaceId=interface)


    print(interface)

  # a = client.delete_network_interface(NetworkInterfaceId='eni-2a81ca01')
  # print(a)


foo()
