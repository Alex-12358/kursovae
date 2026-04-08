"""
Тест LLM gateway - проверка базовой работоспособности deepseek-course
"""
import asyncio
import logging
import sys

# Настроим логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

sys.path.insert(0, '.')

from llm.gateway import OllamaGateway

async def test_simple_chat():
    """Простой тест chat API"""
    gateway = OllamaGateway()
    
    messages = [
        {"role": "system", "content": "Ты помощник."},
        {"role": "user", "content": "Привет! Ответь одним словом: работаешь?"}
    ]
    
    print("\n=== ТЕСТ 1: Простой запрос ===")
    try:
        response = await gateway.chat(
            model="deepseek-course",
            messages=messages,
            temperature=0.3,
            max_tokens=50
        )
        print(f"✓ Ответ получен: {response}")
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()

async def test_json_response():
    """Тест с JSON ответом"""
    gateway = OllamaGateway()
    
    messages = [
        {"role": "system", "content": "Верни ТОЛЬКО валидный JSON без текста до или после. Формат: {\"status\": \"ok\", \"number\": 42}"},
        {"role": "user", "content": "Сгенерируй JSON с полями status и number."}
    ]
    
    print("\n=== ТЕСТ 2: JSON запрос ===")
    try:
        response = await gateway.chat(
            model="deepseek-course",
            messages=messages,
            temperature=0.2,
            max_tokens=100
        )
        print(f"✓ Ответ получен: {response}")
        
        # Попытка распарсить
        import json
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1:
            json_str = response[start:end+1]
            data = json.loads(json_str)
            print(f"✓ JSON распарсен: {data}")
        else:
            print(f"✗ JSON не найден в ответе")
            
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("Тестирование LLM Gateway с deepseek-course\n")
    await test_simple_chat()
    await test_json_response()
    print("\n=== ТЕСТЫ ЗАВЕРШЕНЫ ===")

if __name__ == "__main__":
    asyncio.run(main())
