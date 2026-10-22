# Scripts to control a Zyxel SP300E thermal printer

These printers are made to work with a Zyxel N4100. But I don't care, I don't have a N4100.

However, I have paper, and I have a computer. So I want to print.

## How to use

After some tests, it is really easy. When connected to ethernet, the printer take the IP `192.168.1.7`.

Access to HTTP interface. Username: `admin`. Password: `1234`.

Change network details. Set "destination" IP to the host what will run the program. Set a port, and don't encrypt.

Run the `server.py` program.

You can send JSON data to `/print` and it will print the result.

```
curl -X POST http://localhost:8000/print --data '{"text": "Hello world"}' -H "Content-Type: application/json"
```

## How it works

The printer open a TCP connection to the destination IP (you can set the port, default 9001).

If you send data to the TCP connection, it gets printed.

If you send too much data, only the 457 first bytes gets printed in one chunk, then there is a line break, and 457 chars, then a line break, and 86 chars (total of 1000).

To avoid this, you need to empty the buffer. To do so, you need to print `\n`.

However, the auto-wrap is smaller than the `\n`. When sending a packet, you can set the `\n` size using `\x1b3\x01`. It kinda respects the `ESC/POS` commands reference.

My strategy is then to set the `\n` to the minimum, then to send less than 457 bytes. And if there is a need to send more than `457` bytes with no line break, I add `\n` after a number of chars divisible by `24` (row size), so it's not visible.

White all of this in mind, you should be able to understand the code.

## Use the printer buttons

Future.

Code needs to be refactored a bit and improved. Then some new features will be added.
