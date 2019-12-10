import re

# similar to unix command strings, get all strings 
def getStrings(data):	
	return re.findall("[^\x00-\x1F\x7F-\xFF]{4,}", data)
