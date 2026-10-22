import asyncio
import contextvars
import re

import fastapi
import uvicorn
from pydantic import BaseModel

prints_queue: asyncio.Queue[str] = asyncio.Queue()
print_ready = asyncio.Event()
current_connection: asyncio.Task[None] | None = None

app = fastapi.FastAPI()

async def print_text(text: str, writer: asyncio.StreamWriter):
    parts = text.replace("\r", "\n").encode("utf-8").split(b"\n")
    # Set new line spacing to minimum
    current_chunk = b"\x1b3\x01"
    for part in parts:
        # by tests, a packet can only contains 457 bytes. We send packets by 15 rows (24 chars) to avoid the overflow.
        for i in range(0, len(part), 360):
            chunk = part[i:i + 360]
            if len(chunk) + len(current_chunk) >= 360:
                writer.write(current_chunk)
                _ = await print_ready.wait()
                await writer.drain()
                await asyncio.sleep(0.2)
                current_chunk = b""
            # Adding \n at the end of a 24 char line is invisible, and allows to prints the buffer
            current_chunk += chunk + b"\n"

    current_chunk = current_chunk.rstrip(b"\n") + b"\n\n\n\n"
    writer.write(current_chunk)
    _ = await print_ready.wait()
    await writer.drain()
    await asyncio.sleep(0.2)


# async def wait_for_buffer(reader: asyncio.StreamReader):
#     data = await reader.read(1024)
#     while b"\x13" in data:
#         await asyncio.sleep(1)
#         data = await reader.read(1024)

async def block():
    if print_ready.is_set():
        print("Blocking the printing until buffer is free")
        print_ready.clear()
    await asyncio.sleep(1)
    print_ready.set()
    print("Unblock the printing")

async def connection_listener(reader: asyncio.StreamReader):
    lock_task = None
    callback_tasks: set[asyncio.Task[None]] = set()
    try:
        while True:
            data = await reader.read(1024)
            strdata = data.decode(errors="ignore")
            if b"\x13" in data:
                if lock_task is not None and not lock_task.done():
                    _ = lock_task.cancel()
                lock_task = asyncio.create_task(block())

            if match := re.search(r"\(A(\d\d)\)\(B(\d\d)\)\(C(\d\d)\)", strdata):
                a, b, c = map(int, match.groups())
                callback_tasks.add(asyncio.create_task(handle_click(a, b, c)))
                callback_tasks = {t for t in callback_tasks if not t.done()}
    except asyncio.CancelledError:
        print("Listener task was cancelled.")
    finally:
        if lock_task and not lock_task.done():
            _ = lock_task.cancel()
        for t in callback_tasks:
            if not t.done():
                _ = t.cancel()

async def handle_click(a: int, b: int, c: int):
    if (a, b, c) == (1, 0, 0):
        print("Cheer !")
    else:
        print(f"Unknown command for {a}, {b}, {c}")

async def print_worker(writer: asyncio.StreamWriter):
    try:
        while True:
            message = await prints_queue.get()
            try:
                await print_text(message, writer)
            except asyncio.CancelledError:
                # If we get cancelled mid-print, re-queue the message!
                print("Print interrupted! Re-queueing message.")
                prints_queue.put_nowait(message)
                raise  # Re-raise the cancellation to exit the task
            except Exception as e:
                print(f"Print error: {e}")
    except asyncio.CancelledError:
        print("Print worker was cancelled.")

async def connexion(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global current_connection
    print("Connection opened")
    if current_connection is not None and not current_connection.done():
        print("Old connection detected, closing..")
        _ = current_connection.cancel()

    current_connection = asyncio.current_task()
    print_ready.set()
    listener_task = asyncio.create_task(connection_listener(reader))
    printer_task = asyncio.create_task(print_worker(writer))

    try:
        _, pending = await asyncio.wait(
            [listener_task, printer_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            _ = task.cancel()
    except asyncio.CancelledError:
        print("Root connection task cancelled (replaced by a new connection).")
        _ = listener_task.cancel()
        _ = printer_task.cancel()
    finally:
        print("Cleaning up socket...")
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
        except Exception:
            pass  # The printer is a ghost, force-abandoned successfully
        print("Socket closed cleanly.")

class PrintRequest(BaseModel):
    text: str

@app.post("/print")
async def print_cb(print_request: PrintRequest):
    prints_queue.put_nowait(print_request.text)
    print(f"Printing: {print_request.text}")
    return 200


async def main():
    print_server = await asyncio.start_server(connexion, "0.0.0.0", "1001")
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000)
    api_server = uvicorn.Server(config)

    await asyncio.gather(
        print_server.serve_forever(),
        api_server.serve()
    )

if __name__ == "__main__":
    asyncio.run(main())


