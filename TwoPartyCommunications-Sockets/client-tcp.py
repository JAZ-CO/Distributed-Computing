from socket  import *
HOST = 'localhost'
PORT = 5000
s = socket(AF_INET, SOCK_STREAM)
s.connect((HOST, PORT)) # connect to server (block until accepted)
s.send('Hello, World!'.encode())  # send some data
data = s.recv(1024)     # receive the response
print(data.decode())              # print the result
s.close()               # close the connection
