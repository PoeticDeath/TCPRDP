from sys import argv
import numpy as np
import pynput
import cv2

from pynput.mouse import Button

mouse = pynput.mouse.Controller()
from pynput.keyboard import Key

keyboard = pynput.keyboard.Controller()

from win32 import win32api
from win32.lib import win32con

width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)


def server():
    import socketserver
    from time import sleep
    from PIL import ImageGrab
    from threading import Thread

    oldbuf = bytearray()
    buf = bytearray()

    def cap_jpg():
        im = np.frombuffer(ImageGrab.grab().tobytes(), np.uint8)
        im.shape = (height, width, 3)
        buf[:] = cv2.imencode(".jpg", im)[1].tobytes()

    class TCPRDP(socketserver.TCPServer):
        allow_reuse_address = True
        request_queue_size = 0

    class TCPRDPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            Thread(target=self.keys, args=(), daemon=True).start()
            while True:
                scr = bytes(buf)
                mousepos = mouse.position
                if scr != oldbuf:
                    self.request.sendall(
                        b"D"
                        + len(scr).to_bytes(4, "big")
                        + mousepos[0].to_bytes(2, "big")
                        + mousepos[1].to_bytes(2, "big")
                    )
                    self.request.sendall(scr)
                    oldbuf[:] = scr
                else:
                    self.request.sendall(
                        b"D"
                        + b"\x00" * 4
                        + mousepos[0].to_bytes(2, "big")
                        + mousepos[1].to_bytes(2, "big")
                    )
                    sleep(1 / 60)

        def keys(self):
            while True:
                data = self.request.recv(6)
                size = int.from_bytes(data[2:6], "big")
                key = self.request.recv(size)
                match data[:2]:
                    case b"KP":
                        keyboard.press(eval(key))
                    case b"KR":
                        keyboard.release(eval(key))
                    case b"ME":
                        mouse.position = int.from_bytes(key[:2], "big"), int.from_bytes(
                            key[2:4], "big"
                        )
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
    Thread(target=server.serve_forever, args=(), daemon=True).start()

    try:
        while True:
            cap_jpg()
    except KeyboardInterrupt:
        pass


def client():
    def mouse_evt(*args):
        win32api.SetCursor(win32api.LoadCursor(0, win32con.IDC_ARROW))

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        press = set()
        sock.connect((argv[2], int(argv[3])))
        cv2.namedWindow("TCPRDP", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("TCPRDP", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.setMouseCallback("TCPRDP", mouse_evt)

        def on_press(key):
            if key not in press:
                press.add(key)
                sock.sendall(b"KP" + len(str(key).encode()).to_bytes(4, "big"))
                sock.sendall(str(key).encode())

        def on_release(key):
            if key in press:
                press.remove(key)
            sock.sendall(b"KR" + len(str(key).encode()).to_bytes(4, "big"))
            sock.sendall(str(key).encode())

        keylistener = pynput.keyboard.Listener(
            on_press=on_press, on_release=on_release, suppress=True
        )
        keylistener.start()

        def on_click(x, y, button, pressed):
            sock.sendall(
                b"MC"
                + len(str(button).encode() + pressed.to_bytes(1, "big")).to_bytes(
                    4, "big"
                )
            )
            sock.sendall(str(button).encode() + pressed.to_bytes(1, "big"))

        def on_scroll(x, y, dx, dy):
            sock.sendall(
                b"MS"
                + len(
                    dx.to_bytes(1, "big", signed=True)
                    + dy.to_bytes(1, "big", signed=True)
                ).to_bytes(4, "big")
            )
            sock.sendall(
                dx.to_bytes(1, "big", signed=True) + dy.to_bytes(1, "big", signed=True)
            )

        mouselistener = pynput.mouse.Listener(on_click=on_click, on_scroll=on_scroll)
        mouselistener.start()
        oldmousepos = mouse.position
        sock.sendall(b"ME" + int(4).to_bytes(4, "big"))
        sock.sendall(
            oldmousepos[0].to_bytes(2, "big") + oldmousepos[1].to_bytes(2, "big")
        )
        try:
            while True:
                frame = b""
                data = sock.recv(9)
                size = int.from_bytes(data[1:5], "big")
                if size and (data[0:1] == b"D"):
                    while len(frame) < size:
                        frame += sock.recv(size - len(frame))
                    frame = cv2.cvtColor(
                        cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR),
                        cv2.COLOR_BGR2RGB,
                    )
                    cv2.imshow("TCPRDP", frame)
                cv2.waitKey(1)
                newmousepos = mouse.position
                mousepos = (
                    int.from_bytes(data[5:7], "big"),
                    int.from_bytes(data[7:9], "big"),
                )
                if newmousepos == mousepos:
                    oldmousepos = mousepos
                if oldmousepos != newmousepos:
                    x = newmousepos[0] - oldmousepos[0]
                    y = newmousepos[1] - oldmousepos[1]
                    oldmousepos = newmousepos
                    sock.sendall(b"MM" + int(4).to_bytes(4, "big"))
                    sock.sendall(
                        x.to_bytes(2, "big", signed=True)
                        + y.to_bytes(2, "big", signed=True)
                    )
                else:
                    mouse.position = mousepos
                    oldmousepos = mousepos
                if newmousepos[0] == 0 or newmousepos[0] == width - 1:
                    mouse.position = (mousepos[0], mouse.position[1])
                    oldmousepos = (mousepos[0], oldmousepos[1])
                if newmousepos[1] == 0 or newmousepos[1] == height - 1:
                    mouse.position = (mouse.position[0], mousepos[1])
                    oldmousepos = (oldmousepos[0], mousepos[1])
                press = set()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    if argv[1] == "1":
        server()
    else:
        client()
