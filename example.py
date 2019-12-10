#!/usr/bin/env python
import iottl, sys, time


# this callback is called everytime anything is publised into any of subscribed topics
def message(obj, topic, payload):
    # mqtt    - client object
    # topic   - that fired this event
    # payload - either dict or bytes/bytearray

    # in case payload is decoded BSON or JSON it must be stored inside dict object
    if type(payload) == type(dict()):
        # if the payload is sent using this library some system keys exists:
        # _sys_timestamp  - unixepoch time when the payload has been created at sender
        # _sys_clientid   - id of client that sent this payload (future implementation will use this for querying directly publisher)
        # _sys_pubid      - sequential number of message (used to deduplication when QOS=1, clientid + pubid, must be globaly unique key)
        #

        print ("J/BSON message arrive on topic %s with content:" % (topic))
        print (payload)
      

    else:
        print ("raw message arrived on topic %s with length %d bytes" % (topic, len(payload)))





if __name__ =="__main__":

    # create MQTT client, if username and password is ommited hardcoded pair is used
    client = iottl.Hermes(
        "SERVER, 
        username='USERNAME',
        password='PASSWORD',
        port=8883, 
        cacert="ca.crt", 
        callback = message)

    # optional address with no encryption
    # client = iottl.Hermes("bran01.ff.avast.com", port=1883, callback = message)


    # try to connect
    if client.connect():

           # subscribe, optional parameter callback can be used to tie it with
        # explicit topic, in that case # + wildcards could not be used in subscription
        client.subscribe('honeyfeed/adb/shell')
        
        client.subscribe('honeyfeed/raw')

        client.subscribe('honeyfeed/connection')

        
        # sending data to bus on topic honeyfeed/adb/shell

        # input parameter for payload should be dict, you can embed binary data, but keep in mind that
        # although mqtt limitation is  256MB per message, usually due to performance
        # reasons it's advisable to use much smaller binary blobs
        client.send('honeyfeed/adb/shell',  {"commandline": "pipa", "binarydata":  b'\x00\x01\x02\x03\x40' } )

        # if you want to send raw data in payload without any added information by framework use this method
        # the size limitations are however the same.
        client.send_raw('honeyfeed/raw', b'\x00\x01\x02\x03\x40')

        '''
         === Topics for honeypots projects ===

         let's keep this schema:
         for data from honeypots let's use this topic schema:
         honeyfeed/[honeypot type]/[feed]
         where:
           honeypot type - is adb, telnet, ssh, eml, upnp...
           feed          -  will be data type, this can be honeypot dependent but let's define these fixed ones:
                            shell - extracted command lines and inputs
                            file  - file feed, extracted file
                            secrets - feed for password/username or other secrets extracted at honeypots
                            sha256 - in case you don't want to send file directly that will be only "announcement" that his file is stored on honeypot
                            log   - everything that's not crucial but should be saved to global log
         examples of topics:

           honeyfeed/adb/file
           honefeed/adb/shell
           honeyfeed/eml/file  - for extracted attachements (just example)
           honeyfeed/mikrotik/secrets - username password combination

        '''


        # endless loop
        while True:
            time.sleep(1)
  
