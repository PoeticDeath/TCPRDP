import pynput
from sys import argv
from pynput.mouse import Button

mouse = pynput.mouse.Controller()

def server():
    import socketserver
    from time import sleep

    class TCPRDP(socketserver.TCPServer):
        allow_reuse_address = True
        request_queue_size = 0

    class TCPRDPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            while True:
                mousepos = mouse.position
                self.request.sendall(
                    mousepos[0].to_bytes(2, "big")
                    + mousepos[1].to_bytes(2, "big")
                )
                sleep(0.0001)

    server = TCPRDP((argv[2], int(argv[3])), TCPRDPHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def client():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((argv[2], int(argv[3])))
        oldmousepos = mouse.position
        try:
            while True:
                data = sock.recv(4)
                newmousepos = mouse.position
                mousepos = (
                    int.from_bytes(data[:2], "big"),
                    int.from_bytes(data[2:4], "big"),
                )
                if newmousepos == mousepos:
                    oldmousepos = mousepos
                if oldmousepos == newmousepos:
                    mouse.position = mousepos
                    oldmousepos = mousepos
                else:
                    oldmousepos = newmousepos
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    if argv[1] == "1":
        server()
    else:
        client()
