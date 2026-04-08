from PIL import Image

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64


class FrameBuffer:
    def __init__(self, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT):
        self.width = width
        self.height = height
        self.bytes_per_row = width // 8
        self.buffer = bytearray(self.bytes_per_row * height)

    def clear(self):
        self.buffer[:] = b"\x00" * len(self.buffer)

    def set_pixel(self, x, y, value):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        index = y * self.bytes_per_row + (x >> 3)
        mask = 0x80 >> (x & 7)
        if value:
            self.buffer[index] |= mask
        else:
            self.buffer[index] &= ~mask

    def draw_hline(self, x0, y, x1, value=1):
        if y < 0 or y >= self.height:
            return
        if x0 > x1:
            x0, x1 = x1, x0
        for x in range(max(0, x0), min(self.width, x1 + 1)):
            self.set_pixel(x, y, value)

    def draw_vline(self, x, y0, y1, value=1):
        if x < 0 or x >= self.width:
            return
        if y0 > y1:
            y0, y1 = y1, y0
        for y in range(max(0, y0), min(self.height, y1 + 1)):
            self.set_pixel(x, y, value)

    def draw_rect(self, x0, y0, x1, y1, value=1):
        self.draw_hline(x0, y0, x1, value)
        self.draw_hline(x0, y1, x1, value)
        self.draw_vline(x0, y0, y1, value)
        self.draw_vline(x1, y0, y1, value)

    def fill_rect(self, x0, y0, x1, y1, value=1):
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        for y in range(max(0, y0), min(self.height, y1 + 1)):
            for x in range(max(0, x0), min(self.width, x1 + 1)):
                self.set_pixel(x, y, value)

    def from_pil_image(self, image):
        image = image.convert("1")
        image = image.resize((self.width, self.height), Image.NEAREST)
        for y in range(self.height):
            for x in range(self.width):
                pixel = image.getpixel((x, y))
                self.set_pixel(x, y, 0 if pixel else 1)

    def as_bytes(self):
        return bytes(self.buffer)
