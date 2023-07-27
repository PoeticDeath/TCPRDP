import pynput
from sys import argv
from pynput.mouse import Button

mouse = pynput.mouse.Controller()


def server():
    import socketserver

    class TCPRDP(socketserver.TCPServer):
        allow_reuse_address = True
        request_queue_size = 0

    class TCPRDPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            while True:
                data = self.request.recv(6)
                size = int.from_bytes(data[2:6], "big")
                key = self.request.recv(size)
                match data[:2]:
                    case b"MM":
                        mouse.move(
                            int.from_bytes(key[:2], "big", signed=True),
                            int.from_bytes(key[2:4], "big", signed=True),
                        )
                    case b"MC":
                        if key[-1]:
                            mouse.press(eval(key[:-1]))
                        else:
                            mouse.release(eval(key[:-1]))
                    case b"MS":
                        mouse.scroll(
                            int.from_bytes(key[:1], "big", signed=True),
                            int.from_bytes(key[1:2], "big", signed=True),
                        )

    server = TCPRDP((argv[2], int(argv[3])), TCPRDPHandler)
    server.serve_forever()


def client():
    import socket

    def on_move(x, y):
        mousepos = mouse.position
        X = x - mousepos[0]
        Y = y - mousepos[1]
        sock.sendall(b"MM" + b"\x00" * 3 + b"\x04")
        sock.sendall(
            X.to_bytes(2, "big", signed=True) + Y.to_bytes(2, "big", signed=True)
        )

    def on_click(x, y, button, pressed):
        sock.sendall(
            b"MC"
            + len(str(button).encode() + pressed.to_bytes(1, "big")).to_bytes(4, "big")
        )
        sock.sendall(str(button).encode() + pressed.to_bytes(1, "big"))

    def on_scroll(x, y, dx, dy):
        sock.sendall(
            b"MS"
            + len(
                dx.to_bytes(1, "big", signed=True) + dy.to_bytes(1, "big", signed=True)
            ).to_bytes(4, "big")
        )
        sock.sendall(
            dx.to_bytes(1, "big", signed=True) + dy.to_bytes(1, "big", signed=True)
        )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((argv[2], int(argv[3])))
        with pynput.mouse.Listener(
            on_move=on_move, on_click=on_click, on_scroll=on_scroll, suppress=True
        ) as mouselistener:
            mouselistener.join()


if __name__ == "__main__":
    try:
        if argv[1] == "1":
            server()
        else:
            client()
    except KeyboardInterrupt:
        pass
