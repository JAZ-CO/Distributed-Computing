from socket import *
HOST = 'localhost'
PORT = 5000
s = socket(AF_INET, SOCK_DGRAM)
# send some data
s.sendto('Hello, World!'.encode(), (HOST,PORT))
# receive the response
data = s.recvfrom(1024) 
# print the result
print(data[0].decode()) 