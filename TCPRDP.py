from sys import argv
import pynput

from pynput.mouse import Button

mouse = pynput.mouse.Controller()
from pynput.keyboard import Key

keyboard = pynput.keyboard.Controller()

from win32 import win32api
from win32.lib import win32con

width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)


def server():
    from io import BytesIO
    from PIL import Image
    import socketserver
    from threading import Thread, Lock

    lock = Lock()

    from win32 import win32gui
    from pythonwin import win32ui

    def grab_screen():
        memdc.BitBlt((0, 0), (width, height), srcdc, (left, top), win32con.SRCCOPY)
        return bmp.GetBitmapBits(True)

    def bgra2rgb(bgra):
        rgb[::3] = bgra[2::4]
        rgb[1::3] = bgra[1::4]
        rgb[2::3] = bgra[::4]

    def cap_jpg():
        with lock:
            bgra2rgb(grab_screen())
            IM = Image.frombytes("RGB", (width, height), rgb)
            cur.seek(0)
            cur.truncate(0)
            IM.save(cur, "jpeg")

    class TCPRDP(socketserver.TCPServer):
        allow_reuse_address = True
        request_queue_size = 0



    class TCPRDPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            Thread(target=self.keys, args=(), daemon=True).start()
            while True:
                with lock:
                    size = cur.tell()
                    if size:
                        self.request.sendall(b"D" + size.to_bytes(4, "big"))
                        cur.seek(0)
                        self.request.sendall(cur.read(size))
                        cur.seek(0)

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
                        mouse.position = int.from_bytes(
                            key[:2], "big"
                        ), int.from_bytes(key[2:4], "big")
                    case b"MM":
                        mouse.move(
                            int.from_bytes(key[:2], "big", signed=True),
                            int.from_bytes(key[2:4], "big", signed=True),
                        )
                    case b"MC":
                        mouse.click(eval(key[:-1]), key[-1])
                    case b"MS":
                        mouse.scroll(
                            int.from_bytes(key[:1], "big", signed=True),
                            int.from_bytes(key[1:2], "big", signed=True),
                        )


    cur = BytesIO()

    left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

    hwin = win32gui.GetDesktopWindow()

    hwindc = win32gui.GetWindowDC(hwin)
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, width, height)
    memdc.SelectObject(bmp)

    server = TCPRDP((argv[2], int(argv[3])), TCPRDPHandler)
    Thread(target=server.serve_forever, args=(), daemon=True).start()

    rgb = bytearray(width * height * 3)
    try:
        while True:
            cap_jpg()
    except KeyboardInterrupt:
        pass
    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwin, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())


def client():
    def mouse_evt(*args):
        win32api.SetCursor(win32api.LoadCursor(0, win32con.IDC_ARROW))

    import cv2
    import socket
    import numpy as np

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
                data = sock.recv(5)
                size = int.from_bytes(data[1:5], "big")
                if size and (data[0:1] == b"D"):
                    while len(frame) < size:
                        frame += sock.recv(size - len(frame))
                    frame = cv2.imdecode(
                        np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR
                    )
                    cv2.imshow("TCPRDP", frame)
                cv2.waitKey(1)
                if oldmousepos != mouse.position:
                    x = mouse.position[0] - oldmousepos[0]
                    y = mouse.position[1] - oldmousepos[1]
                    oldmousepos = mouse.position
                    sock.sendall(b"MM" + int(4).to_bytes(4, "big"))
                    sock.sendall(
                        x.to_bytes(2, "big", signed=True)
                        + y.to_bytes(2, "big", signed=True)
                    )
                press = set()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    if argv[1] == "1":
        server()
    else:
        client()
