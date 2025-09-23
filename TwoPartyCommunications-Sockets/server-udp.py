from socket  import *
HOST = 'localhost'
PORT = 5000
s = socket(AF_INET, SOCK_DGRAM)
s.bind((HOST, PORT))
while True:                # forever
  data, addr = s.recvfrom(1024)   # receive data from client
  
  print("received: "+data.decode())
  if not data: break       # stop if client stopped
  s.sendto((data.decode()+"*").encode(), addr) # return sent data plus an "*"
