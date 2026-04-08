import asyncio
import sys
sys.path.insert(0, '.')

from llm.gateway import OllamaGateway

async def test():
    gateway = OllamaGateway()
    print("Отправляю запрос к deepseek-course...")
    result = await gateway.chat(
        model="deepseek-course",
        messages=[
            {"role": "user", "content": "Ответь одним словом: какой металл самый твёрдый?"}
        ]
    )
    print(f"Ответ: {result}")

asyncio.run(test())
