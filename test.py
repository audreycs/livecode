import openai

client = openai.OpenAI(api_key="your_key")


response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": "Hello, world!"}],
    max_completion_tokens=4000,
    timeout=60
)

print(response.choices[0].message.content)