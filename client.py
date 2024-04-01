import socket
import termux

client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
host = input('Enter hostname')
port = int(input('Enter port'))
client.connect((host,port))

title = 'Trade signal'

while True:
    data = client.recv(64).decode()
    termux.Notification.notify(title = title, content = data)
