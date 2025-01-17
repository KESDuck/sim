import asyncio

async def long_running_task(task_id):
    print(f"[Task {task_id}] started...")
    await asyncio.sleep(5)
    print(f"[Task {task_id}] finished.")
    return f"Result of task {task_id}"

async def main():
    task = asyncio.create_task(long_running_task(1))
    
    while not task.done():
        print("[Main] Task is still running...")
        await asyncio.sleep(1)  # Check every second
    
    result = await task
    print(f"[Main] Task completed with result: {result}")

asyncio.run(main())
