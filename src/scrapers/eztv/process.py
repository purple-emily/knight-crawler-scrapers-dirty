import asyncio


async def process_data(queue):
    while True:
        data = await queue.get()
        # Process the data and store it in the database
        print("Processing data:", data)
        # Simulate processing time
        await asyncio.sleep(1)
        queue.task_done()


async def main():
    queue = asyncio.Queue()
    tasks = [
        asyncio.create_task(process_data(queue)) for _ in range(5)
    ]  # Adjust the number of processing tasks as needed

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
