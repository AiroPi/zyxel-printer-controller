import asyncio
import fastapi
import uvicorn
from pydantic import BaseModel

prints_queue: asyncio.Queue[str] = asyncio.Queue()

app = fastapi.FastAPI()

async def print_text(text: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    parts = text.replace("\r", "\n").encode("utf-8").split(b"\n")
    # Set new line spacing to minimum
    current_chunk = b"\x1b3\x01"
    for part in parts:
        # by tests, a packet can only contains 457 bytes. We send packets by 15 rows (24 chars) to avoid the overflow.
        for i in range(0, len(part), 360):
            chunk = part[i:i + 360]
            if len(chunk) + len(current_chunk) >= 360:
                writer.write(current_chunk)
                await wait_for_buffer(reader)
                await writer.drain()
                current_chunk = b""
            # Adding \n at the end of a 24 char line is invisible, and allows to prints the buffer
            current_chunk += chunk + b"\n"

    current_chunk = current_chunk.rstrip(b"\n") + b"\n\n\n\n"
    writer.write(current_chunk)
    await writer.drain()
    await wait_for_buffer(reader)


async def wait_for_buffer(reader: asyncio.StreamReader):
    data = await reader.read(1024)
    while b"\x13" in data:
        await asyncio.sleep(1)
        data = await reader.read(1024)



async def connexion(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while True:
        message = await prints_queue.get()
        await print_text(message, reader, writer)
        await asyncio.sleep(5)

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


