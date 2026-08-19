# python3 -c "
# from google import genai
# import os
# from dotenv import load_dotenv
# load_dotenv('../.env')
# client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
# response = client.models.generate_content(model='gemini-2.5-flash', contents='Say hello in 5 words')
# print(response.text)
# "