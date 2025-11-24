import os
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_reply(message, history):
    messages = [{'role': 'system', 'content': 'Respond in English using clear technical language.'}]
    if history:
        messages.extend(history)
    messages.append({'role': 'user', 'content': message})

    completion = client.responses.create(
        model='gpt-5-mini',
        messages=messages
    )

    return {'response': completion.output_text}

def generate_diagnosis(req):
    messages = [{
        'role': 'system',
        'content': 'You are a forklift diagnostic assistant. Respond in English.'
    },
    {'role': 'user', 'content': req.message}]

    completion = client.responses.create(
        model='gpt-5-mini',
        messages=messages
    )

    return {'diagnosis': completion.output_text}
